"""Exercise Qt controls without a display, DXGI or the system clipboard."""

from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from stream_code_capture import gui  # noqa: E402
from stream_code_capture.capture import CaptureWorker  # noqa: E402
from stream_code_capture.clipboard import MemoryClipboard  # noqa: E402
from stream_code_capture.domain import Rect  # noqa: E402
from stream_code_capture.live import LiveSession  # noqa: E402


@pytest.mark.parametrize("scale", [1, 1.25])
def test_mapping_uses_painted_extent_and_physical_image_size(scale):
    area = QRectF(20, 50, 960 / scale, 540 / scale)
    start = QPointF(20 + 400 / scale, 50 + 300 / scale)
    end = QPointF(20 + 160 / scale, 50 + 100 / scale)
    assert gui.physical_rect(start, end, area, 1920, 1080) == Rect(320, 200, 800, 600)
    assert gui.physical_rect(start, QPointF(2000, 2000), area, 1920, 1080).right == 1920
    with pytest.raises(ValueError):
        gui.physical_rect(QPointF(0, 0), end, area, 1920, 1080)
    with pytest.raises(ValueError):
        gui.physical_rect(start, start, area, 1920, 1080)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(["test_gui", "-platform", "offscreen"])


def until(app, predicate):
    deadline = monotonic() + 5
    while not predicate() and monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    class Settings(QSettings):
        def __init__(self, *args):
            super().__init__(str(tmp_path / "sounds.ini"), QSettings.Format.IniFormat)

    monkeypatch.setattr(gui, "QSettings", Settings)
    monitor = gui.Monitor(0, 1, "Test monitor", 1920, 1080)
    monkeypatch.setattr(gui, "monitors", lambda: [monitor])
    window = gui.Window()
    window.show()
    until(app, lambda: window.job is None)
    yield window
    window.close()
    until(app, lambda: window.job is None and not window.isVisible())


def select_region(app, window, monkeypatch):
    image = QImage(1920, 1080, QImage.Format.Format_BGR888)
    image.fill(Qt.GlobalColor.black)
    monkeypatch.setattr(gui, "preview", lambda *_: image)
    assert not window.start.isEnabled()
    window.snapshot.click()
    until(app, lambda: window.job is None)
    area = window.canvas.displayed()
    QTest.mousePress(
        window.canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(area.left() + area.width() * 0.2), int(area.top() + area.height() * 0.2)),
    )
    QTest.mouseRelease(
        window.canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(area.left() + area.width() * 0.7), int(area.top() + area.height() * 0.7)),
    )
    assert window.start.isEnabled()


@pytest.mark.parametrize("profile", ["Discount", "Game"])
def test_live_controls_and_close_release_capture(app, window, monkeypatch, profile):
    select_region(app, window, monkeypatch)
    window.profile.setCurrentText(profile)
    closed = Event()
    sessions = []

    class Recognizer:
        provider = "CPUExecutionProvider"
        model_paths = [Path("det.onnx"), Path("rec.onnx")]

        def warmup(self):
            pass

        def recognize(self, pixels):
            return []

    class Source:
        tick = 0

        def grab(self):
            self.tick += 1
            pixels = np.zeros((32, 32, 3), dtype=np.uint8)
            pixels[8:16] = 255
            pixels[0, 0] = self.tick % 255
            return pixels

        def close(self):
            closed.set()

    def session(recognizer, config, controls, emit):
        assert config.dry_run and config.profile == profile.lower()
        instance = LiveSession(recognizer, config, controls, emit, worker=CaptureWorker(Source))
        assert isinstance(instance.clipboard, MemoryClipboard)
        instance.pipeline.roi = Rect(0, 0, 32, 32)
        sessions.append(instance)
        return instance

    monkeypatch.setattr(gui, "RapidRecognizer", Recognizer)
    monkeypatch.setattr(gui, "LiveSession", session)
    window.start.click()
    assert not window.arm.isEnabled()
    until(app, window.arm.isEnabled)
    window.arm.click()
    until(app, window.disarm.isEnabled)
    window.disarm.click()
    until(app, window.arm.isEnabled)
    if profile == "Discount":
        window.stop.click()
        until(app, lambda: window.job is None)
        assert window.isVisible()
    else:
        window.close()
        until(app, lambda: not window.isVisible())
    assert closed.is_set()
    assert not sessions[0].policy.armed
    assert "CPUExecutionProvider" in window.ocr_info.text()
    assert "det.onnx / rec.onnx" in window.ocr_info.text()
    assert "(last session)" in window.ocr_info.text()
    assert "device 0 / output 1" in window.capture_info.text()
    assert window.clipboard_info.text() == "Clipboard: memory · dry run"


