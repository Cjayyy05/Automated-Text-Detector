"""Console live session. Policy remains single-owner; urgent controls gate in-flight OCR."""

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from queue import Empty, Full, Queue
from threading import Event, Lock
from time import perf_counter_ns
from typing import Any

import numpy as np

from .activity import ActivityGate
from .capture import CaptureWorker, DxcamSource
from .clipboard import MemoryClipboard, WindowsClipboard
from .domain import Clipboard, Frame, Recognizer, Rect
from .metrics import Metrics
from .pipeline import Pipeline
from .policy import DecisionPolicy, PolicyConfig, code_text


@dataclass(frozen=True)
class LiveConfig:
    roi: Rect
    device: int = 0
    output: int = 0
    fps: int = 60
    dry_run: bool = True
    max_frame_age_ms: float = 1000
    source_timeout_ms: float = 2500
    baseline_ms: float = 500
    activity_gate_ms: float = 0
    profile: str = "discount"

    def __post_init__(self) -> None:
        PolicyConfig(profile=self.profile)
        self.roi.validate(self.roi.right, self.roi.bottom)
        if self.device < 0 or self.output < 0 or not 1 <= self.fps <= 240:
            raise ValueError("Invalid capture device, output or FPS")
        for value in (self.max_frame_age_ms, self.source_timeout_ms, self.baseline_ms):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Timing limits must be finite and positive")
        if self.baseline_ms < 500:
            raise ValueError("Live baseline must span at least 500 ms")
        if not math.isfinite(self.activity_gate_ms) or not 0 <= self.activity_gate_ms <= 1000:
            raise ValueError("Activity gate interval must be in [0, 1000] ms")


class Controls:
    def __init__(self) -> None:
        self.commands: Queue[str] = Queue(maxsize=16)
        self.stop = Event()
        self.inhibit = Event()
        self.inhibit.set()
        self.lock = Lock()
        self.generation = 0

    def send(self, command: str) -> None:
        command = command.strip().lower()
        if command not in {"start", "stop", "arm", "disarm", "status"}:
            raise ValueError("Commands: start, arm, disarm, status, stop")
        with self.lock:
            if command in {"stop", "disarm"}:
                self.generation += 1
                self.inhibit.set()
            if command == "stop":
                self.stop.set()
            try:
                self.commands.put_nowait(command)
            except Full:
                if command not in {"stop", "disarm"}:
                    raise RuntimeError("Control queue full; wait and retry") from None


class GuardedClipboard:
    def __init__(self, target: Clipboard, controls: Controls, healthy: Callable[[], bool]) -> None:
        self.target, self.controls, self.healthy = target, controls, healthy

    def write(self, text: str) -> None:
        # Linearizes disarm with write: when send(disarm) returns no later write can begin.
        with self.controls.lock:
            if self.controls.stop.is_set() or self.controls.inhibit.is_set() or not self.healthy():
                raise RuntimeError("Clipboard write cancelled by control or capture state")
            self.target.write(text)


