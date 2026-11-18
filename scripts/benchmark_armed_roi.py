"""Profile armed ROI processing with offline pixels and the memory clipboard."""

import argparse
import json
import random
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline

SIZES = {"small": (440, 165, 0), "medium": (780, 430, 6), "large": (1137, 841, 18)}


def scene(width, height, rows, code, position, phase, *, moving_text):
    image = np.full((height, width, 3), (30, 37, 48), np.uint8)
    for row in range(rows):
        for col in range(width // 310):
            text = f"Market {col + 1}  price {248.25 + row + (phase if moving_text else 0):.2f}"
            cv2.putText(
                image,
                text,
                (10 + col * 310, 24 + row * 31),
                0,
                0.54,
                (210, 215, 219),
                1,
                cv2.LINE_AA,
            )
    # Motion both inside the text scene and away from code pixels.
    cv2.rectangle(
        image, (6 + phase * 11, height - 4), (15 + phase * 11, height - 2), (66, 150, 99), -1
    )
    if code:
        scale = 0.66 if position == "right" else 0.93
        text = f"Code: {code}" if position == "left" else code
        text_width = cv2.getTextSize(text, 0, scale, 2)[0][0]
        x = 8 if position == "left" else width - text_width - 13
        y = height - 21 if position == "left" else height - 59
        context = "LIMITED TIME OFFER" if position == "left" else "100% off"
        cv2.putText(
            image,
            context,
            (x, y - 38 if position == "left" else y + 32),
            0,
            0.61,
            (240, 205, 175),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(image, text, (x, y), 0, scale, (250, 236, 205), 2, cv2.LINE_AA)
    return image


def run(ocr, size, seed, events, moving_text, observations=2):
    width, height, rows = SIZES[size]
    roi = Rect(0, 0, width, height)
    metrics, results = Metrics(), []
    rng = random.Random(seed)
    for event in range(events + 2):
        code = (
            None
            if event >= events
            else "".join(rng.sample("ABDEFGHJKMNPQRSTUVWYZ23456789", 8)) + "K7"
        )
        position = "left" if event % 2 == 0 else "right"
        existing = "WJ78NZ29FQ"
        baseline = scene(width, height, rows, existing, "left", 0, moving_text=moving_text)
        # One negative is the unchanged existing code with other changed screen pixels.
        frames = [
            scene(
                width,
                height,
                rows,
                existing if event == events else code,
                "left" if event == events else position,
                phase,
                moving_text=moving_text,
            )
            for phase in range(1, observations + 1)
        ]
        clipboard = MemoryClipboard()
        pipeline = Pipeline(ocr, clipboard, roi, copy_roi=False)
        pipeline.baseline(Frame(baseline, 0, perf_counter_ns()))
        pipeline.policy.arm()
        outcomes, armed_before = [], []
        for i, image in enumerate(frames, 1):
            armed_before.append(pipeline.policy.armed)
            outcomes.append(pipeline.process(Frame(image, i, perf_counter_ns())))
        for outcome in outcomes:
            metrics.add(outcome.timings_ms)
            metrics.add({"recognized_lines": float(len(outcome.lines))})
        results.append(
            {
                "expected": code,
                "position": position,
                "suppressed": sorted(pipeline.policy.suppressed),
                "writes": clipboard.writes,
                "statuses": [o.status for o in outcomes],
                "armed_before": armed_before,
                "candidates": [o.candidates for o in outcomes],
                "timings": [o.timings_ms for o in outcomes],
            }
        )
    return {
        "size": size,
        "dimensions": [width, height],
        "moving_text": moving_text,
        "timings": metrics.summary(),
        "events": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", nargs="+", choices=SIZES, default=list(SIZES))
    parser.add_argument("--threads", type=int, nargs="+", default=[2])
    parser.add_argument("--no-spinning", action="store_true")
    parser.add_argument("--events", type=int, default=4)
    parser.add_argument("--observations", type=int, default=2)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--seed", type=int, default=57211)
    parser.add_argument("--moving-text", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with args.report.open("x", encoding="utf-8") as report:
        for threads in args.threads:
            recognizer = RapidRecognizer(
                threads=threads,
                allow_spinning=not args.no_spinning,
                profile_inference=True,
                reuse_static_batches=args.reuse,
            )
            recognizer.warmup()
            for size in args.size:
                result = run(
                    recognizer, size, args.seed, args.events, args.moving_text, args.observations
                )
                result["threads"] = threads
                result["reuse"] = args.reuse
                report.write(json.dumps(result) + "\n")
                report.flush()
                print(
                    size,
                    threads,
                    result["timings"]["process"],
                    [(e["statuses"], e["writes"]) for e in result["events"]],
                    flush=True,
                )


if __name__ == "__main__":
    main()
