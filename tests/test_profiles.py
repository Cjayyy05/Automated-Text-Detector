import pytest

from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.policy import DecisionPolicy, PolicyConfig, candidates


def lines(code="AB23-CD45EF", context="Expiry Date:"):
    return [
        TextLine(code, 0.99, Rect(200, 10, 440, 40)),
        TextLine(context, 0.99, Rect(80, 10, 190, 35)),
    ]


def test_profiles_are_explicit_and_discount_remains_default():
    assert PolicyConfig().profile == "discount"
    assert candidates(lines(), PolicyConfig()) == []
    assert candidates(lines(), PolicyConfig(profile="game")) == ["AB23-CD45EF"]
    with pytest.raises(ValueError):
        PolicyConfig(profile="typo")


def test_cli_game_profile_reuses_live_and_refuses_discount_specific_cascade():
    from stream_code_capture.cli import parser, recognizer_from_args
    from stream_code_capture.live import Controls, LiveConfig, LiveSession

    args = parser().parse_args(
        ["live", "--roi", "0", "0", "600", "150", "--profile", "game", "--model-profile", "tiny"]
    )
    with pytest.raises(ValueError, match="baseline OCR model"):
        recognizer_from_args(args)  # Fails before loading models or opening capture.

    class UnusedRecognizer:
        def warmup(self):
            raise AssertionError("No OCR initialization for this configuration check")

        def recognize(self, image):
            raise AssertionError("No image processing for this configuration check")

    session = LiveSession(
        UnusedRecognizer(),
        LiveConfig(Rect(0, 0, 600, 150), profile="game"),
        Controls(),
        lambda event: None,
    )
    assert session.policy.config.profile == "game"
    assert not session.policy.armed and session.config.dry_run


@pytest.mark.parametrize(
    "code",
    [
        "AB--23CD45",
        "123456789",
        "ABCDEFGHIJK",
        "-AB23CD45EF",
        "AB23CD45EF-",
    ],
)
def test_game_rejects_unsupported_strings(code):
    assert candidates(lines(code), PolicyConfig(profile="game")) == []


def test_game_uses_context_for_simple_tokens_and_requires_quality():
    config = PolicyConfig(profile="game")
    simple = lines("spring2026", context="Chat username")[0]
    assert candidates([simple, lines(context="Chat username")[1]], config) == []
    assert (
        candidates([simple, TextLine("Expiry Date:", 0.99, Rect(0, 300, 100, 320))], config) == []
    )
    assert candidates([simple, lines()[1]], config) == ["spring2026"]
    assert candidates(lines("aB0O-cD45ef")[:1], config) == ["aB0O-cD45ef"]
    assert (
        candidates([TextLine("AB23-CD45EF", 0.99, Rect(200, 10, 240, 40)), lines()[1]], config)
        == []
    )
    assert (
        candidates(
            [
                TextLine("AB23-CD45EF", 0.99, Rect(200, 10, 440, 40), "verification_disagreement"),
                lines()[1],
            ],
            config,
        )
        == []
    )


def test_game_baseline_dedup_and_rearm():
    policy = DecisionPolicy(PolicyConfig(profile="game"))
    policy.learn_baseline(lines())
    policy.arm()
    assert policy.observe(lines(), 1, 1, 2)[0] == "no_candidate"
    new = lines("ZX67-GH89JK")
    assert policy.observe(new, 2, 2, 3) == ("ready", "ZX67-GH89JK")
    policy.committed("ZX67-GH89JK")
    policy.arm()
    assert policy.observe(new, 4, 4, 5)[0] == "no_candidate"


def test_game_ambiguous_multiple_candidates_and_low_scores_abstain():
    config = PolicyConfig(profile="game")
    policy = DecisionPolicy(config)
    policy.learn_baseline([])
    policy.arm()
    two = lines() + [TextLine("ZX67-GH89JK", 0.99, Rect(200, 45, 440, 75))]
    assert policy.observe(two, 1, 1, 2)[0] == "ambiguous"
    assert (
        candidates([TextLine("AB23-CD45EF", 0.95, Rect(200, 10, 440, 40)), lines()[1]], config)
        == []
    )


@pytest.mark.ocr
def test_real_ocr_hyphenated_game_code_to_memory():
    import random
    from time import perf_counter_ns

    import cv2
    import numpy as np

    from stream_code_capture.clipboard import MemoryClipboard
    from stream_code_capture.domain import Frame
    from stream_code_capture.ocr import RapidRecognizer
    from stream_code_capture.pipeline import Pipeline
    from stream_code_capture.synthetic import make_code

    value = make_code(random.Random(20261101))
    value = value[:5] + "-" + value[5:]
    pixels = np.full((150, 600, 3), 35, np.uint8)
    cv2.putText(
        pixels,
        "Expiry Date:",
        (10, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (245, 245, 245),
        1,
        cv2.LINE_AA,
    )
    recognizer = RapidRecognizer()
    recognizer.warmup()
    memory = MemoryClipboard()
    policy = DecisionPolicy(PolicyConfig(profile="game", max_frame_age_ms=10000))
    pipeline = Pipeline(recognizer, memory, Rect(0, 0, 600, 150), policy)
    pipeline.baseline(Frame(pixels.copy(), 0, perf_counter_ns()))
    policy.arm()
    cv2.putText(
        pixels, value, (180, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (245, 245, 245), 2, cv2.LINE_AA
    )
    for index in (1, 2):
        pixels[0, 0] = index
        pipeline.process(Frame(pixels.copy(), index, perf_counter_ns()))
    assert memory.writes == [value]
