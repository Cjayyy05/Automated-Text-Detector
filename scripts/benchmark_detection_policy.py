"""Compare policies on identical local pixels through warmed OCR and a memory clipboard."""

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter_ns

import numpy as np
from benchmark_armed_roi import SIZES, scene
from benchmark_discount_layouts import generated
from livestream_code_simulator import Simulator
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QImage
from PySide6.QtWidgets import QApplication

from stream_code_capture.cli import read_image
from stream_code_capture.clipboard import MemoryClipboard
from stream_code_capture.domain import Frame, Image, Rect
from stream_code_capture.metrics import Metrics
from stream_code_capture.ocr import RapidRecognizer
from stream_code_capture.pipeline import Pipeline
from stream_code_capture.policy import DecisionPolicy, PolicyConfig


@dataclass
class Case:
    name: str
    group: str
    expected: str | None
    baseline: Image
    frames: list[Image]
    profile: str = "discount"
    simulated_delay_ms: int = 0
    repeat: bool = False


def manifest_cases(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    roi = Rect(*data["roi"])
    for entry in data["cases"]:
        images = [roi.crop(read_image(path.parent / item["file"])) for item in entry["frames"][:3]]
        yield Case(
            str(entry["id"]),
            path.parent.name,
            next(iter(entry["expected_writes"]), None),
            images[0],
            images[1:],
        )


def game_cases(path: Path):
    split = json.loads(path.read_text(encoding="utf-8"))
    for item in split["datasets"]:
        manifest = path.parent / "imported" / Path(item["manifest"]).parent.name / "labelled.json"
        for frame in json.loads(manifest.read_text(encoding="utf-8"))["frames"]:
            label = frame["label"]
            image = Rect(*label["roi"]).crop(read_image(manifest.parent / frame["file"]))
            # These are stills. Change one corner pixel to exercise the previous policy.
            changed = image.copy()
            changed[0, 0] ^= 1
            yield Case(
                label["event_id"],
                "game-" + item["partition"],
                label["code"],
                np.zeros_like(image),
                [image, changed],
                "game",
            )


def simulator_cases(window: Simulator, seed: int):
    rng = random.Random(seed)

    def token():
        return "".join(rng.sample("ACKMPRTUVWXY", 6) + rng.sample("23456789", 4))

    def render(text):
        window.return_to_input()
        window.editor.setPlainText(text)
        window.start_countdown()
        window.timer.stop()
        window.deadline = 0
        window.update_countdown()
        QApplication.processEvents()
        # Snapshot the actual simulator reveal widget. No screen capture or native clipboard.
        image = (
            window.editor.viewport().grab().toImage().convertToFormat(QImage.Format.Format_BGR888)
        )
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(), image.bytesPerLine()
        )
        return rows[:, : image.width() * 3].reshape(image.height(), image.width(), 3).copy()

    a, b, c, d, e = (token() for _ in range(5))
    a = a[:3] + "23" + a[3:]
    b = b[:3].lower() + "4" + b[3:].lower()
    c = c[:2] + "O" + c[2:4].lower() + "0" + c[4:]
    d = d[:3] + "-" + d[3:5].lower() + "0" + d[5:]
    baseline = render("")
    for name, code, text, profile in (
        ("uppercase standalone", a, a, "discount"),
        ("lowercase standalone", b, b, "discount"),
        ("mixed with O and zero", c, f"Use code {c}\nLimited time offer", "discount"),
        ("game lowercase, zero and hyphen", d, f"Redemption code:\n{d}", "game"),
        ("offer above", e, f"40% off\n{e}", "discount"),
        ("clustered standalone", e, e, "discount"),
        ("game standalone", a.lower(), a.lower(), "game"),
        (
            "sentence price time and handle",
            None,
            "Current market price\nUSD 499.99\n12:34:56 PM\n@Trader2345",
            "discount",
        ),
        ("bare username", None, "Trader2345", "game"),
    ):
        yield Case(name, "simulator-static", code, baseline, [render(text)], profile)

    yield Case("pre-existing", "simulator-suppression", None, render(a), [render(f"{a}\n25% off")])
    yield Case("repeat after rearm", "simulator-static", a, baseline, [render(a)], repeat=True)
    for delay in (1300, 3200):
        yield Case(
            f"{delay} ms injected OCR delay",
            "simulated-slow",
            a if delay < 3000 else None,
            baseline,
            [render(a)],
            simulated_delay_ms=delay,
        )


