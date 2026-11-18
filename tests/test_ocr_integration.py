"""Real generated pixels -> local ONNX -> policy -> memory clipboard. No display."""

import json
import socket
from time import perf_counter_ns

import pytest

from stream_code_capture.cli import read_image
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig
from stream_code_capture.synthetic import generate


@pytest.mark.ocr
def test_actual_offline_ocr_chart_sequence(tmp_path, monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("OCR attempted network access")

    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    manifest_path = generate(tmp_path / "fixtures", seed=7, count=3)
    manifest = json.loads(manifest_path.read_text())
    recognizer = RapidRecognizer()
    recognizer.warmup()
    assert recognizer.warmed
    for case in manifest["cases"]:
        clipboard = MemoryClipboard()
        # Accuracy gate uses a generous offline budget, never a live latency assertion.
        policy = DecisionPolicy(PolicyConfig(max_frame_age_ms=10000))
        pipeline = Pipeline(recognizer, clipboard, Rect(*manifest["roi"]), policy)
        observations = []
        for seq, item in enumerate(case["frames"]):
            image = read_image(manifest_path.parent / item["file"])
            frame = Frame(image, seq, perf_counter_ns())
            if seq == 0:
                pipeline.baseline(frame)
                pipeline.policy.arm()
            else:
                observations.append(pipeline.process(frame))
        assert clipboard.writes == case["expected_writes"], observations
        assert "JORDY" not in clipboard.writes
