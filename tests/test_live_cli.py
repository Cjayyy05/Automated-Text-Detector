import json
from threading import Event

import pytest

from stream_code_capture import live
from stream_code_capture.cli import parser, run_live


@pytest.mark.parametrize("last_command", ["stop\n", None])
def test_live_console_commands_and_report(monkeypatch, tmp_path, capsys, last_command):
    monitoring = Event()

    def commands():
        yield "start\n"
        assert monitoring.wait(2)
        yield "invalid\n"
        yield " STATUS \n"
        yield "arm\n"
        yield "disarm\n"
        if last_command is not None:
            yield last_command
            pytest.fail("Console read again after stop")

    events = [
        {"event": "started", "dry_run": True},
        {"event": "ready"},
        {"event": "frame", "status": "disarmed", "sequence": 1},
        {"event": "stale_before_ocr", "sequence": 2},
        {"event": "status", "running": True},
        {"event": "armed"},
        {"event": "frame", "status": "would_copy", "code": "TEST1234", "error": None},
        {"event": "disarmed"},
        {"event": "frame", "status": "clipboard_failed", "code": None, "error": "locked"},
        {"event": "summary", "failure": None, "captured": 3},
    ]

    class Session:
        def __init__(self, recognizer, config, controls, emit):
            assert config.dry_run
            self.controls, self.emit = controls, emit

        def run(self, duration):
            assert self.controls.commands.get(timeout=2) == "start"
            for event in events[:4]:
                self.emit(event)
            monitoring.set()
            for expected in ("status", "arm", "disarm", "stop"):
                assert self.controls.commands.get(timeout=2) == expected
            assert self.controls.stop.is_set()
            for event in events[4:]:
                self.emit(event)
            return 0

    report = tmp_path / "live.jsonl"
    args = parser().parse_args(
        ["live", "--roi", "0", "0", "100", "100", "--dry-run", "--report", str(report)]
    )
    monkeypatch.setattr("sys.stdin", commands())
    monkeypatch.setattr(live, "LiveSession", Session)
    assert run_live(args, None) == 0

    stdout, stderr = capsys.readouterr()
    assert "Commands: start, arm, disarm, status, stop" in stderr
    assert [json.loads(line)["event"] for line in stdout.splitlines()] == [
        "started",
        "ready",
        "status",
        "armed",
        "would_copy",
        "disarmed",
        "clipboard_failed",
        "stopped",
    ]
    assert [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()] == events
