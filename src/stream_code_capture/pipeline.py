"""Synchronous single-consumer pipeline; callers provide the newest available frame."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Protocol

from .domain import (
    Clipboard,
    Frame,
    RecognitionProfile,
    Recognizer,
    Rect,
    TextLine,
    TimedRecognizer,
)
from .policy import DecisionPolicy


class Clock(Protocol):
    def __call__(self) -> int: ...


@dataclass(frozen=True)
class Outcome:
    sequence: int
    status: str
    code: str | None
    candidates: list[str]
    lines: list[TextLine]
    timings_ms: dict[str, float]
    error: str | None = None
    captured_ns: int = 0
    completed_ns: int = 0
    recognized_ns: int = 0
    ocr_profile: RecognitionProfile | None = None


class Pipeline:
    def __init__(
        self,
        recognizer: Recognizer,
        clipboard: Clipboard,
        roi: Rect,
        policy: DecisionPolicy | None = None,
        clock: Clock = perf_counter_ns,
        before_decision: Callable[[], bool] | None = None,
        copy_roi: bool = True,
    ) -> None:
        self.recognizer, self.clipboard, self.roi = recognizer, clipboard, roi
        self.policy = policy if policy is not None else DecisionPolicy()
        self.clock = clock
        self.before_decision = before_decision
        self.copy_roi = copy_roi
        self.copy_deadline_ns: int | None = None

    def baseline(self, frame: Frame) -> None:
        self.policy.learn_baseline(self.recognizer.recognize(self.roi.crop(frame.image)))

    def process(self, frame: Frame) -> Outcome:
        start = self.clock()
        age = (start - frame.captured_ns) / 1e6
        if age < 0 or age > self.policy.config.max_frame_age_ms:
            status, _ = self.policy.observe([], frame.sequence, frame.captured_ns, start)
            return Outcome(
                frame.sequence,
                status,
                None,
                [],
                [],
                {
                    "capture": frame.capture_ms,
                    "queue_age": age,
                    "handoff": (start - (frame.delivered_ns or frame.captured_ns)) / 1e6,
                    "frame_to_result": age,
                    "process": (self.clock() - start) / 1e6,
                },
                captured_ns=frame.captured_ns,
                completed_ns=self.clock(),
            )
        cropped = self.roi.crop(frame.image, copy=self.copy_roi)
        prepared = self.clock()
        ocr_profile = None
        try:
            if isinstance(self.recognizer, TimedRecognizer):
                recognition = self.recognizer.recognize_timed(cropped)
                lines, stages = recognition.lines, recognition.timings_ms
                ocr_profile = recognition.profile
            else:
                lines = self.recognizer.recognize(cropped)
                stages = {"ocr": (self.clock() - prepared) / 1e6, "preprocess": 0.0}
        except Exception:
            self.policy.disarm()
            raise
        recognized = self.clock()
        if self.before_decision is not None and not self.before_decision():
            self.policy.disarm()
        controlled = self.clock()
        status, code = self.policy.observe(lines, frame.sequence, frame.captured_ns, controlled)
        decided = self.clock()
        error = None
        if code is not None:
            self.copy_deadline_ns = frame.captured_ns + int(
                self.policy.config.max_frame_age_ms * 1e6
            )
            try:
                if self.clock() > self.copy_deadline_ns:
                    status, code = "stale", None
                else:
                    self.clipboard.write(code)
            except Exception as exc:
                # Do not mark copied on failure. Require explicit rearm before another attempt.
                self.policy.disarm()
                status, error = "clipboard_failed", str(exc)
            else:
                if code is not None:
                    self.policy.committed(code)
                    status = "copied"
            finally:
                self.copy_deadline_ns = None
        finished = self.clock()
        timings = {
            "capture": frame.capture_ms,
            "handoff": (start - (frame.delivered_ns or frame.captured_ns)) / 1e6,
            "queue_age": (start - frame.captured_ns) / 1e6,
            "queue_wait": ((frame.dequeued_ns or start) - (frame.delivered_ns or frame.captured_ns))
            / 1e6,
            "frame_age_at_dequeue": ((frame.dequeued_ns or start) - frame.captured_ns) / 1e6,
            "crop": (prepared - start) / 1e6,
            "recognition": (recognized - prepared) / 1e6,
            "policy": (decided - recognized) / 1e6,
            "decision": (decided - recognized) / 1e6,
            "control_check": (controlled - recognized) / 1e6,
            "candidate_validation": self.policy.validation_ms,
            "confirmation_dedup": max(
                0.0, (decided - controlled) / 1e6 - self.policy.validation_ms
            ),
            "clipboard": (finished - decided) / 1e6 if code else 0,
            "process": (finished - start) / 1e6,
            "frame_to_result": (finished - frame.captured_ns) / 1e6,
            **stages,
        }
        if status == "copied":
            timings["first_observed_to_clipboard"] = (finished - frame.captured_ns) / 1e6
            timings["first_recognition_to_confirmation"] = (decided - recognized) / 1e6
        return Outcome(
            frame.sequence,
            status,
            code,
            self.policy.last_candidates,
            lines,
            timings,
            error,
            frame.captured_ns,
            finished,
            recognized,
            ocr_profile,
        )
