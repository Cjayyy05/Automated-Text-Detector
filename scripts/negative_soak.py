"""Explicit real-screen negative monitoring of both profiles; memory clipboard only.

One real DXcam handoff, two LiveSession policies and sequential real OCR on the same frames.
This is a loaded reliability soak, not an isolated latency benchmark.
"""

import argparse
import ctypes
import json
import random
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from time import perf_counter, perf_counter_ns, sleep

import cv2
import numpy as np
from phase4_scenes import draw_motion
from qualification_metrics import ocr_options

from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.synthetic import make_code


def negative_pixels(seed, tick, active):
    rng = random.Random(seed)
    permanent = make_code(rng)
    image = np.full((540, 960, 3), (35, 28, 22), np.uint8)
    for x in range(210, 950, 36):
        y = 415 + (x + tick * 3) % 85
        cv2.line(image, (x, y), (x, y + 23), (55, 70, 45), 2)
    cv2.putText(image, permanent, (235, 445), 0, 0.75, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(image, "100% off", (235, 478), 0, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
    cv2.putText(image, "Expiry Date:", (235, 510), 0, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
    if active:
        group = tick // 180
        rng = random.Random(seed + 1000 + group)
        code = make_code(rng)
        if group % 3 == 0:
            code = code[:2] + "O" + code[3:6] + "0" + code[7:]
            cv2.putText(image, code, (530, 460), 0, 0.8, (245, 245, 245), 2, cv2.LINE_AA)
            cv2.putText(image, "Expiry Date:", (745, 480), 0, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            cv2.putText(image, "100% off", (530, 524), 0, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
        elif group % 3 == 1:
            cv2.putText(image, code, (530, 460), 0, 0.8, (245, 245, 245), 2, cv2.LINE_AA)
            cv2.putText(image, make_code(rng), (530, 495), 0, 0.8, (245, 245, 245), 2, cv2.LINE_AA)
            cv2.putText(image, "Expiry Date:", (745, 480), 0, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            cv2.putText(image, "100% off", (530, 524), 0, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
        else:
            cv2.putText(image, code, (550, 460), 0, 0.8, (245, 245, 245), 2, cv2.LINE_AA)
            cv2.putText(
                image,
                "Price 235.68 Chat: next?",
                (550, 500),
                0,
                0.55,
                (220, 210, 190),
                1,
                cv2.LINE_AA,
            )
    draw_motion(image, Rect(200, 400, 960, 540), tick)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--cpu-arena", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seconds", type=float, default=1800)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.show_window or not 1 <= args.seconds <= 7200:
        parser.error("Explicit --show-window and duration in [1,7200] required")
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import win32api
    import win32con
    import win32gui
    import win32process
    from PIL import Image, ImageWin

    ready, begin, closed = Event(), Event(), Event()
    errors, sessions, snapshots = [], [], []
    started = [None]
    counts = {p: {} for p in ("discount", "game")}

    def display():
        hwnd = None
        try:
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "Phase5NegativeSoak"
            wc.lpfnWndProc = win32gui.DefWindowProc
            atom = win32gui.RegisterClass(wc)
            hwnd = win32gui.CreateWindowEx(
                win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE,
                atom,
                "Phase 5 negative soak - memory only",
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
                image = negative_pixels(args.seed, tick, begin.is_set())
                dc = win32gui.GetDC(hwnd)
                try:
                    ImageWin.Dib(Image.fromarray(image[:, :, ::-1])).draw(dc, (0, 0, 960, 540))
                finally:
                    win32gui.ReleaseDC(hwnd, dc)
                ready.set()
                win32gui.PumpWaitingMessages()
                tick += 1
                sleep(1 / 60)
        except Exception as exc:
            errors.append(str(exc))
            ready.set()
            closed.set()
        finally:
            if hwnd:
                win32gui.DestroyWindow(hwnd)

    recognizer = RapidRecognizer(
        scale=1, threads=4, cpu_arena=args.cpu_arena, allow_spinning=False, det_limit=640
    )
    recognizer.warmup()
    worker = CaptureWorker(lambda: DxcamSource(Rect(250, 450, 1010, 590)))
    with args.report.open("x", encoding="utf-8") as report:
        report.write(
            json.dumps(
                {
                    "event": "test_config",
                    "cpu_arena": args.cpu_arena,
                    "ocr_sessions": ocr_options(recognizer),
                    "seed": args.seed,
                    "memory_limit_bytes": 50 * 1024 * 1024,
                }
            )
            + "\n"
        )

        def emit(profile, event):
            report.write(json.dumps({"profile": profile, **event}) + "\n")
            report.flush()
            if event["event"] == "frame":
                status = event["status"]
                counts[profile][status] = counts[profile].get(status, 0) + 1
                if status in {"copied", "would_copy", "clipboard_failed"}:
                    errors.append(f"Unexpected {profile} write attempt: {event.get('code')}")
                    closed.set()
            if event["event"] == "ready" and all(s.ready for s in sessions):
                for session in sessions:
                    session.controls.send("arm")
                started[0] = perf_counter()
                begin.set()

        for profile in counts:
            session = LiveSession(
                recognizer,
                LiveConfig(Rect(250, 450, 1010, 590), profile=profile),
                Controls(),
                lambda event, p=profile: emit(p, event),
                worker=worker,
            )
            session.running = True  # Shared producer is started/stopped exactly once below.
            session.started_ns = perf_counter_ns()
            sessions.append(session)
        thread = Thread(target=display, name="negative-soak-stimulus")
        thread.start()
        elapsed, next_sample = 0.0, 0.0
        producer_started = False

        def snapshot():
            memory = win32process.GetProcessMemoryInfo(win32api.GetCurrentProcess())
            sample = {
                "event": "soak_progress",
                "elapsed_s": elapsed,
                "counts": {p: dict(c) for p, c in counts.items()},
                "working_set_bytes": memory["WorkingSetSize"],
                "private_bytes": memory["PagefileUsage"],
                "captured": worker.captured,
                "dropped": worker.latest.dropped,
            }
            snapshots.append(sample)
            report.write(json.dumps(sample) + "\n")
            report.flush()
            print(json.dumps(sample), flush=True)

        try:
            if not ready.wait(5) or errors:
                raise RuntimeError(f"Display failed: {errors}")
            worker.start()
            producer_started = True
            startup = perf_counter()
            while not closed.is_set():
                if not begin.is_set() and perf_counter() - startup > 20:
                    raise RuntimeError("No stable baseline")
                elapsed = perf_counter() - started[0] if started[0] is not None else 0
                if elapsed >= args.seconds:
                    break
                for session in sessions:
                    session.handle_commands()
                    if worker.error or not session.healthy():
                        raise RuntimeError(worker.error or "Capture stalled")
                frame = worker.latest.wait()
                if frame is not None:
                    for session in sessions:
                        session.consume(replace(frame, dequeued_ns=perf_counter_ns()))
                if begin.is_set() and elapsed >= next_sample:
                    snapshot()
                    next_sample = elapsed + 60
        except Exception as exc:
            errors.append(str(exc))
        finally:
            snapshot()  # Measure before releasing producer/model allocations.
            for session in sessions:
                session.controls.send("stop")
                session.policy.disarm()
            closed.set()
            if producer_started:
                try:
                    worker.stop()
                except RuntimeError as exc:
                    errors.append(str(exc))
            thread.join(5)
        growth = snapshots[-1]["private_bytes"] - snapshots[0]["private_bytes"]
        # Post-measurement inspection only: do not contaminate the final memory sample.
        # This upper bound counts shared float objects more than once; it is not a heap trace.
        metric_storage = {}
        for name, metrics in [("capture", worker.metrics)] + [
            (s.config.profile, s.metrics) for s in sessions
        ]:
            metric_storage[name] = {
                "retained_samples": sum(len(values) for values in metrics.samples.values()),
                "sample_storage_upper_bound_bytes": sum(
                    sys.getsizeof(values) + sum(sys.getsizeof(value) for value in values)
                    for values in metrics.samples.values()
                ),
                "per_stage_cap": 10000,
            }
        result = {
            "event": "test_result",
            "passed": (
                not errors
                and elapsed >= args.seconds
                and not thread.is_alive()
                and growth <= 50 * 1024 * 1024
            ),
            "duration_s": elapsed,
            "requested_s": args.seconds,
            "seed": args.seed,
            "cpu_arena": args.cpu_arena,
            "counts": counts,
            "errors": errors,
            "native_clipboard": False,
            "snapshots": snapshots,
            "private_growth_bytes": growth,
            "memory_gate_passed": growth <= 50 * 1024 * 1024,
            "metric_storage": metric_storage,
            "profiles": {
                s.config.profile: {"writes": s.clipboard.writes, "timings": s.metrics.summary()}
                for s in sessions
            },
            "capture_timings": worker.metrics.summary(),
        }
        report.write(json.dumps(result) + "\n")
        print(
            json.dumps({k: result[k] for k in ("passed", "duration_s", "counts", "errors")}),
            flush=True,
        )
        return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