def test_preview_error_keeps_start_disabled(app, window, monkeypatch):
    def fail(*_):
        raise RuntimeError("capture unavailable")

    monkeypatch.setattr(gui, "preview", fail)
    window.snapshot.click()
    until(app, lambda: window.job is None)
    assert "capture unavailable" in window.error.text()
    assert window.snapshot.isEnabled() and not window.start.isEnabled()


def test_preview_owns_bgr_image_and_releases_source(monkeypatch):
    monitor = gui.Monitor(0, 1, "Test monitor", 4, 2)
    pixels = np.full((2, 4, 3), (11, 22, 33), dtype=np.uint8)
    closed = Event()

    class Source:
        def __init__(self, roi, device, output):
            assert (roi, device, output) == (Rect(0, 0, 4, 2), 0, 1)

        def grab(self):
            return pixels

        def close(self):
            closed.set()
            pixels.fill(0)

    monkeypatch.setattr(gui, "monitors", lambda: [monitor])
    monkeypatch.setattr(gui, "DxcamSource", Source)
    image = gui.preview(monitor, lambda: False)
    assert closed.is_set()
    assert (image.width(), image.height()) == (4, 2)
    assert image.pixelColor(3, 1).getRgb() == (33, 22, 11, 255)


def test_session_error_and_confirmation_update_controls(app, window, monkeypatch):
    select_region(app, window, monkeypatch)

    def session(monitor, roi, profile, controls, emit):
        emit({"event": "ready"})
        emit({"event": "armed"})
        emit({"event": "confirmation", "code": "AB23CD45EF", "error": None})
        raise RuntimeError("Capture stalled")

    monkeypatch.setattr(gui, "run_session", session)
    window.start.click()
    until(app, lambda: window.job is None)
    assert "AB23CD45EF" in window.code.text()
    assert "Capture stalled" in window.error.text()
    assert window.start.isEnabled() and not window.arm.isEnabled()


def test_native_opt_in_requires_confirmation_and_resets(app, window, monkeypatch):
    select_region(app, window, monkeypatch)
    assert not window.native.isChecked()
    window.native.setChecked(True)
    assert "consent required" in window.clipboard_info.text()
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: gui.QMessageBox.Cancel)
    window.start.click()
    assert window.controls is None and window.job is None
    calls = []

    def session(
        monitor, roi, profile, controls, emit, *, native=False, sound=False, sound_path=None
    ):
        calls.append(native)
        emit({"event": "ready"})
        emit({"event": "confirmation", "code": "AB23CD45EF", "error": None})

    monkeypatch.setattr(gui, "run_session", session)
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: gui.QMessageBox.Yes)
    window.start.click()
    until(app, lambda: window.job is None)
    assert calls == [True]
    assert not window.native.isChecked()
    assert "DRY RUN" in window.badge.text()
    assert "memory" in window.clipboard_info.text()


def test_sound_checkbox_is_optional_and_forwarded_only_to_native_session(app, window, monkeypatch):
    select_region(app, window, monkeypatch)
    assert not window.sound.isChecked()
    window.sound.setChecked(True)
    calls = []

    def session(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(gui, "run_session", session)
    window.start.click()
    until(app, lambda: window.job is None)
    assert calls == [{}]
    window.native.setChecked(True)
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: gui.QMessageBox.Yes)
    window.start.click()
    until(app, lambda: window.job is None)
    assert calls[-1] == {"native": True, "sound": True, "sound_path": None}


def test_choose_test_remember_and_reset_local_sound(app, window, monkeypatch, tmp_path):
    from test_notifications import make_wav

    path = make_wav(tmp_path / "selected.wav")
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args: (path, ""))
    window.choose_sound.click()
    assert window.sound_path == path
    assert str(window.settings.value("notificationSoundPath")) == path
    other = gui.Window()
    until(app, lambda: other.job is None)
    try:
        assert other.sound_path == path
        calls = []
        monkeypatch.setattr(gui, "play_copy_sound", calls.append)
        other.native.setChecked(True)
        other.test_sound.click()
        until(app, lambda: other.sound_job is None)
        assert calls == [path] and other.controls is None
        assert other.native.isChecked()  # Preview completion never resets session options.
        (tmp_path / "selected.wav").unlink()
        other.update_sound_name()
        assert "unavailable" in other.sound_name.text()
        other.default_sound.click()
        assert other.sound_path is None
        assert other.settings.value("notificationSoundPath") == ""
    finally:
        other.close()


