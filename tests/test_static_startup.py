"""Baseline stability may use idle time. Code confirmation still needs changed frames."""

from threading import Event, Thread
from time import monotonic, sleep

import numpy as np
import pytest

from stream_code_capture.capture import CaptureWorker
from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.live import Controls, LiveConfig, LiveSession


@pytest.mark.parametrize("style", ["idle", "identical", "moving_to_static"])
def test_static_baseline_suppresses_existing_code_and_confirms_only_new_frames(style):
    state = [0]
    closed = Event()
    events = []
    calls = []

    class Source:
        previous_state = None
        pixels = None
        tick = 0

        def grab(self):
            self.tick += 1
            moving = style == "moving_to_static" and self.tick < 5
            if self.previous_state == state[0] and not moving:
                return self.pixels.copy() if style == "identical" else None
            self.previous_state = state[0]
            self.pixels = np.full((60, 160, 3), 120, np.uint8)
            self.pixels[:16] = 255
            self.pixels[32, 32] = state[0]
            self.pixels[0, 0] = self.tick % 255
            return self.pixels.copy()

        def close(self):
            closed.set()

    class Recognizer:
        def recognize(self, image):
            marker = int(image[32, 32, 0])
            calls.append(marker)
            code = "ZX78UV23KL" if marker >= 2 else "AB23CD45EF"
            return [
                TextLine(code, 0.999, Rect(0, 0, 140, 20)),
                TextLine("100% off", 0.999, Rect(0, 30, 140, 50)),
            ]

    controls = Controls()
    worker = CaptureWorker(Source, fps=30)
    session = LiveSession(
        Recognizer(), LiveConfig(Rect(0, 0, 160, 60)), controls, events.append, worker
    )

    def wait_for(predicate):
        deadline = monotonic() + 4
        while not predicate() and monotonic() < deadline:
            sleep(0.01)
        assert predicate(), session.failure

    controls.send("start")
    thread = Thread(target=session.run)
    thread.start()
    try:
        wait_for(lambda: any(e["event"] == "ready" for e in events))
        assert session.policy.suppressed == {"AB23CD45EF"}
        if style != "moving_to_static":
            assert len(calls) == 1
        controls.send("arm")
        wait_for(lambda: any(e["event"] == "armed" for e in events))
        state[0] = 1
        wait_for(lambda: 1 in calls)
        assert session.clipboard.writes == []
        state[0] = 2
        wait_for(lambda: any(e.get("status") == "confirming" for e in events))
        count = len(calls)
        sleep(0.15)
        assert len(calls) == count
        assert session.clipboard.writes == []
        state[0] = 3
        wait_for(lambda: session.clipboard.writes == ["ZX78UV23KL"])
        assert not session.policy.armed
    finally:
        controls.send("stop")
        thread.join(5)
    assert not thread.is_alive() and closed.is_set()


def test_idle_readiness_requires_consumed_observation_and_healthy_capture():
    from time import perf_counter_ns

    session = LiveSession(None, LiveConfig(Rect(0, 0, 160, 60)), Controls(), lambda _: None)
    session.running = True
    session.started_ns = perf_counter_ns()
    session.ready_from_idle_baseline()
    assert not session.ready
    session.baseline_count = 1
    session.baseline_start_ns = perf_counter_ns() - 600_000_000
    session.baseline_sequence = 1
    session.worker.captured = 2  # A changed frame is still pending OCR.
    session.worker.last_capture_poll_ns = perf_counter_ns()
    session.ready_from_idle_baseline()
    assert not session.ready
    session.worker.captured = 1
    session.worker.error = "Monitor access lost"
    session.ready_from_idle_baseline()
    assert not session.ready


