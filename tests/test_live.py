from threading import Event, Thread
from time import monotonic, perf_counter_ns, sleep

import numpy as np
import pytest

from stream_code_capture.capture import CaptureWorker
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect, TextLine
from stream_code_capture.live import Controls, GuardedClipboard, LiveConfig, LiveSession
from stream_code_capture.metrics import Metrics
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy


class Recognizer:
    def warmup(self):
        pass

    def recognize(self, image):
        return [
            TextLine("AB23CD45EF", 0.999, Rect(0, 0, 140, 20)),
            TextLine("100% off", 0.99, Rect(0, 30, 140, 50)),
        ]


@pytest.mark.parametrize("command", ["stop", "disarm"])
def test_control_during_ocr_prevents_clipboard_write(command):
    entered, resume = Event(), Event()

    class SlowRecognizer(Recognizer):
        def recognize(self, image):
            entered.set()
            assert resume.wait(2)
            return super().recognize(image)

    controls, target = Controls(), MemoryClipboard()
    controls.inhibit.clear()
    policy = DecisionPolicy()
    policy.learn_baseline([])
    policy.arm()
    pipeline = Pipeline(
        SlowRecognizer(),
        GuardedClipboard(target, controls, lambda: True),
        Rect(0, 0, 150, 60),
        policy,
        before_decision=lambda: not controls.inhibit.is_set(),
    )
    result = []
    worker = Thread(
        target=lambda: result.append(
            pipeline.process(Frame(np.zeros((60, 150, 3), np.uint8), 1, perf_counter_ns()))
        )
    )
    worker.start()
    assert entered.wait(2)
    controls.send(command)
    resume.set()
    worker.join(2)
    assert not worker.is_alive()
    assert result[0].status == "disarmed" and not target.writes


def test_dry_run_ignores_native_target_and_requires_ready():
    target, controls, events = MemoryClipboard(), Controls(), []
    session = LiveSession(
        Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), controls, events.append, clipboard=target
    )
    controls.send("arm")
    session.handle_commands()
    assert events[-1]["event"] == "arm_rejected"
    session.clipboard.write("EXAMPLE23")
    assert not target.writes


def test_capture_newest_and_cleanup_under_slow_consumer():
    closed, enough = Event(), Event()

    class Source:
        def __init__(self):
            self.count = 0

        def grab(self):
            self.count += 1
            if self.count == 20:
                enough.set()
            return np.full((10, 10, 3), self.count % 255, np.uint8)

        def close(self):
            closed.set()

    worker = CaptureWorker(Source, fps=240)
    worker.start()
    assert enough.wait(2)
    worker.stop()
    latest = worker.latest.take()
    assert latest.sequence == worker.captured
    assert worker.latest.dropped == worker.captured - 1
    assert worker.latest.take() is None and closed.is_set()


def test_capture_failure_is_reported_and_disarms():
    def failed():
        raise RuntimeError("access lost")

    controls, events = Controls(), []
    worker = CaptureWorker(failed)
    session = LiveSession(
        Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), controls, events.append, worker=worker
    )
    controls.send("start")
    assert session.run(duration=2) == 1
    assert "access lost" in session.failure
    assert not session.policy.armed and controls.inhibit.is_set()


def test_identical_roi_frames_do_not_confirm_reused_pixels():
    enough = Event()

    class StaticSource:
        calls = 0

        def grab(self):
            self.calls += 1
            if self.calls == 10:
                enough.set()
            return np.zeros((10, 10, 3), np.uint8)

        def close(self):
            pass

    worker = CaptureWorker(StaticSource, fps=240)
    worker.start()
    assert enough.wait(2)
    worker.stop()
    assert worker.captured == 1 and worker.duplicates >= 9


def test_baseline_requires_multiple_observations_and_half_second():
    controls, events = Controls(), []
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), controls, events.append)
    session.running = True
    session.started_ns = perf_counter_ns()
    pixels = np.indices((60, 150)).sum(axis=0).astype(np.uint8)
    pixels = np.repeat(pixels[:, :, None], 3, axis=2)
    now = perf_counter_ns()
    session.consume(Frame(pixels, 1, now - 600_000_000))
    assert not session.ready
    session.consume(Frame(pixels, 2, now - 200_000_000))
    assert not session.ready
    session.consume(Frame(pixels, 3, now))
    assert session.ready and session.policy.suppressed == {"AB23CD45EF"}
    controls.send("arm")
    session.handle_commands()
    session.consume(Frame(pixels, 4, perf_counter_ns()))
    assert not session.clipboard.writes  # Persistent code is not a new arrival.


def test_frame_captured_before_arm_cannot_copy():
    controls, events = Controls(), []
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), controls, events.append)
    session.running = session.ready = True
    session.started_ns = perf_counter_ns()
    session.policy.learn_baseline([])
    pixels = np.indices((60, 150)).sum(axis=0).astype(np.uint8)
    pixels = np.repeat(pixels[:, :, None], 3, axis=2)
    pending = Frame(pixels, 1, perf_counter_ns())
    controls.send("arm")
    session.handle_commands()
    session.consume(pending)
    assert session.policy.armed and session.clipboard.writes == []
    with pytest.raises(RuntimeError, match="Blank"):
        session.consume(Frame(np.zeros_like(pixels), 1, pending.captured_ns))
    session.consume(Frame(pixels, 2, perf_counter_ns()))
    assert not session.policy.armed and session.clipboard.writes == ["AB23CD45EF"]


