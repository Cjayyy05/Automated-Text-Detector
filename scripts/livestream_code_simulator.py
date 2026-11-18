"""Show user-entered text after a countdown for manual screen OCR testing."""

import json
import sys
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import perf_counter, perf_counter_ns

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeyEvent, QKeySequence, QPalette, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

REVEAL_LOG = Path(__file__).resolve().parents[1] / "artifacts/livestream-simulator-reveals.jsonl"


class Simulator(QWidget):
    def __init__(self, reveal_log: Path = REVEAL_LOG) -> None:
        super().__init__()
        self.setWindowTitle("Livestream Code Simulator")
        self.resize(820, 540)
        self.reveal_log = reveal_log
        self.deadline = 0.0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_countdown)

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setAccessibleName("Reveal text")
        self.editor.setPlaceholderText("Enter the text to reveal")
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.document().setDocumentMargin(24)

        self.family = QFontComboBox()
        font_name = self.family.lineEdit()
        assert font_name is not None  # QFontComboBox is editable by default.
        font_name.setReadOnly(True)
        self.default_font = self.family.currentFont()
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 144)
        self.font_size.setSuffix(" pt")
        self.bold = QCheckBox("Bold")
        self.italic = QCheckBox("Italic")
        self.alignment = QComboBox()
        self.alignment.addItem("Left", Qt.AlignmentFlag.AlignLeft)
        self.alignment.addItem("Center", Qt.AlignmentFlag.AlignHCenter)
        self.alignment.addItem("Right", Qt.AlignmentFlag.AlignRight)
        self.text_color = QPushButton()
        self.background_color = QPushButton()
        self.text_color.clicked.connect(lambda: self.choose_color(QPalette.ColorRole.Text))
        self.background_color.clicked.connect(lambda: self.choose_color(QPalette.ColorRole.Base))

        font_row = QHBoxLayout()
        font_row.addWidget(self.family, 1)
        font_row.addWidget(self.font_size)
        font_row.addWidget(self.bold)
        font_row.addWidget(self.italic)
        self.formatting = QWidget()
        format_layout = QFormLayout(self.formatting)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.addRow("Font", font_row)
        format_layout.addRow("Alignment", self.alignment)
        format_layout.addRow("Text color", self.text_color)
        format_layout.addRow("Background color", self.background_color)
        self.font_size.setAccessibleName("Font size")
        self.family.currentFontChanged.connect(self.apply_format)
        self.font_size.valueChanged.connect(self.apply_format)
        self.bold.toggled.connect(self.apply_format)
        self.italic.toggled.connect(self.apply_format)
        self.alignment.currentIndexChanged.connect(self.apply_format)

        self.counter = QLabel()
        counter_font = QFont(self.font())
        counter_font.setPointSize(76)
        counter_font.setBold(True)
        self.counter.setFont(counter_font)
        message = QLabel("Revealing text shortly…")
        self.countdown = QWidget()
        countdown_layout = QVBoxLayout(self.countdown)
        countdown_layout.addStretch()
        countdown_layout.addWidget(self.counter, alignment=Qt.AlignmentFlag.AlignHCenter)
        countdown_layout.addWidget(message, alignment=Qt.AlignmentFlag.AlignHCenter)
        countdown_layout.addStretch()
        self.surface = QStackedWidget()
        self.surface.addWidget(self.editor)
        self.surface.addWidget(self.countdown)

        self.seconds = QSpinBox()
        self.seconds.setRange(1, 3600)
        self.seconds.setSuffix(" s")
        self.seconds.setAccessibleName("Countdown")
        self.countdown_label = QLabel("&Countdown")
        self.countdown_label.setBuddy(self.seconds)
        self.start = QPushButton("&Start")
        self.start.clicked.connect(self.start_countdown)
        self.reset = QPushButton("&Reset")
        self.reset.clicked.connect(self.reset_simulator)
        self.escape = QShortcut(QKeySequence("Esc"), self)
        self.escape.activated.connect(self.return_to_input)
        for widget in (
            self.editor,
            font_name,
            self.font_size.lineEdit(),
            self.seconds.lineEdit(),
        ):
            self.disable_clipboard_writes(widget)

        actions = QHBoxLayout()
        actions.addWidget(self.countdown_label)
        actions.addWidget(self.seconds)
        actions.addStretch()
        actions.addWidget(self.start)
        actions.addWidget(self.reset)
        layout = QVBoxLayout(self)
        layout.addWidget(self.formatting)
        layout.addWidget(self.surface, 1)
        layout.addLayout(actions)
        self.reset_simulator()

    def disable_clipboard_writes(self, widget: QWidget) -> None:
        widget.installEventFilter(self)
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and (
                event.matches(QKeySequence.StandardKey.Copy)
                or event.matches(QKeySequence.StandardKey.Cut)
            )
        ):
            return True
        return super().eventFilter(watched, event)

    def apply_format(self) -> None:
        font = self.family.currentFont()
        font.setPointSize(self.font_size.value())
        font.setBold(self.bold.isChecked())
        font.setItalic(self.italic.isChecked())
        document = self.editor.document()
        document.setDefaultFont(font)
        options = document.defaultTextOption()
        options.setAlignment(self.alignment.currentData())
        document.setDefaultTextOption(options)

    def choose_color(self, role: QPalette.ColorRole) -> None:
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dialog.setCurrentColor(self.editor.palette().color(role))
        for field in dialog.findChildren(QLineEdit):
            self.disable_clipboard_writes(field)
        if dialog.exec():
            self.set_color(role, dialog.selectedColor())
        dialog.deleteLater()

    def set_color(self, role: QPalette.ColorRole, color: QColor) -> None:
        palette = self.editor.palette()
        palette.setColor(role, color)
        self.editor.setPalette(palette)
        button = self.text_color if role == QPalette.ColorRole.Text else self.background_color
        button.setText(color.name().upper())

    def start_countdown(self) -> None:
        self.deadline = perf_counter() + self.seconds.value()
        self.surface.setCurrentWidget(self.countdown)
        for widget in (self.formatting, self.countdown_label, self.seconds, self.start):
            widget.hide()
        self.reset.setFocus()
        self.update_countdown()

    def update_countdown(self) -> None:
        remaining = self.deadline - perf_counter()
        if remaining > 0:
            seconds = ceil(remaining)
            self.counter.setNum(seconds)
            self.timer.start(ceil((remaining - seconds + 1) * 1000))
            return
        self.editor.setPlaceholderText("")
        self.editor.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.editor.moveCursor(QTextCursor.MoveOperation.Start)
        self.surface.setCurrentWidget(self.editor)
        self.editor.verticalScrollBar().setValue(0)
        self.record_reveal()

    def record_reveal(self) -> None:
        event = {
            "event": "reveal",
            "perf_counter_ns": perf_counter_ns(),
            "utc": datetime.now(UTC).isoformat(),
        }
        try:
            self.reveal_log.parent.mkdir(parents=True, exist_ok=True)
            with self.reveal_log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")
        except OSError as exc:
            print(f"Could not record reveal timestamp: {exc}", file=sys.stderr)

    def return_to_input(self) -> None:
        self.timer.stop()
        self.editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.editor.setPlaceholderText("Enter the text to reveal")
        self.surface.setCurrentWidget(self.editor)
        for widget in (self.formatting, self.countdown_label, self.seconds, self.start):
            widget.show()
        self.editor.setFocus()

    def reset_simulator(self) -> None:
        if not self.formatting.isHidden():
            self.editor.clear()
            self.family.setCurrentFont(self.default_font)
            self.font_size.setValue(30)
            self.bold.setChecked(False)
            self.italic.setChecked(False)
            self.alignment.setCurrentIndex(1)
            self.seconds.setValue(5)
            self.set_color(QPalette.ColorRole.Text, QColor("#f5f7fa"))
            self.set_color(QPalette.ColorRole.Base, QColor("#171b24"))
            self.apply_format()
        self.return_to_input()


def main() -> int:
    app = QApplication(sys.argv)
    window = Simulator()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
