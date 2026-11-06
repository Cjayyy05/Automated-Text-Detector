"""Explicit sequential Windows playback matrix. Memory-only unless --native-clipboard."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def capture_completed(rows):
    if not rows or rows[-1].get("event") != "test_result":
        return False
    result = rows[-1]
    session = next((row for row in rows if row["event"] == "summary"), {})
    return bool(
        rows[0].get("event") == "test_config"
        and rows[0].get("schedule")
        and session
        and not session.get("failure")
        and not result.get("errors")
        and result.get("captured_events") == len(rows[0].get("schedule", []))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--native-clipboard", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite", choices=["smoke", "matrix"], default="smoke")
    parser.add_argument("--comparison", choices=["original", "arena"], default="original")
    parser.add_argument("--reverse-pairs", action="store_true", help="Reverse arena pair order")
    parser.add_argument(
        "--cohorts",
        nargs="+",
        choices=["discount-long", "game-long", "discount-short", "game-short", "screenshots"],
        help="Arena matrix only: rerun complete pairs in a new output directory",
    )
    args = parser.parse_args()
    if not args.show_window:
        parser.error("Explicit --show-window is required")
    if args.cohorts and (args.comparison != "arena" or args.suite != "matrix"):
        parser.error("--cohorts requires --comparison arena --suite matrix")
    if args.reverse_pairs and args.comparison != "arena":
        parser.error("--reverse-pairs requires --comparison arena")
    args.output.mkdir(parents=True, exist_ok=False)
    fast = ["--scale", "1", "--threads", "4", "--cpu-arena", "--no-spinning", "--det-limit", "640"]
    jobs = []
    for profile in ("discount", "game"):
        for mode in ("baseline", "cpu"):
            jobs.append(
                (
                    f"{profile}-{mode}-long",
                    profile,
                    mode,
                    [
                        "--synthetic-count",
                        "40" if args.suite == "matrix" else "1",
                        "--exposures-ms",
                        "2000",
                    ],
                )
            )
    if args.suite == "matrix":
        for profile in ("discount", "game"):
            jobs.append((f"{profile}-cpu-short", profile, "cpu", ["--synthetic-count", "4"]))
        for mode in ("baseline", "cpu"):
            jobs.append(
                (
                    f"screenshots-{mode}",
                    "game",
                    mode,
                    ["datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json"],
                )
            )
    if args.comparison == "arena":
        # Pair identical inputs; alternate pair order to reduce systematic order bias.
        cases = [
            ("discount-long", "discount", ["--synthetic-count", "40", "--exposures-ms", "2000"]),
            ("game-long", "game", ["--synthetic-count", "40", "--exposures-ms", "2000"]),
            ("discount-short", "discount", ["--synthetic-count", "4"]),
            ("game-short", "game", ["--synthetic-count", "4"]),
            (
                "screenshots",
                "game",
                ["datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json"],
            ),
        ]
        if args.suite == "smoke":
            cases = [
                (f"{p}-smoke", p, ["--synthetic-count", "1", "--exposures-ms", "2000"])
                for p in ("discount", "game")
            ]
        jobs = []
        for index, (name, profile, source) in enumerate(cases):
            if args.cohorts and name not in args.cohorts:
                continue
            modes = (
                ("arena-on", "arena-off")
                if (index + int(args.reverse_pairs)) % 2 == 0
                else ("arena-off", "arena-on")
            )
            jobs.extend((f"{name}-{mode}", profile, mode, source) for mode in modes)
    results = []
    for name, profile, mode, source in jobs:
        report = args.output / f"{name}.jsonl"
        command = [
            sys.executable,
            "scripts/game_playback.py",
            *source,
            "--seed",
            "20261105",
            "--profile",
            profile,
            "--profile-inference",
            "--precise-stimulus",
            "--drain-ms",
            "1000",
            "--report",
            str(report),
        ]
        if mode in {"cpu", "arena-on"}:
            command.extend(fast)
        elif mode == "arena-off":
            command.extend(flag for flag in fast if flag != "--cpu-arena")
        if args.native_clipboard:
            command.extend(["--clipboard", "windows"])
        print(json.dumps({"name": name, "command": command}), flush=True)
        with (args.output / f"{name}-console.txt").open("x", encoding="utf-8") as console:
            completed = subprocess.run(
                command, stdout=console, stderr=subprocess.STDOUT, check=False
            )
        rows = (
            [json.loads(line) for line in report.read_text().splitlines()]
            if report.exists()
            else []
        )
        result = rows[-1] if rows and rows[-1].get("event") == "test_result" else {}
        session = next((row for row in rows if row["event"] == "summary"), {})
        failure = session.get("failure")
        complete = capture_completed(rows)
        record = {
            "name": name,
            "command": command,
            "exit_code": completed.returncode,
            "session_failure": failure,
            "completed_schedule": complete,
            **{
                k: result.get(k)
                for k in (
                    "passed",
                    "exact_copies",
                    "incorrect_writes",
                    "abstentions",
                    "readback_mismatches",
                    "late_writes",
                    "timings",
                )
            },
        }
        results.append(record)
        (args.output / "matrix.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(record), flush=True)
        if (
            not complete
            or result["incorrect_writes"]
            or result["readback_mismatches"]
            or result["late_writes"]
        ):
            return 1  # Stop native tests immediately on incorrect or late writes.
    return int(any(not row["passed"] for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
