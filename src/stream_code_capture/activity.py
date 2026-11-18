"""Optional cheap OCR scheduling hint; never a recognition or correctness signal."""

import math

import numpy as np

from .domain import Image


class ActivityGate:
    def __init__(self, max_interval_ms: float) -> None:
        if not math.isfinite(max_interval_ms) or not 0 < max_interval_ms <= 1000:
            raise ValueError("Activity scan interval must be in (0, 1000] ms")
        self.interval_ns = int(max_interval_ms * 1e6)
        self.last_scan_ns: int | None = None
        self.previous: np.ndarray[tuple[int, ...], np.dtype[np.bool_]] | None = None

    def should_scan(self, image: Image, now_ns: int) -> bool:
        # Bright, approximately achromatic strokes exclude many colored candles.
        # Colored/low-contrast text can be absent from this hint: always scan on a
        # deadline measured from the last SCAN, never from the latest motion.
        # Pairwise ufuncs give the same extrema without a generic color-axis reduction.
        blue, green, red = image[:, :, 0], image[:, :, 1], image[:, :, 2]
        high = np.maximum(np.maximum(blue, green), red)
        low = np.minimum(np.minimum(blue, green), red)
        mask = (low >= 128) & (high - low <= 30)
        changed = self.previous is None or not np.array_equal(mask, self.previous)
        expired = self.last_scan_ns is None or now_ns - self.last_scan_ns >= self.interval_ns
        self.previous = mask
        if changed or expired:
            self.last_scan_ns = now_ns
            return True
        return False
