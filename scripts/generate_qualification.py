"""Generate labelled synthetic sessions; never presented as real broadcast holdout data."""

import argparse
import hashlib
import json
import random
from pathlib import Path

import cv2
import numpy as np

from stream_code_capture.dataset import save_json, store_frame, validate
from stream_code_capture.synthetic import chart_frame, make_code


def generate(output, seed, sessions):
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    styles = (
        "standard",
        "italic",
        "small",
        "compressed",
        "blur",
        "dim",
        "lowercase",
        "hyphen",
        "short",
        "long",
        "partial",
        "persistent",
    )
    paths = []
    for session in range(sessions):
        root = output / f"session_{session:02d}"
        (root / "frames").mkdir(parents=True)
        source = f"phase3-synthetic-v1:{seed}:{session}"
        data = {
            "schema": 1,
            "labelled": True,
            "session_id": source,
            "source_kind": "synthetic",
            "sources": [{"name": source, "sha256": hashlib.sha256(source.encode()).hexdigest()}],
            "frames": [],
            "timestamp_basis": "synthetic frame index; not measured presentation time",
        }
        for event, style in enumerate(styles):
            code = make_code(rng, challenge=True)
            if style == "lowercase":
                code = code.lower()
            elif style == "hyphen":
                code = code[:5] + "-" + code[5:]
            elif style == "short":
                code = code[:6]
            elif style == "long":
                code += make_code(rng, challenge=True)[:2]
            font = (
                cv2.FONT_HERSHEY_COMPLEX | cv2.FONT_ITALIC
                if style == "italic"
                else cv2.FONT_HERSHEY_SIMPLEX
            )
            scale = 0.46 if style == "small" else 0.7
            x, y, angle = rng.randint(90, 330), rng.randint(170, 215), rng.uniform(-6, 6)
            matrix = cv2.getRotationMatrix2D((125, 42), angle, 1)
            glyphs = np.zeros((85, 250), np.uint8)
            cv2.putText(glyphs, code, (12, 28), font, scale, 245, 1, cv2.LINE_AA)
            glyphs = cv2.warpAffine(glyphs, matrix, (250, 85))
            gx, gy, gw, gh = cv2.boundingRect(np.asarray(glyphs > 10, dtype=np.uint8))
            box = [x + gx - 2, y + gy - 2, x + gx + gw + 2, y + gy + gh + 2]
            for tick in range(3):
                pixels = chart_frame(
                    code, tick=tick, visible=False, seed=seed + event + session * 100
                )
                # Fixture-only background variation, never a recognition template.
                background = ("chart", "gradient", "moving_shapes")[session % 3]
                if background == "gradient":
                    ramp = np.linspace(25, 90, 690, dtype=np.uint8)
                    pixels[160:325, 20:710] = ramp[None, :, None]
                elif background == "moving_shapes":
                    pixels[160:325, 20:710] = (65, 35, 20)
                    for offset in range(8):
                        cv2.circle(
                            pixels,
                            (70 + offset * 70 + tick * 5, 230),
                            25,
                            (80 + offset * 8, 70, 40),
                            -1,
                        )
                visible = tick > 0 or style == "persistent"
                if visible:
                    context = np.zeros((85, 250), np.uint8)
                    cv2.putText(
                        context,
                        "100% off",
                        (12, 65),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        245,
                        1,
                        cv2.LINE_AA,
                    )
                    overlay = np.maximum(glyphs, cv2.warpAffine(context, matrix, (250, 85)))
                    if style == "partial":
                        overlay[gy : gy + gh + 1, gx : gx + max(3, gw // 4)] = 0
                    image_patch = np.repeat(overlay[:, :, None], 3, axis=2)
                    pixels[y : y + 85, x : x + 250] = np.maximum(
                        pixels[y : y + 85, x : x + 250], image_patch
                    )
                if style == "blur":
                    pixels = cv2.GaussianBlur(pixels, (3, 3), 0.9)
                if style == "dim":
                    pixels = np.asarray(pixels * 0.6, dtype=np.uint8)
                quality = 40 if style == "compressed" else 85
                ok, compressed = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if not ok:
                    raise RuntimeError("Fixture encoding failed")
                pixels = cv2.imdecode(compressed, cv2.IMREAD_COLOR)
                frame = store_frame(root, pixels, len(data["frames"]), event * 3 + tick, None)
                state = (
                    "baseline"
                    if tick == 0
                    else (
                        "negative"
                        if style == "persistent"
                        else "partial"
                        if style == "partial"
                        else "visible"
                    )
                )
                frame["label"] = {
                    "event_id": str(event),
                    "state": state,
                    "code": code if state in {"visible", "partial"} else "",
                    "box": box if state in {"visible", "partial"} else None,
                    "roi": [70, 160, 610, 325],
                    "tags": [style, background, "banner", "chat"],
                    "reviewer": "synthetic-generator-v1 (not human broadcast labels)",
                }
                data["frames"].append(frame)
        validate(data, root)
        path = root / "labelled.json"
        save_json(path, data)
        paths.append(str(path))
    print(json.dumps({"manifests": paths, "source_kind": "synthetic"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--sessions", type=int, default=3)
    args = parser.parse_args()
    if args.sessions < 2:
        parser.error("Use at least two independently generated sessions")
    generate(args.output, args.seed, args.sessions)


if __name__ == "__main__":
    main()
