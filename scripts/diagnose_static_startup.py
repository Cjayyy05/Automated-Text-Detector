"""Explicit static Windows surface -> real DXcam -> local OCR, memory clipboard only."""

import argparse
import json
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from stream_code_capture.domain import Rect
from stream_code_capture.live import Controls, LiveConfig, LiveSession
from stream_code_capture.ocr import RapidRecognizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=12)
    args = parser.parse_args()
    if not args.show_window or not 1 <= args.seconds <= 60:
        parser.error("Explicit --show-window and duration 1..60 required")
    app = QApplication([])
    # Fixture coordinates match the operator's failing ROI on the primary output.
    image = np.full((605, 1336, 3), 235, np.uint8)
    for row in range(14):
        for column in range(3):
            cv2.putText(
                image,
                f"STATIC PANEL {row + 1} item {column + 1}",
                (15 + column * 440, 30 + row * 40),
                0,
                0.6,
                (25, 25, 25),
                1,
                cv2.LINE_AA,
            )
    window = QLabel()
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    window.setGeometry(560, 293, 1336, 605)
    data = image.tobytes()
    window.setPixmap(QPixmap.fromImage(QImage(data, 1336, 605, 4008, QImage.Format.Format_BGR888)))
    window.show()

    class Bridge(QObject):
        done = Signal()

    bridge = Bridge()
    bridge.done.connect(app.quit)
    controls = Controls()
    results = []
    ready_seen = []

    def run():
        try:
            with args.report.open("x", encoding="utf-8") as report:

                def emit(event):
                    if event["event"] == "ready":
                        ready_seen.append(True)
                    report.write(json.dumps(event) + "\n")
                    report.flush()

                recognizer = RapidRecognizer()
                recognizer.warmup()
                session = LiveSession(
                    recognizer, LiveConfig(Rect(560, 293, 1896, 898)), controls, emit
                )
                controls.send("start")
                code = session.run(duration=args.seconds)
                results.append((code, session.baseline_count))
        finally:
            bridge.done.emit()

    worker = Thread(target=run)
    QTimer.singleShot(500, worker.start)
    app.exec()
    controls.send("stop")
    if worker.ident is not None:
        worker.join()
    print(json.dumps({"result": results, "scope": "Real DXcam static fixture, memory only"}))
    return int(not results or results[0][0] != 0 or not ready_seen)


if __name__ == "__main__":
    raise SystemExit(main())
