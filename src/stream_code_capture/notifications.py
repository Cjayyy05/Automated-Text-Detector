"""Optional native-copy sound. Verification and playback run off the detection thread."""

import logging
import wave
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from .live import Controls

logger = logging.getLogger(__name__)


def clipboard_text() -> str:
    import win32clipboard
    import win32con

    win32clipboard.OpenClipboard()
    try:
        value = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        if not isinstance(value, str):
            raise RuntimeError("Clipboard readback is not Unicode text")
        return value
    finally:
        win32clipboard.CloseClipboard()


def validate_sound_file(path: str) -> None:
    file = Path(path)
    if file.suffix.lower() != ".wav" or not file.is_file():
        raise ValueError("Choose an existing local WAV file.")
    try:
        with wave.open(str(file), "rb") as audio:
            if audio.getnframes() == 0:
                raise ValueError("The WAV file contains no audio.")
    except (OSError, EOFError, wave.Error) as exc:
        raise ValueError("Choose a readable PCM WAV file.") from exc


def play_copy_sound(path: str | None = None) -> None:
    import winsound

    if path:
        try:
            validate_sound_file(path)
            winsound.PlaySound(
                path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
            )
            return
        except (ValueError, RuntimeError, OSError):
            logger.warning("Custom sound unavailable. Using Windows notification sound.")
    winsound.PlaySound(
        "SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT
    )


class CopySound:
    """One notifier per session. Successful-copy event identities are consumed once."""

    def __init__(self, controls: Controls, sound_path: str | None = None) -> None:
        self.controls = controls
        self.sound_path = sound_path
        self.seen: set[tuple[int, int]] = set()
        self.lock = Lock()

    def notify(self, event: dict[str, Any]) -> None:
        if (
            event.get("status") != "copied"
            or event.get("dry_run") is not False
            or event.get("error")
            or not event.get("code")
            or self.controls.stop.is_set()
            or self.controls.inhibit.is_set()
        ):
            return
        identity = (event["sequence"], event["captured_ns"])
        with self.lock:
            if identity in self.seen:
                return
            self.seen.add(identity)
        generation = self.controls.generation
        try:
            Thread(
                target=self.verify_and_play,
                args=(event["code"], generation),
                name="copy-notification",
                daemon=True,
            ).start()
        except RuntimeError:
            logger.warning("Copy notification worker unavailable", exc_info=True)

    def verify_and_play(self, text: str, generation: int) -> None:
        try:
            if self.controls.stop.is_set() or self.controls.inhibit.is_set():
                return
            if clipboard_text() != text:
                logger.warning("Copy sound skipped because clipboard readback differs")
                return
            # Linearize playback initiation with stop/disarm. PlaySound returns
            # immediately with SND_ASYNC, and readback takes place outside this lock.
            with self.controls.lock:
                if (
                    self.controls.stop.is_set()
                    or self.controls.inhibit.is_set()
                    or self.controls.generation != generation
                ):
                    return
                if self.sound_path:
                    play_copy_sound(self.sound_path)
                else:
                    play_copy_sound()
        except Exception:
            # Audio or readback failure must never turn a successful write into a retry.
            logger.warning("Copy sound unavailable or clipboard readback failed", exc_info=True)
