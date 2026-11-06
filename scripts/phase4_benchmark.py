"""Offline Phase 4 configuration/independent-line diagnostics. No display or clipboard."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

import cv2
from phase4_scenes import scenes

from stream_code_capture.dataset import audit_split, digest, load_dataset, load_pixels
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument(
        "--configs",
        nargs="+",
        choices=[
            "baseline",
            "cpu_reuse",
            "scale1",
            "smaller_roi",
            "gray",
            "clahe",
            "tiny_diagnostic",
        ],
        help="Optional subset of named configurations",
    )
    args = parser.parse_args()
    if not 1 <= args.count <= 64:
        parser.error("count must be in [1, 64]")
    inputs = []
    for entry in audit_split(args.split):
        path = Path(entry["manifest"])
        for frame in load_dataset(path)["frames"]:
            if frame["label"]["state"] == "visible":
                image = cv2.resize(load_pixels(path.parent / frame["file"]), (960, 540))
                inputs.append(("reused_game", "game", image, frame["label"]["code"]))
    for profile in ("game", "discount"):
        inputs.extend(
            ("generated", profile, p, c) for p, c in scenes(args.seed, args.count, profile)
        )
    configs = [
        ("baseline", {}, [200, 400, 960, 540]),
        (
            "cpu_reuse",
            {"threads": 4, "cpu_arena": True, "allow_spinning": False},
            [200, 400, 960, 540],
        ),
        (
            "scale1",
            {
                "scale": 1,
                "threads": 4,
                "cpu_arena": True,
                "allow_spinning": False,
                "det_limit": 640,
            },
            [200, 400, 960, 540],
        ),
        (
            "smaller_roi",
            {
                "scale": 1,
                "threads": 4,
                "cpu_arena": True,
                "allow_spinning": False,
                "det_limit": 640,
            },
            [215, 410, 850, 525],
        ),
        (
            "gray",
            {
                "scale": 1,
                "threads": 4,
                "cpu_arena": True,
                "allow_spinning": False,
                "det_limit": 640,
                "preprocessing": "gray",
            },
            [200, 400, 960, 540],
        ),
        (
            "clahe",
            {
                "scale": 1,
                "threads": 4,
                "cpu_arena": True,
                "allow_spinning": False,
                "det_limit": 640,
                "preprocessing": "clahe",
            },
            [200, 400, 960, 540],
        ),
        (
            "tiny_diagnostic",
            {
                "model_profile": "tiny",
                "scale": 1,
                "threads": 4,
                "cpu_arena": True,
                "allow_spinning": False,
                "det_limit": 640,
            },
            [200, 400, 960, 540],
        ),
    ]
    with args.report.open("x", encoding="utf-8") as report:
        verifier = RapidRecognizer(
            model_profile="v4", threads=4, cpu_arena=True, allow_spinning=False
        )
        verifier.warmup()
        for name, config, box in configs:
            if args.configs and name not in args.configs:
                continue
            recognizer = RapidRecognizer(**config, profile_inference=True)
            start = perf_counter_ns()
            recognizer.warmup()
            warmup_ms = (perf_counter_ns() - start) / 1e6
            metrics, outcomes = Metrics(), []
            for kind, profile, image, truth in inputs:
                pixels = Rect(*box).crop(image)
                start = perf_counter_ns()
                result = recognizer.recognize_timed(pixels)
                elapsed = (perf_counter_ns() - start) / 1e6
                accepted = candidates(result.lines, PolicyConfig(profile=profile))
                independent = None
                if name == "baseline" and len(accepted) == 1:
                    line = next(line for line in result.lines if line.text.strip() == accepted[0])
                    start = perf_counter_ns()
                    text, score = verifier.verify_line(pixels, line.box)
                    independent = {
                        "text": text,
                        "score": score,
                        "ms": (perf_counter_ns() - start) / 1e6,
                        "agreed": text == accepted[0] and score is not None and score >= 0.96,
                    }
                metrics.add({"wall": elapsed, **result.timings_ms})
                outcomes.append(
                    {
                        "kind": kind,
                        "profile": profile,
                        "expected": truth,
                        "accepted": accepted,
                        "wall_ms": elapsed,
                        "independent": independent,
                        "lines": [asdict(line) for line in result.lines],
                    }
                )
            summary = {
                "exact": sum(o["accepted"] == [o["expected"]] for o in outcomes),
                "wrong_candidates": sum(
                    bool(o["accepted"]) and o["accepted"] != [o["expected"]] for o in outcomes
                ),
                "abstentions": sum(not o["accepted"] for o in outcomes),
                "total": len(outcomes),
            }
            record = {
                "name": name,
                "config": config,
                "roi": box,
                "seed": args.seed,
                "warmup_ms": warmup_ms,
                "summary": summary,
                "timings": metrics.summary(),
                "model_hashes": {
                    str(p): digest(p) for p in recognizer.model_paths + verifier.model_paths
                },
                "outcomes": outcomes,
            }
            report.write(json.dumps(record) + "\n")
            report.flush()
            print(
                json.dumps({"name": name, **summary, "wall": metrics.summary()["wall"]}), flush=True
            )


if __name__ == "__main__":
    main()
