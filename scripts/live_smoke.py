"""Opt-in Windows integration harness: visible test surface -> DXcam -> real OCR -> clipboard.

This is a test stimulus, not application UI. No fixture pixels enter the capture pipeline.
Default is dry-run. --clipboard windows intentionally replaces the clipboard with test codes.
"""

import argparse
import ctypes
import json
import random
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter, perf_counter_ns, sleep

from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.cli import add_ocr_arguments, recognizer_from_args
from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.metrics import Metrics
from stream_code_capture.synthetic import chart_frame, make_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clipboard", choices=["windows"])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--activity-gate-ms", type=float, default=0)
    parser.add_argument(
        "--visible-ms",
        type=float,
        help="Single-event finite exposure test; missing copy fails the test",
    )
    add_ocr_arguments(parser)
    args = parser.parse_args()
    if not 1 <= args.count <= 255:
        parser.error("count must be in 1..255")
    if args.visible_ms is not None and (args.count != 1 or not 0 < args.visible_ms <= 10000):
        parser.error("--visible-ms requires --count 1 and a duration in (0, 10000]")
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import pywintypes
    import win32clipboard
    import win32con
    import win32gui
    from PIL import Image, ImageWin

    ready, closed = Event(), Event()
    state = {"index": 0, "visible": False, "draw_ns": None, "error": None}
    state_lock = Lock()
    rng = random.Random(args.seed)
    codes = [make_code(rng) for _ in range(args.count)]
    controls = Controls()
    observations = []
    first_captured = {}
    arm_at = [None]

    def display():
        hwnd = None
        try:
            window_class = win32gui.WNDCLASS()
            window_class.lpszClassName = "StreamCodeCaptureValidation"
            window_class.lpfnWndProc = win32gui.DefWindowProc
            atom = win32gui.RegisterClass(window_class)
            hwnd = win32gui.CreateWindowEx(
                win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE,
                atom,
                "Stream Code Capture — test stimulus",
                win32con.WS_POPUP,
                50,
                50,
                960,
                540,
                0,
                0,
                0,
                None,
            )
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            tick = 0
            while not closed.is_set():
                with state_lock:
                    if (
                        args.visible_ms is not None
                        and state["draw_ns"] is not None
                        and (perf_counter_ns() - state["draw_ns"]) / 1e6 >= args.visible_ms
                    ):
                        state["visible"] = False
                    index, visible = state["index"], state["visible"]
                image = chart_frame(
                    codes[index], tick=tick, visible=visible, seed=args.seed + index
                )
                # Test-only marker lets the capture-side observer retain the first
                # actual code frame even when the OCR handoff later drops that frame.
                image[164:172, 74:82] = (index + 1, 91, 231) if visible else (0, 0, 0)
                dib = ImageWin.Dib(Image.fromarray(image[:, :, ::-1]))
                dc = win32gui.GetDC(hwnd)
                try:
                    dib.draw(dc, (0, 0, 960, 540))
                finally:
                    win32gui.ReleaseDC(hwnd, dc)
                with state_lock:
                    if (
                        visible
                        and state["visible"]
                        and index == state["index"]
                        and state["draw_ns"] is None
                    ):
                        state["draw_ns"] = perf_counter_ns()
                ready.set()
                win32gui.PumpWaitingMessages()
                tick += 1
                if arm_at[0] is not None and perf_counter() >= arm_at[0]:
                    arm_at[0] = None
                    controls.send("arm")
                closed.wait(1 / 30)
        except Exception as exc:
            state["error"] = str(exc)
            ready.set()
            controls.send("stop")
        finally:
            if hwnd:
                win32gui.DestroyWindow(hwnd)

    recognizer = recognizer_from_args(args)
    recognizer.warmup()
    with args.report.open("x", encoding="utf-8") as report:

        def emit(event):
            event["recorded_ns"] = perf_counter_ns()
            report.write(json.dumps(event) + "\n")
            report.flush()
            if event["event"] == "ready":
                controls.send("arm")
            elif event["event"] == "armed":
                with state_lock:
                    state["visible"] = True
            elif event.get("status") in {"copied", "would_copy"}:
                expected = codes[state["index"]]
                actual = event["code"]
                readback = None
                if args.clipboard == "windows":
                    # Readback is a test assertion, not a retry of the app's write.
                    # Clipboard viewers may briefly lock it after a successful write.
                    for attempt in range(20):
                        try:
                            win32clipboard.OpenClipboard()
                        except pywintypes.error:
                            if attempt == 19:
                                raise
                            sleep(0.05)
                        else:
                            try:
                                readback = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                            finally:
                                win32clipboard.CloseClipboard()
                            break
                observed = {
                    "expected": expected,
                    "actual": actual,
                    "readback": readback,
                    "stimulus_draw_to_result_ms": (perf_counter_ns() - state["draw_ns"]) / 1e6,
                    "first_captured_to_clipboard_ms": (
                        event["completed_ns"] - first_captured[state["index"]]
                    )
                    / 1e6,
                }
                observations.append(observed)
                print(json.dumps(observed), flush=True)
                with state_lock:
                    state["visible"] = False
                    state["draw_ns"] = None
                    if len(observations) < len(codes):
                        state["index"] += 1
                if len(observations) == len(codes):
                    controls.send("stop")
                else:
                    arm_at[0] = perf_counter() + 2  # Independent new appearance after absence.
            elif event["event"] in {"error", "summary"}:
                print(json.dumps(event), flush=True)

        display_thread = Thread(target=display, name="test-stimulus")
        display_thread.start()
        try:
            if not ready.wait(5) or state["error"]:
                raise RuntimeError(f"Test surface failed: {state['error']}")
            config = LiveConfig(
                Rect(120, 210, 660, 375),
                dry_run=args.clipboard != "windows",
                activity_gate_ms=args.activity_gate_ms,
            )

            class ObservedSource(DxcamSource):
                def grab(self):
                    started = perf_counter_ns()
                    pixels = super().grab()
                    if pixels is not None:
                        blue, green, red = map(int, pixels[6, 6])
                        if green == 91 and red == 231 and 1 <= blue <= len(codes):
                            first_captured.setdefault(blue - 1, started)
                    return pixels

            worker = CaptureWorker(lambda: ObservedSource(config.roi))
            session = LiveSession(recognizer, config, controls, emit, worker=worker)
            controls.send("start")
            result = session.run(
                duration=10 if args.visible_ms is not None else 15 + args.count * 12
            )
        finally:
            closed.set()
            display_thread.join(5)
        passed = (
            result == 0
            and len(observations) == len(codes)
            and all(
                item["actual"] == item["expected"]
                and (args.clipboard != "windows" or item["readback"] == item["expected"])
                for item in observations
            )
        )
        metrics = Metrics()
        for observation in observations:
            metrics.add(
                {"first_captured_to_clipboard": observation["first_captured_to_clipboard_ms"]}
            )
        result_summary = {
            "event": "test_result",
            "passed": passed,
            "exact_copies": sum(item["actual"] == item["expected"] for item in observations),
            "incorrect_writes": sum(item["actual"] != item["expected"] for item in observations),
            "abstentions": len(codes) - len(observations),
            "captured_events": len(first_captured),
            "observations": observations,
            "config": {
                key: str(value) if isinstance(value, Path) else value
                for key, value in vars(args).items()
            },
            "timings": metrics.summary(),
        }
        report.write(json.dumps(result_summary) + "\n")
        print(json.dumps(result_summary), flush=True)
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
