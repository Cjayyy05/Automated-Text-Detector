import random
import socket
from pathlib import Path
from threading import Thread
from time import perf_counter_ns

import cv2
import numpy as np
import pytest

from stream_code_capture.activity import ActivityGate
from stream_code_capture.cli import main
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Recognition, Rect, TextLine
from stream_code_capture.latest import LatestFrame
from stream_code_capture.ocr import RapidRecognizer, needs_fallback
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig, candidates
from stream_code_capture.synthetic import chart_frame, make_code


def test_stale_frame_never_enters_expensive_ocr_and_clears_confirmation():
    class NeverRun:
        def recognize(self, image):
            raise AssertionError("Stale pixels reached OCR")

    policy = DecisionPolicy(PolicyConfig(confirmations=2, max_frame_age_ms=50))
    policy.learn_baseline([])
    policy.arm()
    lines = [
        TextLine("AB23CD45EF", 0.99, Rect(0, 0, 150, 20)),
        TextLine("100% off", 0.99, Rect(0, 30, 100, 50)),
    ]
    assert policy.observe(lines, 1, 1, 2)[0] == "confirming"
    clipboard = MemoryClipboard()
    pipeline = Pipeline(
        NeverRun(), clipboard, Rect(0, 0, 10, 10), policy, clock=lambda: 100_000_000
    )
    result = pipeline.process(Frame(np.zeros((10, 10, 3), np.uint8), 2, 3))
    assert result.status == "stale" and not clipboard.writes
    assert policy.first_observed_ns is None and "ocr" not in result.timings_ms


def test_latest_wait_wakes_on_publication_without_queueing():
    slot, outcomes = LatestFrame(), []
    consumer = Thread(target=lambda: outcomes.append(slot.wait(1)))
    consumer.start()
    slot.publish(Frame(np.zeros((3, 3, 3), np.uint8), 1, perf_counter_ns()))
    consumer.join(1)
    assert not consumer.is_alive() and outcomes[0].sequence == 1
    assert slot.take() is None


def test_activity_background_motion_and_colored_text_cannot_defer_deadline():
    gate = ActivityGate(100)
    for index in range(20):
        pixels = np.full((30, 40, 3), (20, 40 + index, 200), np.uint8)
        assert gate.should_scan(pixels, index * 10_000_000) == (index in {0, 10})


def test_activity_detects_small_new_neutral_text_and_does_not_delay_confirmation():
    gate, pixels = ActivityGate(100), np.zeros((30, 40, 3), np.uint8)
    assert gate.should_scan(pixels, 0)
    assert not gate.should_scan(pixels, 1)
    pixels[5:10, 5:10] = 240
    assert gate.should_scan(pixels, 2)
    assert gate.should_scan(pixels, 3, confirming=True)


@pytest.mark.parametrize("value", [0, -1, 1001, float("inf"), float("nan")])
def test_activity_invalid_deadlines_fail(value):
    with pytest.raises(ValueError):
        ActivityGate(value)


def test_fallback_never_overrides_quality_rejection_or_invents_confidence():
    class ForbiddenFallback:
        def recognize_timed(self, image):
            raise AssertionError("Quality guard was bypassed")

    lines = [
        TextLine("AB23CD450F", 0.999, Rect(0, 0, 150, 20), "unresolved_O0_glyph"),
        TextLine("100% off", 0.99, Rect(0, 30, 100, 50)),
    ]
    recognizer = RapidRecognizer.__new__(RapidRecognizer)
    recognizer._recognize_once = lambda image: Recognition(lines, {"ocr": 1})
    recognizer._fallback = ForbiddenFallback()
    assert recognizer.recognize_timed(np.zeros((60, 150, 3), np.uint8)).lines == lines
    assert not needs_fallback([])
    assert needs_fallback([TextLine("100% off", 0.99, Rect(0, 30, 100, 50))])


def test_full_owned_roi_can_be_borrowed_without_copy():
    class ReadOnlyRecognizer:
        def recognize(self, image):
            assert np.shares_memory(image, pixels)
            assert not image.flags.writeable
            return []

    pixels = np.zeros((20, 30, 3), np.uint8)
    pixels.flags.writeable = False
    pipeline = Pipeline(ReadOnlyRecognizer(), MemoryClipboard(), Rect(0, 0, 30, 20), copy_roi=False)
    result = pipeline.process(Frame(pixels, 1, perf_counter_ns()))
    assert result.status == "disarmed"


