"""Moving synthetic capture source through real local OCR and the memory clipboard."""

import argparse
import json
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from stream_code_capture.capture import CaptureWorker
from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer

EXISTING = "AB23CD45EF"
NEW = "ZX78UV23KL"


def scene(width, height, rows, new):
    image = np.full((height, width, 3), (32, 39, 48), np.uint8)
    for row in range(rows):
        for column in range(4):
            cv2.putText(
                image,
                f"Market panel {column + 1}  price {248.25 + row:.2f}",
                (24 + column * 465, 28 + row * 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )
    y = height - 88
    for x, code in [(35, EXISTING), (width - 260, NEW if new else "")]:
        cv2.putText(image, code, (x, y), 0, 0.9, (245, 245, 245), 2, cv2.LINE_AA)
        if code:
            cv2.putText(image, "100% off", (x, y + 32), 0, 0.6, (235, 235, 235), 1, cv2.LINE_AA)
    return image


def probe(recognizer, width, height, rows, seconds):
    controls = Controls()
    stages = Metrics()
    baseline = scene(width, height, rows, False)
    positive = scene(width, height, rows, True)
    events = []
    reveal = False
    first_positive_ns = 0

    class Source:
        tick = 0

        def grab(self):
            nonlocal first_positive_ns
            self.tick += 1
            image = (positive if reveal else baseline).copy()
            if reveal and not first_positive_ns:
                first_positive_ns = perf_counter_ns()
            # Motion stays in a region with no text.
            x = (self.tick * 7) % (width - 20)
            image[-4:, x : x + 12] = (70, 175, 65)
            return image

        def close(self):
            pass

    class MeasuredRecognizer:
        def recognize_timed(self, image):
            result = recognizer.recognize_timed(image)
            group = "armed" if session.policy.armed else "baseline"
            stages.add({f"{group}_{key}": value for key, value in result.timings_ms.items()})
            return result

        def recognize(self, image):
            return self.recognize_timed(image).lines

    def emit(event):
        nonlocal reveal
        kind = event["event"]
        if kind != "frame" or event["status"] in {"confirming", "would_copy", "stale"}:
            payload = {key: val for key, val in event.items() if key not in {"lines", "timings_ms"}}
            events.append({"elapsed_ms": (perf_counter_ns() - start) / 1e6, **payload})
        if kind == "ready":
            controls.send("arm")
        elif kind == "armed":
            reveal = True
        elif event.get("status") == "would_copy":
            controls.send("stop")

    worker = CaptureWorker(Source, fps=30)
    session = LiveSession(
        MeasuredRecognizer(), LiveConfig(Rect(0, 0, width, height)), controls, emit, worker
    )
    start = perf_counter_ns()
    controls.send("start")
    exit_code = session.run(duration=seconds)
    ready = next((event for event in events if event["event"] == "ready"), None)
    copied = next((event for event in events if event.get("status") == "would_copy"), None)
    recognized = next((event for event in events if event.get("status") == "confirming"), None)
    return {
        "roi": [width, height],
        "distractor_text_lines": rows * 4,
        "exit_code": exit_code,
        "ready_ms": ready["elapsed_ms"] if ready else None,
        "accepted_ready_observations": ready["baseline_observations"] if ready else None,
        "accepted_baseline_observations": session.baseline_accepted,
        "rejected_baseline_observations": session.baseline_rejected,
        "suppressed": sorted(session.policy.suppressed),
        "writes": session.clipboard.writes,
        "first_positive_capture_to_copy_ms": (
            (copied["completed_ns"] - first_positive_ns) / 1e6 if copied else None
        ),
        "first_recognition_to_copy_ms": (
            (copied["completed_ns"] - recognized["recognized_ns"]) / 1e6
            if copied and recognized
            else None
        ),
        "stages": stages.summary(),
        "events": events,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    with args.report.open("x", encoding="utf-8") as report:
        recognizer = RapidRecognizer(profile_inference=True)
        recognizer.warmup()
        for width, height, rows in ((760, 140, 0), (1920, 1000, 3), (1920, 1000, 19)):
            result = probe(recognizer, width, height, rows, args.seconds)
            report.write(json.dumps(result) + "\n")
            report.flush()
            print(json.dumps({k: v for k, v in result.items() if k not in {"events", "stages"}}))


if __name__ == "__main__":
    main()
