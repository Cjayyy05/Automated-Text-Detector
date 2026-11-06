"""Display a generated code for a supervised GUI test. No OCR or clipboard access."""

import argparse
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

from phase4_scenes import draw_motion, scenes
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from stream_code_capture.domain import Rect


class Stimulus(QLabel):
    def __init__(self, scene, expected, profile):
        super().__init__()
        self.scene = scene[:, :800].copy()
        self.baseline = self.scene.copy()
        self.baseline[410:515, 200:800] = (35, 35, 35)
        self.expected, self.profile = expected, profile
        self.revealed = False
        self.tick = 0
        self.setWindowTitle(f"Controlled {profile.title()} GUI clipboard test")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(800, 540)
        self.move(320, 320)  # Fixture placement inside the approved center-monitor ROI.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(33)
        self.refresh()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not self.revealed:
            self.revealed = True
            print(f"Expected {self.profile} code: {self.expected}", flush=True)
        elif event.key() == Qt.Key.Key_Escape:
            self.close()

    def refresh(self):
        pixels = (self.scene if self.revealed else self.baseline).copy()
        draw_motion(pixels, Rect(0, 0, 800, 540), self.tick)
        self.tick += 1
        image = QImage(pixels.data, 800, 540, pixels.strides[0], QImage.Format.Format_BGR888)
        self.setPixmap(QPixmap.fromImage(image))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["discount", "game"], default="game")
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "artifacts/gui-clipboard-stimuli",
    )
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    screen = app.primaryScreen()
    if (
        screen is None
        or screen.geometry().width() != 1920
        or screen.geometry().height() != 1080
        or screen.devicePixelRatio() != 1
    ):
        raise SystemExit("Use the approved center primary monitor at 1920 × 1080 and 100%.")
    seed = secrets.randbits(32)
    ((scene, expected),) = scenes(seed, 1, args.profile)
    args.directory.mkdir(parents=True, exist_ok=True)
    record = args.directory / f"{args.profile}-{uuid4().hex}.json"
    with record.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "seed": seed,
                "profile": args.profile,
                "expected": expected,
                "fixture_roi": [320, 320, 1120, 860],
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(f"Expected-code record: {record.resolve()}", flush=True)
    print(
        "Code hidden. Start the GUI, wait for Ready, then Arm before pressing Space here.",
        flush=True,
    )
    window = Stimulus(scene, expected, args.profile)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
