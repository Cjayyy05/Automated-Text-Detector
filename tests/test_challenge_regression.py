"""Known recall failures stay explicit; the previously accepted wrong code must abstain."""

import json

import pytest

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, candidates
from stream_code_capture.synthetic import generate


@pytest.fixture(scope="module")
def challenge_results(tmp_path_factory):
    path = generate(
        tmp_path_factory.mktemp("challenge") / "fixtures", seed=19, count=3, challenge=True
    )
    manifest = json.loads(path.read_text())
    recognizer = RapidRecognizer()
    recognizer.warmup()
    results = []
    for case in manifest["cases"][:-1]:
        image = Rect(*manifest["roi"]).crop(read_image(path.parent / case["frames"][1]["file"]))
        results.append((case["expected_writes"][0], recognizer.recognize(image)))
    return results


@pytest.mark.ocr
@pytest.mark.parametrize("case", [0, 1, 2])
def test_challenge_never_accepts_known_wrong_transcription(challenge_results, case):
    expected, lines = challenge_results[case]
    accepted = candidates(lines, PolicyConfig())
    assert accepted in ([], [expected])
    code_lines = [line for line in lines if len(line.text) == len(expected) and line.text.isalnum()]
    assert code_lines
    assert all(line.rejection == "insufficient_source_resolution" for line in code_lines)


@pytest.mark.ocr
@pytest.mark.xfail(strict=True, reason="Unresolved tiny compressed O/0 exact-code recall")
@pytest.mark.parametrize("case", [0, 1, 2])
def test_challenge_exact_recall_release_gate(challenge_results, case):
    expected, lines = challenge_results[case]
    assert candidates(lines, PolicyConfig()) == [expected]


def test_quality_rejection_beats_high_confidence_and_preserves_text():
    line = TextLine("6428IT020E", 0.99999, Rect(0, 0, 78, 20), "insufficient_source_resolution")
    context = TextLine("100% off", 0.99, Rect(0, 30, 78, 50))
    assert candidates([line, context], PolicyConfig()) == []
    assert line.text == "6428IT020E"  # Never silently rewrite zero to O.
