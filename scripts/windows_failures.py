"""Explicit real-screen failure probes; memory-only unless --native-clipboard.

Test stimulus and fault injection only. Actual DXcam pixels feed unmodified real OCR.
No physical monitor, lock-screen or source-identity recovery is simulated as a pass.
"""

import argparse
import ctypes
import json
import random
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread, Timer
from time import perf_counter, perf_counter_ns, sleep

import cv2
import numpy as np
from native_readback import MeasuredWindowsClipboard, readback
from phase4_scenes import draw_motion
from qualification_metrics import ocr_options

from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.synthetic import make_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--cpu-arena", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--native-clipboard", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args()
    if not args.show_window:
        parser.error("Explicit --show-window required")
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import win32con
    import win32gui
    from PIL import Image, ImageWin

    real = RapidRecognizer(
        scale=1, threads=4, cpu_arena=args.cpu_arena, allow_spinning=False, det_limit=640
    )
    real.warmup()
    rng = random.Random(args.seed)
    results = []
    with args.report.open("x", encoding="utf-8") as report:
        report.write(
            json.dumps(
                {
                    "event": "test_config",
                    "cpu_arena": args.cpu_arena,
                    "ocr_sessions": ocr_options(real),
                }
            )
            + "\n"
        )

        def record(event):
            report.write(json.dumps(event) + "\n")
            report.flush()

        def probe(profile, case):
            ready, closed = Event(), Event()
            locked, release = Event(), Event()
            controls = Controls()
            codes = [make_code(rng), make_code(rng)]
            state = {"visible": False, "blank": False, "freeze": False, "code": codes[0]}
            writes, events, races, errors = [], [], [], []
            interrupt = [False]
            stop_after = [None]
            busy_seen = [False]
            timers = []

            def display():
                hwnd = None
                try:
                    wc = win32gui.WNDCLASS()
                    wc.lpszClassName = f"Phase5Failure_{profile}_{case}"
                    wc.lpfnWndProc = win32gui.DefWindowProc
                    atom = win32gui.RegisterClass(wc)
                    hwnd = win32gui.CreateWindowEx(
                        win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE,
                        atom,
                        "Phase 5 failure probe",
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
                        if not state["freeze"] or tick == 0:
                            image = np.full((540, 960, 3), (35, 28, 22), np.uint8)
                            cv2.putText(image, "Live test", (235, 430), 0, 0.5, (150, 150, 150), 1)
                            if state["visible"]:
                                cv2.putText(
                                    image,
                                    state["code"],
                                    (300, 470),
                                    0,
                                    1,
                                    (245, 245, 245),
                                    2,
                                    cv2.LINE_AA,
                                )
                                context = "Expiry Date:" if profile == "game" else "100% off"
                                cv2.putText(
                                    image,
                                    context,
                                    (300, 503),
                                    0,
                                    0.6,
                                    (235, 235, 235),
                                    1,
                                    cv2.LINE_AA,
                                )
                            draw_motion(image, Rect(200, 400, 960, 540), tick)
                            if state["blank"]:
                                image[:] = 0
                            dc = win32gui.GetDC(hwnd)
                            try:
                                ImageWin.Dib(Image.fromarray(image[:, :, ::-1])).draw(
                                    dc, (0, 0, 960, 540)
                                )
                            finally:
                                win32gui.ReleaseDC(hwnd, dc)
                        ready.set()
                        win32gui.PumpWaitingMessages()
                        tick += 1
                        if stop_after[0] is not None and perf_counter() >= stop_after[0]:
                            controls.send("stop")
                            stop_after[0] = None
                        sleep(1 / 60)
                except Exception as exc:
                    errors.append(str(exc))
                    ready.set()
                    controls.send("stop")
                finally:
                    if hwnd:
                        win32gui.DestroyWindow(hwnd)

            def hold_clipboard():
                try:
                    # Same-process OpenClipboard ownership is not a reliable contention
                    # probe. A distinct process must own the lock until explicit release.
                    with subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            (
                                "import sys,win32clipboard,win32gui; "
                                "w=win32gui.CreateWindowEx(0,'STATIC','Clipboard lock probe',"
                                "0,0,0,0,0,0,0,0,None); win32clipboard.OpenClipboard(w); "
                                "print('LOCKED',flush=True); sys.stdin.readline(); "
                                "win32clipboard.CloseClipboard(); win32gui.DestroyWindow(w)"
                            ),
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    ) as holder:
                        if holder.stdout.readline().strip() != "LOCKED":
                            raise RuntimeError(holder.stderr.read())
                        if not ctypes.windll.user32.GetOpenClipboardWindow():
                            holder.communicate(input="\n", timeout=3)
                            raise RuntimeError("Clipboard holder has no active owner window")
                        locked.set()
                        release.wait(10)
                        _, stderr = holder.communicate(input="\n", timeout=3)
                        if holder.returncode:
                            raise RuntimeError(stderr)
                except Exception as exc:
                    errors.append(f"Lock probe failed: {exc}")
                    locked.set()

            class ObservedRecognizer:
                def warmup(self):
                    pass

                def recognize(self, pixels):
                    return self.recognize_timed(pixels).lines

                def recognize_timed(self, pixels):
                    race = None
                    if interrupt[0]:
                        interrupt[0] = False
                        race = {"command": case, "ocr_start_ns": perf_counter_ns()}

                        def urgent():
                            controls.send(case)
                            race["command_accepted_ns"] = perf_counter_ns()

                        timer = Timer(0.01, urgent)
                        timers.append(timer)
                        timer.start()
                    result = real.recognize_timed(pixels)
                    if race is not None:
                        race["ocr_end_ns"] = perf_counter_ns()
                        races.append(race)
                    return result

            native = MeasuredWindowsClipboard() if args.native_clipboard else None
            locker = None

            def emit(event):
                nonlocal locker
                record({"profile": profile, "case": case, **event})
                events.append(event)
                if event["event"] == "ready":
                    if case == "clipboard_busy":
                        locker = Thread(target=hold_clipboard)
                        locker.start()
                        if not locked.wait(2) or errors:
                            controls.send("stop")
                            return
                    controls.send("arm")
                if event["event"] == "armed" and not state["visible"]:
                    interrupt[0] = case in {"stop", "disarm"}
                    state["blank"] = case == "blank"
                    state["freeze"] = case == "static"
                    state["visible"] = case not in {"blank", "static"}
                    if case == "static":
                        timer = Timer(4, lambda: controls.send("status"))
                        timers.append(timer)
                        timer.start()
                if case == "static" and event["event"] == "status":
                    controls.send("stop")
                if event.get("status") == "disarmed" and races:
                    controls.send("stop")
                if event.get("status") == "clipboard_failed":
                    busy_seen[0] = (
                        not session.policy.armed and codes[0] not in session.policy.copied
                    )
                    release.set()
                    if locker:
                        locker.join(2)
                    state["code"] = codes[1]
                    controls.send("arm")  # Explicit recovery, not an automatic application retry.
                if event.get("status") in {"copied", "would_copy"}:
                    check = readback() if native else None
                    expected = codes[1] if case == "clipboard_busy" else codes[0]
                    writes.append({"code": event["code"], "expected": expected, "readback": check})
                    if event["code"] != expected or (check and check["value"] != expected):
                        errors.append("Wrong write/readback")
                        controls.send("stop")
                    elif case == "duplicate" and len(writes) == 1:
                        controls.send("arm")
                        stop_after[0] = perf_counter() + 2
                    else:
                        controls.send("stop")

            thread = Thread(target=display)
            thread.start()
            try:
                if not ready.wait(5) or errors:
                    raise RuntimeError(f"Display failed: {errors}")
                session = LiveSession(
                    ObservedRecognizer(),
                    LiveConfig(Rect(250, 450, 1010, 590), profile=profile, dry_run=native is None),
                    controls,
                    emit,
                    clipboard=native,
                )
                controls.send("arm")  # Must reject premature arm before start/baseline.
                controls.send("start")
                exit_code = session.run(duration=15)
            finally:
                release.set()
                closed.set()
                thread.join(5)
                for timer in timers:
                    timer.join(2)
                if locker:
                    locker.join(2)
            expected_count = int(case in {"duplicate", "clipboard_busy", "fresh_session_recovery"})
            passed = (
                not errors
                and not thread.is_alive()
                and len(writes) == expected_count
                and not session.policy.armed
                and controls.inhibit.is_set()
                and any(e["event"] == "arm_rejected" for e in events)
            )
            if case == "blank":
                passed &= exit_code == 1 and "Blank" in (session.failure or "")
            else:
                passed &= exit_code == 0
            if case == "static":
                passed &= any(
                    e["event"] == "status" and e["running"] and e["ready"] and e["armed"]
                    for e in events
                )
            if case in {"stop", "disarm"}:
                passed &= len(races) == 1 and all(
                    r["ocr_start_ns"] < r.get("command_accepted_ns", 0) < r["ocr_end_ns"]
                    for r in races
                )
            if case == "clipboard_busy":
                passed &= busy_seen[0]
            if case == "duplicate":
                passed &= any(
                    e.get("status") == "no_candidate" for e in events if e.get("event") == "frame"
                )
            result = {
                "event": "probe_result",
                "profile": profile,
                "case": case,
                "passed": bool(passed),
                "writes": writes,
                "races": races,
                "failure": session.failure,
                "errors": errors,
                "native_clipboard": args.native_clipboard,
                "busy_disarmed_uncommitted": busy_seen[0],
            }
            results.append(result)
            record(result)
            print(json.dumps(result), flush=True)
            return bool(passed)

        for profile in ("discount", "game"):
            cases = ["duplicate", "disarm", "stop", "blank", "static"]
            if args.native_clipboard:
                cases.append("clipboard_busy")
            cases.append("fresh_session_recovery")
            for case in cases:
                if not probe(profile, case):
                    break
            if not results[-1]["passed"]:
                break
        passed = all(row["passed"] for row in results)
        record({"event": "test_result", "passed": passed, "results": results})
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
