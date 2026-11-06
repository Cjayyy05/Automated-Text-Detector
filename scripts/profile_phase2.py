"""Offline Phase 2 profiler: wall latency, scheduled CPU time and true ORT run calls."""

import argparse
import json
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, candidates


def attach_inference_meter(engine, values):
    for name, model in (("det_inference", engine.text_det), ("rec_inference", engine.text_rec)):
        session = model.session.session
        original = session.run

        def measured(*args, _name=name, _original=original, **kwargs):
            start = perf_counter_ns()
            result = _original(*args, **kwargs)
            values[_name] = values.get(_name, 0) + (perf_counter_ns() - start) / 1e6
            return result

        session.run = measured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--roi", type=int, nargs=4, default=[70, 160, 610, 325])
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    recognizer = RapidRecognizer()
    recognizer.warmup()
    meter = {}
    attach_inference_meter(recognizer._engine, meter)
    timings, cases = Metrics(), []
    for case in manifest["cases"]:
        image = Rect(*args.roi).crop(read_image(args.manifest.parent / case["frames"][1]["file"]))
        for _ in range(args.repeats):
            meter.clear()
            wall, cpu = perf_counter_ns(), process_time_ns()
            result = recognizer.recognize_timed(image)
            values = {
                "wall_total": (perf_counter_ns() - wall) / 1e6,
                "process_cpu": (process_time_ns() - cpu) / 1e6,
                **result.timings_ms,
                **meter,
            }
            timings.add(values)
        cases.append(
            {
                "id": case["id"],
                "expected": case["expected_writes"],
                "candidates": candidates(result.lines, PolicyConfig()),
            }
        )
    print(
        json.dumps(
            {
                "timings": timings.summary(),
                "cases": cases,
                "note": "CPU is aggregate scheduled CPU across threads; wall includes waits. "
                "Offline input: capture/wait/queue/clipboard not measured here.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
