from pathlib import Path

import numpy as np

from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect, TextLine
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy


def test_confirmation_elapsed_time_is_separate_from_first_capture_age():
    class TimedInput:
        now = 100_000_000

        def recognize(self, pixels):
            self.now += 200_000_000
            return [
                TextLine("AB23CD45EF", 0.99, Rect(5, 5, 145, 25)),
                TextLine("100% off", 0.99, Rect(5, 35, 145, 55)),
            ]

    recognizer, memory, policy = TimedInput(), MemoryClipboard(), DecisionPolicy()
    policy.learn_baseline([])
    policy.arm()
    pipeline = Pipeline(recognizer, memory, Rect(0, 0, 150, 60), policy, lambda: recognizer.now)
    pixels = np.zeros((60, 150, 3), np.uint8)
    first = pipeline.process(Frame(pixels, 1, recognizer.now))
    assert first.status == "copied" and memory.writes == ["AB23CD45EF"]
    assert first.recognized_ns == 300_000_000
    assert first.timings_ms["first_recognition_to_confirmation"] == 0
    assert first.timings_ms["first_observed_to_clipboard"] == 200
    assert not policy.armed


def test_stale_exact_observation_does_not_supply_confirmation_evidence():
    policy = DecisionPolicy()
    policy.learn_baseline([])
    policy.arm()
    lines = [
        TextLine("AB23CD45EF", 0.99, Rect(5, 5, 145, 25)),
        TextLine("100% off", 0.99, Rect(5, 35, 145, 55)),
    ]
    assert policy.observe(lines, 1, 1, 3_100_000_001) == ("stale", None)
    assert policy.observe(lines, 2, 4_200_000_000, 5_500_000_000) == ("ready", "AB23CD45EF")


def test_stimulus_motion_remains_inside_roi_for_every_exposure(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from phase4_scenes import draw_motion

    region = Rect(200, 400, 960, 540)
    previous = None
    for tick in range(180):
        pixels = np.zeros((540, 960, 3), np.uint8)
        draw_motion(pixels, region, tick)
        roi = region.crop(pixels)
        assert np.count_nonzero(roi) == 8 * 2 * 3
        assert not np.any(pixels[:, : region.left])
        if previous is not None:
            assert not np.array_equal(previous, roi)
        previous = roi


def test_playback_fixtures_vary_values_and_preserve_ambiguous_cases(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from phase4_scenes import scenes

    first = scenes(20261120, 8, "game")
    again = scenes(20261120, 8, "game")
    other = scenes(20261121, 8, "game")
    assert len({code for _, code in first}) == 8
    assert [code for _, code in first] != [code for _, code in other]
    assert any("-" in code for _, code in first)
    assert sum(any(char in code for char in "O0") for _, code in first) == 2
    assert all(
        np.array_equal(a[0], b[0]) and a[1] == b[1] for a, b in zip(first, again, strict=True)
    )
