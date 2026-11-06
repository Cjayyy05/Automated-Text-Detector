"""No test reads the system clipboard or plays actual audio."""

from threading import Event, get_ident

import pytest

from stream_code_capture import notifications
from stream_code_capture.live import Controls


def copied():
    return {
        "status": "copied",
        "dry_run": False,
        "code": "AB23CD45EF",
        "sequence": 9,
        "captured_ns": 1234,
        "error": None,
    }


def enabled_controls():
    controls = Controls()
    controls.inhibit.clear()
    return controls


def test_async_readback_precedes_single_sound_and_duplicate_is_ignored(monkeypatch):
    entered, release, played = Event(), Event(), Event()
    order = []
    owner = get_ident()

    def read():
        assert get_ident() != owner
        order.append("readback")
        entered.set()
        assert release.wait(2)
        return "AB23CD45EF"

    def play():
        order.append("sound")
        played.set()

    monkeypatch.setattr(notifications, "clipboard_text", read)
    monkeypatch.setattr(notifications, "play_copy_sound", play)
    notifier = notifications.CopySound(enabled_controls())
    notifier.notify(copied())
    assert entered.wait(2)  # notify returned while verification is still pending.
    notifier.notify(copied())
    release.set()
    assert played.wait(2)
    assert order == ["readback", "sound"]


@pytest.mark.parametrize(
    "change",
    [
        {"status": "would_copy", "dry_run": True},
        {"status": "clipboard_failed"},
        {"status": "no_candidate"},
        {"status": "stale"},
        {"dry_run": True},
        {"error": "write failed"},
    ],
)
def test_ineligible_events_never_schedule_notifications(monkeypatch, change):
    def unexpected(*args, **kwargs):
        pytest.fail("Notification scheduled for an ineligible event")

    monkeypatch.setattr(notifications, "Thread", unexpected)
    notifier = notifications.CopySound(enabled_controls())
    notifier.notify(copied() | change)
    assert notifier.seen == set()


@pytest.mark.parametrize("condition", ["mismatch", "read_error", "audio_error", "stop", "disarm"])
def test_unverified_or_cancelled_notification_is_silent_and_errors_are_contained(
    monkeypatch, condition
):
    controls = enabled_controls()
    sounds = []

    def read():
        if condition == "read_error":
            raise RuntimeError("Clipboard busy")
        if condition in {"stop", "disarm"}:
            controls.send(condition)
        return "OTHER" if condition == "mismatch" else "AB23CD45EF"

    def play():
        if condition == "audio_error":
            raise RuntimeError("No audio device")
        sounds.append(True)

    monkeypatch.setattr(notifications, "clipboard_text", read)
    monkeypatch.setattr(notifications, "play_copy_sound", play)
    notifications.CopySound(controls).verify_and_play("AB23CD45EF", controls.generation)
    assert sounds == []


def make_wav(path):
    import wave

    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        output.writeframes(b"\x00" * 160)
    return str(path)


@pytest.mark.parametrize("state", ["custom", "default", "missing", "invalid", "play_error"])
def test_custom_wav_or_default_playback_is_async_and_falls_back(monkeypatch, tmp_path, state):
    import sys
    from types import SimpleNamespace

    calls = []
    path = make_wav(tmp_path / "tone.wav")
    if state == "missing":
        (tmp_path / "tone.wav").unlink()
    elif state == "invalid":
        (tmp_path / "tone.wav").write_bytes(b"bad")

    def play(value, flags):
        calls.append((value, flags))
        if state == "play_error" and value == path:
            raise RuntimeError("Unreadable sound")

    monkeypatch.setitem(
        sys.modules,
        "winsound",
        SimpleNamespace(
            PlaySound=play,
            SND_FILENAME=1,
            SND_ALIAS=2,
            SND_ASYNC=4,
            SND_NODEFAULT=8,
        ),
    )
    notifications.play_copy_sound(None if state == "default" else path)
    assert all(flags & 4 for _, flags in calls)
    if state == "custom":
        assert calls == [(path, 13)]
    else:
        assert calls[-1] == ("SystemAsterisk", 14)


def test_verified_copy_uses_custom_path(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications, "clipboard_text", lambda: "AB23CD45EF")
    monkeypatch.setattr(notifications, "play_copy_sound", calls.append)
    controls = enabled_controls()
    notifications.CopySound(controls, "local.wav").verify_and_play(
        "AB23CD45EF", controls.generation
    )
    assert calls == ["local.wav"]
