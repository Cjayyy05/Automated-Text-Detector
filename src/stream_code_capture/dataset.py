"""Local evaluation data only. Never imported by live recognition or policy.

Frames are lossless copies; annotations and source timestamps are evaluation metadata.
Splits join entire sessions, repeated identities and duplicate pixels before partitioning.
"""

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .domain import Image, Rect

LABEL_FIELDS = ("frame_id", "event_id", "state", "code", "box", "roi", "tags", "reviewer")
STATES = {"baseline", "visible", "partial", "negative", "unknown"}


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def image_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Frame path must stay inside its dataset directory")
    return path


def load_pixels(path: Path) -> Image:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    return np.asarray(image, dtype=np.uint8)


def store_frame(
    root: Path, pixels: Image, index: int, source_index: int, timestamp_ms: float | None
) -> dict[str, Any]:
    name = f"frames/{index:07d}.png"
    path = root / name
    ok, encoded = cv2.imencode(".png", pixels)
    if not ok:
        raise ValueError("PNG encoding failed")
    with path.open("xb") as handle:
        handle.write(encoded.tobytes())
    return {
        "frame_id": str(index),
        "file": name,
        "sha256": digest(path),
        "pixel_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
        "width": pixels.shape[1],
        "height": pixels.shape[0],
        "source_index": source_index,
        "timestamp_ms": timestamp_ms,
    }


