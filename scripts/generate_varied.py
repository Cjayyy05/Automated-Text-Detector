"""Additional seeded evaluation corpus: full alphabet, fonts, sizes and compression.

Run once and freeze the output before choosing optimizations; never train on expected strings.
"""

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np

from stream_code_capture.synthetic import chart_frame, make_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--per-style", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    rng, cases = random.Random(args.seed), []
    styles = [
        ("standard", 0.65, cv2.FONT_HERSHEY_SIMPLEX, 95, 1, False),
        ("compressed", 0.65, cv2.FONT_HERSHEY_SIMPLEX, 50, 1, False),
        ("small", 0.46, cv2.FONT_HERSHEY_SIMPLEX, 65, 1, True),
        ("large_duplex", 0.9, cv2.FONT_HERSHEY_DUPLEX, 85, 1, False),
        ("serif", 0.7, cv2.FONT_HERSHEY_COMPLEX, 80, 1, False),
        ("dim", 0.65, cv2.FONT_HERSHEY_SIMPLEX, 70, 0.6, False),
    ]
    for name, scale, font, quality, contrast, challenge in styles:
        for index in range(args.per_style + 1):
            negative = index == args.per_style
            code, frames, case_id = make_code(rng, challenge=True), [], len(cases)
            for tick in range(5):
                visible = not negative and tick in (1, 2, 4)
                pixels = chart_frame(
                    code,
                    tick=tick,
                    visible=visible,
                    seed=args.seed + case_id,
                    challenge=challenge,
                    code_scale=scale,
                    font=font,
                    angle_limit=6,
                )
                pixels = np.asarray(pixels * contrast, dtype=np.uint8)
                ok, encoded = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if not ok:
                    raise RuntimeError("JPEG encoding failed")
                filename = f"case_{case_id:03d}_{tick}.jpg"
                encoded.tofile(args.output / filename)
                frames.append({"file": filename, "target": code if visible else None})
            cases.append(
                {
                    "id": case_id,
                    "style": name,
                    "frames": frames,
                    "expected_writes": [] if negative else [code],
                }
            )
    manifest = {
        "schema": 1,
        "seed": args.seed,
        "roi": [70, 160, 610, 325],
        "profile": "varied",
        "cases": cases,
        "note": "Synthetic, not broadcast footage. Small cases intentionally undersampled.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "manifest": str(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
