"""Compare Discount policy versions on reproducible pixels using only memory clipboard."""

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from stream_code_capture.cli import read_image
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import discount_code


def render(lines, style, phase):
    image = np.full((200, 610, 3), (24, 27, 31), np.uint8)
    fonts = (cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_COMPLEX)
    for text, x, y in lines:
        cv2.putText(
            image,
            text,
            (x, y),
            fonts[style],
            (0.88, 0.96, 0.82)[style],
            ((255, 175, 100), (226, 231, 235), (168, 234, 199))[style],
            2,
            cv2.LINE_AA,
        )
    # Change pixels outside text to model independent rendered frames.
    cv2.line(image, (580, 166), (589, 175 + phase), (72, 108, 92), 2)
    if style == 2:
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 55])
        assert ok
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return image


def generated(seed):
    rng = random.Random(seed)

    def token():
        return "".join(rng.choices("ABCDEFGHJKMNPQRTUVWXYZ", k=5) + rng.choices("2345679", k=5))

    for style in range(3):
        for layout, position, context in (
            ("above", (30, 44), ("100% off", 30, 125)),
            ("below", (30, 111), ("35% off", 30, 68)),
            ("left", (30, 111), ("25% off", 234, 111)),
            ("right", (184, 110), ("50% off", 28, 110)),
            ("label", (30, 110), ("LIMITED TIME OFFER", 30, 66)),
            ("promo-label", (30, 110), ("LIMITED TIME OFFER", 30, 66)),
        ):
            value = token()
            label = {"label": "CODE: ", "promo-label": "Promo code: "}.get(layout, "")
            lines = [(label + value, *position), context]
            if layout == "above":
                lines.append(("Pro Trial 25k", 30, 83))
            yield f"{layout}-{style}", "clear", value, [render(lines, style, i) for i in (0, 1)]

        pair = token()
        for char in "O0":
            value = pair[:2] + char + pair[3:]
            lines = [(value, 30, 55), ("100% off", 30, 118)]
            yield f"glyph-{char}-{style}", "O0", value, [render(lines, style, i) for i in (0, 1)]

        for label, value, context, x, y in (
            ("number", "1234567890", "25% off", 30, 126),
            ("username", "@Trader2345", "25% off", 30, 126),
            ("price", "USD 499.99", "25% off", 30, 126),
            ("timestamp", "12:34:56 PM", "25% off", 30, 126),
            ("chat", "TRADER2345", "chat about a promo", 30, 126),
            ("remote", "TRADER2345", "25% off", 400, 167),
            ("metadata", "Order ID: AB234567CD", "25% off", 30, 126),
            ("other-label", "CODE: AB234567CD", "Market commentary", 30, 126),
        ):
            lines = [(value, 30, 82), (context, x, y)]
            yield f"{label}-{style}", "negative", None, [render(lines, style, i) for i in (0, 1)]


def from_manifest(path):
    manifest = json.loads(path.read_text())
    roi = Rect(*manifest["roi"])
    for case in manifest["cases"]:
        expected = next(iter(case["expected_writes"]), None)
        frames = [roi.crop(read_image(path.parent / f["file"])) for f in case["frames"][1:3]]
        yield f"{path.parent.name}-{case['id']}", path.parent.name, expected, frames


def run(cases, alternate):
    ocr = RapidRecognizer()
    ocr.warmup()
    verifier = RapidRecognizer(model_profile=alternate) if alternate else None
    if verifier:
        verifier.warmup()
    metrics = Metrics()
    records = []
    for name, group, expected, frames in cases:
        assert len(frames) == 2 and not np.array_equal(*frames), name
        height, width = frames[0].shape[:2]
        clipboard = MemoryClipboard()
        pipeline = Pipeline(ocr, clipboard, Rect(0, 0, width, height))
        pipeline.policy.learn_baseline([])
        pipeline.policy.arm()
        # Simulate independent, timely captures; elapsed processing is measured below.
        outcomes = [
            pipeline.process(Frame(image, i, perf_counter_ns())) for i, image in enumerate(frames)
        ]
        for outcome in outcomes:
            metrics.add(
                {key: outcome.timings_ms[key] for key in ("ocr", "candidate_validation", "process")}
            )
        probes = []
        if verifier and group in {"O0", "challenge", "reported"}:
            for line in outcomes[0].lines:
                if not discount_code(line.text):
                    continue
                started = perf_counter_ns()
                text, score = verifier.verify_line(frames[0], line.box)
                elapsed = (perf_counter_ns() - started) / 1e6
                metrics.add({"alternate_crop": elapsed})
                probes.append({"primary": line.text, "alternate": text, "score": score})
        records.append(
            {
                "case": name,
                "group": group,
                "expected": expected,
                "writes": clipboard.writes,
                "statuses": [outcome.status for outcome in outcomes],
                "candidates": [outcome.candidates for outcome in outcomes],
                "lines": [[asdict(line) for line in outcome.lines] for outcome in outcomes],
                "probes": probes,
            }
        )
    return {"timings": metrics.summary(), "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=41361)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--alternate", choices=("tiny", "v4"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    cases = list(generated(args.seed))
    for path in args.manifest:
        cases.extend(from_manifest(path))
    # Recreate the reported layout from text, independently of any TradingView pixels.
    lines = [("680J6BN7JX", 30, 46), ("LudiFlex Eval 50k", 30, 88), ("100% off", 30, 132)]
    cases.append(
        ("reported-layout", "reported", lines[0][0], [render(lines, 0, i) for i in (0, 1)])
    )
    with args.report.open("x", encoding="utf-8") as output:
        report = run(cases, args.alternate)
        json.dump(report, output, indent=2)
    for group in sorted({r["group"] for r in report["records"]}):
        records = [r for r in report["records"] if r["group"] == group]
        positives = [r for r in records if r["expected"] is not None]
        wrong = sum(bool(r["writes"]) and r["writes"] != [r["expected"]] for r in records)
        exact = sum(r["writes"] == [r["expected"]] for r in positives)
        abstained = sum(not r["writes"] for r in positives)
        negatives = len(records) - len(positives)
        print(
            f"{group}: exact {exact}/{len(positives)}, abstained {abstained}, "
            f"wrong {wrong}, negatives {negatives}"
        )
    print(json.dumps(report["timings"], indent=2))


if __name__ == "__main__":
    main()
