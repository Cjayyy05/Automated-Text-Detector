"""Small, pixel-based interfaces; coordinates are relative to the source image."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def validate(self, width: int, height: int) -> None:
        if not (0 <= self.left < self.right <= width and 0 <= self.top < self.bottom <= height):
            raise ValueError("ROI must be nonempty and entirely within the image")

    def crop(self, image: Image, *, copy: bool = True) -> Image:
        self.validate(image.shape[1], image.shape[0])
        view = image[self.top : self.bottom, self.left : self.right]
        return view.copy() if copy else view


@dataclass(frozen=True)
class TextLine:
    text: str
    confidence: float
    box: Rect
    rejection: str | None = None
    verification_text: str | None = None
    verification_confidence: float | None = None


@dataclass(frozen=True)
class Frame:
    image: Image
    sequence: int
    captured_ns: int  # perf_counter_ns domain, never a wall-clock timestamp
    capture_ms: float = 0
    delivered_ns: int | None = None
    dequeued_ns: int | None = None


@dataclass(frozen=True)
class RecognitionBatchTiming:
    crops: int
    input_width: int
    inference_ms: float


@dataclass
class RecognitionProfile:
    detected_lines: int = 0
    cache_state: str = "inactive"
    crop_bytes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    grouping_misses: int = 0
    matched_crops_in_misses: int = 0
    code_batches_excluded: int = 0
    batches: list[RecognitionBatchTiming] = field(default_factory=list)


@dataclass(frozen=True)
class Recognition:
    lines: list[TextLine]
    timings_ms: dict[str, float]
    profile: RecognitionProfile | None = None


@runtime_checkable
class TimedRecognizer(Protocol):
    def recognize_timed(self, image: Image) -> Recognition: ...


class Recognizer(Protocol):
    def warmup(self) -> None: ...

    def recognize(self, image: Image) -> list[TextLine]: ...


class Clipboard(Protocol):
    def write(self, text: str) -> None:
        """Return only after successful write; raise on failure."""
        ...
