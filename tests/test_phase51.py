"""Validate actual local sessions, not merely the CLI argument value."""

from pathlib import Path

import pytest

from stream_code_capture.ocr import RapidRecognizer


def test_zero_capture_report_without_a_schedule_is_not_a_completed_run(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from phase5_qualification import capture_completed

    assert not capture_completed(
        [
            {"event": "summary", "failure": None},
            {"event": "test_result", "captured_events": 0, "errors": []},
        ]
    )


@pytest.mark.parametrize("failure,captured", [("Capture stalled", 2), (None, 0), (None, 1)])
def test_capture_failure_or_missing_events_abort_qualification(failure, captured, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from phase5_qualification import capture_completed

    rows = [
        {"event": "test_config", "schedule": [{}, {}]},
        {"event": "summary", "failure": failure},
        {
            "event": "test_result",
            "captured_events": captured,
            "errors": [],
            "incorrect_writes": 0,
            "readback_mismatches": 0,
            "late_writes": 0,
        },
    ]
    assert not capture_completed(rows)  # Zero unsafe writes is insufficient evidence.
    rows[1]["failure"] = None
    rows[2]["captured_events"] = 2
    rows[2]["passed"] = False  # Accuracy abstentions do not invalidate capture timing.
    assert capture_completed(rows)


@pytest.mark.ocr
@pytest.mark.parametrize("arena", [False, True])
def test_warmed_detector_and_recognizer_apply_requested_arena(arena, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from qualification_metrics import ocr_options

    recognizer = RapidRecognizer(
        scale=1, threads=4, cpu_arena=arena, allow_spinning=False, det_limit=640
    )
    recognizer.warmup()
    for options in ocr_options(recognizer).values():
        assert options["cpu_arena"] is arena
        assert options["threads"] == 4 and options["inter_threads"] == 1
        assert options["intra_spinning"] == options["inter_spinning"] == "0"
        assert options["providers"][0] == "CPUExecutionProvider"