def test_queue_wait_excludes_live_validation_work_before_ocr():
    class EmptyRecognizer:
        def recognize(self, image):
            return []

    pipeline = Pipeline(
        EmptyRecognizer(), MemoryClipboard(), Rect(0, 0, 3, 3), clock=lambda: 3_000_000
    )
    result = pipeline.process(
        Frame(
            np.zeros((3, 3, 3), np.uint8), 1, 100_000, delivered_ns=500_000, dequeued_ns=2_000_000
        )
    )
    assert result.timings_ms["queue_wait"] == 1.5
    assert result.timings_ms["handoff"] == 2.5
    assert result.timings_ms["frame_age_at_dequeue"] == 1.9


@pytest.mark.parametrize("profile", ["tiny", "v4"])
def test_unverified_experimental_profiles_cannot_write_native_clipboard(profile):
    assert (
        main(
            [
                "live",
                "--roi",
                "0",
                "0",
                "100",
                "100",
                "--clipboard",
                "windows",
                "--model-profile",
                profile,
            ]
        )
        == 2
    )


@pytest.mark.ocr
def test_large_high_confidence_O0_regression_is_an_explicit_abstention():
    # First new corpus event exposed a wrong O->0 copy even above the pitch floor.
    code = make_code(random.Random(20261030), challenge=True)
    image = chart_frame(code, tick=1, visible=True, seed=20261030, angle_limit=6)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    pixels = Rect(70, 160, 610, 325).crop(cv2.imdecode(encoded, cv2.IMREAD_COLOR))
    recognizer = RapidRecognizer()
    recognizer.warmup()
    lines = recognizer.recognize(pixels)
    assert any(line.rejection == "unresolved_O0_glyph" for line in lines)
    assert candidates(lines, PolicyConfig()) == []


@pytest.mark.ocr
def test_optional_tiny_model_is_offline_and_does_not_mutate_borrowed_pixels(monkeypatch):
    if not (Path(__file__).resolve().parents[1] / "models/PP-OCRv6_rec_tiny.onnx").is_file():
        pytest.skip("Run scripts/provision_models.py to provision optional local models")

    def forbidden(*args, **kwargs):
        raise AssertionError("Network access during local inference")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    recognizer = RapidRecognizer(
        model_profile="tiny",
        scale=1,
        threads=4,
        cpu_arena=True,
        allow_spinning=False,
        profile_inference=True,
    )
    recognizer.warmup()
    image = chart_frame("AB23CD45EF", tick=1, visible=True, seed=7)
    pixels = Rect(70, 160, 610, 325).crop(image, copy=False)
    before = pixels.copy()
    pixels.flags.writeable = False
    result = recognizer.recognize_timed(pixels)
    assert np.array_equal(pixels, before)
    assert candidates(result.lines, PolicyConfig()) == ["AB23CD45EF"]
    assert result.timings_ms["text_det_inference"] > 0
    assert result.timings_ms["text_rec_inference"] > 0


@pytest.mark.ocr
def test_omitted_leading_glyph_is_vetoed_using_independent_pixel_recognition():
    if not (Path(__file__).resolve().parents[1] / "models/PP-OCRv6_rec_tiny.onnx").is_file():
        pytest.skip("Provision optional local models")
    rng = random.Random(20261101)
    for _ in range(21):
        code = make_code(rng, challenge=True)
    image = chart_frame(code, tick=1, visible=True, seed=20261121, angle_limit=6)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 50])
    assert ok
    pixels = Rect(70, 160, 610, 325).crop(cv2.imdecode(encoded, cv2.IMREAD_COLOR))
    recognizer = RapidRecognizer(
        model_profile="tiny",
        scale=1,
        threads=4,
        cpu_arena=True,
        det_limit=640,
        allow_spinning=False,
        fallback_baseline=True,
    )
    recognizer.warmup()
    result = recognizer.recognize_timed(pixels)
    assert candidates(result.lines, PolicyConfig()) == []
    assert any(
        line.verification_text == code
        and line.text != code
        and line.rejection == "verification_disagreement"
        for line in result.lines
    )
    assert result.timings_ms["verification"] > 0
