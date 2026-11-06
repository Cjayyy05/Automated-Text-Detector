import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "manual_batch", Path(__file__).resolve().parents[1] / "scripts/manual_clipboard_batch.py"
)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def test_plan_balances_profiles_and_preserves_single_code():
    tasks = batch.plan()
    assert len(tasks) == 24
    assert sum(t["profile"] == "discount" for t in tasks) == 13
    assert sum(t["profile"] == "game" for t in tasks) == 11
    assert len({t["seed"] for t in tasks}) == 24
    assert {t["exposure_ms"] for t in tasks} == {2000, 5000, 10000}
    args = batch.command(tasks[0], Path("unique.jsonl"))
    assert args[args.index("--synthetic-count") + 1] == "1"
    assert args[args.index("--clipboard") + 1] == "windows"
    assert "--confirmations" not in args


def test_report_requires_manual_exact_match_and_success(tmp_path):
    # Inject a minimal harness report so this test is portable and needs no display.
    report = tmp_path / "report.jsonl"
    config = {
        "event": "test_config",
        "profile": "game",
        "seed": 123,
        "schedule": [{"kind": "new", "expected": "EXACT", "visible_s": 2}],
    }
    result = {
        "event": "test_result",
        "passed": True,
        "exact_copies": 1,
        "incorrect_writes": 0,
        "readback_mismatches": 0,
        "late_writes": 0,
        "session_failure": None,
        "errors": [],
        "writes": [
            {
                "code": "EXACT",
                "expected": "EXACT",
                "correct": True,
                "readback": {"value": "EXACT", "error": None},
                "readback_correct": True,
            }
        ],
        "by_exposure": [{"copied_before_disappearance": 1}],
    }
    task = {"profile": "game", "seed": 123, "exposure_ms": 2000}
    report.write_text(json.dumps(config) + "\n" + json.dumps(result))
    assert batch.verify(report, task, "EXACT", 0)["passed"]
    for pasted in ("", "exact", "EXACT "):
        assert not batch.verify(report, task, pasted, 0)["passed"]
    assert not batch.verify(report, task, "EXACT", 1)["passed"]
    assert not batch.verify(report, task, "EXACT", None)["passed"]
    result["readback_mismatches"] = 1
    report.write_text(json.dumps(config) + "\n" + json.dumps(result))
    assert not batch.verify(report, task, "EXACT", 0)["passed"]
    batch.save_new(tmp_path / "saved.json", {"passed": False})
    import pytest

    with pytest.raises(FileExistsError):
        batch.save_new(tmp_path / "saved.json", {"passed": True})


def test_resume_skips_completed_and_retains_failed_attempts(tmp_path, monkeypatch, capsys):
    task = batch.plan()[0]
    for name, passed in (("done", True), ("failed", False)):
        folder = tmp_path / f"attempt-{name}"
        folder.mkdir()
        batch.save_new(folder / "attempt.json", {"task_index": 0, "task": task})
        batch.save_new(folder / "manual-result.json", {"passed": passed})
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    batch.run(tmp_path)
    output = capsys.readouterr().out
    assert "7/30" in output
    assert "20261204" in output
    assert (tmp_path / "attempt-failed/manual-result.json").exists()


def test_interrupted_attempt_never_passes_without_confirmation(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "attempt-interrupted"
    folder.mkdir()
    batch.save_new(folder / "attempt.json", {"task_index": 0, "task": batch.plan()[0]})
    answers = iter(["ABANDON", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    batch.run(tmp_path)
    result = json.loads((folder / "manual-result.json").read_text())
    assert result["passed"] is False
    assert "6/30" in capsys.readouterr().out
