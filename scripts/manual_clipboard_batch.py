"""Supervised G2 paste checks. Each native write requires an explicit operator start."""

import argparse
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BASE_MATCHES = 6  # Recorded ledger: two Discount and four Game matches.


def plan():
    tasks = []
    for index in range(13):
        tasks.append({"profile": "discount", "seed": 20261301 + index})
        if index < 11:
            tasks.append({"profile": "game", "seed": 20261204 + index})
    for index, task in enumerate(tasks):
        task["exposure_ms"] = (2000, 5000, 10000)[index % 3]
    return tasks


def save_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def verify(report, task, pasted, exit_code):
    """Read actual harness evidence, independently of the operator's claimed verdict."""
    errors = []
    expected = None
    try:
        rows = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()]
        configs = [row for row in rows if row.get("event") == "test_config"]
        results = [row for row in rows if row.get("event") == "test_result"]
        if len(configs) != 1 or len(results) != 1:
            raise ValueError("Missing or repeated test_config/test_result")
        config, result = configs[0], results[0]
        new = [item for item in config["schedule"] if item["kind"] == "new"]
        if len(new) != 1:
            raise ValueError("Expected exactly one new code")
        expected = new[0]["expected"]
        if config["profile"] != task["profile"] or config["seed"] != task["seed"]:
            errors.append("Report profile/seed mismatch")
        if new[0]["visible_s"] * 1000 != task["exposure_ms"]:
            errors.append("Report exposure mismatch")
        writes = result["writes"]
        if len(writes) != 1:
            errors.append(f"Expected one write, found {len(writes)} (miss or extra write)")
        for write in writes:
            if (
                write["code"] != expected
                or write["expected"] != expected
                or write["correct"] is not True
                or write["readback"]["value"] != expected
                or write["readback"].get("error") is not None
                or write["readback_correct"] is not True
            ):
                errors.append("Native write/readback mismatch or error")
        if result["passed"] is not True or result["exact_copies"] != 1:
            errors.append("Harness did not pass with one exact copy")
        for field in ("incorrect_writes", "readback_mismatches", "late_writes"):
            if result[field] != 0:
                errors.append(f"{field}={result[field]}")
        if result["session_failure"] is not None or result["errors"]:
            errors.append(f"Harness failure/errors: {result['session_failure']} {result['errors']}")
        if sum(item["copied_before_disappearance"] for item in result["by_exposure"]) != 1:
            errors.append("Copy before disappearance unconfirmed")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Incomplete or invalid report: {exc}")
    if exit_code != 0:
        errors.append(f"Harness exit code: {exit_code}")
    if not pasted or pasted != expected:
        errors.append("Manual pasted text missing or mismatched")
    return {"passed": not errors, "expected": expected, "pasted": pasted, "errors": errors}


def command(task, report):
    return [
        sys.executable,
        str(ROOT / "scripts/game_playback.py"),
        "--profile",
        task["profile"],
        "--synthetic-count",
        "1",
        "--seed",
        str(task["seed"]),
        "--exposures-ms",
        str(task["exposure_ms"]),
        "--precise-stimulus",
        "--drain-ms",
        "1000",
        "--scale",
        "1",
        "--threads",
        "4",
        "--no-spinning",
        "--det-limit",
        "640",
        "--clipboard",
        "windows",
        "--report",
        str(report),
    ]


@contextmanager
def exclusive_session(directory):
    # OS lock is released even on process termination. The file can safely persist.
    import msvcrt

    with (directory / "session.lock").open("a+b") as stream:
        stream.write(b"\0")
        stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def run(directory):
    tasks = plan()
    while True:
        completed = set()
        pending = []
        for path in sorted(directory.glob("attempt-*/attempt.json")):
            attempt = json.loads(path.read_text(encoding="utf-8"))
            result_path = path.parent / "manual-result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if result["passed"]:
                    completed.add(attempt["task_index"])
            else:
                pending.append((path.parent, attempt))
        print(f"\n{BASE_MATCHES + len(completed)}/30 confirmed matches. G2 remains pending.")
        if pending:
            folder, attempt = pending[0]
            report = folder / "report.jsonl"
            print(f"Unfinished attempt: {report}")
            print("Confirm only if you retained this attempt's Notepad paste.")
            if (
                input("Enter REVIEW to enter retained text, or ABANDON to retain as failed: ")
                == "REVIEW"
            ):
                pasted = input("Exact retained Notepad text (blank for missing copy): ")
                exit_path = folder / "exit.json"
                status = (
                    json.loads(exit_path.read_text())["exit_code"] if exit_path.exists() else None
                )
                outcome = verify(report, attempt["task"], pasted, status)
            else:
                outcome = {"passed": False, "errors": ["Interrupted/unconfirmed attempt retained"]}
            save_new(folder / "manual-result.json", outcome)
            print(json.dumps(outcome, indent=2))
            continue
        remaining = [i for i in range(len(tasks)) if i not in completed]
        if not remaining:
            print("30 manual matches recorded. Full G2 review and other checks remain pending.")
            return
        index = remaining[0]
        task = tasks[index]
        print(f"Next: {task}. Native test replaces clipboard. Keep GUI dry-run and stopped.")
        if input("Type RUN to start one test, or Enter to save and exit: ") != "RUN":
            return
        folder = directory / f"attempt-{uuid4().hex}"
        folder.mkdir()
        report = folder / "report.jsonl"
        args = command(task, report)
        save_new(folder / "attempt.json", {"task_index": index, "task": task, "command": args})
        print(f"Report: {report}")
        with (folder / "console.txt").open("x", encoding="utf-8") as console:
            status = subprocess.run(
                args, cwd=ROOT, stdout=console, stderr=subprocess.STDOUT
            ).returncode
        save_new(folder / "exit.json", {"exit_code": status})
        print("Now press Ctrl+V in Notepad BEFORE copying anything else.")
        pasted = input("Enter the exact text pasted in Notepad (blank for missing copy): ")
        outcome = verify(report, task, pasted, status)
        save_new(folder / "manual-result.json", outcome)
        print("PASS" if outcome["passed"] else "FAIL")
        print(json.dumps(outcome, indent=2))
        print(f"Diagnostics: {folder / 'console.txt'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "artifacts/g2-supervised")
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_session(args.directory):
            run(args.directory.resolve())
    except (EOFError, KeyboardInterrupt):
        print("\nStopped. Evidence retained; rerun the same command to resume.")


if __name__ == "__main__":
    main()
