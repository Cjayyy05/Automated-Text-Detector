"""Local-file-only commands. stdout is JSON; nothing captures the screen on import."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from threading import Thread
from time import perf_counter_ns
from typing import Any

import cv2
import numpy as np

from .clipboard import MemoryClipboard, WindowsClipboard
from .domain import Frame, Image, Rect
from .ocr import RapidRecognizer
from .pipeline import Pipeline
from .policy import DecisionPolicy, PolicyConfig
from .synthetic import generate


def read_image(path: Path) -> Image:
    # imdecode supports Unicode Windows paths without depending on cv2.imread behavior.
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return np.asarray(image, dtype=np.uint8)


def add_ocr_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--scale", type=float, default=2)
    command.add_argument("--threads", type=int, default=2)
    command.add_argument("--provider", choices=["cpu", "cuda", "directml"], default="cpu")
    command.add_argument("--model-profile", choices=["baseline", "tiny", "v4"], default="baseline")
    command.add_argument("--model-dir", type=Path)
    command.add_argument("--det-limit", type=int, default=960)
    command.add_argument("--preprocessing", choices=["none", "gray", "clahe"], default="none")
    command.add_argument("--cpu-arena", action="store_true")
    command.add_argument("--profile-inference", action="store_true")
    command.add_argument("--fallback-baseline", action="store_true")
    command.add_argument("--no-spinning", action="store_true")


def recognizer_from_args(args: argparse.Namespace) -> RapidRecognizer:
    if getattr(args, "profile", "discount") == "game" and args.model_profile != "baseline":
        raise ValueError(
            "Game profile currently requires the baseline OCR model; "
            "experimental verification is discount-specific"
        )
    if (
        getattr(args, "clipboard", None) == "windows"
        and args.model_profile != "baseline"
        and (args.model_profile != "tiny" or not args.fallback_baseline)
    ):
        raise ValueError(
            "Experimental native copying requires the tiny profile with "
            "--fallback-baseline independent candidate verification; "
            "use dry-run for other benchmark profiles"
        )
    return RapidRecognizer(
        scale=args.scale,
        provider=args.provider,
        threads=args.threads,
        model_profile=args.model_profile,
        model_dir=args.model_dir,
        det_limit=args.det_limit,
        preprocessing=args.preprocessing,
        cpu_arena=args.cpu_arena,
        profile_inference=args.profile_inference,
        fallback_baseline=args.fallback_baseline,
        allow_spinning=not args.no_spinning,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Instant Stream Code Capture — offline foundation")
    sub = root.add_subparsers(dest="command", required=True)
    fixture = sub.add_parser(
        "generate", help="Generate deterministic chart sequences and ground truth"
    )
    fixture.add_argument("output", type=Path)
    fixture.add_argument("--seed", type=int, default=7)
    fixture.add_argument("--count", type=int, default=3)
    fixture.add_argument("--challenge", action="store_true")
    image = sub.add_parser("image", help="Inspect one local image; disarmed by default")
    image.add_argument("path", type=Path)
    image.add_argument("--roi", type=int, nargs=4, required=True, metavar=("L", "T", "R", "B"))
    image.add_argument("--baseline", type=Path)
    image.add_argument("--clipboard", choices=["memory", "windows"], default="memory")
    image.add_argument("--confirmations", type=int, default=2)
    replay = sub.add_parser(
        "replay", help="Replay generated pixels; compare memory writes to truth"
    )
    replay.add_argument("manifest", type=Path)
    replay.add_argument(
        "--age-budget-ms",
        type=float,
        default=10000,
        help="Offline replay only: freshness and confirmation budget",
    )
    live = sub.add_parser(
        "live", help="Live Windows chart capture; disarmed and dry-run by default"
    )
    live.add_argument("--roi", type=int, nargs=4, required=True, metavar=("L", "T", "R", "B"))
    live.add_argument("--device", type=int, default=0)
    live.add_argument("--output", type=int, default=0)
    live.add_argument("--fps", type=int, default=60)
    mode = live.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--clipboard", choices=["windows"])
    live.add_argument(
        "--start", action="store_true", help="Start capture after warmup; still disarmed"
    )
    live.add_argument("--duration", type=float, help="Stop after this many seconds")
    live.add_argument("--max-frame-age-ms", type=float, default=1000)
    live.add_argument("--report", type=Path, help="New JSONL file; refuses overwrite")
    live.add_argument(
        "--activity-gate-ms",
        type=float,
        default=0,
        help="Experimental bounded periodic scan; 0 disables skipping",
    )
    for command in (image, replay):
        command.add_argument("--arm", action="store_true")
        command.add_argument("--confidence", type=float, default=0.96)
    for command in (image, replay, live):
        command.add_argument("--profile", choices=["discount", "game"], default="discount")
        add_ocr_arguments(command)
    return root


def run_live(args: argparse.Namespace, recognizer: RapidRecognizer) -> int:
    import math

    from .live import Controls, LiveConfig, LiveSession

    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        raise ValueError("duration must be finite and positive")
    controls = Controls()
    config = LiveConfig(
        Rect(*args.roi),
        device=args.device,
        output=args.output,
        fps=args.fps,
        dry_run=args.clipboard != "windows",
        max_frame_age_ms=args.max_frame_age_ms,
        activity_gate_ms=args.activity_gate_ms,
        profile=args.profile,
    )
    report = args.report.open("x", encoding="utf-8") if args.report else None

    def emit(event: dict[str, Any]) -> None:
        if report is not None:
            report.write(json.dumps(event) + "\n")
            report.flush()
        kind = event["event"]
        if kind == "summary":
            print(json.dumps({"event": "stopped", "failure": event["failure"]}), flush=True)
        elif kind == "frame":
            status = event["status"]
            if status in {"copied", "would_copy"} or event.get("error"):
                print(
                    json.dumps({"event": status, "code": event["code"], "error": event["error"]}),
                    flush=True,
                )
        elif kind in {
            "waiting",
            "started",
            "ready",
            "armed",
            "arm_rejected",
            "disarmed",
            "status",
            "error",
        }:
            print(json.dumps(event), flush=True)

    def console() -> None:
        try:
            for line in sys.stdin:
                try:
                    controls.send(line)
                except (ValueError, RuntimeError) as exc:
                    print(str(exc), file=sys.stderr, flush=True)
                if controls.stop.is_set():
                    return
        finally:
            if not controls.stop.is_set():
                controls.send("stop")  # Closed input never leaves an unattended armed process.

    try:
        if args.start:
            controls.send("start")
        Thread(target=console, name="console-controls", daemon=True).start()
        return LiveSession(recognizer, config, controls, emit).run(args.duration)
    finally:
        if report is not None:
            report.close()


def replay(args: argparse.Namespace, recognizer: RapidRecognizer) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    roi = Rect(*manifest["roi"])
    cases: list[dict[str, Any]] = []
    durations: list[float] = []
    for case in manifest["cases"]:
        clipboard = MemoryClipboard()
        policy = DecisionPolicy(
            PolicyConfig(
                min_confidence=args.confidence,
                profile=args.profile,
                max_frame_age_ms=args.age_budget_ms,
                confirmation_window_ms=args.age_budget_ms,
            )
        )
        pipeline = Pipeline(recognizer, clipboard, roi, policy)
        outcomes = []
        for sequence, item in enumerate(case["frames"]):
            pixels = read_image(args.manifest.parent / item["file"])
            frame = Frame(pixels, sequence, perf_counter_ns())
            if sequence == 0:
                pipeline.baseline(frame)
                if args.arm:
                    policy.arm()
            else:
                outcome = pipeline.process(frame)
                outcomes.append(asdict(outcome))
                durations.append(outcome.timings_ms["process"])
        expected = case["expected_writes"] if args.arm else []
        cases.append(
            {
                "id": case["id"],
                "expected": expected,
                "writes": clipboard.writes,
                "passed": clipboard.writes == expected,
                "outcomes": outcomes,
            }
        )
    passed = all(case["passed"] for case in cases)
    print(
        json.dumps(
            {
                "passed": passed,
                "clipboard": "memory",
                "armed_requested": args.arm,
                "provider": recognizer.provider,
                "offline_age_budget_ms": args.age_budget_ms,
                "cases": cases,
                "process_ms": {str(p): float(np.percentile(durations, p)) for p in (50, 95, 99)}
                if durations
                else {},
                "timing_note": "Sequential file replay, NOT captured-frame-to-clipboard latency.",
            },
            indent=2,
        )
    )
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    arg_parser = parser()
    args = arg_parser.parse_args(argv)
    try:
        if args.command == "generate":
            path = generate(args.output, args.seed, args.count, args.challenge)
            print(json.dumps({"manifest": str(path.resolve())}))
            return 0
        if args.command == "image":
            if args.arm and args.baseline is None:
                arg_parser.error("--arm requires a separate --baseline image")
            if args.clipboard == "windows" and not args.arm:
                arg_parser.error("--clipboard windows requires explicit --arm")
        recognizer = recognizer_from_args(args)
        recognizer.warmup()
        if args.command == "live":
            return run_live(args, recognizer)
        if args.command == "replay":
            return replay(args, recognizer)
        clipboard = WindowsClipboard() if args.clipboard == "windows" else MemoryClipboard()
        policy = DecisionPolicy(
            PolicyConfig(
                min_confidence=args.confidence,
                confirmations=args.confirmations,
                profile=args.profile,
            )
        )
        pipeline = Pipeline(recognizer, clipboard, Rect(*args.roi), policy)
        if args.baseline:
            pipeline.baseline(Frame(read_image(args.baseline), 0, perf_counter_ns()))
        if args.arm:
            policy.arm()
        pixels = read_image(args.path)
        outcome = pipeline.process(Frame(pixels, 1, perf_counter_ns()))
        print(json.dumps({"clipboard": args.clipboard, "outcome": asdict(outcome)}, indent=2))
        return 1 if outcome.status == "clipboard_failed" else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
