from time import perf_counter_ns

import numpy as np
import pytest

from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect, TextLine
from stream_code_capture.latest import LatestFrame
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig


class StubRecognizer:
    def __init__(self):
        self.inputs = []
        self.lines = []

    def warmup(self):
        pass

    def recognize(self, image):
        self.inputs.append(image)
        return self.lines


def test_roi_is_cropped_before_recognition_and_mock_clipboard_is_one_shot():
    recognizer, clipboard = StubRecognizer(), MemoryClipboard()
    pixels = np.arange(120 * 200 * 3, dtype=np.uint8).reshape(120, 200, 3)
    policy = DecisionPolicy(PolicyConfig(confirmations=2))
    pipeline = Pipeline(recognizer, clipboard, Rect(20, 30, 180, 110), policy, lambda: 100)
    pipeline.baseline(Frame(pixels, 0, 0))
    policy.arm()
    recognizer.lines = [
        TextLine("AB23CD45EF", 0.99, Rect(5, 5, 140, 20)),
        TextLine("100% off", 0.99, Rect(5, 40, 140, 60)),
    ]
    assert pipeline.process(Frame(pixels, 1, 10)).status == "confirming"
    assert pipeline.process(Frame(pixels, 2, 20)).status == "copied"
    assert pipeline.process(Frame(pixels, 3, 30)).status == "disarmed"
    assert clipboard.writes == ["AB23CD45EF"]
    assert np.array_equal(recognizer.inputs[0], pixels[30:110, 20:180])
    assert not np.shares_memory(recognizer.inputs[0], pixels)


def test_clipboard_failure_does_not_commit_or_retry_unarmed():
    class BusyClipboard:
        calls = 0

        def write(self, text):
            self.calls += 1
            raise OSError("clipboard busy")

    recognizer, clipboard = StubRecognizer(), BusyClipboard()
    policy = DecisionPolicy(PolicyConfig(confirmations=1))
    policy.learn_baseline([])
    policy.arm()
    recognizer.lines = [
        TextLine("AB23CD45EF", 0.99, Rect(5, 5, 80, 15)),
        TextLine("100% off", 0.99, Rect(5, 25, 80, 35)),
    ]
    pipeline = Pipeline(recognizer, clipboard, Rect(0, 0, 100, 100), policy, lambda: 100)
    pixels = np.zeros((100, 100, 3), np.uint8)
    result = pipeline.process(Frame(pixels, 1, 1))
    assert result.status == "clipboard_failed"
    assert result.error == "clipboard busy"
    assert not policy.copied and not policy.armed
    pipeline.process(Frame(pixels, 2, 2))
    assert clipboard.calls == 1


def test_recognition_exception_disarms():
    class BrokenRecognizer(StubRecognizer):
        def recognize(self, image):
            raise RuntimeError("inference failure")

    policy = DecisionPolicy()
    policy.learn_baseline([])
    policy.arm()
    pipeline = Pipeline(BrokenRecognizer(), MemoryClipboard(), Rect(0, 0, 10, 10), policy)
    with pytest.raises(RuntimeError, match="inference"):
        pipeline.process(Frame(np.zeros((10, 10, 3), np.uint8), 1, perf_counter_ns()))
    assert not policy.armed


@pytest.mark.parametrize("roi", [Rect(-1, 0, 10, 10), Rect(0, 0, 11, 10), Rect(1, 1, 1, 5)])
def test_invalid_roi_fails(roi):
    with pytest.raises(ValueError, match="ROI"):
        roi.crop(np.zeros((10, 10, 3), np.uint8))


def test_latest_handoff_drops_old_frames_and_takes_once():
    slot = LatestFrame()
    pixels = np.zeros((10, 10, 3), np.uint8)
    for sequence in range(100):
        slot.publish(Frame(pixels, sequence, sequence))
    assert slot.dropped == 99
    assert slot.take().sequence == 99
    assert slot.take() is None
    with pytest.raises(ValueError, match="increase"):
        slot.publish(Frame(pixels, 98, 98))
