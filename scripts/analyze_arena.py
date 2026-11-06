"""Audit completed arena pairs and compare metrics; never opens capture or clipboard."""

import argparse
import json
from pathlib import Path

from analyze_playback import summarize


def load_report(path):
    first, last = None, None
    with path.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if first is None:
                first = row
            last = row
    if first is None or last.get("event") != "test_result":
        raise ValueError(f"Incomplete report: {path}")
    return first, last


def allocations(result):
    samples = result["memory_samples"]
    baseline = next(s for s in samples if s["stage"] == "baseline")
    monitoring = [s for s in samples if s["stage"] in {"baseline", "monitoring"}]
    return {
        "baseline_private_bytes": baseline["private_bytes"],
        "sampled_private_peak_growth_bytes": max(s["private_bytes"] for s in monitoring)
        - baseline["private_bytes"],
        "last_monitoring_private_growth_bytes": monitoring[-1]["private_bytes"]
        - baseline["private_bytes"],
        "post_cleanup_private_growth_bytes": samples[-1]["private_bytes"]
        - baseline["private_bytes"],
        "sampled_working_set_peak_bytes": max(s["working_set_bytes"] for s in samples),
        "sample_count": len(samples),
    }


def compare(on_path, off_path):
    on_config, on = load_report(on_path)
    off_config, off = load_report(off_path)
    on_analysis, off_analysis = summarize(on_path), summarize(off_path)
    for config, result, analysis in ((on_config, on, on_analysis), (off_config, off, off_analysis)):
        if (
            analysis["session"]["failure"]
            or result.get("errors")
            or result["captured_events"] != len(config["schedule"])
        ):
            raise ValueError("Interrupted capture cannot support a performance comparison")
    for key in (
        "schedule",
        "seed",
        "window_roi",
        "profile",
        "provider",
        "model_hashes",
        "versions",
    ):
        if on_config[key] != off_config[key]:
            raise ValueError(f"Mismatched {key}: {on_path}, {off_path}")
    ignored = {"report", "cpu_arena"}
    if {k: v for k, v in on_config["options"].items() if k not in ignored} != {
        k: v for k, v in off_config["options"].items() if k not in ignored
    }:
        raise ValueError("Configuration differs beyond arena and report path")
    for name, enabled in (("on", True), ("off", False)):
        config = on_config if enabled else off_config
        if config["options"]["cpu_arena"] is not enabled:
            raise ValueError(f"Unexpected requested arena setting: {name}")
        if not all(s["cpu_arena"] is enabled for s in config["ocr_sessions"].values()):
            raise ValueError(f"Unexpected actual ONNX arena setting: {name}")
    for stage in on_config["ocr_sessions"]:
        a, b = on_config["ocr_sessions"][stage], off_config["ocr_sessions"][stage]
        if {k: v for k, v in a.items() if k != "cpu_arena"} != {
            k: v for k, v in b.items() if k != "cpu_arena"
        }:
            raise ValueError("Actual ONNX session options differ beyond arena")
    on_exact = {w["index"] for w in on["writes"] if w["correct"]}
    off_exact = {w["index"] for w in off["writes"] if w["correct"]}
    delta = {}
    for metric in ("first_captured_to_clipboard", "first_captured_to_readback"):
        delta[metric] = {
            key: (off["timings"][metric][key] / on["timings"][metric][key] - 1) * 100
            for key in ("p50_ms", "p95_ms", "max_ms")
        }
    return {
        "cohort": on_path.stem.removesuffix("-arena-on"),
        "inputs_and_models_match": True,
        "extra_missed_indexes_arena_off": sorted(on_exact - off_exact),
        "extra_copied_indexes_arena_off": sorted(off_exact - on_exact),
        "arena_off_latency_change_percent": delta,
        "arena_on": {"analysis": on_analysis, "memory": allocations(on)},
        "arena_off": {"analysis": off_analysis, "memory": allocations(off)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cohorts", nargs="+")
    args = parser.parse_args()
    pairs = []
    for path in sorted(args.directory.glob("*-arena-on.jsonl")):
        if args.cohorts and path.stem.removesuffix("-arena-on") not in args.cohorts:
            continue
        pairs.append(compare(path, path.with_name(path.name.replace("-arena-on", "-arena-off"))))
    if not pairs:
        raise ValueError("No paired reports")
    with args.output.open("x", encoding="utf-8") as report:
        json.dump(pairs, report, indent=2)
    for pair in pairs:
        print(json.dumps({k: v for k, v in pair.items() if k not in {"arena_on", "arena_off"}}))


if __name__ == "__main__":
    main()