def test_invalid_sound_selection_preserves_previous_choice(window, monkeypatch, tmp_path):
    path = tmp_path / "invalid.wav"
    path.write_bytes(b"invalid")
    monkeypatch.setattr(gui.QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))
    window.choose_sound.click()
    assert window.sound_path is None and "WAV" in window.error.text()


def test_diagnostics_region_edit_and_processing_error(app, window, monkeypatch):
    select_region(app, window, monkeypatch)
    replacement = Rect(10, 20, 300, 200)
    window.canvas.roi = replacement
    window.canvas.selected.emit(replacement)
    assert "10, 20 → 300, 200" in window.region.text()
    window.handle_event(
        {
            "event": "session_info",
            "provider": "CPUExecutionProvider",
            "models": ["det.onnx", "rec.onnx"],
        }
    )
    window.handle_event({"event": "error", "error": "capture invalidated"})
    assert window.error.text() == "capture invalidated"
    assert "CPUExecutionProvider" in window.ocr_info.text()
    window.clear_preview()
    assert window.canvas.roi is None and not window.start.isEnabled()


def test_baseline_progress_and_ready_reach_gui(window):
    from stream_code_capture.live import Controls

    window.controls = Controls()
    window.handle_event(
        {
            "event": "baseline_progress",
            "reason": "Recognizing baseline pixels",
            "captured": 1,
            "observations": 0,
            "rejected": 2,
            "ocr_ms": 1800,
        }
    )
    assert "Recognizing baseline pixels" in window.status.text()
    assert "1 changed frames" in window.stats.text()
    assert "2 rejected" in window.stats.text() and "1800 ms" in window.stats.text()
    assert not window.arm.isEnabled()
    window.handle_event({"event": "ready"})
    assert window.arm.isEnabled() and "Ready" in window.status.text()
    window.controls = None


def test_ocr_details_show_raw_read_and_decision_without_changing_state(window):
    from stream_code_capture.policy import DecisionPolicy

    policy = DecisionPolicy()
    frame = {
        "status": "disarmed",
        "code": None,
        "candidates": ["Q8M4Z7P2VK"],
        "lines": [
            {
                "text": "CODE: Q8M4Z7P2VK",
                "confidence": 0.98,
                "rejection": None,
                "box": {"left": 0, "top": 0, "right": 300, "bottom": 24},
            },
            {
                "text": "100% off",
                "confidence": 0.98,
                "rejection": None,
                "box": {"left": 0, "top": 30, "right": 175, "bottom": 54},
            },
        ],
    }
    detail = gui.describe_ocr(frame, policy)
    window.handle_event({"event": "ocr_detail", "text": detail})
    assert "CODE: Q8M4Z7P2VK" in window.ocr_detail.toPlainText()
    assert "eligible candidate with code label" in detail
    assert not window.armed
    policy.suppressed.add("Q8M4Z7P2VK")
    assert "suppressed by baseline" in gui.describe_ocr(frame, policy)
    frame["lines"][0]["rejection"] = "insufficient_source_resolution"
    assert "insufficient_source_resolution" in gui.describe_ocr(frame, policy)


def test_ocr_details_separate_stale_from_missing_token_or_label():
    from dataclasses import asdict

    from stream_code_capture.domain import Rect, TextLine
    from stream_code_capture.policy import DecisionPolicy

    label = TextLine("Code", 0.987, Rect(8, 60, 85, 85))
    token = TextLine("AK74ZM53Q8", 0.993, Rect(97, 60, 267, 85))
    heading = TextLine("LIMITED TIME OFFER", 0.99, Rect(7, 20, 270, 45))
    noise = [TextLine("market price", 0.99, Rect(500, 100, 600, 120))] * 20
    frame = {
        "status": "stale",
        "code": None,
        "lines": [asdict(line) for line in [*noise, label, token, heading]],
    }
    detail = gui.describe_ocr(frame, DecisionPolicy())
    assert "Expired frame" in detail
    assert "LIMITED TIME OFFER" in detail and "limited context" in detail
    assert "eligible candidate with nearby context" in detail
    assert "Code [0.987]" in detail

    frame["lines"] = [asdict(label), asdict(heading)]
    assert "Code [0.987] (8,60)–(85,85) · unsupported exact code format" in gui.describe_ocr(
        frame, DecisionPolicy()
    )