class LiveSession:
    def __init__(
        self,
        recognizer: Recognizer,
        config: LiveConfig,
        controls: Controls,
        emit: Callable[[dict[str, Any]], None],
        worker: CaptureWorker | None = None,
        clipboard: Clipboard | None = None,
    ) -> None:
        self.recognizer, self.config, self.controls, self.emit = recognizer, config, controls, emit
        self.worker = worker or CaptureWorker(
            lambda: DxcamSource(config.roi, config.device, config.output), fps=config.fps
        )
        # Dry-run cannot be overridden with an injected native clipboard.
        self.clipboard: Clipboard = (
            MemoryClipboard()
            if config.dry_run
            else (clipboard if clipboard is not None else WindowsClipboard())
        )
        self.metrics = Metrics()
        self.activity = ActivityGate(config.activity_gate_ms) if config.activity_gate_ms else None
        self.activity_skipped = 0
        self.policy = DecisionPolicy(
            PolicyConfig(max_frame_age_ms=config.max_frame_age_ms, profile=config.profile)
        )
        self.pipeline = Pipeline(
            recognizer,
            GuardedClipboard(self.clipboard, controls, self.healthy),
            Rect(0, 0, config.roi.right - config.roi.left, config.roi.bottom - config.roi.top),
            self.policy,
            before_decision=self.before_decision,
            copy_roi=False,  # DXcam owns the published pixels; the OCR adapter never mutates them.
        )
        self.running = False
        self.ready = False
        self.started_ns = 0
        self.deadline_ns: int | None = None
        self.baseline_start_ns = 0
        self.baseline_key: frozenset[str] | None = None
        self.baseline_count = 0
        self.baseline_sequence = 0
        self.next_baseline_diagnostic_ns = 0
        self.baseline_reason = "Waiting for the first usable capture frame"
        self.active_generation = 0
        self.failure: str | None = None

    def healthy(self) -> bool:
        last = self.worker.last_capture_poll_ns or self.worker.ready_ns or self.started_ns
        timeout_ms = self.config.source_timeout_ms if self.worker.started.is_set() else 10000
        return (
            self.running
            and self.worker.error is None
            and (perf_counter_ns() - last) / 1e6 <= timeout_ms
            and (self.deadline_ns is None or perf_counter_ns() < self.deadline_ns)
            # GuardedClipboard checks this again while holding the control/write lock.
            and (
                self.pipeline.copy_deadline_ns is None
                or perf_counter_ns() <= self.pipeline.copy_deadline_ns
            )
        )

    def before_decision(self) -> bool:
        return (
            not self.controls.stop.is_set()
            and not self.controls.inhibit.is_set()
            and self.active_generation == self.controls.generation
            and self.healthy()
        )

    def handle_commands(self) -> None:
        while True:
            try:
                command = self.controls.commands.get_nowait()
            except Empty:
                break
            if command == "start" and not self.running:
                self.started_ns = perf_counter_ns()
                self.worker.start()
                self.running = True
                self.emit(
                    {
                        "event": "started",
                        "dry_run": self.config.dry_run,
                        "profile": self.config.profile,
                    }
                )
            elif command == "arm":
                with self.controls.lock:
                    if not self.ready or not self.healthy() or self.controls.stop.is_set():
                        self.emit({"event": "arm_rejected", "reason": "not ready/healthy"})
                        continue
                    self.policy.arm()
                    self.active_generation = self.controls.generation
                    self.controls.inhibit.clear()
                self.emit({"event": "armed", "dry_run": self.config.dry_run})
            elif command == "disarm":
                self.policy.disarm()
                self.emit({"event": "disarmed"})
            elif command == "status":
                self.emit(
                    {
                        "event": "status",
                        "running": self.running,
                        "ready": self.ready,
                        "armed": self.policy.armed,
                        "dropped": self.worker.latest.dropped,
                    }
                )

    def consume(self, frame: Frame) -> None:
        now = perf_counter_ns()
        if not 0 <= (now - frame.captured_ns) / 1e6 <= self.config.max_frame_age_ms:
            self.policy.reset_pending()
            self.emit({"event": "stale_before_ocr", "sequence": frame.sequence})
            return
        # Refuse nearly black/blank capture (not a DRM workaround).
        if float(np.std(frame.image[::8, ::8])) < 1:
            raise RuntimeError("Blank capture; source must be visible and unprotected")
        self.metrics.add({"input_validation": (perf_counter_ns() - now) / 1e6})
        if not self.ready:
            baseline_ocr_started = perf_counter_ns()
            self.baseline_diagnostic("Recognizing baseline pixels", force=True)
            lines = self.recognizer.recognize(frame.image)
            if not self.healthy() or self.controls.stop.is_set():
                return
            now = perf_counter_ns()
            baseline_ocr_ms = (now - baseline_ocr_started) / 1e6
            age = (now - frame.captured_ns) / 1e6
            # Baseline learning cannot trigger a copy. Slow OCR may still describe
            # current pixels if successful capture polls saw no intervening change.
            unchanged_current = (
                self.worker.captured == frame.sequence
                and self.worker.last_capture_poll_ns >= frame.captured_ns
                and 0
                <= (now - self.worker.last_capture_poll_ns) / 1e6
                <= self.config.max_frame_age_ms
            )
            if age > self.config.max_frame_age_ms and not unchanged_current:
                self.baseline_start_ns, self.baseline_count = 0, 0
                self.emit({"event": "baseline_stale"})
                self.baseline_diagnostic(
                    "Baseline expired while pixels changed. Select a smaller region.",
                    force=True,
                )
                return
            key = frozenset(
                text for line in lines if (text := code_text(line, self.config.profile))
            )
            self.policy.learn_baseline(lines)
            if key != self.baseline_key or not self.baseline_start_ns:
                self.baseline_start_ns, self.baseline_count = frame.captured_ns, 0
                self.baseline_key = key
            self.baseline_count += 1
            self.baseline_sequence = frame.sequence
            self.baseline_reason = (
                f"Baseline recognized in {baseline_ocr_ms:.0f} ms. Waiting for stable capture."
            )
            elapsed = (frame.captured_ns - self.baseline_start_ns) / 1e6
            if elapsed >= self.config.baseline_ms and self.baseline_count >= 2:
                self.ready = True
                self.emit(
                    {
                        "event": "ready",
                        "baseline_ms": elapsed,
                        "baseline_observations": self.baseline_count,
                    }
                )
            return
        if self.activity is not None:
            started = perf_counter_ns()
            scan = self.activity.should_scan(
                frame.image, started, confirming=self.policy.first_observed_ns is not None
            )
            self.metrics.add({"activity_gate": (perf_counter_ns() - started) / 1e6})
            if not scan:
                self.activity_skipped += 1
                return
        result = self.pipeline.process(frame)
        if result.status == "disarmed":
            self.policy.learn_baseline(result.lines)
        self.metrics.add(
            {
                key: value
                for key, value in result.timings_ms.items()
                if key != "clipboard" or result.code is not None
            }
        )
        payload = asdict(result)
        if self.config.dry_run and result.status == "copied":
            payload["status"] = "would_copy"
        self.emit({"event": "frame", "dry_run": self.config.dry_run, **payload})

    def baseline_diagnostic(self, reason: str | None = None, *, force: bool = False) -> None:
        if reason is not None:
            self.baseline_reason = reason
        now = perf_counter_ns()
        if not self.ready and (force or now >= self.next_baseline_diagnostic_ns):
            self.next_baseline_diagnostic_ns = now + 1_000_000_000
            self.emit(
                {
                    "event": "baseline_progress",
                    "reason": self.baseline_reason,
                    "captured": self.worker.captured,
                    "observations": self.baseline_count,
                }
            )

    def ready_from_idle_baseline(self) -> None:
        """An unchanged, healthy ROI can stabilize the learned disarmed baseline."""
        if (
            self.ready
            or not self.baseline_count
            or self.worker.captured != self.baseline_sequence
            or not self.healthy()
            or self.controls.stop.is_set()
        ):
            return
        elapsed = (self.worker.last_capture_poll_ns - self.baseline_start_ns) / 1e6
        if elapsed >= self.config.baseline_ms:
            self.ready = True
            self.emit(
                {
                    "event": "ready",
                    "baseline_ms": elapsed,
                    "baseline_observations": self.baseline_count,
                    "baseline_stability": "unchanged ROI with healthy capture polls",
                }
            )

    def run(self, duration: float | None = None) -> int:
        run_started = perf_counter_ns()
        if duration is not None:
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("duration must be finite and positive")
            self.deadline_ns = run_started + int(duration * 1e9)
        self.emit({"event": "waiting", "commands": ["start", "arm", "disarm", "status", "stop"]})
        try:
            while not self.controls.stop.is_set():
                self.handle_commands()
                if duration is not None and (perf_counter_ns() - run_started) / 1e9 >= duration:
                    break
                if not self.running:
                    self.controls.stop.wait(0.01)
                    continue
                if self.worker.error:
                    raise RuntimeError(self.worker.error)
                if not self.healthy():
                    raise RuntimeError("Capture stalled; restart and acquire a new baseline")
                waiting = perf_counter_ns()
                frame = self.worker.latest.wait()
                self.metrics.add({"frame_wait": (perf_counter_ns() - waiting) / 1e6})
                if frame is None:
                    self.ready_from_idle_baseline()
                    self.baseline_diagnostic()
                    continue
                self.consume(replace(frame, dequeued_ns=perf_counter_ns()))
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
            self.emit({"event": "error", "error": self.failure})
        finally:
            self.controls.inhibit.set()
            self.policy.disarm()
            self.ready = False
            if self.running:
                try:
                    self.worker.stop()
                except RuntimeError as exc:
                    self.failure = self.failure or str(exc)
                self.failure = self.failure or self.worker.error
            self.emit(
                {
                    "event": "summary",
                    "failure": self.failure,
                    "dry_run": self.config.dry_run,
                    "captured": self.worker.captured,
                    "capture_initialization_ms": (
                        (self.worker.ready_ns - self.started_ns) / 1e6
                        if self.worker.ready_ns
                        else None
                    ),
                    "duplicate_roi_frames": self.worker.duplicates,
                    "dropped": self.worker.latest.dropped,
                    "activity_skipped": self.activity_skipped,
                    "timings": self.metrics.summary(),
                    "capture_timings": self.worker.metrics.summary(),
                    "latency_scope": "First OCR-observed capture to clipboard; excludes any "
                    "earlier dropped code frames. Not first-visible-frame latency.",
                }
            )
        return 1 if self.failure else 0
