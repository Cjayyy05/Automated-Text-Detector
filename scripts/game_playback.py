"""Explicit simulated playback -> real DXcam -> unchanged OCR -> clipboard.

Shows a test window only when run. Native writes require explicit --clipboard windows.
Labels/marker are scoring instrumentation, never recognition inputs.
"""

import argparse
import ctypes
import json
import random
from importlib.metadata import version
from pathlib import Path
from threading import Event, Thread
from time import perf_counter, perf_counter_ns, sleep

import cv2
import numpy as np
from native_readback import MeasuredWindowsClipboard, readback
from phase4_scenes import draw_motion, scenes
from qualification_metrics import memory_snapshot, ocr_options

from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.cli import add_ocr_arguments, recognizer_from_args
from stream_code_capture.dataset import audit_split, digest, load_dataset, load_pixels
from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.metrics import Metrics
from stream_code_capture.synthetic import make_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", type=Path, nargs="?")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--profile", choices=["discount", "game"], default="game")
    parser.add_argument("--clipboard", choices=["memory", "windows"], default="memory")
    parser.add_argument(
        "--synthetic-count", type=int, default=0, help="New codes per exposure duration"
    )
    parser.add_argument("--exposures-ms", type=int, nargs="+", default=[250, 500, 1000, 2000])
    parser.add_argument("--activity-gate-ms", type=float, default=0)
    parser.add_argument(
        "--drain-ms",
        type=int,
        default=0,
        help="Test-only absent interval for in-flight results before disarm (default 0)",
    )
    parser.add_argument(
        "--precise-stimulus", action="store_true", help="60 Hz high-resolution test pacing"
    )
    add_ocr_arguments(parser)
    parser.add_argument(
        "--roi",
        type=int,
        nargs=4,
        default=[200, 400, 960, 540],
        help="Test-window-relative capture ROI, L T R B",
    )
    args = parser.parse_args()
    if not 0 <= args.drain_ms <= 2000:
        parser.error("drain-ms must be in [0, 2000]")
    region = Rect(*args.roi)
    region.validate(960, 540)
    if region.right - region.left < 16 or region.bottom - region.top < 16:
        parser.error("Test ROI must fit the capture marker (at least 16x16)")
    slides = []
    if args.synthetic_count:
        if args.synthetic_count < 1 or any(ms <= 0 for ms in args.exposures_ms):
            parser.error("Synthetic counts and exposure durations must be positive")
        slides = scenes(args.seed, args.synthetic_count * len(args.exposures_ms), args.profile)
    elif args.split is not None:
        for entry in audit_split(args.split):
            path = Path(entry["manifest"])
            data = load_dataset(path)
            for frame in data["frames"]:
                if frame["label"]["state"] == "visible":
                    pixels = load_pixels(path.parent / frame["file"])
                    slides.append((cv2.resize(pixels, (960, 540)), frame["label"]["code"]))
    else:
        parser.error("Provide an imported split or --synthetic-count")
    rng = random.Random(args.seed)
    if not 1 <= len(slides) <= 253:
        parser.error("Test marker supports 1..253 positive slides")
    unrelated = make_code(random.Random(args.seed + 1))
    rng.shuffle(slides)
    schedule = [
        {
            "slide": i,
            "expected": code,
            "kind": "new",
            "gap_s": rng.uniform(1.2, 2.1),
            "visible_s": args.exposures_ms[i % len(args.exposures_ms)] / 1000
            if args.synthetic_count
            else rng.uniform(2.5, 4.5),
        }
        for i, (_, code) in enumerate(slides)
    ]
    schedule.extend(
        [
            {"slide": 0, "expected": None, "kind": "repeat", "gap_s": 1.5, "visible_s": 3.0},
            {"slide": None, "expected": None, "kind": "negative", "gap_s": 1.5, "visible_s": 3.0},
        ]
    )
    if args.synthetic_count:
        # A missed positive repeated later is not a duplicate. Keep repeat qualification
        # in the imported long-exposure benchmark instead of mis-scoring short misses.
        schedule.pop(-2)
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import win32con
    import win32gui
    from PIL import Image, ImageWin

    ready, closed, begin = Event(), Event(), Event()
    controls = Controls()
    captures, first, writes, display_times = [], {}, [], []
    first_recognized, raw_recognized, painted = {}, set(), []
    errors = []

    def display():
        hwnd = None
        try:
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "GameCodePlaybackValidation"
            wc.lpfnWndProc = win32gui.DefWindowProc
            atom = win32gui.RegisterClass(wc)
            hwnd = win32gui.CreateWindowEx(
                win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE,
                atom,
                "Game code simulated playback test",
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
            index, phase, deadline, tick = -1, "waiting", 0.0, 0
            last_painted = None
            while not closed.is_set():
                now = perf_counter()
                if begin.is_set() and (phase == "waiting" or now >= deadline):
                    if phase == "gap":
                        phase, deadline = "visible", now + schedule[index]["visible_s"]
                    elif phase == "visible" and args.drain_ms:
                        phase, deadline = "drain", now + args.drain_ms / 1000
                    else:
                        index += 1
                        if index >= len(schedule):
                            controls.send("stop")
                            break
                        controls.send("disarm")
                        controls.send("arm")  # Test controller only; product remains one-shot.
                        phase, deadline = "gap", now + schedule[index]["gap_s"]
                    display_times.append({"index": index, "phase": phase, "ns": perf_counter_ns()})
                image = np.full((540, 960, 3), (35, 28, 22), np.uint8)
                cv2.putText(
                    image,
                    unrelated
                    if phase == "visible" and schedule[index]["kind"] == "negative"
                    else "CHAT AB23CD45EF",
                    (235, 485),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (220, 220, 220),
                    1,
                    cv2.LINE_AA,
                )
                if phase == "visible" and schedule[index]["slide"] is not None:
                    image = slides[schedule[index]["slide"]][0].copy()
                # Top-of-window chat stays outside the original bottom code bands.
                image[0:28] = (35, 28, 22)
                cv2.putText(
                    image,
                    "LIVE chat: nice!",
                    (30, 21),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (180, 180, 180),
                    1,
                    cv2.LINE_AA,
                )
                if args.precise_stimulus:
                    draw_motion(image, region, tick)
                else:
                    image[538:540, (tick * 7) % 950 : (tick * 7) % 950 + 8] = (70, 160, 50)
                marker = index + 1 if phase == "visible" else 0
                image[region.top + 2 : region.top + 10, region.left + 2 : region.left + 10] = (
                    marker,
                    91,
                    231,
                )
                dc = win32gui.GetDC(hwnd)
                try:
                    ImageWin.Dib(Image.fromarray(image[:, :, ::-1])).draw(dc, (0, 0, 960, 540))
                finally:
                    win32gui.ReleaseDC(hwnd, dc)
                if last_painted != (index, phase):
                    painted.append({"index": index, "phase": phase, "ns": perf_counter_ns()})
                    last_painted = (index, phase)
                ready.set()
                win32gui.PumpWaitingMessages()
                tick += 1
                if args.precise_stimulus:
                    sleep(
                        max(0, min(1 / 60, deadline - perf_counter()))
                        if phase != "waiting"
                        else 1 / 60
                    )
                else:
                    closed.wait(1 / 30)
        except Exception as exc:
            errors.append(str(exc))
            ready.set()
            controls.send("stop")
        finally:
            if hwnd:
                win32gui.DestroyWindow(hwnd)

    recognizer = recognizer_from_args(args)
    recognizer.warmup()
    memory_samples = [{"stage": "warmed", **memory_snapshot()}]
    next_memory_ns = [0]
    native = MeasuredWindowsClipboard() if args.clipboard == "windows" else None
    with args.report.open("x", encoding="utf-8") as report:

        def emit(event):
            report.write(json.dumps(event) + "\n")
            report.flush()
            if event["event"] == "ready":
                memory_samples.append({"stage": "baseline", **memory_snapshot()})
                next_memory_ns[0] = perf_counter_ns() + 5_000_000_000
                begin.set()
            if event.get("event") == "frame":
                marker = next((m for stamp, m in captures if stamp >= event["captured_ns"]), 0)
                index = marker - 1
                if 0 <= index < len(schedule):
                    expected = schedule[index]["expected"]
                    if expected and any(line["text"] == expected for line in event["lines"]):
                        raw_recognized.add(index)
                        first_recognized.setdefault(index, event["recognized_ns"])
            if event.get("status") in {"would_copy", "copied"}:
                # Match the processed acquisition time, not current display state.
                marker = next((m for stamp, m in captures if stamp >= event["captured_ns"]), 0)
                index = marker - 1
                expected = schedule[index]["expected"] if 0 <= index < len(schedule) else None
                latency = (event["completed_ns"] - first[index]) / 1e6 if index in first else None
                check = readback() if native is not None else None
                writes.append(
                    {
                        "index": index,
                        "code": event["code"],
                        "expected": expected,
                        "correct": event["code"] == expected,
                        "completed_ns": event["completed_ns"],
                        "write_frame_age_ms": (event["completed_ns"] - event["captured_ns"]) / 1e6,
                        "native_write_ms": (
                            (native.last_write["end_ns"] - native.last_write["start_ns"]) / 1e6
                            if native is not None and native.last_write is not None
                            else None
                        ),
                        "readback": check,
                        "readback_correct": check is None or check["value"] == expected,
                        "first_captured_to_readback_ms": (
                            (check["end_ns"] - first[index]) / 1e6
                            if check is not None and index in first
                            else None
                        ),
                        "first_captured_to_clipboard_ms": latency,
                        "first_recognition_to_clipboard_ms": (
                            (event["completed_ns"] - first_recognized[index]) / 1e6
                            if index in first_recognized
                            else None
                        ),
                    }
                )
                if (
                    event["code"] != expected
                    or (check is not None and check["value"] != expected)
                    or writes[-1]["write_frame_age_ms"] > 1000
                ):
                    controls.send("stop")
            # Sample after write/readback processing, at most once every five seconds.
            if next_memory_ns[0] and perf_counter_ns() >= next_memory_ns[0]:
                memory_samples.append({"stage": "monitoring", **memory_snapshot()})
                next_memory_ns[0] = perf_counter_ns() + 5_000_000_000
            if event["event"] == "summary":
                memory_samples.append({"stage": "finished", **memory_snapshot()})

        config = LiveConfig(
            Rect(region.left + 50, region.top + 50, region.right + 50, region.bottom + 50),
            profile=args.profile,
            dry_run=native is None,
            activity_gate_ms=args.activity_gate_ms,
        )

        class ObservedSource(DxcamSource):
            def grab(self):
                stamp = perf_counter_ns()
                pixels = super().grab()
                if pixels is not None:
                    blue, green, red = map(int, pixels[6, 6])
                    marker = blue if green == 91 and red == 231 else 0
                    captures.append((stamp, marker))
                    if marker:
                        first.setdefault(marker - 1, stamp)
                return pixels

        report.write(
            json.dumps(
                {
                    "event": "test_config",
                    "schedule": schedule,
                    "seed": args.seed,
                    "window_roi": args.roi,
                    "profile": args.profile,
                    "provider": recognizer.provider,
                    "ocr_sessions": ocr_options(recognizer),
                    "model_hashes": {str(p): digest(p) for p in recognizer.model_paths},
                    "versions": {
                        name: version(name) for name in ("rapidocr", "onnxruntime", "dxcam")
                    },
                    "options": {
                        k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()
                    },
                    "note": "Seeded simulated slide playback; real DXcam pixels, "
                    "explicit clipboard selection recorded in options",
                }
            )
            + "\n"
        )
        worker = CaptureWorker(lambda: ObservedSource(config.roi))
        thread = Thread(target=display, name="game-test-stimulus")
        thread.start()
        try:
            if not ready.wait(5) or errors:
                raise RuntimeError(f"Display failed: {errors}")
            session = LiveSession(
                recognizer, config, controls, emit, worker=worker, clipboard=native
            )
            controls.send("start")
            status = session.run(
                duration=20
                + sum(e["gap_s"] + e["visible_s"] + args.drain_ms / 1000 for e in schedule)
            )
        finally:
            closed.set()
            thread.join(5)
        metrics = Metrics()
        for write in writes:
            if write["correct"] and write["first_captured_to_clipboard_ms"] is not None:
                metrics.add(
                    {"first_captured_to_clipboard": write["first_captured_to_clipboard_ms"]}
                )
                if write["first_captured_to_readback_ms"] is not None:
                    metrics.add(
                        {
                            "first_captured_to_readback": write["first_captured_to_readback_ms"],
                            "native_write": write["native_write_ms"],
                            "readback": (
                                write["readback"]["end_ns"] - write["readback"]["start_ns"]
                            )
                            / 1e6,
                        }
                    )
        correct = {w["index"] for w in writes if w["correct"]}
        wrong = sum(not w["correct"] for w in writes)
        by_exposure = []
        exposure_ends = {}
        actual_exposures = {}
        for position, transition in enumerate(painted[:-1]):
            if transition["phase"] == "visible":
                end = painted[position + 1]["ns"]
                exposure_ends[transition["index"]] = end
                actual_exposures[transition["index"]] = (end - transition["ns"]) / 1e6
        for duration in sorted({e["visible_s"] for e in schedule if e["kind"] == "new"}):
            indexes = {
                i
                for i, e in enumerate(schedule)
                if e["kind"] == "new" and e["visible_s"] == duration
            }
            times = Metrics()
            for index in indexes:
                if index in actual_exposures:
                    times.add({"actual_painted_exposure": actual_exposures[index]})
            for write in writes:
                if write["index"] in indexes and write["correct"]:
                    times.add(
                        {"first_captured_to_clipboard": write["first_captured_to_clipboard_ms"]}
                    )
            by_exposure.append(
                {
                    "exposure_ms": duration * 1000,
                    "events": len(indexes),
                    "O0_events": sum(
                        any(c in schedule[index]["expected"] for c in "O0") for index in indexes
                    ),
                    "captured": len(indexes & first.keys()),
                    "raw_exact": len(indexes & raw_recognized),
                    "exact_copies": len(indexes & correct),
                    "abstentions": len(indexes - correct),
                    "raw_exact_before_disappearance": sum(
                        index in first_recognized
                        and first_recognized[index] <= exposure_ends.get(index, 0)
                        for index in indexes
                    ),
                    "copied_before_disappearance": sum(
                        w["index"] in indexes
                        and w["correct"]
                        and w["completed_ns"] <= exposure_ends.get(w["index"], 0)
                        for w in writes
                    ),
                    "timings": times.summary(),
                }
            )
        passed = (
            status == 0
            and not errors
            and len(first) == len(schedule)
            and not thread.is_alive()
            and len(correct) == len(slides)
            and wrong == 0
            and len(writes) == len(slides)
            and all(w["readback_correct"] and w["write_frame_age_ms"] <= 1000 for w in writes)
        )
        summary = {
            "event": "test_result",
            "session_failure": session.failure,
            "completed_schedule": len(first) == len(schedule) and status == 0 and not errors,
            "passed": passed,
            "exact_copies": len(correct),
            "incorrect_writes": wrong,
            "readback_mismatches": sum(not w["readback_correct"] for w in writes),
            "late_writes": sum(w["write_frame_age_ms"] > 1000 for w in writes),
            "abstentions": len(slides) - len(correct),
            "captured_events": len(first),
            "first_captured_ns": first,
            "writes": writes,
            "timings": metrics.summary(),
            "display_transitions": display_times,
            "painted_transitions": painted,
            "by_exposure": by_exposure,
            "errors": errors,
            "memory_samples": memory_samples,
        }
        report.write(json.dumps(summary) + "\n")
        print(json.dumps(summary, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
