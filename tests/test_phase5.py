import numpy as np
import pytest

from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect, TextLine
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig


def test_control_delay_cannot_allow_an_expired_frame_to_write():
    now = [100_000_000]

    class Recognizer:
        def recognize(self, pixels):
            return [
                TextLine("AB23CD45EF", 0.99, Rect(0, 0, 150, 20)),
                TextLine("100% off", 0.99, Rect(0, 30, 150, 50)),
            ]

    def delayed_control_check():
        now[0] += 1_100_000_000
        return True

    policy = DecisionPolicy(PolicyConfig(confirmations=1))
    policy.learn_baseline([])
    policy.arm()
    memory = MemoryClipboard()
    pipeline = Pipeline(
        Recognizer(),
        memory,
        Rect(0, 0, 150, 60),
        policy,
        clock=lambda: now[0],
        before_decision=delayed_control_check,
    )
    result = pipeline.process(Frame(np.zeros((60, 150, 3), np.uint8), 1, now[0]))
    assert result.status == "stale"
    assert not memory.writes


def test_frame_expiring_while_waiting_for_write_lock_is_rejected(monkeypatch):
    now = [100_000_000]
    monkeypatch.setattr("stream_code_capture.live.perf_counter_ns", lambda: now[0])
    controls = Controls()
    session = LiveSession(object(), LiveConfig(Rect(0, 0, 150, 60)), controls, lambda event: None)
    session.running = True
    session.started_ns = now[0]
    controls.inhibit.clear()
    session.pipeline.copy_deadline_ns = now[0] + 1_000_000_000
    assert session.healthy()

    class DelayedLock:
        def __enter__(self):
            now[0] += 1_000_000_001

        def __exit__(self, *args):
            pass

    controls.lock = DelayedLock()
    with pytest.raises(RuntimeError, match="cancelled"):
        session.pipeline.clipboard.write("AB23CD45EF")
    assert not session.clipboard.writes


def test_deadline_is_cleared_after_clipboard_failure():
    class Recognizer:
        def recognize(self, pixels):
            return [
                TextLine("AB23CD45EF", 0.99, Rect(0, 0, 150, 20)),
                TextLine("100% off", 0.99, Rect(0, 30, 150, 50)),
            ]

    class FailedClipboard:
        def write(self, code):
            raise RuntimeError("busy")

    policy = DecisionPolicy(PolicyConfig(confirmations=1))
    policy.learn_baseline([])
    policy.arm()
    pipeline = Pipeline(
        Recognizer(), FailedClipboard(), Rect(0, 0, 150, 60), policy, clock=lambda: 100
    )
    result = pipeline.process(Frame(np.zeros((60, 150, 3), np.uint8), 1, 100))
    assert result.status == "clipboard_failed"
    assert pipeline.copy_deadline_ns is None
    assert not policy.armed and not policy.copied
