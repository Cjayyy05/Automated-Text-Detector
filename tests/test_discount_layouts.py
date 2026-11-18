"""Discount layouts and negative text with exact-token, memory-only decisions."""

from time import perf_counter_ns

import cv2
import numpy as np
import pytest

from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect, TextLine
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig, candidates

TOKEN = "AK74ZM53Q8"
CODE_BOX = Rect(120, 70, 290, 94)


@pytest.mark.parametrize(
    "box",
    [
        Rect(120, 20, 240, 42),
        Rect(120, 145, 240, 168),
        Rect(14, 72, 98, 94),
        Rect(311, 72, 397, 94),
    ],
)
def test_offer_can_be_above_below_or_beside_token(box):
    assert candidates(
        [TextLine(TOKEN, 0.99, CODE_BOX), TextLine("40% off", 0.98, box)], PolicyConfig()
    ) == [TOKEN]


@pytest.mark.parametrize(
    "text",
    ["1234567890", "@TRADER2345", "USD 499.99", "12:34:56 PM", "Order ID: AK74ZM53Q8"],
)
def test_nearby_offer_does_not_promote_noncode_text(text):
    assert (
        candidates(
            [TextLine(text, 0.99, CODE_BOX), TextLine("40% off", 0.98, Rect(110, 20, 220, 42))],
            PolicyConfig(),
        )
        == []
    )


@pytest.mark.parametrize(
    "text,box,rejection",
    [
        ("chat about a promo", Rect(120, 100, 300, 124), None),
        ("40% off", Rect(450, 72, 545, 94), None),
        ("40% off", Rect(120, 20, 220, 42), "bad_read"),
    ],
)
def test_bare_token_requires_specific_spatial_offer_evidence(text, box, rejection):
    assert (
        candidates(
            [TextLine("winter2026", 0.99, CODE_BOX), TextLine(text, 0.98, box, rejection)],
            PolicyConfig(),
        )
        == []
    )


def test_explicit_labels_extract_only_exact_token_with_original_case():
    code = TextLine(f"Coupon code: {TOKEN}", 0.99, Rect(120, 70, 410, 94))
    offer = TextLine("LIMITED-TIME OFFER", 0.99, Rect(120, 105, 360, 132))
    assert candidates([code], PolicyConfig()) == [TOKEN]
    assert candidates([offer, code], PolicyConfig()) == [TOKEN]
    assert candidates([offer, TextLine(code.text.lower(), 0.99, code.box)], PolicyConfig()) == [
        TOKEN.lower()
    ]
    heading = TextLine("Promo code:", 0.99, Rect(2, 70, 100, 94))
    assert candidates([heading, TextLine(TOKEN, 0.99, CODE_BOX)], PolicyConfig()) == [TOKEN]


@pytest.mark.parametrize("box", [Rect(30, 70, 105, 94), Rect(120, 47, 195, 69)])
def test_split_label_and_nearby_offer_confirm_only_a_new_token(box):
    token = TextLine(TOKEN, 0.99, CODE_BOX)
    label = TextLine("Code:", 0.99, box)
    offer = TextLine("LIMITED TIME OFFER", 0.99, Rect(120, 17, 350, 38))
    observations = [label, token, offer]
    config = PolicyConfig()
    assert candidates([label, token], config) == [TOKEN]
    assert candidates([token, offer], config) == [TOKEN]
    assert candidates(observations, config) == [TOKEN]

    policy = DecisionPolicy(config)
    policy.learn_baseline([token])
    policy.arm()
    assert policy.observe(observations, 1, 10, 10) == ("no_candidate", None)

    new_code = "AY77MN55H8"
    new_lines = [label, TextLine(new_code, 0.99, CODE_BOX), offer]
    assert policy.observe(new_lines, 2, 20, 20) == ("ready", new_code)
    policy.committed(new_code)
    assert not policy.armed
    policy.arm()
    assert policy.observe(new_lines, 4, 40, 40) == ("no_candidate", None)


@pytest.mark.parametrize(
    "text,confidence,box,rejection",
    [
        ("User ID:", 0.99, Rect(30, 70, 105, 94), None),
        ("Code:", 0.7, Rect(30, 70, 105, 94), None),
        ("Code:", 0.99, Rect(30, 70, 105, 94), "bad_read"),
        ("Code:", 0.99, Rect(600, 400, 640, 430), None),
    ],
)
def test_split_label_support_for_short_code_requires_confidence_and_proximity(
    text, confidence, box, rejection
):
    assert (
        candidates(
            [TextLine(text, confidence, box, rejection), TextLine("Save20", 0.99, CODE_BOX)],
            PolicyConfig(),
        )
        == []
    )


def test_split_label_cannot_bypass_pitch_or_merged_text_guards():
    label = TextLine("Code:", 0.99, Rect(30, 70, 105, 94))
    offer = TextLine("LIMITED TIME OFFER", 0.99, Rect(120, 17, 350, 38))
    config = PolicyConfig()
    for token in (
        TextLine(TOKEN, 0.999, Rect(120, 70, 206, 94)),
        TextLine(f"{TOKEN} 25% off", 0.999, CODE_BOX),
        TextLine("TRADER2345 25% off", 0.999, CODE_BOX),
    ):
        assert candidates([label, token, offer], config) == []


@pytest.mark.ocr
def test_rendered_discount_copy_including_o0():
    recognizer = RapidRecognizer()
    recognizer.warmup()
    for value, lines, rejection in (
        (TOKEN, [("25% off", 28, 110), (TOKEN, 184, 110)], None),
        (TOKEN, [("LIMITED TIME OFFER", 30, 46), ("Code:", 30, 110), (TOKEN, 187, 110)], None),
        (
            "680J6BN7JX",
            [("680J6BN7JX", 30, 46), ("LudiFlex Eval 50k", 30, 88), ("100% off", 30, 132)],
            None,
        ),
    ):
        clipboard = MemoryClipboard()
        pipeline = Pipeline(recognizer, clipboard, Rect(0, 0, 610, 200))
        pipeline.policy.learn_baseline([])
        pipeline.policy.arm()
        for sequence in (1, 2):
            image = np.full((200, 610, 3), (24, 27, 31), np.uint8)
            for text, x, y in lines:
                cv2.putText(
                    image,
                    text,
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.88,
                    (255, 175, 100),
                    2,
                    cv2.LINE_AA,
                )
            image[-1, -1] = sequence
            result = pipeline.process(Frame(image, sequence, perf_counter_ns()))
            observed = next(line for line in result.lines if line.text == value)
            assert observed.rejection == rejection
            assert result.candidates == ([] if rejection else [value])
            if sequence == 1:
                assert result.status == ("no_candidate" if rejection else "copied")
                assert clipboard.writes == ([] if rejection else [value])
        assert clipboard.writes == ([] if rejection else [value])
