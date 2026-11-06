"""Explicit one-shot ROI inspection; no OCR, clipboard access or viewer launch."""

import argparse
import json
import platform
from pathlib import Path
from time import perf_counter, perf_counter_ns, sleep

import cv2

from stream_code_capture.capture import DxcamSource
from stream_code_capture.domain import Rect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", help="Explicit screen-capture opt-in")
    parser.add_argument("--roi", type=int, nargs=4, required=True, metavar=("L", "T", "R", "B"))
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument(
        "--directory", type=Path, required=True, help="New local evidence directory"
    )
    args = parser.parse_args()
    if not args.capture:
        parser.error("Explicit --capture is required; this saves pixels from your desktop")
    if args.device < 0 or args.output < 0:
        parser.error("Device and output indexes must be nonnegative")
    region = Rect(*args.roi)
    region.validate(region.right, region.bottom)
    args.directory.mkdir(parents=True, exist_ok=False)
    record = {
        "scope": "One captured ROI, not OCR, live-policy or manual visual validation",
        "platform": platform.platform(),
        "device": args.device,
        "output": args.output,
        "roi": args.roi,
        "coordinate_space": "Selected output physical pixels; right/bottom exclusive",
        "manual_result": "NOT_RUN",
        "error": None,
    }
    source = None
    try:
        source = DxcamSource(region, args.device, args.output)
        deadline = perf_counter() + 3
        while True:
            started = perf_counter_ns()
            pixels = source.grab()
            completed = perf_counter_ns()
            if pixels is not None:
                break
            if perf_counter() >= deadline:
                raise RuntimeError("No new capture within three seconds; no image saved")
            sleep(0.02)
        ok, encoded = cv2.imencode(".png", pixels)
        if not ok:
            raise RuntimeError("PNG encoding failed")
        with (args.directory / "roi.png").open("xb") as image:
            image.write(encoded.tobytes())
        record.update(shape=list(pixels.shape), capture_start_ns=started, capture_end_ns=completed)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if source is not None:
            try:
                source.close()
            except Exception as exc:
                record["error"] = record["error"] or f"Capture cleanup failed: {exc}"
        with (args.directory / "capture.json").open("x", encoding="utf-8") as report:
            json.dump(record, report, indent=2)
    print(json.dumps(record))
    return int(record["error"] is not None)


if __name__ == "__main__":
    raise SystemExit(main())
