"""Compare whole-batch reuse with an offline-only, exact per-crop reuse experiment."""

import argparse
import json
from pathlib import Path
from time import perf_counter, perf_counter_ns, sleep

import cv2
import numpy as np
from benchmark_armed_roi import scene
from rapidocr.ch_ppocr_rec import TextRecOutput

from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.domain import Rect
from stream_code_capture.ocr import RECOGNITION_REUSE_BYTES, RapidRecognizer, RecognitionBatchReuse
from stream_code_capture.policy import PolicyConfig, candidates


class CropProbe:
    """Keep the original group's padding width while rerunning only uncached rows."""

    def __init__(self, reader):
        self.reader = reader
        self.model = reader._engine.text_rec
        self.original = reader._engine.recognize_txt
        self.previous = {}
        self.hits = 0

    def __call__(self, images):
        started = perf_counter()
        self.hits = 0
        if sum(image.nbytes for image in images) > RECOGNITION_REUSE_BYTES:
            self.previous = {}
            return self.original(images)
        current = {}
        rows = [("", 0.0)] * len(images)
        ratios = [image.shape[1] / image.shape[0] for image in images]
        order = np.argsort(ratios).tolist()
        batch_size = self.model.rec_batch_num
        _, height, width = self.model.rec_image_shape
        resize = self.model.resize_norm_img
        for offset in range(0, len(order), batch_size):
            group = order[offset : offset + batch_size]
            ratio = max(width / height, *(ratios[i] for i in group))
            keys = {i: (int(height * ratio), images[i].shape, images[i].tobytes()) for i in group}
            misses = []
            for i, key in keys.items():
                if key in self.previous:
                    rows[i] = current[key] = self.previous[key]
                    self.hits += 1
                else:
                    misses.append(i)
            if misses:
                self.model.resize_norm_img = lambda image, _ratio, target=ratio: resize(
                    image, target
                )
                try:
                    batch = self.original([images[i] for i in misses])
                finally:
                    self.model.resize_norm_img = resize
                for i, reading in zip(
                    misses, zip(batch.txts, batch.scores, strict=True), strict=True
                ):
                    rows[i] = reading
                    if RecognitionBatchReuse.can_reuse((reading,)):
                        current[keys[i]] = reading
        self.previous = current
        texts, scores = zip(*rows, strict=True)
        return TextRecOutput(
            imgs=images,
            txts=texts,
            scores=list(scores),
            word_results=(None,) * len(images),
            elapse=perf_counter() - started,
        )


def captured(roi, output, count):
    worker = CaptureWorker(lambda: DxcamSource(roi, output=output))
    samples = []
    worker.start()
    try:
        worker.started.wait(3)
        for _ in range(count):
            frame = worker.latest.wait(3)
            if frame is None or worker.error:
                break
            samples.append(frame.image)
            sleep(0.35)
    finally:
        worker.stop()
    if worker.error or len(samples) != count:
        raise RuntimeError(worker.error or "Not enough changed desktop frames")
    return samples


def synthetic(count, changing):
    samples = []
    for i in range(count):
        pixels = scene(1173, 870, 18, "ZB75EV38KT", "right", i, moving_text=changing)
        # A long caption forces a wide batch, even when most crops are short.
        cv2.putText(
            pixels,
            "Market watch closes near session high as other sectors trade flat",
            (35, 625),
            0,
            0.75,
            (245, 245, 245),
            1,
            cv2.LINE_AA,
        )
        if not changing:
            for row in (2, 7, 11):
                y = 24 + row * 31
                pixels[y - 20 : y + 5, 10:290] = (30, 37, 48)
                cv2.putText(
                    pixels,
                    f"Market 1  price {249.0 + i + row:.2f}",
                    (10, y),
                    0,
                    0.54,
                    (210, 215, 219),
                    1,
                    cv2.LINE_AA,
                )
        samples.append(pixels)
    return samples


def compare(samples):
    records = {}
    reference = []
    config = PolicyConfig()
    for method in ("whole_batch", "per_crop"):
        reader = RapidRecognizer(
            profile_inference=True, reuse_static_batches=method == "whole_batch"
        )
        reader.warmup()
        probe = None
        if method == "per_crop":
            probe = CropProbe(reader)
            reader._engine.recognize_txt = probe
        rows = []
        for index, image in enumerate(samples):
            started = perf_counter_ns()
            result = reader.recognize_timed(image)
            elapsed = (perf_counter_ns() - started) / 1e6
            lines = result.lines
            if method == "whole_batch":
                reference.append(lines)
            other = reference[index]
            rows.append(
                {
                    "process_ms": elapsed,
                    "recognition_ms": result.timings_ms.get("text_recognition", 0),
                    "batch_hits": result.profile.cache_hits,
                    "crop_hits": probe.hits if probe else None,
                    "same_text_boxes_and_rejections": [
                        (line.text, line.box, line.rejection) for line in lines
                    ]
                    == [(line.text, line.box, line.rejection) for line in other],
                    "max_score_delta": max(
                        (
                            abs(a.confidence - b.confidence)
                            for a, b in zip(lines, other, strict=False)
                        ),
                        default=0,
                    ),
                    "same_candidates": candidates(lines, config) == candidates(other, config),
                    "candidate_count": len(candidates(lines, config)),
                }
            )
        records[method] = rows
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--roi", nargs=4, type=int)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.capture != bool(args.roi) or not 2 <= args.frames <= 10:
        parser.error("Use --capture and --roi together, with 2–10 frames")
    suites = (
        {"desktop": captured(Rect(*args.roi), args.output, args.frames)}
        if args.capture
        else {
            "mixed": synthetic(args.frames, False),
            "moving": synthetic(args.frames, True),
        }
    )
    with args.report.open("x", encoding="utf-8") as report:
        json.dump({name: compare(samples) for name, samples in suites.items()}, report, indent=2)


if __name__ == "__main__":
    main()
