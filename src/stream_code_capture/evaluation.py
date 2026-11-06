"""Sequential labelled-file accuracy evaluation; memory clipboard is not configurable.

Labels score results and supply the user-selected chart ROI, never code localization,
recognition text, confidence, or policy thresholds. This is not live latency validation.
"""

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns, process_time_ns
from typing import Any

import numpy as np

from .clipboard import MemoryClipboard
from .dataset import image_path, load_dataset, load_pixels
from .domain import Frame, Recognizer, Rect
from .metrics import Metrics
from .pipeline import Pipeline
from .policy import DecisionPolicy, PolicyConfig


def overlap(box: Rect, truth: Rect) -> dict[str, float]:
    intersection = max(0, min(box.right, truth.right) - max(box.left, truth.left)) * max(
        0, min(box.bottom, truth.bottom) - max(box.top, truth.top)
    )
    area = (box.right - box.left) * (box.bottom - box.top)
    truth_area = (truth.right - truth.left) * (truth.bottom - truth.top)
    return {
        "truth_coverage": intersection / truth_area,
        "iou": intersection / (area + truth_area - intersection),
    }


def evaluate(path: Path, recognizer: Recognizer, *, profile: str = "discount") -> dict[str, Any]:
    data = load_dataset(path)
    if any(frame["label"]["state"] == "unknown" for frame in data["frames"]):
        raise ValueError("Resolve unknown labels before evaluation; do not silently drop frames")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for frame in data["frames"]:
        grouped[frame["label"]["event_id"]].append(frame)
    metrics = Metrics()
    events: list[dict[str, Any]] = []
    counts = dict.fromkeys(
        (
            "positive_events",
            "negative_events",
            "exact_copies",
            "incorrect_writes",
            "unsafe_partial_writes",
            "abstentions",
            "snapshot_events",
            "visible_frames",
            "recognized_visible_frames",
            "duplicate_roi_frames",
            "raw_exact_frames",
            "eligible_exact_frames",
        ),
        0,
    )
    cpu_start, wall_start = process_time_ns(), perf_counter_ns()
    for event_id, frames in grouped.items():
        memory = MemoryClipboard()
        policy = DecisionPolicy(
            PolicyConfig(max_frame_age_ms=10000, confirmation_window_ms=10000, profile=profile)
        )
        pipeline = Pipeline(recognizer, memory, Rect(*frames[0]["label"]["roi"]), policy)
        replay = frames[0]["label"]["state"] == "baseline"
        truth = next((f["label"]["code"] for f in frames if f["label"]["state"] == "visible"), None)
        observations = []
        invalid_writes = 0
        previous_roi = None
        for sequence, item in enumerate(frames):
            image = load_pixels(image_path(path.parent, item["file"]))
            frame = Frame(image, sequence, perf_counter_ns())
            label = item["label"]
            counts["visible_frames"] += label["state"] == "visible"
            roi_pixels = pipeline.roi.crop(image)
            if previous_roi is not None and np.array_equal(previous_roi, roi_pixels):
                counts["duplicate_roi_frames"] += 1
                observations.append({"frame_id": item["frame_id"], "status": "duplicate_roi"})
                continue
            previous_roi = roi_pixels
            if sequence == 0 and replay:
                pipeline.baseline(frame)
                policy.arm()
                continue
            # Snapshot datasets stay disarmed: no invented duplicate confirmation.
            result = pipeline.process(frame)
            metrics.add(result.timings_ms)
            if label["state"] == "visible":
                counts["recognized_visible_frames"] += 1
                counts["raw_exact_frames"] += any(
                    line.text == label["code"] for line in result.lines
                )
                counts["eligible_exact_frames"] += result.candidates == [label["code"]]
            if result.status == "copied" and (
                label["state"] != "visible" or result.code != label["code"]
            ):
                counts["incorrect_writes"] += 1
                counts["unsafe_partial_writes"] += label["state"] == "partial"
                invalid_writes += 1
            localization = []
            if label["box"] is not None:
                truth_box = Rect(*label["box"])
                localization = [
                    {"text": line.text, **overlap(line.box, truth_box)} for line in result.lines
                ]
            observations.append(
                {
                    "frame_id": item["frame_id"],
                    "state": label["state"],
                    "expected": label["code"],
                    "localization_overlap": localization,
                    **asdict(result),
                }
            )
        if replay:
            counts["positive_events" if truth else "negative_events"] += 1
            if truth:
                counts["exact_copies"] += memory.writes == [truth] and invalid_writes == 0
                counts["abstentions"] += not memory.writes
        else:
            counts["snapshot_events"] += 1
        events.append(
            {
                "id": event_id,
                "expected": truth,
                "writes": memory.writes,
                "replay_eligible": replay,
                "observations": observations,
            }
        )
    positives = counts["positive_events"]
    return {
        "manifest": str(path.resolve()),
        "profile": profile,
        "source_kind": data["source_kind"],
        "accuracy": {
            **counts,
            "exact_event_recall": counts["exact_copies"] / positives if positives else None,
            "abstention_rate": counts["abstentions"] / positives if positives else None,
        },
        "timings": metrics.summary(),
        "events": events,
        "resources": {
            "evaluation_process_cpu_ms": (process_time_ns() - cpu_start) / 1e6,
            "evaluation_wall_ms": (perf_counter_ns() - wall_start) / 1e6,
        },
        "live_end_to_end_ms": None,
        "note": "Sequential file replay, 10000 ms accuracy-only age budget. No native clipboard. "
        "Event counts require an annotated baseline; snapshots are frame recognition only. "
        "Partial/negative-frame writes count as incorrect even if identity matches later truth. "
        "Raw exact counts mean an exact ROI text occurrence; "
        "overlap is separate diagnostic evidence. "
        "Capture/queue fields are file-pipeline placeholders, not captured timings. "
        "Stage percentiles retain at most the latest 10000 observations per dataset.",
    }
