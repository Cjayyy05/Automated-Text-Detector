"""Summarize completed capture reports without starting capture, OCR or clipboard access."""

import argparse
import json
from collections import Counter
from pathlib import Path

from stream_code_capture.metrics import Metrics


def summarize(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    result = rows[-1]
    if result.get("event") != "test_result":
        raise ValueError(f"Incomplete playback: {path}")
    frames = [r for r in rows if r["event"] == "frame"]
    positive = [r for r in frames if r["candidates"]]
    stages = Metrics()
    evidence_stages = Metrics()
    for frame in positive:
        stages.add(frame["timings_ms"])
        if frame["status"] in {"confirming", "would_copy", "copied"}:
            evidence_stages.add(
                {
                    key: value
                    for key, value in frame["timings_ms"].items()
                    if key != "clipboard" or frame["status"] in {"would_copy", "copied"}
                }
            )
    confirmation = Metrics()
    for write in result["writes"]:
        value = write.get("first_recognition_to_clipboard_ms")
        if write["correct"] and value is not None:
            confirmation.add({"first_raw_exact_recognition_to_clipboard": value})
    session = next(r for r in rows if r["event"] == "summary")
    return {
        "path": str(path),
        "config": rows[0],
        "passed": result["passed"],
        "exact_copies": result["exact_copies"],
        "incorrect_writes": result["incorrect_writes"],
        "abstentions": result["abstentions"],
        "captured_events": result["captured_events"],
        "end_to_end": result["timings"],
        "confirmation": confirmation.summary(),
        "candidate_frame_stages": stages.summary(),
        "copy_evidence_stages": evidence_stages.summary(),
        "candidate_frame_statuses": dict(Counter(f["status"] for f in positive)),
        "all_frame_statuses": dict(Counter(f["status"] for f in frames)),
        "session": session,
        "by_exposure": result["by_exposure"],
        "missed": [
            e
            for i, e in enumerate(rows[0]["schedule"])
            if e["kind"] == "new"
            and not any(w["correct"] and w["index"] == i for w in result["writes"])
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    results = [summarize(path) for path in args.reports]
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(results, target, indent=2)
    for result in results:
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "path",
                        "exact_copies",
                        "incorrect_writes",
                        "abstentions",
                        "end_to_end",
                        "confirmation",
                    )
                }
            )
        )


if __name__ == "__main__":
    main()
