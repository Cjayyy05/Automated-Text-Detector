"""Full policy evaluation; exclusively uses a memory clipboard."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

from stream_code_capture.cli import read_image
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=["baseline", "tiny", "cascade"], required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--no-spinning", action="store_true")
    args = parser.parse_args()
    config = (
        {
            "model_profile": "tiny",
            "scale": 1,
            "threads": 4,
            "cpu_arena": True,
            "det_limit": 640,
            "fallback_baseline": args.profile == "cascade",
        }
        if args.profile in {"tiny", "cascade"}
        else {}
    )
    config["allow_spinning"] = not args.no_spinning
    recognizer = RapidRecognizer(**config)
    recognizer.warmup()
    data = json.loads(args.manifest.read_text())
    timings, cases = Metrics(), []
    with args.report.open("x", encoding="utf-8") as report:
        for case in data["cases"]:
            clipboard = MemoryClipboard()
            policy = DecisionPolicy(PolicyConfig(max_frame_age_ms=10000))
            pipeline = Pipeline(recognizer, clipboard, Rect(*data["roi"]), policy)
            outcomes = []
            for index, item in enumerate(case["frames"]):
                pixels = read_image(args.manifest.parent / item["file"])
                frame = Frame(pixels, index, perf_counter_ns())
                if index == 0:
                    pipeline.baseline(frame)
                    policy.arm()
                else:
                    result = pipeline.process(frame)
                    outcomes.append(asdict(result))
                    timings.add(result.timings_ms)
            record = {
                "case": case["id"],
                "style": case.get("style"),
                "expected": case["expected_writes"],
                "writes": clipboard.writes,
                "outcomes": outcomes,
            }
            cases.append(record)
            report.write(json.dumps({"event": "case", **record}) + "\n")
            report.flush()
        positive = [case for case in cases if case["expected"]]
        summary = {
            "positive_events": len(positive),
            "negative_events": len(cases) - len(positive),
            "exact_copies": sum(c["writes"] == c["expected"] for c in positive),
            "incorrect_writes": sum(w not in c["expected"] for c in cases for w in c["writes"]),
            "abstentions": sum(not c["writes"] for c in positive),
        }
        result = {
            "event": "summary",
            "profile": args.profile,
            "config": config,
            "accuracy": summary,
            "timings": timings.summary(),
            "note": "Sequential file replay. Process wall latency is NOT live capture latency.",
        }
        report.write(json.dumps(result) + "\n")
        print(json.dumps({"accuracy": summary, "process": result["timings"]["process"]}, indent=2))


if __name__ == "__main__":
    main()