def prepare(
    sources: list[Path],
    output: Path,
    *,
    session: str,
    kind: str,
    stride: int = 1,
    start: int = 0,
    stop: int | None = None,
    max_frames: int = 3000,
) -> Path:
    if not session.strip() or kind not in {"recording", "screenshot", "synthetic"}:
        raise ValueError("Specify a session identity and recording/screenshot/synthetic origin")
    if not sources or any(not path.is_file() for path in sources):
        raise ValueError("Inputs must be existing local files; URLs/cameras are not accepted")
    if stride < 1 or start < 0 or max_frames < 1 or (stop is not None and stop <= start):
        raise ValueError("Invalid extraction bounds")
    if kind == "recording" and len(sources) != 1:
        raise ValueError("Prepare one recording at a time")
    allowed = (
        {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
        if kind == "recording"
        else {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    )
    if any(path.suffix.lower() not in allowed for path in sources):
        raise ValueError(
            "Unsupported local media extension; playlists/network sources are not accepted"
        )
    output.mkdir(parents=True, exist_ok=False)
    (output / "frames").mkdir()
    data: dict[str, Any] = {
        "schema": 1,
        "session_id": session,
        "source_kind": kind,
        "sources": [{"name": p.name, "sha256": digest(p)} for p in sources],
        "frames": [],
        "labelled": False,
        "extraction": {"start": start, "stop": stop, "stride": stride, "max_frames": max_frames},
        "timestamp_basis": "unavailable for images",
    }
    if kind == "recording":
        capture = cv2.VideoCapture(str(sources[0].resolve()))
        try:
            if not capture.isOpened():
                raise ValueError("Local video decoder could not open the recording")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            data["decoder"] = capture.getBackendName()
            data["reported_fps"] = fps if math.isfinite(fps) and fps > 0 else None
            data["timestamp_basis"] = "decoder CAP_PROP_POS_MSEC; not capture or verified VFR PTS"
            index = 0
            while stop is None or index < stop:
                ok, pixels = capture.read()
                if not ok:
                    data["end_reason"] = "decoder_end_or_failure"
                    break
                if index >= start and (index - start) % stride == 0:
                    stamp = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                    data["frames"].append(
                        store_frame(
                            output,
                            np.asarray(pixels, dtype=np.uint8),
                            len(data["frames"]),
                            index,
                            stamp if math.isfinite(stamp) and stamp >= 0 else None,
                        )
                    )
                    if len(data["frames"]) >= max_frames:
                        data["end_reason"] = "max_frames"
                        break
                index += 1
        finally:
            capture.release()
    else:
        for index in range(start, min(stop or len(sources), len(sources)), stride):
            data["frames"].append(
                store_frame(
                    output,
                    load_pixels(sources[index]),
                    len(data["frames"]),
                    index,
                    None,
                )
            )
            if len(data["frames"]) >= max_frames:
                data["end_reason"] = "max_frames"
                break
    if not data["frames"]:
        raise ValueError("No frames extracted; incomplete output retained for inspection")
    data.setdefault("end_reason", "requested_stop_or_image_list_end")
    save_json(output / "dataset.json", data)
    with (output / "labels.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        for frame in data["frames"]:
            writer.writerow({"frame_id": frame["frame_id"], "state": "unknown"})
    return output / "dataset.json"


def parse_rect(text: str, width: int, height: int) -> list[int]:
    values = [int(value) for value in text.split()]
    if len(values) != 4:
        raise ValueError("Rectangles require four space-separated integers: left top right bottom")
    Rect(*values).validate(width, height)
    return values


def annotate(manifest: Path, labels: Path, output: Path) -> None:
    if output.parent.resolve() != manifest.parent.resolve():
        raise ValueError("Labelled manifest must remain beside its relative frame files")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    with labels.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != set(LABEL_FIELDS):
            raise ValueError("Unexpected label CSV columns")
        rows = list(reader)
    by_id = {row["frame_id"]: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {f["frame_id"] for f in data["frames"]}:
        raise ValueError("Labels must cover every frame exactly once")
    for frame in data["frames"]:
        row = by_id[frame["frame_id"]]
        frame["label"] = {key: row[key] for key in ("event_id", "state", "code", "reviewer")}
        frame["label"].update(
            {
                "box": parse_rect(row["box"], frame["width"], frame["height"])
                if row["box"]
                else None,
                "roi": parse_rect(row["roi"], frame["width"], frame["height"]),
                "tags": [value.strip() for value in row["tags"].split(";") if value.strip()],
            }
        )
    data["labelled"] = True
    data["labels_sha256"] = digest(labels)
    validate(data, manifest.parent)
    save_json(output, data)


def validate(data: dict[str, Any], root: Path) -> None:
    if data.get("schema") != 1 or not data.get("labelled") or not data.get("frames"):
        raise ValueError("A nonempty labelled schema-1 dataset is required")
    if (
        not data.get("session_id")
        or data.get("source_kind") not in {"recording", "screenshot", "synthetic"}
        or not data.get("sources")
    ):
        raise ValueError("Missing source provenance")
    seen: set[str] = set()
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for frame in data["frames"]:
        identity = frame["frame_id"]
        if identity in seen:
            raise ValueError("Duplicate frame identity")
        seen.add(identity)
        path = image_path(root, frame["file"])
        if digest(path) != frame["sha256"]:
            raise ValueError("Frame hash changed")
        pixels = load_pixels(path)
        if pixels.shape[:2] != (frame["height"], frame["width"]) or (
            hashlib.sha256(pixels.tobytes()).hexdigest() != frame["pixel_sha256"]
        ):
            raise ValueError("Decoded frame identity changed")
        label = frame["label"]
        state, code = label["state"], label["code"]
        if state not in STATES or not label["event_id"] or not label["reviewer"].strip():
            raise ValueError("Every frame requires a state, event and reviewer")
        if code and any(not 33 <= ord(character) <= 126 for character in code):
            raise ValueError(
                "Transcribe exact printable ASCII without whitespace; never normalize case"
            )
        if state in {"baseline", "negative", "unknown"} and code:
            raise ValueError("Only visible/partial targets carry a code identity")
        if state == "visible" and (not code or label["box"] is None):
            raise ValueError("Visible targets require independent exact truth and a code box")
        roi = Rect(*label["roi"])
        roi.validate(frame["width"], frame["height"])
        if label["box"] is not None:
            box = Rect(*label["box"])
            box.validate(frame["width"], frame["height"])
            if not (
                roi.left <= box.left < box.right <= roi.right
                and roi.top <= box.top < box.bottom <= roi.bottom
            ):
                raise ValueError("Code box must lie within the selected chart ROI")
        events[label["event_id"]].append(frame)
    for frames in events.values():
        labels = [frame["label"] for frame in frames]
        if len({tuple(label["roi"]) for label in labels}) != 1:
            raise ValueError("ROI must remain fixed within an event")
        if len({label["code"] for label in labels if label["code"]}) > 1:
            raise ValueError("Use a separate event for each target code identity")
        indices = [frame["source_index"] for frame in frames]
        if indices != sorted(set(indices)):
            raise ValueError("Event frames must have strictly increasing source indices")
        if any(label["state"] == "baseline" for label in labels[1:]):
            raise ValueError("Only the first event frame may be its baseline")


def load_dataset(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    validate(data, path.parent)
    return data


def leakage_keys(data: dict[str, Any]) -> set[str]:
    keys = {"session:" + data["session_id"]}
    keys.update("source:" + item["sha256"] for item in data["sources"])
    keys.update("pixels:" + frame["pixel_sha256"] for frame in data["frames"])
    keys.update(
        "code:" + frame["label"]["code"] for frame in data["frames"] if frame["label"]["code"]
    )
    return keys


def audit_split(path: Path) -> list[dict[str, Any]]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = plan["datasets"]
    seen_paths: set[Path] = set()
    keys: dict[str, set[str]] = {"tuning": set(), "holdout": set()}
    for item in entries:
        manifest = Path(item["manifest"]).resolve()
        partition = item["partition"]
        if manifest in seen_paths or partition not in keys or digest(manifest) != item["sha256"]:
            raise ValueError("Duplicate manifest, invalid partition or changed frozen manifest")
        seen_paths.add(manifest)
        keys[partition].update(leakage_keys(load_dataset(manifest)))
    if not all(keys.values()) or keys["tuning"] & keys["holdout"]:
        raise ValueError("Empty partition or session/code/source/pixel leakage across split")
    return entries


def split_datasets(paths: list[Path], output: Path, *, seed: str, fraction: float = 0.25) -> None:
    if not 0 < fraction < 1 or len(set(p.resolve() for p in paths)) != len(paths):
        raise ValueError("Require unique manifests and a holdout fraction between zero and one")
    datasets = [load_dataset(path) for path in paths]
    parent = list(range(len(paths)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owners: dict[str, int] = {}
    for index, data in enumerate(datasets):
        for key in leakage_keys(data):
            if key in owners:
                parent[find(index)] = find(owners[key])
            owners[key] = index
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(paths)):
        groups[find(index)].append(index)
    if len(groups) < 2:
        raise ValueError("Fewer than two independent groups; cannot split without leakage")
    ordered = sorted(
        groups.values(),
        key=lambda group: hashlib.sha256(
            (seed + "|" + "|".join(sorted(digest(paths[i]) for i in group))).encode()
        ).hexdigest(),
    )
    target = max(1, round(len(paths) * fraction))
    holdout: set[int] = set()
    for group in ordered[:-1]:
        if len(holdout) >= target:
            break
        holdout.update(group)
    save_json(
        output,
        {
            "schema": 1,
            "seed": seed,
            "requested_holdout_fraction": fraction,
            "groups": len(groups),
            "note": "Freeze before tuning; synthetic is not real-video qualification.",
            "datasets": [
                {
                    "manifest": str(path.resolve()),
                    "sha256": digest(path),
                    "partition": "holdout" if index in holdout else "tuning",
                }
                for index, path in enumerate(paths)
            ],
        },
    )