def test_saturation_cannot_drop_stop_or_disarm_inhibition():
    controls = Controls()
    controls.inhibit.clear()
    for _ in range(16):
        controls.send("status")
    controls.send("disarm")
    controls.send("stop")
    assert controls.inhibit.is_set() and controls.stop.is_set()


def test_guard_blocks_source_failure_after_policy_decision():
    target, controls = MemoryClipboard(), Controls()
    controls.inhibit.clear()
    with pytest.raises(RuntimeError, match="cancelled"):
        GuardedClipboard(target, controls, lambda: False).write("AB23CD45EF")
    assert not target.writes


def test_metrics_are_bounded_and_percentiles_are_defined():
    metrics = Metrics(limit=3)
    for value in range(5):
        metrics.add({"ocr": value})
    result = metrics.summary()["ocr"]
    assert result["count"] == 3 and result["p50_ms"] == 3 and result["p95_ms"] == 3.9


def test_blank_capture_fails_closed():
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), Controls(), lambda e: None)
    with pytest.raises(RuntimeError, match="Blank"):
        session.consume(Frame(np.zeros((60, 150, 3), np.uint8), 1, perf_counter_ns()))


def test_duration_deadline_inhibits_inflight_write():
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), Controls(), lambda e: None)
    session.running = True
    session.started_ns = perf_counter_ns()
    session.controls.inhibit.clear()
    session.deadline_ns = perf_counter_ns() - 1
    assert not session.before_decision()


def test_capture_initialization_has_separate_deadline_from_running_stall():
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 150, 60)), Controls(), lambda e: None)
    session.running = True
    now = perf_counter_ns()
    session.started_ns = now - 3_000_000_000
    assert session.healthy()  # Still within bounded 10-second initialization allowance.
    session.worker.ready_ns = now
    session.worker.started.set()
    assert session.healthy()
    session.worker.ready_ns = now - 3_000_000_000
    assert not session.healthy()  # A capture poll that never returns still fails closed.


@pytest.mark.parametrize("scenario", ["resume", "interrupt", "disarm", "stop"])
def test_armed_session_with_static_source(scenario):
    roi = Rect(0, 0, 150, 60)
    controls, events, outcomes = Controls(), [], []
    paused, resumed, interrupted, closed = Event(), Event(), Event(), Event()

    class Source:
        tick = 0
        previous = np.zeros((60, 150, 3), np.uint8)
        idle_polls = 0

        def grab(self):
            if interrupted.is_set():
                raise RuntimeError("Selected monitor access lost")
            if paused.is_set() and not resumed.is_set():
                self.idle_polls += 1
                # Both DXGI idle outcomes: no desktop update, or an identical ROI.
                return None if self.idle_polls % 2 else self.previous.copy()
            self.tick += 1
            pixels = np.full((60, 150, 3), 120, np.uint8)
            pixels[:16] = 255
            pixels[0, 0] = self.tick % 255
            pixels[32, 32] = int(resumed.is_set())
            self.previous = pixels
            return pixels

        def close(self):
            closed.set()

    class PausableRecognizer(Recognizer):
        def recognize(self, image):
            return super().recognize(image) if image[32, 32, 0] else []

    source = Source()
    worker = CaptureWorker(lambda: source, fps=30)
    session = LiveSession(PausableRecognizer(), LiveConfig(roi), controls, events.append, worker)
    assert isinstance(session.clipboard, MemoryClipboard)

    def wait_for(predicate):
        deadline = monotonic() + 5
        while not predicate() and monotonic() < deadline:
            sleep(0.01)
        assert predicate(), session.failure

    controls.send("start")
    thread = Thread(target=lambda: outcomes.append(session.run()))
    thread.start()
    try:
        wait_for(lambda: any(e["event"] == "ready" for e in events))
        controls.send("arm")
        wait_for(lambda: any(e["event"] == "armed" for e in events))
        paused.set()
        wait_for(lambda: source.idle_polls >= 3)
        frame_count = worker.captured
        if scenario == "resume":
            # Actual elapsed time past the watchdog threshold, with no new observations.
            assert not closed.wait(30)
            assert worker.captured == frame_count and worker.duplicates > 0
            assert session.clipboard.writes == []
            controls.send("status")
            wait_for(lambda: any(e["event"] == "status" and e["armed"] for e in events))
            resumed.set()
            wait_for(lambda: session.clipboard.writes == ["AB23CD45EF"])
            assert sum(e["event"] == "armed" for e in events) == 1
        elif scenario == "interrupt":
            interrupted.set()
            wait_for(lambda: bool(outcomes))
            assert outcomes == [1]
            assert "Selected monitor access lost" in (session.failure or "")
            assert not session.policy.armed and session.clipboard.writes == []
        elif scenario == "disarm":
            controls.send("disarm")
            wait_for(lambda: any(e["event"] == "disarmed" for e in events))
            assert not session.policy.armed and worker.captured == frame_count
            resumed.set()
            wait_for(lambda: worker.captured >= frame_count + 3)
            assert session.clipboard.writes == []
        else:
            controls.send("stop")
            wait_for(lambda: bool(outcomes))
            assert worker.captured == frame_count and session.clipboard.writes == []
    finally:
        controls.send("stop")
        thread.join(5)
    assert not thread.is_alive() and closed.is_set()
    assert outcomes == [int(scenario == "interrupt")]
