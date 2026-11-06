"""Conservative, exact-string decisions. No spelling correction or O/0 substitution."""

import math
import re
from dataclasses import dataclass
from time import perf_counter_ns

from .domain import TextLine

CODE = re.compile(r"(?=[A-Z0-9]{8,16}\Z)(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]+", re.ASCII)
CONTEXT = re.compile(r"(?:\b\d{1,3}\s*%\s*off\b|\bpromo(?:tion)?\b|\buse\s+code\b)", re.I)
GAME_CODE = re.compile(r"(?=.{8,20}\Z)(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]+(?:-[A-Z0-9]+)*", re.ASCII)
GAME_CONTEXT = re.compile(r"expiry\s*date|redemption\s*code|有効期限|有效期至|兑换码|兌換碼", re.I)


@dataclass(frozen=True)
class PolicyConfig:
    min_confidence: float = 0.96
    confirmations: int = 2
    confirmation_window_ms: float = 1000
    max_frame_age_ms: float = 1000
    profile: str = "discount"

    def __post_init__(self) -> None:
        if self.profile not in {"discount", "game"}:
            raise ValueError("Detection profile must be discount or game")
        if not math.isfinite(self.min_confidence) or not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be between zero and one")
        if self.confirmations < 1:
            raise ValueError("confirmations must be positive")
        for value in (self.confirmation_window_ms, self.max_frame_age_ms):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("timing limits must be finite and positive")


def code_text(line: TextLine, profile: str = "discount") -> str | None:
    text = line.text.strip()
    pattern = GAME_CODE if profile == "game" else CODE
    return text if pattern.fullmatch(text) else None


def candidates(lines: list[TextLine], config: PolicyConfig) -> list[str]:
    """Require exact code format and nearby context for the selected detection profile."""
    result: set[str] = set()
    for line in lines:
        code = code_text(line, config.profile)
        if code is None or line.rejection or not config.min_confidence <= line.confidence <= 1:
            continue
        height = max(1, line.box.bottom - line.box.top)
        center = (line.box.left + line.box.right) / 2
        if config.profile == "game":
            # Hyphens must not bypass the adapter's alphanumeric-only quality guards.
            if (
                any(char in code for char in "O0")
                or (line.box.right - line.box.left) / len(code) < 10
            ):
                continue
            for context in lines:
                if context is line or not 0.75 <= context.confidence <= 1 or context.rejection:
                    continue
                horizontal_gap = max(
                    0, line.box.left - context.box.right, context.box.left - line.box.right
                )
                vertical_gap = max(
                    0, line.box.top - context.box.bottom, context.box.top - line.box.bottom
                )
                if (
                    GAME_CONTEXT.search(context.text)
                    and horizontal_gap <= height * 4
                    and vertical_gap <= height * 2
                ):
                    result.add(code)
            continue
        for context in lines:
            if context is line or not 0.75 <= context.confidence <= 1:
                continue
            if not CONTEXT.search(context.text):
                continue
            nearby_below = 0 <= context.box.top - line.box.bottom <= height * 10
            aligned = context.box.left - height * 2 <= center <= context.box.right + height * 2
            if nearby_below and aligned:
                result.add(code)
                break
    return sorted(result)


class DecisionPolicy:
    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config if config is not None else PolicyConfig()
        self.armed = False
        self.baseline_ready = False
        self.suppressed: set[str] = set()
        self.copied: set[str] = set()
        self._pending: str | None = None
        self._count = 0
        self._started_ns = 0
        self._last_sequence = -1
        self._last_capture_ns = -1
        self._recognized_ns = 0
        self.validation_ms = 0.0

    @property
    def first_observed_ns(self) -> int | None:
        return self._started_ns if self._pending is not None else None

    @property
    def first_recognized_ns(self) -> int | None:
        return self._recognized_ns if self._pending is not None else None

    def reset_pending(self) -> None:
        self._pending = None
        self._count = 0

    def learn_baseline(self, lines: list[TextLine]) -> None:
        if self.armed:
            raise RuntimeError("Disarm before learning a baseline")
        self.suppressed.update(
            code for line in lines if (code := code_text(line, self.config.profile))
        )
        self.baseline_ready = True
        self.reset_pending()

    def arm(self) -> None:
        if not self.baseline_ready:
            raise RuntimeError("A disarmed baseline is required before arming")
        self.reset_pending()
        self.armed = True

    def disarm(self) -> None:
        self.armed = False
        self.reset_pending()

    def observe(
        self, lines: list[TextLine], sequence: int, captured_ns: int, now_ns: int
    ) -> tuple[str, str | None]:
        self.validation_ms = 0.0
        if sequence <= self._last_sequence or captured_ns <= self._last_capture_ns:
            self.reset_pending()
            return "out_of_order", None
        self._last_sequence, self._last_capture_ns = sequence, captured_ns
        age_ms = (now_ns - captured_ns) / 1e6
        if age_ms < 0 or age_ms > self.config.max_frame_age_ms:
            self.reset_pending()
            return "stale", None
        if not self.armed:
            self.reset_pending()
            return "disarmed", None
        validation_started = perf_counter_ns()
        validated = candidates(lines, self.config)
        self.validation_ms = (perf_counter_ns() - validation_started) / 1e6
        eligible = [
            code for code in validated if code not in self.suppressed and code not in self.copied
        ]
        if len(eligible) != 1:
            self.reset_pending()
            return ("ambiguous" if len(eligible) > 1 else "no_candidate"), None
        code = eligible[0]
        expired = (captured_ns - self._started_ns) / 1e6 > self.config.confirmation_window_ms
        if code != self._pending or expired:
            self._pending, self._count, self._started_ns = code, 0, captured_ns
            self._recognized_ns = now_ns
        self._count += 1
        if self._count < self.config.confirmations:
            return "confirming", None
        return "ready", code

    def committed(self, code: str) -> None:
        self.copied.add(code)
        self.disarm()  # One successful copy per explicit arm.