def moving_cases(seed):
    rng = random.Random(seed)
    width, height, rows = SIZES["large"]

    def render(code, position, phase):
        return scene(width, height, rows, code, position, phase, moving_text=True)

    for idx, position in enumerate(("left", "right", "left", "right")):
        code = "".join(rng.sample("ACDEFGHJKMNPQRTUVWXY23456789", 8)) + ("4A" if idx < 3 else "O0")
        yield Case(
            position + str(idx),
            "large-moving",
            code,
            render(None, position, 0),
            [render(code, position, i) for i in (1, 2, 3)],
        )
    yield Case(
        "prices only",
        "large-moving",
        None,
        render(None, "left", 0),
        [render(None, "left", i) for i in (1, 2)],
    )


class DelayedOCR:
    """Add elapsed time to the replay clock after each armed OCR result."""

    def __init__(self, ocr, delay_ms):
        self.ocr = ocr
        self.delay_ns = delay_ms * 1_000_000
        self.offset = 0

    def clock(self):
        return perf_counter_ns() + self.offset

    def recognize(self, image):
        return self.ocr.recognize(image)

    def recognize_timed(self, image):
        result = self.ocr.recognize_timed(image)
        self.offset += self.delay_ns
        return result


def run(cases, ocr, output):
    metrics = Metrics()
    for case in cases:
        roi = Rect(0, 0, case.baseline.shape[1], case.baseline.shape[0])
        memory = MemoryClipboard()
        policy = DecisionPolicy(PolicyConfig(profile=case.profile))
        recognizer = DelayedOCR(ocr, case.simulated_delay_ms)
        pipeline = Pipeline(recognizer, memory, roi, policy, clock=recognizer.clock, copy_roi=False)
        pipeline.baseline(Frame(case.baseline, 0, recognizer.clock()))
        policy.arm()
        start = recognizer.clock()
        outcomes = []
        for index, image in enumerate(case.frames, 1):
            result = pipeline.process(Frame(image, index, recognizer.clock()))
            outcomes.append(result)
            if result.status == "copied":
                break
        if case.repeat and memory.writes:
            policy.arm()
            for index in range(len(outcomes) + 1, len(outcomes) + 3):
                image = case.frames[-1].copy()
                image[0, 0] ^= index
                outcomes.append(pipeline.process(Frame(image, index, recognizer.clock())))

        confirmation = next((r for r in outcomes if r.status == "copied"), None)
        exact = case.expected is not None and memory.writes == [case.expected]
        elapsed = (confirmation.completed_ns - start) / 1e6 if confirmation else None
        if not case.simulated_delay_ms:
            metrics.add({f"{case.group}/first_process": outcomes[0].timings_ms["process"]})
            if exact and elapsed is not None:
                metrics.add({f"{case.group}/exact_reveal_to_copy": elapsed})
        record = {
            "name": case.name,
            "group": case.group,
            "expected": case.expected,
            "writes": memory.writes,
            "exact": exact,
            "reveal_to_copy_ms": elapsed,
            "simulated_delay_ms": case.simulated_delay_ms,
            "pixels_sha256": [
                hashlib.sha256(pixels).hexdigest() for pixels in (case.baseline, *case.frames)
            ],
            "outcomes": [asdict(o) for o in outcomes],
        }
        output.write(json.dumps(record) + "\n")
        output.flush()
    output.write(json.dumps({"timing_summary": metrics.summary()}) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=927105)
    parser.add_argument("--simulator-only", action="store_true")
    args = parser.parse_args()
    app = QApplication([])
    window = Simulator(args.report.with_suffix(".simulator.jsonl"))
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.show()
    window.resize(750, 510)
    window.font_size.setValue(34)
    window.family.setCurrentFont(QFont("Consolas"))
    app.processEvents()

    def cases():
        yield from simulator_cases(window, args.seed)
        if args.simulator_only:
            return
        yield from moving_cases(args.seed)
        for name, group, code, images in generated(args.seed):
            yield Case(name, "layout-" + group, code, np.zeros_like(images[0]), images)
        for name in ("smoke", "challenge", "phase2-holdout"):
            yield from manifest_cases(Path("samples") / name / "manifest.json")
        yield from game_cases(
            Path("datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json")
        )

    ocr = RapidRecognizer()
    ocr.warmup()
    with args.report.open("x", encoding="utf-8") as output:
        run(cases(), ocr, output)
    window.close()


if __name__ == "__main__":
    main()
