import json
import random

import numpy as np
import pytest

from stream_code_capture.cli import read_image
from stream_code_capture.synthetic import chart_frame, generate, make_code


def test_generator_reproducible_varied_and_preserves_output(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    first = generate(a, seed=44, count=3)
    second = generate(b, seed=44, count=3)
    assert first.read_bytes() == second.read_bytes()
    manifest = json.loads(first.read_text())
    values = [c["expected_writes"][0] for c in manifest["cases"][:-1]]
    assert len(set(values)) == 3
    assert manifest["cases"][-1]["expected_writes"] == []
    for file in a.glob("*.png"):
        assert file.read_bytes() == (b / file.name).read_bytes()
    baseline = read_image(a / "case_000_0.png")
    transient = read_image(a / "case_000_1.png")
    assert np.array_equal(baseline[:100], transient[:100])  # permanent banner
    assert not np.array_equal(baseline[330:450], transient[330:450])  # moving candles
    with pytest.raises(FileExistsError):
        generate(a)


def test_challenge_has_distinct_pixels_and_generated_codes():
    rng = random.Random(8)
    codes = [make_code(rng, True) for _ in range(100)]
    assert len(set(codes)) == 100
    assert any("0" in code or "O" in code for code in codes)
    pixels = chart_frame(codes[0], tick=1, visible=True, seed=8, challenge=True)
    assert pixels.shape == (540, 960, 3)
