"""Known-font pixel matching experiment, NOT a production OCR or clipboard adapter.

Reranks O/0 alternatives from OCR using measured normalized cross correlation.
No truth is used to construct templates, crop, select scale or rank candidates.
"""

import argparse
import itertools
import json
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.policy import CODE


def variants(text):
    choices = [("O", "0") if character in "O0" else (character,) for character in text]
    # Bound work; this is not a brute force code dictionary.
    return ("".join(items) for items in itertools.islice(itertools.product(*choices), 32))


def match(pixels, text, box):
    left, top = max(0, box["left"] - 12), max(0, box["top"] - 12)
    right, bottom = (
        min(pixels.shape[1], box["right"] + 12),
        min(pixels.shape[0], box["bottom"] + 12),
    )
    region = cv2.cvtColor(pixels[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    scores = []
    for value in variants(text):
        best = -1
        for scale in (0.46, 0.58, 0.65, 0.7, 0.8, 0.9):
            for angle in range(-6, 7):
                canvas = np.zeros((70, 300), np.uint8)
                cv2.putText(
                    canvas, value, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, scale, 245, 1, cv2.LINE_AA
                )
                matrix = cv2.getRotationMatrix2D((150, 35), angle, 1)
                rotated = cv2.warpAffine(canvas, matrix, (300, 70))
                x, y, width, height = cv2.boundingRect(np.asarray(rotated > 20, dtype=np.uint8))
                template = rotated[y : y + height, x : x + width]
                if height > region.shape[0] or width > region.shape[1]:
                    continue
                score = float(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED).max())
                best = max(score, best)
        scores.append({"text": value, "ncc": best})
    return sorted(scores, key=lambda item: item["ncc"], reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recognition_report", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.recognition_report.read_text().splitlines()[0])
    timings, cases = Metrics(), []
    for outcome in record["outcomes"]:
        lines = [
            line
            for line in outcome["raw_lines"]
            if CODE.fullmatch(line["text"]) and any(character in line["text"] for character in "O0")
        ]
        for line in lines:
            path = Path(outcome["manifest"])
            data = json.loads(path.read_text())
            case = next(item for item in data["cases"] if item["id"] == outcome["case"])
            # OCR benchmark uses the same small ROI, independent of truth/expected value.
            image = Rect(70, 160, 610, 325).crop(
                read_image(path.parent / case["frames"][1]["file"])
            )
            start = perf_counter_ns()
            scores = match(image, line["text"], line["box"])
            elapsed = (perf_counter_ns() - start) / 1e6
            timings.add({"template_search": elapsed})
            cases.append(
                {
                    "case": outcome["case"],
                    "style": case.get("style"),
                    "expected": outcome["expected"],
                    "ocr": line["text"],
                    "scores": scores,
                    "wall_ms": elapsed,
                }
            )
    result = {
        "timings": timings.summary(),
        "cases": cases,
        "note": "Known Hershey Simplex font only; NCC is NOT an exact-code probability. "
        "This diagnostic does not write any clipboard.",
    }
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(
        json.dumps(
            {
                "timings": result["timings"],
                "cases": len(cases),
                "exact_top_match": sum(
                    item["scores"][0]["text"] in item["expected"] for item in cases
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
