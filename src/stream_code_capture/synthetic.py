"""Seeded chart-video fixtures. Ground truth is never consumed by the recognizer."""

import json
import random
import string
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .domain import Image


def make_code(rng: random.Random, challenge: bool = False) -> str:
    alphabet = string.ascii_uppercase + string.digits
    if not challenge:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(rng.choices(alphabet, k=10))
        if any(c.isalpha() for c in code) and any(c.isdigit() for c in code):
            return code


def chart_frame(
    code: str,
    *,
    tick: int,
    visible: bool,
    seed: int,
    challenge: bool = False,
    code_scale: float | None = None,
    font: int = cv2.FONT_HERSHEY_SIMPLEX,
    angle_limit: float | None = None,
) -> Image:
    rng = random.Random(seed)
    image: Image = np.full((540, 960, 3), (23, 21, 18), dtype=np.uint8)
    cv2.rectangle(image, (0, 0), (959, 100), (55, 35, 25), -1)
    cv2.putText(
        image,
        "40% OFF - USE CODE: JORDY",
        (30, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.45,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )
    cv2.rectangle(image, (20, 125), (709, 509), (32, 29, 25), -1)
    for y in range(150, 510, 45):
        cv2.line(image, (20, y), (709, y), (48, 43, 38), 1)
        cv2.putText(
            image,
            f"{19500 + y / 10:.2f}",
            (630, y - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (140, 140, 140),
            1,
            cv2.LINE_AA,
        )
    for index, x in enumerate(range(35, 620, 17)):
        y = 340 + int(65 * np.sin(index * 0.24 + tick * 0.15))
        delta = rng.randint(8, 35)
        color = (90, 160, 60) if index % 2 else (70, 65, 190)
        cv2.line(image, (x, y - delta - 12), (x, y + 16), color, 1)
        cv2.rectangle(image, (x - 4, y - delta), (x + 4, y + 6), color, -1)
    cv2.putText(
        image,
        "LIVE  NASDAQ  19643.25  +0.81%",
        (30, 145),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (170, 170, 170),
        1,
        cv2.LINE_AA,
    )
    for index, text in enumerate(
        [
            "LIVE CHAT",
            "trader: nice move!",
            "user: JORDY works",
            "viewer: BUY NOW",
            "bot: AB12CD34EF",
            "price: 19735.25",
            f"messages: {125 + tick}",
        ]
    ):
        cv2.putText(
            image,
            text,
            (735, 150 + index * 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (215, 215, 215),
            1,
            cv2.LINE_AA,
        )
    if visible:
        # Position varies by seed, remains fixed across each brief appearance.
        x, y = rng.randint(95, 330), rng.randint(185, 235)
        patch = np.zeros((100, 260, 3), dtype=np.uint8)
        scale = code_scale if code_scale is not None else (0.46 if challenge else 0.65)
        cv2.putText(patch, code, (12, 30), font, scale, (245, 245, 245), 1, cv2.LINE_AA)
        cv2.putText(
            patch,
            "LucidPro Eval 50k",
            (12, 53),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (210, 210, 210),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            patch,
            "100% off",
            (12, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (245, 245, 245),
            1,
            cv2.LINE_AA,
        )
        limit = angle_limit if angle_limit is not None else (6 if challenge else 3)
        angle = rng.uniform(-limit, limit)
        transform = cv2.getRotationMatrix2D((130, 50), angle, 1)
        patch = np.asarray(cv2.warpAffine(patch, transform, (260, 100)), dtype=np.uint8)
        target = image[y : y + 100, x : x + 260]
        np.maximum(target, patch, out=target)
    if challenge:
        image = np.asarray(cv2.GaussianBlur(image, (3, 3), 0.5), dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None:
            raise RuntimeError("JPEG decoding failed")
        image = np.asarray(decoded, dtype=np.uint8)
    return image


def generate(output: Path, seed: int = 7, count: int = 3, challenge: bool = False) -> Path:
    if count < 1:
        raise ValueError("count must be positive")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists() or any(output.glob("case_*.png")):
        raise FileExistsError("Choose an empty output directory; existing fixtures are preserved")
    rng = random.Random(seed)
    cases: list[dict[str, Any]] = []
    for case_id in range(count + 1):
        code = make_code(rng, challenge)
        negative = case_id == count
        frames: list[dict[str, Any]] = []
        for tick in range(5):
            visible = not negative and tick in (1, 2, 4)
            filename = f"case_{case_id:03d}_{tick}.png"
            pixels = chart_frame(
                code, tick=tick, visible=visible, seed=seed + case_id, challenge=challenge
            )
            if not cv2.imwrite(str(output / filename), pixels):
                raise OSError(f"Could not write {filename}")
            frames.append({"file": filename, "target": code if visible else None})
        cases.append(
            {"id": case_id, "frames": frames, "expected_writes": [] if negative else [code]}
        )
    manifest = {
        "schema": 1,
        "seed": seed,
        "profile": "challenge" if challenge else "standard",
        "roi": [20, 125, 710, 510],
        "size": [960, 540],
        "cases": cases,
        "note": "Frame 0 is a disarmed baseline. Arm once; frame 4 must not overwrite.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path