def test_scope_is_checked_before_guarded_clipboard_and_stops_on_failure():
    from stream_code_capture.live import Controls, GuardedClipboard

    controls = Controls()
    target = MemoryClipboard()
    controls.inhibit.clear()

    class Scope:
        fail = False

        def check(self):
            if self.fail:
                raise RuntimeError("display changed")
            controls.inhibit.set()  # Simulate inhibition during slow inventory.

    scope = Scope()
    guarded = GuardedClipboard(target, controls, lambda: True)
    clipboard = gui.ScopedClipboard(guarded, scope, controls)
    with pytest.raises(RuntimeError, match="cancelled"):
        clipboard.write("EXAMPLE234")
    assert not target.writes
    scope.fail = True
    with pytest.raises(RuntimeError, match="display changed"):
        clipboard.write("EXAMPLE234")
    assert controls.stop.is_set() and not target.writes


def test_native_capture_checks_scope_while_idle(monkeypatch):
    clock = [0.0]

    class Scope:
        calls = 0
        fail = False

        def check(self):
            self.calls += 1
            if self.fail:
                raise RuntimeError("topology changed")

    scope = Scope()
    monkeypatch.setattr(gui, "monotonic", lambda: clock[0])
    monkeypatch.setattr(gui.DxcamSource, "__init__", lambda *args: None)
    monkeypatch.setattr(gui.DxcamSource, "grab", lambda self: None)
    source = gui.ScopedSource(gui.Monitor(0, 0, "center", 1920, 1080), Rect(0, 0, 100, 100), scope)
    assert source.grab() is None
    assert scope.calls == 2
    clock[0] = 0.25
    assert source.grab() is None
    assert scope.calls == 2
    clock[0] = 0.51
    scope.fail = True
    with pytest.raises(RuntimeError, match="topology changed"):
        source.grab()


@pytest.mark.parametrize("fail_write", [False, True])
def test_native_session_uses_guarded_adapter_and_forwards_result(monkeypatch, fail_write):
    from stream_code_capture import live
    from stream_code_capture.domain import TextLine

    controls = live.Controls()
    visible = Event()
    monitor = gui.Monitor(0, 0, "center", 1920, 1080)
    target = MemoryClipboard()
    events = []

    class Scope:
        def __init__(self, *args):
            pass

        def check(self):
            pass

    class Source:
        tick = 0

        def __init__(self, *args):
            pass

        def grab(self):
            self.tick += 1
            pixels = np.full((60, 160, 3), 120, np.uint8)
            pixels[:16] = 255
            pixels[0, 0] = self.tick % 255
            return pixels

        def close(self):
            pass

    class Recognizer:
        provider = "CPUExecutionProvider"
        model_paths = [Path("det.onnx"), Path("rec.onnx")]

        def warmup(self):
            pass

        def recognize(self, pixels):
            if not visible.is_set():
                return []
            return [
                TextLine("AB23CD45EF", 0.999, Rect(0, 0, 140, 20)),
                TextLine("100% off", 0.999, Rect(0, 30, 140, 50)),
            ]

    class NativeAdapter:
        def write(self, text):
            if fail_write:
                raise RuntimeError("clipboard busy")
            target.write(text)

    def emit(event):
        events.append(event)
        if event["event"] == "ready":
            controls.send("arm")
        elif event["event"] == "armed":
            visible.set()
        elif event["event"] == "confirmation":
            controls.send("stop")

    monkeypatch.setattr(gui, "NativeScope", Scope)
    monkeypatch.setattr(gui, "ScopedSource", Source)
    monkeypatch.setattr(gui, "RapidRecognizer", Recognizer)
    monkeypatch.setattr(gui, "monitors", lambda: [monitor])
    monkeypatch.setattr(live, "WindowsClipboard", NativeAdapter)
    gui.run_session(monitor, Rect(0, 0, 160, 60), "discount", controls, emit, native=True)
    confirmations = [e for e in events if e["event"] == "confirmation"]
    assert len(confirmations) == 1
    assert bool(confirmations[0]["error"]) == fail_write
    assert target.writes == ([] if fail_write else ["AB23CD45EF"])
    assert events[-1]["event"] == "summary"


@pytest.mark.parametrize("profile", ["game", "discount"])
def test_controlled_stimulus_hides_then_reveals_once(app, monkeypatch, capsys, profile):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from gui_clipboard_stimulus import Stimulus, scenes

    ((scene, expected),) = scenes(20261105, 1, profile)
    window = Stimulus(scene, expected, profile)
    window.show()
    assert not window.revealed
    assert np.all(window.baseline[410:515, 200:800] == (35, 35, 35))
    assert not np.array_equal(window.baseline, window.scene)
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert window.revealed
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert capsys.readouterr().out.count(f"Expected {profile} code: {expected}") == 1
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert not window.isVisible()
