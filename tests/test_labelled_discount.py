"""Regression coverage for explicitly labelled discount annotations."""

from threading import Event, Thread
from time import monotonic, sleep

import cv2
import numpy as np
import pytest

from stream_code_capture.capture import CaptureWorker
from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import DecisionPolicy, PolicyConfig, candidates

CODE = "Q8M4Z7P2VK"


def annotation(code=CODE):
    return [
        TextLine("LIMITED TIME OFFER", 0.99, Rect(17, 20, 292, 47)),
        TextLine(f"CODE: {code}", 0.98, Rect(17, 74, 294, 100)),
    ]


def test_labelled_code_can_stand_alone_but_still_requires_quality():
    heading, code = annotation()
    config = PolicyConfig()
    assert candidates([heading, code], config) == [CODE]
    assert candidates([code], config) == [CODE]
    assert candidates([TextLine("CHAT MESSAGE", 0.99, heading.box), code], config) == [CODE]
    assert candidates([TextLine(heading.text, 0.99, Rect(17, 200, 292, 225)), code], config) == [
        CODE
    ]
    assert candidates([heading, TextLine(code.text, 0.95, code.box)], config) == []
    assert candidates([heading, TextLine(code.text, 0.98, Rect(17, 74, 140, 100))], config) == []
    assert candidates(annotation("Q8M4Z0P2VK"), config) == ["Q8M4Z0P2VK"]
    assert candidates([heading, code], PolicyConfig(profile="game")) == [CODE]


def test_labelled_baseline_suppresses_exact_token():
    policy = DecisionPolicy()
    policy.learn_baseline(annotation()[1:])
    assert policy.suppressed == {CODE}
    policy.arm()
    assert policy.observe(annotation(), 1, 10, 10) == ("no_candidate", None)


@pytest.mark.ocr
@pytest.mark.parametrize(
    "token,scale,stroke,rejection",
    [
        (CODE, 0.95, 2, None),
        ("Q8M4Z0P2VK", 0.95, 2, None),
        (CODE, 0.44, 1, "insufficient_source_resolution"),
    ],
)
def test_blue_annotation_recognition_and_quality_guards(token, scale, stroke, rejection):
    image = np.full((135, 440, 3), 26, np.uint8)
    for line, y in zip(annotation(token), (44, 97), strict=True):
        cv2.putText(
            image,
            line.text,
            (19, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (255, 154, 60),
            stroke,
            cv2.LINE_AA,
        )
    recognizer = RapidRecognizer()
    recognizer.warmup()
    lines = recognizer.recognize(image)
    assert [line.text for line in lines] == ["LIMITED TIME OFFER", f"CODE: {token}"]
    assert lines[1].rejection == rejection
    assert candidates(lines, PolicyConfig()) == ([] if rejection else [token])


@pytest.mark.parametrize("activity_gate_ms", [0, 500])
def test_static_labelled_appearance_copies_without_a_second_changed_frame(activity_gate_ms):
    revealed, primed, closed = Event(), Event(), Event()
    events = []
    controls = Controls()

    class Source:
        def grab(self):
            image = np.full((135, 440, 3), 26, np.uint8)
            image[:16] = 170
            image[32, 32] = int(revealed.is_set())
            image[48, 32] = int(primed.is_set())
            return image

        def close(self):
            closed.set()

    class Recognizer:
        def recognize(self, image):
            return annotation() if image[32, 32, 0] else []

    worker = CaptureWorker(Source)
    session = LiveSession(
        Recognizer(),
        LiveConfig(Rect(0, 0, 440, 135), activity_gate_ms=activity_gate_ms),
        controls,
        events.append,
        worker,
    )

    def until(predicate):
        deadline = monotonic() + 4
        while not predicate() and monotonic() < deadline:
            sleep(0.01)
        assert predicate(), session.failure

    controls.send("start")
    thread = Thread(target=session.run)
    thread.start()
    try:
        until(lambda: session.ready)
        controls.send("arm")
        until(lambda: session.policy.armed)
        if activity_gate_ms:
            primed.set()
            until(lambda: any(e.get("status") == "no_candidate" for e in events))
        revealed.set()
        until(lambda: session.clipboard.writes == [CODE])
        count = worker.captured
        sleep(0.15)
        assert worker.captured == count
        assert session.activity_skipped == int(bool(activity_gate_ms))
        assert CODE not in session.policy.suppressed
        assert not session.policy.armed
    finally:
        controls.send("stop")
        thread.join(5)
    assert not thread.is_alive() and closed.is_set()
