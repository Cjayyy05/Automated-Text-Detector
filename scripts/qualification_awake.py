"""Explicit, bounded keep-awake request for screen qualification; no power-plan edits.

Does not prevent manual sleep, screen savers or locking. Creating --stop-file releases
the request; timeout and Ctrl+C also release it. No capture, GUI or clipboard access.
"""

import argparse
import ctypes
import json
from pathlib import Path
from time import monotonic, sleep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-display", action="store_true")
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.request_display or not 1 <= args.seconds <= 7200 or args.stop_file.exists():
        parser.error("Explicit --request-display, duration [1,7200] and a new stop-file required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    request = kernel.SetThreadExecutionState
    request.argtypes, request.restype = [ctypes.c_uint32], ctypes.c_uint32
    with args.report.open("x", encoding="utf-8") as report:
        if not request(0x80000003):  # ES_CONTINUOUS | SYSTEM_REQUIRED | DISPLAY_REQUIRED
            raise ctypes.WinError(ctypes.get_last_error())
        started = monotonic()
        try:
            report.write(json.dumps({"event": "requested", "max_seconds": args.seconds}) + "\n")
            report.flush()
            print("Temporary qualification display request active", flush=True)
            while monotonic() - started < args.seconds and not args.stop_file.exists():
                sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            released = bool(request(0x80000000))  # Clear this thread's requirements.
            report.write(
                json.dumps(
                    {"event": "released", "success": released, "elapsed_s": monotonic() - started}
                )
                + "\n"
            )
            print(f"Temporary display request released: {released}", flush=True)
        return int(not released)


if __name__ == "__main__":
    raise SystemExit(main())
