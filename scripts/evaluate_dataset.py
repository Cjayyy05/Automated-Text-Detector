"""Frozen split evaluation. Safe in-memory replay only; no screen windows are launched."""

import argparse
import json
import os
from pathlib import Path
from time import perf_counter_ns

from stream_code_capture.cli import add_ocr_arguments, recognizer_from_args
from stream_code_capture.dataset import audit_split, digest
from stream_code_capture.evaluation import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", type=Path)
    parser.add_argument("--partition", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--profile", choices=["discount", "game"], default="discount")
    add_ocr_arguments(parser)
    args = parser.parse_args()
    selected = [item for item in audit_split(args.split) if item["partition"] == args.partition]
    # Refuse an existing report before spending time on inference.
    with args.report.open("x", encoding="utf-8") as report:
        started = perf_counter_ns()
        recognizer = recognizer_from_args(args)
        recognizer.warmup()
        report.write(
            json.dumps(
                {
                    "event": "configuration",
                    "partition": args.partition,
                    "split_sha256": digest(args.split),
                    "config": {
                        k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()
                    },
                    "model_hashes": {
                        p.name: digest(p)
                        for p in recognizer.model_paths
                        + (
                            recognizer._fallback.model_paths
                            if recognizer._fallback is not None
                            else []
                        )
                    },
                    "startup_ms": (perf_counter_ns() - started) / 1e6,
                }
            )
            + "\n"
        )
        for item in selected:
            result = evaluate(Path(item["manifest"]), recognizer, profile=args.profile)
            if os.name == "nt":
                import win32api
                import win32process

                result["resources"]["windows_process_memory_bytes"] = (
                    win32process.GetProcessMemoryInfo(win32api.GetCurrentProcess())
                )
            report.write(json.dumps({"event": "dataset", **result}) + "\n")
            report.flush()
            print(
                json.dumps(
                    {
                        "manifest": item["manifest"],
                        "accuracy": result["accuracy"],
                        "recognition": result["timings"].get("recognition"),
                        "resources": result["resources"],
                    }
                )
            )


if __name__ == "__main__":
    main()
