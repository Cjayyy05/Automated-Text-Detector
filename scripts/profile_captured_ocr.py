"""Profile latest Windows DXcam frames without arming or writing the clipboard."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.domain import Rect
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, assess_candidate, context_kind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", help="Explicit screen capture opt-in")
    parser.add_argument("--roi", nargs=4, type=int, required=True, metavar=("L", "T", "R", "B"))
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument(
        "--include-text", action="store_true", help="Save OCR text to the local report"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.capture or not 1 <= args.frames <= 30:
        parser.error("Use --capture and a frame limit of 1–30")
    reader = RapidRecognizer(profile_inference=True)
    reader.warmup()
    roi = Rect(*args.roi)
    config = PolicyConfig()
    worker = CaptureWorker(lambda: DxcamSource(roi, args.device, args.output))
    records = []
    with args.report.open("x", encoding="utf-8") as report:
        worker.start()
        try:
            worker.started.wait(3)
            for _ in range(args.frames):
                frame = worker.latest.wait(3)
                if frame is None or worker.error:
                    break
                started = perf_counter_ns()
                result = reader.recognize_timed(frame.image)
                finished = perf_counter_ns()
                layout = [
                    (line, assess_candidate(line, result.lines, config)) for line in result.lines
                ]
                record = {
                    "sequence": frame.sequence,
                    "capture_ms": frame.capture_ms,
                    "age_at_start_ms": (started - frame.captured_ns) / 1e6,
                    "result_age_ms": (finished - frame.captured_ns) / 1e6,
                    "process_ms": (finished - started) / 1e6,
                    "timings_ms": result.timings_ms,
                    "ocr_profile": asdict(result.profile) if result.profile else None,
                    "recognized_lines": len(result.lines),
                    "limited_heading_count": sum(
                        context_kind(line.text, config.profile) == "limited"
                        for line in result.lines
                    ),
                    "eligible_lines": sum(code is not None for _, (code, _) in layout),
                }
                if args.include_text:
                    record["lines"] = [
                        {**asdict(line), "candidate": code, "reason": reason}
                        for line, (code, reason) in layout
                    ]
                records.append(record)
        finally:
            worker.stop()
            json.dump(
                {
                    "roi": args.roi,
                    "device": args.device,
                    "output": args.output,
                    "records": records,
                    "capture_metrics": worker.metrics.summary(),
                    "dropped": worker.latest.dropped,
                    "error": worker.error,
                },
                report,
                indent=2,
            )
    print(json.dumps({"frames": len(records), "error": worker.error}))
    return int(not records or worker.error is not None)


if __name__ == "__main__":
    raise SystemExit(main())
