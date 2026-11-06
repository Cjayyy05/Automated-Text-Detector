"""Seeded test pixels only; never imported by the runtime recognizer or policy."""

import random

import cv2
import numpy as np

from stream_code_capture.synthetic import make_code


def draw_motion(pixels, region, tick):
    """Fixture motion must stay inside the selected ROI to supply distinct captures."""
    x = region.left + (tick * 7) % (region.right - region.left - 8)
    pixels[region.bottom - 2 : region.bottom, x : x + 8] = (70, 160, 50)


def scenes(seed, count, profile):
    rng = random.Random(seed)
    result = []
    for index in range(count):
        code = make_code(rng)
        # Include valid but intentionally unsupported ambiguous glyphs, without repairing them.
        if index % 4 == 3:
            code = code[:3] + rng.choice("O0") + code[4:]
        if profile == "game" and index % 4 == 2:
            code = code[:5] + "-" + code[5:]
        pixels = np.empty((540, 960, 3), np.uint8)
        ramp = np.linspace(rng.randint(15, 30), rng.randint(45, 70), 960, dtype=np.uint8)
        pixels[:] = ramp[None, :, None]
        for _ in range(45):
            x, y = rng.randrange(960), rng.randrange(540)
            cv2.line(pixels, (x, y), (x + rng.randrange(5, 55), y + 25), (65, 85, 65), 2)
        cv2.putText(pixels, "Chat: next round? 234.56", (25, 360), 0, 0.6, (190, 180, 175), 1)
        x, y = rng.randint(235, 450), rng.randint(445, 465)
        font = rng.choice([cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX])
        scale = rng.choice([0.8, 0.9, 1.0])
        cv2.putText(pixels, code, (x, y), font, scale, (245, 245, 245), 2, cv2.LINE_AA)
        context = "Expiry Date:" if profile == "game" else "100% off"
        cv2.putText(pixels, context, (x, y + 31), 0, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
        if index % 3 == 1:
            ok, encoded = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                raise RuntimeError("Fixture JPEG encoding failed")
            pixels = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        result.append((pixels, code))
    return result
