"""Oracle-box diagnostics only: localization vs recognition, never a clipboard strategy.

Human/fixture boxes deliberately isolate recognition. All methods see the same pixels,
never expected text or length. Connected-component glyph templates use only A-Z/0-9.
"""

import argparse
import json
import string
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np
from rapidocr.ch_ppocr_rec import TextRecInput

from stream_code_capture.dataset import audit_split, image_path, load_dataset, load_pixels
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer


def normalize(mask):
    x, y, width, height = cv2.boundingRect(mask)
    if width == 0 or height == 0:
        return np.zeros((32, 24), np.float32)
    # Preserve aspect ratio; narrow I and broad O must not be forced to the same width.
    ratio = min(28 / height, 20 / width)
    resized = cv2.resize(
        mask[y : y + height, x : x + width],
        (max(1, round(width * ratio)), max(1, round(height * ratio))),
    )
    output = np.zeros((32, 24), np.float32)
    left = (24 - resized.shape[1]) // 2
    output[2 : 2 + resized.shape[0], left : left + resized.shape[1]] = resized / 255
    return output


class GlyphTemplates:
    def __init__(self):
        self.templates, self.symbols = [], []
        for symbol in string.ascii_uppercase + string.digits:
            for scale in (0.46, 0.65, 0.7, 0.9):
                canvas = np.zeros((50, 50), np.uint8)
                cv2.putText(
                    canvas, symbol, (8, 35), cv2.FONT_HERSHEY_SIMPLEX, scale, 255, 1, cv2.LINE_AA
                )
                self.templates.append(normalize(np.asarray(canvas > 110, np.uint8) * 255))
                self.symbols.append(symbol)
        self.templates = np.stack(self.templates)

    def recognize(self, pixels):
        gray = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        boxes = sorted(
            (x, y, w, h)
            for x, y, w, h, area in stats[1:]
            if area >= 3 and h >= max(3, pixels.shape[0] * 0.3)
        )
        symbols, distances = [], []
        for x, y, width, height in boxes:
            glyph = normalize(mask[y : y + height, x : x + width])
            mse = np.mean((self.templates - glyph) ** 2, axis=(1, 2))
            index = int(np.argmin(mse))
            symbols.append(self.symbols[index])
            distances.append(float(mse[index]))
        return "".join(symbols), distances  # Distances, never fabricated confidence.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", type=Path)
    parser.add_argument("--partition", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--model-profile", choices=("baseline", "tiny", "v4"), default="baseline")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    entries = audit_split(args.split)
    recognizer = RapidRecognizer(model_profile=args.model_profile, allow_spinning=False)
    recognizer.warmup()
    glyphs = GlyphTemplates()
    records, metrics = [], Metrics()
    with args.report.open("x", encoding="utf-8") as report:
        for item in entries:
            if item["partition"] != args.partition:
                continue
            path = Path(item["manifest"])
            data = load_dataset(path)
            for frame in data["frames"]:
                label = frame["label"]
                if label["state"] not in {"visible", "partial"} or label["box"] is None:
                    continue
                pixels = load_pixels(image_path(path.parent, frame["file"]))
                box = Rect(*label["box"])
                raw = box.crop(pixels)
                for method in ("tight", "padded", "gray", "otsu", "glyph_templates"):
                    started = perf_counter_ns()
                    if method == "padded":
                        crop = Rect(
                            max(0, box.left - 12),
                            max(0, box.top - 2),
                            min(pixels.shape[1], box.right + 12),
                            min(pixels.shape[0], box.bottom + 2),
                        ).crop(pixels)
                    else:
                        crop = raw
                    if method in {"gray", "otsu"}:
                        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        if method == "otsu":
                            _, crop = cv2.threshold(
                                crop, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
                            )
                        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
                    if method == "glyph_templates":
                        text, evidence = glyphs.recognize(crop)
                    else:
                        result = recognizer._engine.text_rec(TextRecInput(img=crop))
                        text = result.txts[0] if result.txts else ""
                        evidence = list(result.scores) if result.scores else []
                    elapsed = (perf_counter_ns() - started) / 1e6
                    metrics.add({method: elapsed})
                    records.append(
                        {
                            "manifest": str(path),
                            "frame_id": frame["frame_id"],
                            "state": label["state"],
                            "tags": label["tags"],
                            "method": method,
                            "expected": label["code"],
                            "text": text,
                            "evidence": evidence,
                            "exact": text == label["code"],
                            "wall_ms": elapsed,
                        }
                    )
        accuracy = {
            method: {
                "exact": sum(
                    r["exact"] for r in records if r["method"] == method and r["state"] == "visible"
                ),
                "visible_frames": sum(
                    r["method"] == method and r["state"] == "visible" for r in records
                ),
            }
            for method in ("tight", "padded", "gray", "otsu", "glyph_templates")
        }
        result = {
            "model_profile": args.model_profile,
            "accuracy": accuracy,
            "timings": metrics.summary(),
            "records": records,
            "note": "Oracle annotation boxes; no detection, context, policy, "
            "confirmation or clipboard. Raw recognition ignores safety guards "
            "only in this diagnostic. "
            "Not deployable accuracy or end-to-end latency. Glyph MSE is not confidence.",
        }
        json.dump(result, report, indent=2)
        print(json.dumps({"accuracy": accuracy, "timings": result["timings"]}, indent=2))


if __name__ == "__main__":
    main()
