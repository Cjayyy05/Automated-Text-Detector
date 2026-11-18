"""Controlled model/config matrix; truth scores results, never supplies recognition targets."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from stream_code_capture.cli import read_image
from stream_code_capture.domain import Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.policy import PolicyConfig, candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--manifests",
        type=Path,
        nargs="+",
        default=[Path("samples/smoke/manifest.json"), Path("samples/challenge/manifest.json")],
    )
    parser.add_argument("--profiles", nargs="+", default=["baseline", "tiny", "v4"])
    parser.add_argument("--scales", type=float, nargs="+", default=[1, 2])
    parser.add_argument("--limits", type=int, nargs="+", default=[640, 960])
    parser.add_argument("--threads", type=int, nargs="+", default=[2])
    parser.add_argument("--preprocessing", nargs="+", default=["none"])
    parser.add_argument("--arena", action="store_true")
    parser.add_argument("--fallback-baseline", action="store_true")
    parser.add_argument("--no-spinning", action="store_true")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--full-roi", action="store_true")
    parser.add_argument("--positives-only", action="store_true")
    args = parser.parse_args()
    inputs = []
    for path in args.manifests:
        data = json.loads(path.read_text())
        roi = Rect(*(data["roi"] if args.full_roi else [70, 160, 610, 325]))
        for case in data["cases"]:
            if args.positives_only and not case["expected_writes"]:
                continue
            inputs.append(
                (
                    str(path),
                    case["id"],
                    case["expected_writes"],
                    roi.crop(read_image(path.parent / case["frames"][1]["file"])),
                )
            )
    with args.report.open("x", encoding="utf-8") as report:
        for profile in args.profiles:
            for scale in args.scales:
                for limit in args.limits:
                    for threads in args.threads:
                        for preprocessing in args.preprocessing:
                            config = {
                                "model_profile": profile,
                                "scale": scale,
                                "det_limit": limit,
                                "threads": threads,
                                "preprocessing": preprocessing,
                                "cpu_arena": args.arena,
                            }
                            config["fallback_baseline"] = args.fallback_baseline
                            config["allow_spinning"] = not args.no_spinning
                            recognizer = RapidRecognizer(**config)
                            recognizer.warmup()
                            metrics, outcomes = Metrics(), []
                            for path, case_id, expected, pixels in inputs:
                                for _ in range(args.repeats):
                                    start, cpu = perf_counter_ns(), process_time_ns()
                                    result = recognizer.recognize_timed(pixels)
                                    metrics.add(
                                        {
                                            "wall": (perf_counter_ns() - start) / 1e6,
                                            "cpu": (process_time_ns() - cpu) / 1e6,
                                            **result.timings_ms,
                                        }
                                    )
                                accepted = candidates(result.lines, PolicyConfig())
                                outcomes.append(
                                    {
                                        "manifest": path,
                                        "case": case_id,
                                        "expected": expected,
                                        "accepted": accepted,
                                        "raw_lines": [asdict(line) for line in result.lines],
                                    }
                                )
                            positive = [o for o in outcomes if o["expected"]]
                            summary = {
                                "exact": sum(o["accepted"] == o["expected"] for o in positive),
                                "positives": len(positive),
                                "wrong": sum(
                                    bool(o["accepted"]) and o["accepted"] != o["expected"]
                                    for o in outcomes
                                ),
                                "abstentions": sum(not o["accepted"] for o in positive),
                            }
                            record = {
                                "config": config,
                                "timings": metrics.summary(),
                                "summary": summary,
                                "outcomes": outcomes,
                            }
                            report.write(json.dumps(record) + "\n")
                            report.flush()
                            print(
                                json.dumps(
                                    {
                                        "config": config,
                                        "summary": summary,
                                        "wall": record["timings"]["wall"],
                                    }
                                ),
                                flush=True,
                            )


if __name__ == "__main__":
    main()
