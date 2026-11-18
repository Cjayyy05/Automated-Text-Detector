"""Exercise the simulator with Qt's offscreen platform."""

import json
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPalette  # noqa: E402
from PySide6.QtTest import QSignalSpy, QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QColorDialog, QTextEdit  # noqa: E402

from scripts import livestream_code_simulator as simulator  # noqa: E402


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication(["simulator-test", "-platform", "offscreen"])
    widget = simulator.Simulator(tmp_path / "reveals.jsonl")
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def test_countdown_reveals_the_original_formatted_multiline_text(window, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(simulator, "perf_counter", lambda: clock[0])
    original = "  MixED\n\n<b>Literal</b> & café\n\tLast  \n"
    assert window.findChildren(QTextEdit) == [window.editor]
    assert window.seconds.value() == 5
    window.editor.setPlainText(original)
    # Qt's Windows offscreen plugin can have an empty system font database.
    chosen_font = QFont("Consolas")
    monkeypatch.setattr(window.family, "currentFont", lambda: chosen_font)
    window.family.currentFontChanged.emit(chosen_font)
    window.font_size.setValue(27)
    window.bold.setChecked(True)
    window.italic.setChecked(True)
    window.alignment.setCurrentText("Right")
    for button, color in [(window.text_color, "#86efac"), (window.background_color, "#1e293b")]:
        monkeypatch.setattr(QColorDialog, "exec", lambda _: 1)
        monkeypatch.setattr(QColorDialog, "selectedColor", lambda _, color=color: QColor(color))
        button.click()

    window.editor.selectAll()
    window.start.click()
    assert window.timer.isActive()
    assert not window.editor.isVisible()
    assert not window.formatting.isVisible()
    assert window.counter.text() == "5"
    assert not window.reveal_log.exists()
    clock[0] = 101
    window.timer.stop()
    window.timer.timeout.emit()
    assert window.counter.text() == "4"
    clock[0] = 105
    window.timer.stop()
    window.timer.timeout.emit()

    assert window.editor.isVisible() and not window.countdown.isVisible()
    assert not window.formatting.isVisible()
    assert window.editor.isReadOnly()
    assert not window.editor.textCursor().hasSelection()
    assert window.editor.toPlainText() == original
    document = window.editor.document()
    font = document.defaultFont()
    assert font.family() == "Consolas" and font.pointSize() == 27
    assert font.bold() and font.italic()
    assert document.defaultTextOption().alignment() == Qt.AlignmentFlag.AlignRight
    assert document.begin().layout().lineAt(0).naturalTextRect().x() > 0
    palette = window.editor.palette()
    assert palette.color(QPalette.ColorRole.Text) == QColor("#86efac")
    assert palette.color(QPalette.ColorRole.Base) == QColor("#1e293b")
    (line,) = window.reveal_log.read_text(encoding="utf-8").splitlines()
    event = json.loads(line)
    assert set(event) == {"event", "utc", "perf_counter_ns"}
    assert event["event"] == "reveal" and event["perf_counter_ns"] > 0
    assert datetime.fromisoformat(event["utc"]).utcoffset().total_seconds() == 0

    window.reset.click()
    assert window.formatting.isVisible() and not window.editor.isReadOnly()
    assert window.editor.toPlainText() == original
    window.reset.click()
    assert window.editor.toPlainText() == ""
    assert window.seconds.value() == 5 and window.font_size.value() == 30


def test_escape_cancels_then_real_qt_timer_can_reveal(window):
    window.editor.setPlainText("first line\nsecond line")
    window.seconds.setValue(1)
    window.start.click()
    QTest.keyClick(window.reset, Qt.Key.Key_Escape)
    assert not window.timer.isActive()
    assert window.editor.isVisible() and not window.editor.isReadOnly()
    assert not window.reveal_log.exists()

    window.start.click()
    for _ in range(60):
        if window.editor.isVisible():
            break
        QTest.qWait(50)
    assert window.editor.isVisible() and window.editor.isReadOnly()
    assert window.editor.toPlainText() == "first line\nsecond line"
    assert window.reveal_log.exists()
    QTest.keyClick(window.reset, Qt.Key.Key_Escape)
    assert window.formatting.isVisible() and not window.editor.isReadOnly()


def test_editor_copy_and_cut_do_not_write_to_clipboard(window):
    changes = QSignalSpy(QApplication.clipboard().dataChanged)
    window.editor.setPlainText("test fixture")
    window.editor.selectAll()
    QTest.keySequence(window.editor, "Ctrl+C")
    QTest.keySequence(window.editor, "Ctrl+X")
    assert changes.count() == 0
    assert window.editor.toPlainText() == "test fixture"
