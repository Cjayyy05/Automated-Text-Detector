"""Bounded diagnostic samples: rolling percentiles, not an unbounded event log."""

from collections import defaultdict, deque

import numpy as np


class Metrics:
    def __init__(self, limit: int = 10000) -> None:
        self.samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=limit))

    def add(self, values: dict[str, float]) -> None:
        for key, value in values.items():
            self.samples[key].append(value)

    def summary(self) -> dict[str, dict[str, float | int]]:
        return {
            key: {
                "count": len(values),
                "p50_ms": float(np.percentile(values, 50)),
                "p95_ms": float(np.percentile(values, 95)),
                "max_ms": max(values),
            }
            for key, values in self.samples.items()
            if values
        }
