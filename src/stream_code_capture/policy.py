"""Exact-string eligibility and one-shot clipboard policy."""

import math
import re
from dataclasses import dataclass
from time import perf_counter_ns

from .domain import Rect, TextLine

DEFAULT_FRAME_AGE_MS = 3000
MIN_CODE_PITCH = 10
CODE = re.compile(r"(?=.{6,24}\Z)(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]+", re.ASCII)
GAME_CODE = re.compile(
    r"(?=.{6,24}\Z)(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", re.ASCII
)
DISCOUNT_OFFER = re.compile(r"\b(?:100|[1-9][0-9]?)\s*%\s*off\b", re.I)
PROMO_CODE = r"(?:discount|promo(?:tional)?|coupon|use|redemption|redeem)\s+code"
CODE_LABEL = re.compile(
    rf"(?:(?:{PROMO_CODE}|code|redeem)\s*[:：]|(?:{PROMO_CODE})\s+)", re.I | re.ASCII
)
CODE_HEADING = re.compile(rf"(?:{PROMO_CODE}|code\s*[:：])(?:\s*[:：])?", re.I | re.ASCII)
LIMITED_OFFER = re.compile(r"limited[\s-]+time\s+offer", re.I | re.ASCII)
GAME_CONTEXT = re.compile(r"expiry\s*date|redemption\s*code|有効期限|有效期至|兑换码|兌換碼", re.I)
EMBEDDED_DIGITS = re.compile(r"[A-Za-z][0-9-]*[0-9][0-9-]*[A-Za-z]")


@dataclass(frozen=True)
class PolicyConfig:
    min_confidence: float = 0.96
    max_frame_age_ms: float = DEFAULT_FRAME_AGE_MS
    profile: str = "discount"

    def __post_init__(self) -> None:
        if self.profile not in {"discount", "game"}:
            raise ValueError("Detection profile must be discount or game")
        if not math.isfinite(self.min_confidence) or not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be between zero and one")
        if not math.isfinite(self.max_frame_age_ms) or self.max_frame_age_ms <= 0:
            raise ValueError("frame age limit must be finite and positive")


def extract_code(text: str, profile: str) -> str | None:
    text = text.strip()
    label = CODE_LABEL.match(text)
    token = text[label.end() :].strip() if label else text
    pattern = GAME_CODE if profile == "game" else CODE
    return token if pattern.fullmatch(token) else None


def discount_code(text: str) -> str | None:
    return extract_code(text, "discount")


def code_text(line: TextLine, profile: str = "discount") -> str | None:
    return extract_code(line.text, profile)


def context_near(code: Rect, context: Rect, height: int, *, stacked_offer: bool) -> bool:
    x_gap = max(context.left - code.right, code.left - context.right)
    y_gap = max(context.top - code.bottom, code.top - context.bottom)
    # Permit nearby headings in any direction and percentage offers after product rows.
    return x_gap <= height * 4 and (
        y_gap <= height * 3
        or (stacked_offer and x_gap < 0 and 0 <= context.top - code.bottom <= height * 10)
    )


def context_kind(text: str, profile: str) -> str | None:
    text = text.strip()
    if CODE_HEADING.fullmatch(text):
        return "code heading"
    if profile == "game" and GAME_CONTEXT.search(text):
        return "redemption"
    if DISCOUNT_OFFER.search(text):
        return "percent"
    return "limited" if LIMITED_OFFER.fullmatch(text) else None


def assess_candidate(
    line: TextLine, lines: list[TextLine], config: PolicyConfig
) -> tuple[str | None, str]:
    """Evaluate one OCR line and report the same gate used for actual decisions."""
    if line.rejection:
        return None, line.rejection
    code = code_text(line, config.profile)
    if code is None:
        return None, "unsupported exact code format"
    if not config.min_confidence <= line.confidence <= 1:
        return None, "code confidence outside required range"

    text = line.text.strip()
    labelled = CODE_LABEL.match(text) is not None
    if line.box.right - line.box.left < MIN_CODE_PITCH * len(text):
        return None, "code box below minimum source pitch"
    if labelled:
        return code, "eligible candidate with code label"

    height = max(1, line.box.bottom - line.box.top)
    for context in lines:
        if context is line or context.rejection or not 0.75 <= context.confidence <= 1:
            continue
        kind = context_kind(context.text, config.profile)
        if kind is not None and context_near(
            line.box, context.box, height, stacked_offer=kind == "percent"
        ):
            return code, "eligible candidate with nearby context"

    if (
        len(code) >= 8
        and sum("0" <= glyph <= "9" for glyph in code) >= 2
        and EMBEDDED_DIGITS.search(code)
    ):
        return code, "eligible standalone candidate"
    return None, "short or word-like token needs code or offer context"


def candidates(lines: list[TextLine], config: PolicyConfig) -> list[str]:
    return sorted({code for line in lines if (code := assess_candidate(line, lines, config)[0])})


class DecisionPolicy:
    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config if config is not None else PolicyConfig()
        self.armed = False
        self.baseline_ready = False
        self.suppressed: set[str] = set()
        self.copied: set[str] = set()
        self.last_candidates: list[str] = []
        self._last_sequence = -1
        self._last_capture_ns = -1
        self.validation_ms = 0.0

    def learn_baseline(self, lines: list[TextLine]) -> None:
        if self.armed:
            raise RuntimeError("Disarm before learning a baseline")
        self.suppressed.update(
            code for line in lines if (code := code_text(line, self.config.profile))
        )
        self.baseline_ready = True

    def arm(self) -> None:
        if not self.baseline_ready:
            raise RuntimeError("A disarmed baseline is required before arming")
        self.armed = True

    def disarm(self) -> None:
        self.armed = False

    def observe(
        self, lines: list[TextLine], sequence: int, captured_ns: int, now_ns: int
    ) -> tuple[str, str | None]:
        self.validation_ms = 0.0
        self.last_candidates = []
        if sequence <= self._last_sequence or captured_ns <= self._last_capture_ns:
            return "out_of_order", None
        self._last_sequence, self._last_capture_ns = sequence, captured_ns
        if not 0 <= (now_ns - captured_ns) / 1e6 <= self.config.max_frame_age_ms:
            return "stale", None

        validation_started = perf_counter_ns()
        self.last_candidates = candidates(lines, self.config)
        self.validation_ms = (perf_counter_ns() - validation_started) / 1e6
        if not self.armed:
            return "disarmed", None
        eligible = [
            code
            for code in self.last_candidates
            if code not in self.suppressed and code not in self.copied
        ]
        if len(eligible) != 1:
            return ("ambiguous" if eligible else "no_candidate"), None
        return "ready", eligible[0]

    def committed(self, code: str) -> None:
        self.copied.add(code)
        self.disarm()
