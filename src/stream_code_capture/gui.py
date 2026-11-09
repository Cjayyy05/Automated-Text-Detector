"""Local Windows GUI with explicit, scope-checked native clipboard opt-in."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, floor
from time import monotonic, sleep
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QScreen,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureWorker, DxcamSource
from .domain import Clipboard, Rect, TextLine
from .live import Controls, LiveConfig, LiveSession
from .native_scope import NativeScope
from .notifications import CopySound, play_copy_sound, validate_sound_file
from .ocr import RapidRecognizer
from .policy import DecisionPolicy, code_text

EventSink = Callable[[dict[str, Any]], None]


def describe_ocr(event: dict[str, Any], policy: DecisionPolicy) -> str:
    status = event["status"]
    title = f"Last decision: {status}"
    if status == "confirming":
        title += " · another changed frame is required"
    lines = [
        TextLine(row["text"], row["confidence"], Rect(**row["box"]), row["rejection"])
        for row in event["lines"]
    ]
    parsed = [(line, code_text(line, policy.config.profile)) for line in lines]
    parsed.sort(key=lambda pair: pair[1] is None)
    details = [title]
    for line, code in parsed[:8]:
        if line.rejection:
            reason = line.rejection
        elif code is None:
            reason = "context or unsupported code format"
        elif not policy.config.min_confidence <= line.confidence <= 1:
            reason = "confidence outside required range"
        elif code not in event["candidates"]:
            reason = "context or quality requirements not met"
        elif code in policy.suppressed:
            reason = "suppressed by baseline"
        elif code in policy.copied and code != event["code"]:
            reason = "already copied"
        else:
            reason = "eligible candidate"
        details.append(f"{line.text[:160]} [{line.confidence:.3f}] · {reason}")
    if not lines:
        details.append("No OCR text in this observation.")
    elif len(lines) > 8:
        details.append(f"{len(lines) - 8} additional lines omitted.")
    return "\n".join(details)


@dataclass(frozen=True)
class Monitor:
    device: int
    output: int
    name: str
    width: int
    height: int


def monitors() -> list[Monitor]:
    import dxcam

    # Same pinned DXcam metadata used by the display inventory diagnostic.
    result = []
    for device, outputs in enumerate(dxcam.__factory.outputs):
        for output, item in enumerate(outputs):
            item.update_desc()
            if item.attached_to_desktop:
                result.append(Monitor(device, output, item.devicename, *item.resolution))
    return result


def preview(monitor: Monitor, cancelled: Callable[[], bool]) -> QImage:
    if monitor not in monitors():
        raise RuntimeError("Display changed. Restart the prototype and select the monitor again.")
    source = DxcamSource(Rect(0, 0, monitor.width, monitor.height), monitor.device, monitor.output)
    try:
        deadline = monotonic() + 3
        while monotonic() < deadline and not cancelled():
            pixels = source.grab()
            if pixels is not None:
                data = pixels.tobytes()
                image = QImage(
                    data,
                    monitor.width,
                    monitor.height,
                    monitor.width * 3,
                    QImage.Format.Format_BGR888,
                )
                return image.copy()
            sleep(0.02)
        raise RuntimeError("No preview frame received. Keep the display awake and try again.")
    finally:
        source.close()


def physical_rect(start: QPointF, end: QPointF, displayed: QRectF, width: int, height: int) -> Rect:
    if (
        displayed.isEmpty()
        or not displayed.contains(start)
        or start.x() == end.x()
        or start.y() == end.y()
    ):
        raise ValueError("Draw a rectangle inside the preview.")
    x = sorted((start.x(), end.x()))
    y = sorted((start.y(), end.y()))
    left, right = (
        min(width, max(0, (v - displayed.left()) * width / displayed.width())) for v in x
    )
    top, bottom = (
        min(height, max(0, (v - displayed.top()) * height / displayed.height())) for v in y
    )
    roi = Rect(floor(left), floor(top), ceil(right), ceil(bottom))
    roi.validate(width, height)
    return roi


class RegionPreview(QWidget):
    selected = Signal(object)
    invalid = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.image = QImage()
        self.roi: Rect | None = None
        self.anchor: QPointF | None = None
        self.drag_point: QPointF | None = None
        self.setMinimumSize(320, 200)
        self.setAccessibleName("Monitor preview. Drag to select a capture region.")

    def set_image(self, image: QImage) -> None:
        self.image, self.roi = image, None
        self.anchor = self.drag_point = None
        self.update()

    def displayed(self) -> QRectF:
        if self.image.isNull():
            return QRectF()
        scale = min(self.width() / self.image.width(), self.height() / self.image.height())
        width, height = self.image.width() * scale, self.image.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def paintEvent(self, event: QPaintEvent) -> None:
        with QPainter(self) as painter:
            painter.fillRect(self.rect(), QColor("#172230"))
            area = self.displayed()
            if self.image.isNull():
                painter.setPen(QColor("#eef3f8"))
                painter.drawText(
                    self.rect(), Qt.AlignmentFlag.AlignCenter, "Load a monitor preview"
                )
                return
            painter.drawImage(area, self.image)
            painter.setPen(QPen(QColor("#49d7ff"), 2))
            if self.anchor is not None and self.drag_point is not None:
                painter.setClipRect(area)
                painter.drawRect(QRectF(self.anchor, self.drag_point).normalized())
            elif self.roi is not None:
                x = area.width() / self.image.width()
                y = area.height() / self.image.height()
                r = self.roi
                painter.drawRect(
                    QRectF(
                        area.left() + r.left * x,
                        area.top() + r.top * y,
                        (r.right - r.left) * x,
                        (r.bottom - r.top) * y,
                    )
                )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.displayed().contains(
            event.position()
        ):
            self.anchor = self.drag_point = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.anchor is not None:
            self.drag_point = event.position()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.anchor is None or event.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.roi = physical_rect(
                self.anchor,
                event.position(),
                self.displayed(),
                self.image.width(),
                self.image.height(),
            )
        except ValueError as exc:
            self.invalid.emit(str(exc))
        else:
            self.selected.emit(self.roi)
        finally:
            self.anchor = self.drag_point = None
            self.update()


class Job(QThread):
    update_event = Signal(object)

    def __init__(self, action: Callable[[Job], None], parent: QWidget) -> None:
        super().__init__(parent)
        self.action = action

    def run(self) -> None:
        try:
            self.action(self)
        except Exception as exc:
            self.update_event.emit({"event": "error", "error": f"{type(exc).__name__}: {exc}"})


class ScopedSource(DxcamSource):
    def __init__(self, monitor: Monitor, roi: Rect, scope: NativeScope) -> None:
        scope.check()
        super().__init__(roi, monitor.device, monitor.output)
        self.scope = scope
        self.next_check = 0.0

    def grab(self) -> Any:
        if monotonic() >= self.next_check:
            self.scope.check()
            self.next_check = monotonic() + 0.5
        return super().grab()


class ScopedClipboard:
    def __init__(self, target: Clipboard, scope: NativeScope, controls: Controls) -> None:
        self.target, self.scope, self.controls = target, scope, controls

    def write(self, text: str) -> None:
        try:
            self.scope.check()
        except Exception:
            self.controls.send("stop")
            raise
        # The existing guarded handoff rechecks freshness and inhibition AFTER inventory.
        self.target.write(text)


def run_session(
    monitor: Monitor,
    roi: Rect,
    profile: str,
    controls: Controls,
    emit: EventSink,
    *,
    native: bool = False,
    sound: bool = False,
    sound_path: str | None = None,
) -> None:
    roi.validate(monitor.width, monitor.height)
    scope = NativeScope(monitor.device, monitor.output, monitor.name) if native else None
    recognizer = RapidRecognizer()
    recognizer.warmup()
    emit(
        {
            "event": "session_info",
            "provider": recognizer.provider,
            "models": [path.name for path in recognizer.model_paths],
        }
    )
    if controls.stop.is_set():
        return
    if monitor not in monitors():
        raise RuntimeError("Display changed. Restart the prototype and select the monitor again.")
    config = LiveConfig(
        roi, device=monitor.device, output=monitor.output, profile=profile, dry_run=not native
    )
    next_stats = 0.0
    last_ocr_detail = ""
    copy_sound = CopySound(controls, sound_path) if native and sound else None

    def forward(event: dict[str, Any]) -> None:
        nonlocal next_stats, last_ocr_detail
        if event["event"] == "frame":
            detail = describe_ocr(event, session.policy)
            if detail != last_ocr_detail:
                last_ocr_detail = detail
                emit({"event": "ocr_detail", "text": detail})
            if copy_sound is not None:
                copy_sound.notify(event)
            if event["status"] in {"copied", "would_copy", "clipboard_failed"}:
                emit({"event": "confirmation", "code": event["code"], "error": event["error"]})
            now = monotonic()
            if now >= next_stats:
                next_stats = now + 0.25
                emit(
                    {
                        "event": "stats",
                        "processed": event["sequence"],
                        "dropped": session.worker.latest.dropped,
                        "ms": event["timings_ms"]["process"],
                        "armed": session.policy.armed,
                    }
                )
        elif event["event"] == "stale_before_ocr":
            last_ocr_detail = ""
            emit({"event": "ocr_detail", "text": "Last decision: stale frame rejected before OCR."})
        elif event["event"] != "baseline_stale":
            emit(event)

    if scope is None:
        session = LiveSession(recognizer, config, controls, forward)
    else:
        scope.check()
        worker = CaptureWorker(lambda: ScopedSource(monitor, roi, scope))
        session = LiveSession(recognizer, config, controls, forward, worker=worker)
        session.pipeline.clipboard = ScopedClipboard(session.pipeline.clipboard, scope, controls)
    controls.send("start")
    try:
        session.run()
    finally:
        session.worker.wait_closed()


class Window(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Instant Stream Code Capture · DRY RUN")
        self.resize(900, 690)
        self.job: Job | None = None
        self.sound_job: Job | None = None
        self.settings = QSettings("StreamCodeCapture", "StreamCodeCapture")
        self.sound_path = str(self.settings.value("notificationSoundPath", "")) or None
        self.controls: Controls | None = None
        self.closing = self.stopping = self.display_changed = False
        self.ready = self.armed = self.arm_pending = False
        self.monitor_list: list[Monitor] = []
        self.monitor = QComboBox()
        self.profile = QComboBox()
        self.profile.addItems(["Discount", "Game"])
        self.canvas = RegionPreview()
        self.region = QLabel("Region: select an area on the preview")
        self.status = QLabel("Stopped")
        self.code = QLabel("Last confirmed code: —")
        self.stats = QLabel("Processing statistics will appear here")
        self.ocr_info = QLabel("OCR provider/model: awaiting session initialization")
        self.capture_info = QLabel("Capture: select a monitor")
        self.clipboard_info = QLabel("Clipboard: memory · dry run")
        self.error = QLabel()
        self.show_ocr = QCheckBox("Show last OCR results")
        self.ocr_detail = QPlainTextEdit()
        self.ocr_detail.setReadOnly(True)
        self.ocr_detail.setMaximumHeight(120)
        self.ocr_detail.setPlainText("No monitoring observation yet.")
        self.ocr_detail.hide()
        self.show_ocr.toggled.connect(self.ocr_detail.setVisible)
        self.native = QCheckBox("Use Windows clipboard for this session")
        self.sound = QCheckBox("Play sound when code is copied")
        self.choose_sound = QPushButton("Choose sound")
        self.test_sound = QPushButton("Test sound")
        self.default_sound = QPushButton("Default")
        self.sound_name = QLabel()
        self.sound_name.setTextFormat(Qt.TextFormat.PlainText)
        self.sound_name.setWordWrap(True)
        self.badge = QLabel("DRY RUN · Confirmations stay in memory")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #c04e37")
        for label in (self.code, self.error, self.ocr_info, self.capture_info, self.clipboard_info):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
        self.snapshot = QPushButton("Load preview")
        self.start = QPushButton("Start")
        self.arm = QPushButton("Arm")
        self.disarm = QPushButton("Disarm")
        self.stop = QPushButton("Stop")
        title = QLabel("Instant Stream Code Capture")
        title.setStyleSheet("font-size: 22px; font-weight: 600")
        self.badge.setStyleSheet("font-weight: 600; color: #21816e")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(title)
        layout.addWidget(self.badge)
        layout.addWidget(self.native)
        layout.addWidget(self.sound)
        sound_row = QHBoxLayout()
        for sound_widget in (
            self.choose_sound,
            self.test_sound,
            self.default_sound,
            self.sound_name,
        ):
            sound_row.addWidget(sound_widget)
        layout.addLayout(sound_row)
        inputs = QHBoxLayout()
        for widget in (
            QLabel("Monitor"),
            self.monitor,
            QLabel("Profile"),
            self.profile,
            self.snapshot,
        ):
            inputs.addWidget(widget)
        layout.addLayout(inputs)
        hint = QLabel(
            "Covering windows can supply eligible codes that will be copied in native mode. "
            "Disarm before moving, covering, or minimizing the video. Native copying is limited "
            "to center primary output 0, 1920 × 1080, 100%, SDR, local Windows."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self.canvas, 1)
        buttons = QHBoxLayout()
        for button in (self.start, self.arm, self.disarm, self.stop):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        for label in (self.status, self.code, self.stats):
            layout.addWidget(label)
        diagnostics = QGroupBox("Session diagnostics")
        diagnostic_layout = QVBoxLayout(diagnostics)
        for label in (
            self.ocr_info,
            self.capture_info,
            self.region,
            self.clipboard_info,
            self.error,
        ):
            diagnostic_layout.addWidget(label)
        layout.addWidget(diagnostics)
        layout.addWidget(self.show_ocr)
        layout.addWidget(self.ocr_detail)
        self.monitor.currentIndexChanged.connect(self.clear_preview)
        self.canvas.selected.connect(self.region_selected)
        self.canvas.invalid.connect(self.error.setText)
        self.snapshot.clicked.connect(self.load_preview)
        self.start.clicked.connect(self.start_session)
        self.arm.clicked.connect(self.arm_session)
        self.disarm.clicked.connect(self.disarm_session)
        self.stop.clicked.connect(self.stop_session)
        self.native.toggled.connect(self.mode_changed)
        self.choose_sound.clicked.connect(self.select_sound)
        self.test_sound.clicked.connect(self.preview_sound)
        self.default_sound.clicked.connect(self.reset_sound)
        self.update_sound_name()
        self.launch(lambda job: job.update_event.emit({"event": "monitors", "items": monitors()}))

    def refresh(self) -> None:
        index = self.monitor.currentIndex()
        if 0 <= index < len(self.monitor_list):
            monitor = self.monitor_list[index]
            self.capture_info.setText(
                f"Capture: device {monitor.device} / output {monitor.output} · "
                f"{monitor.name} · {monitor.width} × {monitor.height} physical px"
            )
        self.clipboard_info.setText(
            (
                "Clipboard: Windows · session target"
                if self.controls is not None
                else "Clipboard: Windows requested · consent required at Start"
            )
            if self.native.isChecked()
            else "Clipboard: memory · dry run"
        )
        idle = self.job is None and not self.closing and not self.display_changed
        self.monitor.setEnabled(idle)
        self.profile.setEnabled(idle)
        self.native.setEnabled(idle)
        self.sound.setEnabled(idle)
        for button in (self.choose_sound, self.test_sound, self.default_sound):
            button.setEnabled(idle and self.sound_job is None)
        self.canvas.setEnabled(idle)
        self.snapshot.setEnabled(idle and self.monitor.currentIndex() >= 0)
        self.start.setEnabled(idle and self.canvas.roi is not None)
        active = self.controls is not None and not self.stopping
        self.arm.setEnabled(active and self.ready and not self.armed and not self.arm_pending)
        self.disarm.setEnabled(active and self.armed and not self.arm_pending)
        self.stop.setEnabled(active)

    def launch(self, action: Callable[[Job], None]) -> None:
        self.job = Job(action, self)
        self.job.update_event.connect(self.handle_event, Qt.ConnectionType.QueuedConnection)
        self.job.finished.connect(self.finished, Qt.ConnectionType.QueuedConnection)
        self.refresh()
        self.job.start()

    @Slot()
    def mode_changed(self) -> None:
        native = self.native.isChecked()
        self.badge.setText(
            "NATIVE · Confirmations replace Windows clipboard"
            if native
            else "DRY RUN · Confirmations stay in memory"
        )
        self.setWindowTitle("Instant Stream Code Capture · " + ("NATIVE" if native else "DRY RUN"))
        self.refresh()

    @Slot()
    def clear_preview(self) -> None:
        self.native.setChecked(False)
        self.canvas.set_image(QImage())
        self.region.setText("Region: select an area on the preview")
        self.refresh()

    @Slot(object)
    def region_selected(self, roi: Rect) -> None:
        self.error.clear()
        self.region.setText(
            f"Region: {roi.left}, {roi.top} → {roi.right}, {roi.bottom} physical px"
        )
        self.refresh()

    @Slot()
    def load_preview(self) -> None:
        monitor = self.monitor_list[self.monitor.currentIndex()]
        self.clear_preview()
        self.error.clear()
        self.status.setText("Capturing still preview…")

        def load(job: Job) -> None:
            image = preview(monitor, job.isInterruptionRequested)
            job.update_event.emit({"event": "preview", "image": image})

        self.launch(load)

    @Slot()
    def start_session(self) -> None:
        roi = self.canvas.roi
        if self.job is not None or roi is None or self.display_changed:
            return
        monitor = self.monitor_list[self.monitor.currentIndex()]
        profile = self.profile.currentText().lower()
        native = self.native.isChecked()
        if (
            native
            and QMessageBox.warning(
                self,
                "Enable native copying for this session?",
                "Detected codes will replace your Windows clipboard. Eligible codes in covering "
                "windows can also be copied. Disarm before covering, moving, or minimizing the "
                "source. Continue with native copying on the approved center-monitor "
                "configuration?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.display_changed or (native and not self.native.isChecked()):
            return
        controls = self.controls = Controls()
        self.error.clear()
        self.code.setText("Last confirmed code: —")
        self.stats.setText("Processing statistics will appear here")
        self.ocr_detail.setPlainText("No monitoring observation yet.")
        self.ocr_info.setText("OCR provider/model: initializing and verifying local sessions…")
        self.status.setText("Warming up OCR · Disarmed")
        if native:
            sound = self.sound.isChecked()
            sound_path = self.sound_path
            self.launch(
                lambda job: run_session(
                    monitor,
                    roi,
                    profile,
                    controls,
                    job.update_event.emit,
                    native=True,
                    sound=sound,
                    sound_path=sound_path,
                )
            )
        else:
            self.launch(
                lambda job: run_session(monitor, roi, profile, controls, job.update_event.emit)
            )

    @Slot()
    def arm_session(self) -> None:
        if self.controls is not None and self.arm.isEnabled():
            self.controls.send("arm")
            self.arm_pending = True
            self.refresh()

    @Slot()
    def disarm_session(self) -> None:
        if self.controls is not None:
            self.controls.send("disarm")
            self.arm_pending = True
            self.refresh()

    @Slot()
    def stop_session(self) -> None:
        if self.controls is not None and not self.stopping:
            self.controls.send("stop")
            self.stopping = True
            self.status.setText("Stopping · Disarmed")
            self.refresh()

    @Slot(object)
    def handle_event(self, event: dict[str, Any]) -> None:
        kind = event["event"]
        if kind == "session_info":
            self.ocr_info.setText(f"OCR: {event['provider']} · " + " / ".join(event["models"]))
        elif kind == "ocr_detail":
            self.ocr_detail.setPlainText(event["text"])
        elif kind == "monitors":
            self.monitor_list = event["items"]
            for item in self.monitor_list:
                self.monitor.addItem(
                    f"{item.name} · {item.width} × {item.height} · Output {item.output}"
                )
            if not self.monitor_list:
                self.error.setText("No available capture monitors.")
        elif kind == "preview" and not self.display_changed:
            self.canvas.set_image(event["image"])
        elif kind == "error" or (kind == "summary" and event["failure"]):
            self.error.setText(str(event.get("error") or event["failure"]))
        elif not self.stopping and self.controls is not None:
            if kind == "ready":
                self.ready = True
            elif kind == "baseline_progress" and not self.ready:
                self.status.setText(f"Running · Building baseline · {event['reason']}")
                stats = (
                    f"Captured {event['captured']} changed frames · "
                    f"Baseline {event['observations']} accepted, {event['rejected']} rejected"
                )
                if event["ocr_ms"] is not None:
                    stats += f" · Last baseline OCR {event['ocr_ms']:.0f} ms"
                self.stats.setText(stats)
            elif kind in {"armed", "disarmed", "arm_rejected"}:
                self.armed, self.arm_pending = kind == "armed", False
                if kind == "arm_rejected":
                    self.error.setText(str(event["reason"]))
            elif kind == "confirmation":
                self.armed = False
                if event["error"]:
                    self.error.setText(str(event["error"]))
                else:
                    self.code.setText(f"Last confirmed code: {event['code']}")
            elif kind == "stats":
                self.armed = event["armed"]
                self.stats.setText(
                    f"Frame #{event['processed']} · {event['dropped']} dropped · "
                    f"Last processing time {event['ms']:.1f} ms"
                )
            if kind in {
                "started",
                "ready",
                "armed",
                "disarmed",
                "arm_rejected",
                "stats",
                "confirmation",
            }:
                baseline = "Ready" if self.ready else "Building baseline"
                arm = "Armed" if self.armed else "Disarmed"
                self.status.setText(f"Running · {baseline} · {arm}")
        self.refresh()

    @Slot()
    def finished(self) -> None:
        was_session = self.controls is not None
        if self.job is not None:
            self.job.deleteLater()
        self.job = self.controls = None
        if was_session and self.ocr_info.text().startswith("OCR:"):
            self.ocr_info.setText(self.ocr_info.text() + " (last session)")
        elif was_session:
            self.ocr_info.setText("OCR provider/model: initialization incomplete")
        self.native.setChecked(False)
        self.ready = self.armed = self.arm_pending = self.stopping = False
        self.status.setText("Stopped · Disarmed")
        self.refresh()
        if self.closing:
            self.close()

    @Slot()
    def invalidate_display(self) -> None:
        self.display_changed = True
        self.stop_session()
        self.clear_preview()
        self.error.setText("Display configuration changed. Restart the prototype.")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.job is None and self.sound_job is None:
            event.accept()
        else:
            self.closing = True
            if self.job is not None:
                self.job.requestInterruption()
            if self.sound_job is not None:
                self.sound_job.requestInterruption()
            self.stop_session()
            self.status.setText("Closing after background work finishes…")
            self.refresh()
            event.ignore()

    def update_sound_name(self) -> None:
        if self.sound_path:
            try:
                validate_sound_file(self.sound_path)
            except ValueError:
                self.sound_name.setText("Custom file unavailable · Windows default")
            else:
                from pathlib import Path

                self.sound_name.setText(Path(self.sound_path).name)
            self.sound_name.setToolTip(self.sound_path)
        else:
            self.sound_name.setText("Windows default")
            self.sound_name.setToolTip("")

    @Slot()
    def select_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose notification sound", self.sound_path or "", "WAV audio (*.wav)"
        )
        if not path:
            return
        try:
            validate_sound_file(path)
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.sound_path = path
        self.save_sound()

    def save_sound(self) -> None:
        self.settings.setValue("notificationSoundPath", self.sound_path or "")
        self.settings.sync()
        self.error.clear()
        if self.settings.status() != QSettings.Status.NoError:
            self.error.setText(
                "Sound selected for this run. Windows could not save the preference."
            )
        self.update_sound_name()

    @Slot()
    def reset_sound(self) -> None:
        self.sound_path = None
        self.save_sound()

    @Slot()
    def preview_sound(self) -> None:
        if self.sound_job is not None or self.closing:
            return
        self.error.clear()
        path = self.sound_path

        def play(job: Job) -> None:
            if not job.isInterruptionRequested():
                play_copy_sound(path)

        self.sound_job = Job(play, self)
        self.sound_job.update_event.connect(self.handle_event, Qt.ConnectionType.QueuedConnection)
        self.sound_job.finished.connect(self.sound_finished, Qt.ConnectionType.QueuedConnection)
        self.refresh()
        self.sound_job.start()

    @Slot()
    def sound_finished(self) -> None:
        if self.sound_job is not None:
            self.sound_job.deleteLater()
        self.sound_job = None
        self.update_sound_name()
        self.refresh()
        if self.closing:
            self.close()


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("The dry-run capture GUI requires Windows.")
    app = QApplication(sys.argv)
    window = Window()

    def watch_screen(screen: QScreen) -> None:
        screen.geometryChanged.connect(window.invalidate_display)
        screen.logicalDotsPerInchChanged.connect(window.invalidate_display)

    for screen in app.screens():
        watch_screen(screen)
    app.screenAdded.connect(window.invalidate_display)
    app.screenRemoved.connect(window.invalidate_display)
    app.primaryScreenChanged.connect(window.invalidate_display)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
