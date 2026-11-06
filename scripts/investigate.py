"""Reproduce challenge failures and benchmark identical pixels. Never writes clipboard."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--scales", type=float, nargs="+", default=[1, 2, 3])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--roi", type=int, nargs=4)
    parser.add_argument(
        "--raw", action="store_true", help="Diagnostic only: disable source quality floor"
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    roi = Rect(*(args.roi or manifest["roi"]))
    runs = []
    for scale in args.scales:
        recognizer = RapidRecognizer(
            scale=scale, min_code_pitch=0 if args.raw else 10, ambiguity_guard=not args.raw
        )
        recognizer.warmup()
        metrics = Metrics()
        cases = []
        for case in manifest["cases"][:-1]:
            image = roi.crop(read_image(args.manifest.parent / case["frames"][1]["file"]))
            for _ in range(args.repeats):
                result = recognizer.recognize_timed(image)
                metrics.add(result.timings_ms)
            cases.append(
                {
                    "id": case["id"],
                    "expected": case["expected_writes"],
                    "candidates": candidates(result.lines, PolicyConfig()),
                    "lines": [asdict(line) for line in result.lines],
                }
            )
        runs.append(
            {"scale": scale, "roi": asdict(roi), "timings": metrics.summary(), "cases": cases}
        )
    print(json.dumps(runs, indent=2))


if __name__ == "__main__":
    main()
