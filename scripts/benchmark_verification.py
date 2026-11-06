"""Probe independent recognition on padded candidate crops; no clipboard access."""

import argparse
import json
from pathlib import Path
from time import perf_counter_ns

from rapidocr.ch_ppocr_rec import TextRecInput

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    recognizer = RapidRecognizer(allow_spinning=False)
    recognizer.warmup()
    metrics, records = Metrics(), []
    for case in map(json.loads, args.replay.read_text().splitlines()):
        if case["event"] != "case":
            continue
        outcome = case["outcomes"][0]
        item = next(c for c in data["cases"] if c["id"] == case["case"])
        image = Rect(*data["roi"]).crop(
            read_image(args.manifest.parent / item["frames"][1]["file"])
        )
        for line in outcome["lines"]:
            if line["text"] not in outcome["candidates"]:
                continue
            box = line["box"]
            padding = max(2, (box["bottom"] - box["top"]))
            crop = image[
                max(0, box["top"] - 2) : min(image.shape[0], box["bottom"] + 2),
                max(0, box["left"] - padding) : min(image.shape[1], box["right"] + padding),
            ]
            started = perf_counter_ns()
            result = recognizer._engine.text_rec(TextRecInput(img=crop))
            elapsed = (perf_counter_ns() - started) / 1e6
            metrics.add({"verification": elapsed})
            records.append(
                {
                    "case": case["case"],
                    "expected": case["expected"],
                    "candidate": line["text"],
                    "verified": result.txts,
                    "scores": result.scores,
                    "wall_ms": elapsed,
                }
            )
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump({"timings": metrics.summary(), "records": records}, handle, indent=2)
    print(json.dumps({"timings": metrics.summary(), "records": records}, indent=2))


if __name__ == "__main__":
    main()