@pytest.mark.parametrize(
    "age_ms,intervening_change,accepted",
    [(1500, False, True), (1500, True, True), (2600, True, False), (2600, False, True)],
)
def test_slow_baseline_is_bounded_when_pixels_change(
    monkeypatch, age_ms, intervening_change, accepted
):
    from stream_code_capture import live
    from stream_code_capture.domain import Frame

    clock = [1_000_000_000]
    events = []

    class Recognizer:
        def recognize(self, pixels):
            clock[0] += age_ms * 1_000_000
            session.worker.last_capture_poll_ns = clock[0]
            session.worker.captured += int(intervening_change)
            return [TextLine("AB23CD45EF", 0.999, Rect(0, 0, 140, 20))]

    monkeypatch.setattr(live, "perf_counter_ns", lambda: clock[0])
    session = LiveSession(Recognizer(), LiveConfig(Rect(0, 0, 160, 60)), Controls(), events.append)
    session.running = True
    session.started_ns = clock[0]
    session.worker.captured = 1
    pixels = np.full((60, 160, 3), 120, np.uint8)
    pixels[:16] = 255
    session.consume(Frame(pixels, 1, clock[0]))
    session.ready_from_idle_baseline()
    assert session.ready == (accepted and not intervening_change)
    assert session.clipboard.writes == []
    assert session.policy.suppressed == {"AB23CD45EF"}
    assert session.baseline_count == int(accepted)
    assert any(e["event"] == "baseline_stale" for e in events) is not accepted


@pytest.mark.parametrize("width,height,baseline_ocr_ms", [(760, 140, 80), (1920, 1000, 1800)])
def test_moving_baseline_learns_visible_codes_but_armed_deadline_stays_strict(
    monkeypatch, width, height, baseline_ocr_ms
):
    from stream_code_capture import live
    from stream_code_capture.domain import Frame

    clock = [1_000_000_000]
    events = []
    visible = []
    delay_ms = baseline_ocr_ms
    existing, during, new = "AB23CD45EF", "FG67HJ89KL", "ZX78UV23KL"

    class Recognizer:
        def recognize(self, image):
            assert image.shape[:2] == (height, width)
            clock[0] += delay_ms * 1_000_000
            # The producer observes unrelated changes while OCR is in flight.
            session.worker.captured += 1
            session.worker.last_capture_poll_ns = clock[0]
            return [
                line
                for index, code in enumerate(visible)
                for line in (
                    TextLine(code, 0.999, Rect(width - 160, index * 55, width, index * 55 + 20)),
                    TextLine(
                        "100% off",
                        0.999,
                        Rect(width - 160, index * 55 + 25, width - 60, index * 55 + 44),
                    ),
                )
            ]

    monkeypatch.setattr(live, "perf_counter_ns", lambda: clock[0])
    controls = Controls()
    session = LiveSession(
        Recognizer(), LiveConfig(Rect(0, 0, width, height)), controls, events.append
    )
    session.pipeline.clock = lambda: clock[0]
    session.running = True
    session.started_ns = clock[0]

    def observe(codes, ms=baseline_ocr_ms):
        nonlocal delay_ms
        visible[:] = codes
        delay_ms = ms
        clock[0] += 550_000_000
        session.worker.captured += 1
        pixels = np.full((height, width, 3), 120, np.uint8)
        pixels[:16] = 255
        pixels[-1, 0] = session.worker.captured % 255
        session.consume(Frame(pixels, session.worker.captured, clock[0]))

    observe([existing])
    observe([existing, during])
    observe([existing])
    assert not session.ready  # A changing code set restarted the stability interval.
    observe([existing])
    assert session.ready and session.baseline_accepted == 4
    assert session.policy.suppressed == {existing, during}
    controls.send("arm")
    session.handle_commands()
    observe([existing, during], 80)
    assert events[-1]["status"] == "no_candidate"
    observe([new], 1300)
    assert events[-1]["status"] == "stale"
    observe([new], 80)
    assert events[-1]["status"] == "confirming" and session.clipboard.writes == []
    observe([new], 80)
    assert session.clipboard.writes == [new] and not session.policy.armed
    controls.send("arm")
    session.handle_commands()
    observe([new], 80)
    assert session.clipboard.writes == [new]
