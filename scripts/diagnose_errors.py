"""Read old regression manifests with detected and wider recognition crops, memory only.

No truth selects a detection or repairs output. Every code-shaped OCR line is inspected.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

from rapidocr.ch_ppocr_rec import TextRecInput

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import CODE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--cases", type=int, nargs="+")
    parser.add_argument("--model-profile", choices=("baseline", "tiny"), default="baseline")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    recognizer = RapidRecognizer(
        model_profile=args.model_profile,
        scale=1 if args.model_profile == "tiny" else 2,
        allow_spinning=False,
    )
    verifier = RapidRecognizer(allow_spinning=False)
    recognizer.warmup()
    verifier.warmup()
    records = []
    with args.report.open("x", encoding="utf-8") as handle:
        for case in data["cases"]:
            if not case["expected_writes"] or (
                args.cases is not None and case["id"] not in args.cases
            ):
                continue
            pixels = Rect(*data["roi"]).crop(
                read_image(args.manifest.parent / case["frames"][1]["file"])
            )
            result = recognizer.recognize_timed(pixels)
            probes = []
            for line in result.lines:
                if not CODE.fullmatch(line.text.strip()):
                    continue
                start = perf_counter_ns()
                text, score = verifier.verify_line(pixels, line.box)
                elapsed = (perf_counter_ns() - start) / 1e6
                tight = line.box.crop(pixels)
                same_crop = {}
                for name, model in (("primary", recognizer), ("baseline", verifier)):
                    prediction = model._engine.text_rec(TextRecInput(img=tight))
                    same_crop[name] = {"texts": prediction.txts, "scores": prediction.scores}
                primary_wide, primary_score = recognizer.verify_line(pixels, line.box)
                probes.append(
                    {
                        "detected": asdict(line),
                        "wider_crop_text": text,
                        "wider_crop_score": score,
                        "verification_ms": elapsed,
                        "same_tight_crop": same_crop,
                        "primary_wider_text": primary_wide,
                        "primary_wider_score": primary_score,
                    }
                )
            records.append(
                {
                    "case": case["id"],
                    "expected": case["expected_writes"],
                    "lines": [asdict(line) for line in result.lines],
                    "probes": probes,
                    "timings": result.timings_ms,
                }
            )
        json.dump(
            {
                "model_profile": args.model_profile,
                "records": records,
                "note": "Diagnostic re-read, no new acceptance or clipboard. Wider crops are "
                "selected by detections, not truth. Different text can reflect "
                "crop and model effects; "
                "this does not prove a pure detector defect.",
            },
            handle,
            indent=2,
        )
        print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
