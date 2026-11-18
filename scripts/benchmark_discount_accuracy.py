"""Memory-only split-label holdout and raw O/0 image probes."""

import argparse
import json
import random
from pathlib import Path
from time import perf_counter_ns

import cv2
from benchmark_discount_layouts import from_manifest, generated, render, run

from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer


def annotation(rows, style, phase):
    image = render([], style, phase)
    fonts = (cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_TRIPLEX)
    if style == 2:
        image[:] = (62, 35, 24)
        image[:, 470:] = (57, 31, 20)
        image[173 + phase, 588] = 220
    for text, x, y, scale in rows:
        cv2.putText(image, text, (x, y), fonts[style], scale, (246, 194, 113), 2, cv2.LINE_AA)
    if style == 2:
        success, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 58])
        assert success
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    return image


def split_label_cases(seed, styles):
    rng = random.Random(seed)
    for style in styles:
        for layout in ("side", "above"):
            code = "".join(rng.sample("ABDEFGHJKMNPQRSTUVWYZ23456789", 10))
            # Guarantee mixed alphanumerics without conditioning on OCR output.
            code = code[:8] + "7K"
            token = (code, 182 if layout == "side" else 32, 120, 0.91)
            label = ("Code:", 32, 120 if layout == "side" else 87, 0.73)
            heading = ("LIMITED TIME OFFER", 31, 46, 0.82)
            for group, rows, expected in (
                ("split", [token, label, heading], code),
                ("no_offer", [token, label, ("Market update", 31, 46, 0.82)], None),
                ("wrong_label", [token, ("User ID:", *label[1:]), heading], None),
                ("far_label", [token, ("Code:", 505, 169, 0.73), heading], None),
                ("weak_offer", [token, label, ("promo in chat", 31, 46, 0.82)], None),
            ):
                frames = [annotation(rows, style, phase) for phase in (0, 1)]
                yield f"{layout}-{style}-{group}", group, expected, frames
        for glyph in "O0":
            for size in (0.56, 0.92):
                code = "T" + "".join(rng.sample("ABDEFGHJKMNPQRSTUVWYZ23456789", 7)) + "9"
                # Add the ambiguous glyph within the code, with varied neighboring letters.
                code = code[:4] + glyph + code[4:]
                rows = [(code, 30, 53, size), ("40% off", 32, 126, 0.84)]
                frames = [annotation(rows, style, phase) for phase in (0, 1)]
                yield f"glyph-{glyph}-{style}-{size}", "O0", code, frames


def read_top(ocr, image):
    # Known fixture position isolates transcription. The recognizer sees pixels only.
    return next(
        (
            (line.text, line.confidence, line.box)
            for line in ocr.recognize(image)
            if line.box.bottom < 75
        ),
        ("", None, None),
    )


def probe(cases):
    reader = RapidRecognizer()
    reader.warmup()
    alternatives = {f"scale_{scale}": RapidRecognizer(scale=scale) for scale in (1, 3)}
    for alternate in alternatives.values():
        alternate.warmup()
    metrics, records = Metrics(), []
    for name, group, expected, frames in cases:
        if group != "O0":
            continue
        image = frames[0]

        text, score, box = read_top(reader, image)
        readings = {"baseline": (text, score)}
        for method, alternate in alternatives.items():
            started = perf_counter_ns()
            text, score, _ = read_top(alternate, image)
            readings[method] = (text, score)
            metrics.add({method: (perf_counter_ns() - started) / 1e6})
        if box:
            crop = Rect(
                max(0, box.left - 4), max(0, box.top - 3), box.right + 4, box.bottom + 3
            ).crop(image)
            crop_box = Rect(0, 0, crop.shape[1], crop.shape[0])
            for method in ("tight_crop", "crop_otsu", "crop_clahe"):
                started = perf_counter_ns()
                pixels = crop
                if method != "tight_crop":
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    if method == "crop_otsu":
                        _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                    else:
                        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
                    pixels = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                readings[method] = reader.verify_line(pixels, crop_box)
                metrics.add({method: (perf_counter_ns() - started) / 1e6})
        records.append({"case": name, "expected": expected, "readings": readings})
    return {"records": records, "timings": metrics.summary()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("legacy", "development", "holdout"))
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.suite == "legacy":
        cases = list(generated(41361))
        for name in ("smoke", "challenge"):
            cases.extend(from_manifest(Path("samples") / name / "manifest.json"))
        rows = [("680J6BN7JX", 30, 46), ("LudiFlex Eval 50k", 30, 88), ("100% off", 30, 132)]
        cases.append(
            ("reported-layout", "reported", rows[0][0], [render(rows, 0, i) for i in (0, 1)])
        )
    else:
        seed, styles = (6419, (0,)) if args.suite == "development" else (8143, (1, 2))
        cases = list(split_label_cases(seed, styles))
    with args.report.open("x", encoding="utf-8") as report:
        json.dump(probe(cases) if args.probe else run(cases, alternate=None), report, indent=2)


if __name__ == "__main__":
    main()
