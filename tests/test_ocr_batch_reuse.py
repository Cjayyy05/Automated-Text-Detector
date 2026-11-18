"""Exact crop reuse must keep new code recognition independent."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from stream_code_capture.domain import RecognitionProfile
from stream_code_capture.ocr import RapidRecognizer, RecognitionBatchReuse
from stream_code_capture.policy import PolicyConfig, candidates


def crop(width, value):
    return np.full((8, width, 3), value, dtype=np.uint8)


def test_reuses_exact_distractor_batch_but_rereads_code_and_changed_pixels():
    calls = []

    def recognize(images):
        values = [int(image[0, 0, 0]) for image in images]
        calls.append(values)
        readings = {1: "Market update", 2: "35% off", 3: "Code: AK74ZM53Q8", 4: "Chart data"}
        return SimpleNamespace(txts=tuple(readings[i] for i in values), scores=[0.99] * len(values))

    reuse = RecognitionBatchReuse(recognize, batch_size=2)
    reuse.enabled = True
    # Scrambled detector order exercises mapping back from the aspect sort.
    pixels = [crop(17, 3), crop(9, 1), crop(21, 4), crop(11, 2)]
    first = reuse(pixels)
    reuse.profile = RecognitionProfile()
    second = reuse([image.copy() for image in pixels])
    assert calls == [[3, 1, 4, 2], [3, 4]]
    assert (first.txts, first.scores) == (second.txts, second.scores)
    assert (reuse.profile.cache_hits, reuse.profile.cache_misses) == (1, 1)
    assert reuse.profile.code_batches_excluded == 1

    # A change anywhere in one crop invalidates its entire padding batch.
    pixels[1][-1, -1, 1] = 42
    assert reuse(pixels).txts == first.txts
    assert calls[-1] == [3, 1, 4, 2]

    reuse.enabled = False
    reuse(pixels)
    assert not reuse.previous


@pytest.mark.parametrize("text", ["ZX78UV23KL", "Code: ZX78UV23KL", "A8CD-09EF-12GH", "O0I1B8S5Z2"])
def test_low_confidence_and_ambiguous_tokens_cannot_be_reused(text):
    assert not RecognitionBatchReuse.can_reuse(((text, 0.54),))


def test_oversized_cache_input_uses_original_and_clears_previous(monkeypatch):
    from stream_code_capture import ocr

    result = SimpleNamespace(txts=("price 123.45",), scores=[0.99])
    reuse = RecognitionBatchReuse(lambda _images: result, batch_size=6)
    reuse.enabled = True
    image = crop(11, 3)
    reuse([image])
    assert reuse.previous
    monkeypatch.setattr(ocr, "RECOGNITION_REUSE_BYTES", image.nbytes - 1)
    reuse.profile = RecognitionProfile()
    assert reuse([image]) is result
    assert not reuse.previous
    assert reuse.profile.cache_state == "over byte budget"
    assert reuse.profile.crop_bytes == image.nbytes


@pytest.mark.ocr
def test_large_ocr_reuse_preserves_lines_and_reads_a_new_small_edge_token():
    def render(code):
        image = np.full((780, 1080, 3), (27, 33, 40), dtype=np.uint8)
        for row in range(7):
            for col in range(3):
                cv2.putText(
                    image,
                    f"Market {col} price {229.5 + row:.2f}",
                    (12 + col * 320, 36 + row * 36),
                    0,
                    0.62,
                    (235, 235, 235),
                    1,
                    cv2.LINE_AA,
                )
        cv2.putText(image, code, (937, 710), 0, 0.66, (250, 234, 203), 2, cv2.LINE_AA)
        cv2.putText(image, "100% off", (937, 739), 0, 0.61, (240, 205, 175), 1, cv2.LINE_AA)
        return image

    recognizer = RapidRecognizer(profile_inference=True)
    recognizer.warmup()
    reuse = recognizer._batch_reuse
    assert reuse is not None
    original = reuse.recognize
    counts = []

    def measure(images):
        counts.append(len(images))
        return original(images)

    reuse.recognize = measure
    initial = render("AK74ZM53Q8")
    first = recognizer.recognize(initial)
    total = sum(counts)
    counts.clear()
    profiled = recognizer.recognize_timed(initial.copy())
    second = profiled.lines
    assert 0 < sum(counts) < total  # Only the unrelated batches can be reused.
    assert second == first
    assert profiled.profile is not None
    assert profiled.profile.detected_lines == total
    assert profiled.profile.cache_hits > 0
    assert sum(batch.crops for batch in profiled.profile.batches) == sum(counts)
    assert all(
        batch.input_width > 0 and batch.inference_ms > 0 for batch in profiled.profile.batches
    )
    assert candidates(second, PolicyConfig()) == ["AK74ZM53Q8"]
    timings = profiled.profile.batches.copy()
    recognizer.verify_line(initial, second[-2].box)
    assert profiled.profile.batches == timings

    replacement = render("R7V4K9M2PX")
    assert candidates(recognizer.recognize(replacement), PolicyConfig()) == ["R7V4K9M2PX"]
