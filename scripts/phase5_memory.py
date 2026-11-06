"""Offline allocation diagnostic; no capture, windows, policy changes or clipboard writes.

Run arena on/off in separate processes. Timings under concurrent soak load are diagnostic,
not comparable native latency benchmarks. Uses the same negative pixels only as local input.
"""

import argparse
import json
from pathlib import Path

from negative_soak import negative_pixels
from qualification_metrics import ocr_options

from stream_code_capture.ocr import RapidRecognizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-arena", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--count", type=int, default=60)
    args = parser.parse_args()
    if not 3 <= args.count <= 1000:
        parser.error("count must be in [3,1000]")
    import win32api
    import win32process

    recognizer = RapidRecognizer(
        scale=1, threads=4, cpu_arena=args.cpu_arena, allow_spinning=False, det_limit=640
    )
    recognizer.warmup()
    samples = []

    def sample(stage):
        memory = win32process.GetProcessMemoryInfo(win32api.GetCurrentProcess())
        samples.append(
            {
                "stage": stage,
                "private_bytes": memory["PagefileUsage"],
                "working_set_bytes": memory["WorkingSetSize"],
            }
        )

    with args.report.open("x", encoding="utf-8") as report:
        sample("warmup")
        for _ in range(3):
            pixels = negative_pixels(20261105, 0, False)[400:540, 200:960].copy()
            recognizer.recognize(pixels)
        sample("baseline")
        for index in range(args.count):
            pixels = negative_pixels(20261105 + index, index * 180, True)[400:540, 200:960].copy()
            recognizer.recognize(pixels)
            sample(index)
        result = {
            "cpu_arena": args.cpu_arena,
            "ocr_sessions": ocr_options(recognizer),
            "count": args.count,
            "samples": samples,
            "baseline_to_final_bytes": samples[-1]["private_bytes"] - samples[1]["private_bytes"],
            "baseline_to_peak_bytes": max(s["private_bytes"] for s in samples[2:])
            - samples[1]["private_bytes"],
            "note": "Offline synthetic allocation diagnostic; not capture/accuracy qualification",
        }
        json.dump(result, report, indent=2)
        print(json.dumps({k: v for k, v in result.items() if k != "samples"}))


if __name__ == "__main__":
    main()
