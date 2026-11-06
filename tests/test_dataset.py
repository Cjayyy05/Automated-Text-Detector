import csv
import json
from copy import deepcopy

import cv2
import numpy as np
import pytest

from stream_code_capture.dataset import (
    LABEL_FIELDS,
    annotate,
    audit_split,
    digest,
    image_path,
    load_dataset,
    prepare,
    save_json,
    split_datasets,
    store_frame,
    validate,
)
from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.evaluation import evaluate


def make_dataset(root, *, session="session", code="AB23CD45EF", value=10, states=None):
    (root / "frames").mkdir(parents=True)
    data = {
        "schema": 1,
        "labelled": True,
        "session_id": session,
        "source_kind": "synthetic",
        "sources": [{"name": session, "sha256": session}],
        "frames": [],
    }
    for index, state in enumerate(states or ["baseline", "visible", "visible"]):
        frame = store_frame(
            root, np.full((80, 200, 3), value + index, np.uint8), index, index, None
        )
        frame["label"] = {
            "event_id": "e",
            "state": state,
            "code": code if state in {"visible", "partial"} else "",
            "box": [5, 5, 150, 25] if state in {"visible", "partial"} else None,
            "roi": [0, 0, 200, 80],
            "tags": [],
            "reviewer": "unit fixture",
        }
        data["frames"].append(frame)
    path = root / "labelled.json"
    save_json(path, data)
    return path


def test_prepare_label_round_trip_exact_case_and_source_hash(tmp_path):
    source = tmp_path / "source.png"
    cv2.imwrite(str(source), np.full((80, 200, 3), 30, np.uint8))
    path = prepare([source], tmp_path / "data", session="recording-A", kind="screenshot")
    assert json.loads(path.read_text())["sources"][0]["sha256"] == digest(source)
    csv_path = path.parent / "review.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerow(
            dict(
                frame_id="0",
                event_id="event",
                state="visible",
                code="aB-01",
                box="5 5 150 25",
                roi="0 0 200 80",
                tags="small;slanted",
                reviewer="AB/CD",
            )
        )
    labelled = path.parent / "labelled.json"
    annotate(path, csv_path, labelled)
    assert load_dataset(labelled)["frames"][0]["label"]["code"] == "aB-01"
    with pytest.raises(FileExistsError):
        annotate(path, csv_path, labelled)
    with pytest.raises(FileExistsError):
        prepare([source], path.parent, session="recording-A", kind="screenshot")


def test_local_video_decode_index_stride_and_limit(tmp_path):
    # Real codec encode/decode of synthetic pixels, no display/capture. Not real-video accuracy.
    source = tmp_path / "synthetic.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 60))
    assert writer.isOpened(), "Pinned OpenCV environment must support the test MJPEG codec"
    for index in range(6):
        writer.write(np.full((60, 80, 3), index * 20, np.uint8))
    writer.release()
    path = prepare(
        [source],
        tmp_path / "frames",
        session="synthetic-codec-test",
        kind="recording",
        start=1,
        stride=2,
        max_frames=2,
    )
    data = json.loads(path.read_text())
    assert [f["source_index"] for f in data["frames"]] == [1, 3]
    assert data["end_reason"] == "max_frames"
    assert "not capture" in data["timestamp_basis"]


@pytest.mark.parametrize("name", ["../escape.png", "C:/escape.png"])
def test_frame_paths_cannot_escape_dataset(tmp_path, name):
    with pytest.raises(ValueError):
        image_path(tmp_path, name)


def test_changed_pixels_rejected(tmp_path):
    path = make_dataset(tmp_path / "data")
    frame = path.parent / "frames/0000001.png"
    cv2.imwrite(str(frame), np.zeros((80, 200, 3), np.uint8))
    with pytest.raises(ValueError, match="hash changed"):
        load_dataset(path)


@pytest.mark.parametrize(
    "change",
    [
        "missing_code",
        "missing_reviewer",
        "box_outside_roi",
        "roi_change",
        "order",
        "multiple_codes",
        "late_baseline",
    ],
)
def test_invalid_annotations_fail_closed(tmp_path, change):
    path = make_dataset(tmp_path / "data")
    data = json.loads(path.read_text())
    label = data["frames"][1]["label"]
    if change == "missing_code":
        label["code"] = ""
    elif change == "missing_reviewer":
        label["reviewer"] = ""
    elif change == "box_outside_roi":
        label["roi"] = [10, 10, 200, 80]
    elif change == "roi_change":
        label["roi"] = [0, 0, 190, 80]
    elif change == "order":
        data["frames"][2]["source_index"] = 0
    elif change == "multiple_codes":
        label["code"] = "OTHER12345"
    else:
        data["frames"][2]["label"] = deepcopy(data["frames"][0]["label"])
    with pytest.raises(ValueError):
        validate(data, path.parent)


def test_session_and_code_transitive_split_and_freeze(tmp_path):
    # A-B share session, B-C share code: all three must stay together.
    a = make_dataset(tmp_path / "a", session="s1", code="AB23CD45EF", value=10)
    b = make_dataset(tmp_path / "b", session="s1", code="FG23CD45EF", value=20)
    c = make_dataset(tmp_path / "c", session="s2", code="FG23CD45EF", value=30)
    d = make_dataset(tmp_path / "d", session="s3", code="XY23CD45EF", value=40)
    split = tmp_path / "split.json"
    split_datasets([a, b, c, d], split, seed="unit")
    entries = audit_split(split)
    assert len({e["partition"] for e in entries[:3]}) == 1
    assert entries[0]["partition"] != entries[3]["partition"]
    changed = json.loads(d.read_text())
    changed["session_id"] = "edited"
    d.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="changed frozen"):
        audit_split(split)


def test_duplicate_pixels_cannot_cross_split(tmp_path):
    a = make_dataset(tmp_path / "a", session="a", value=10)
    b = make_dataset(tmp_path / "b", session="b", value=10, code="FG23CD45EF")
    with pytest.raises(ValueError, match="cannot split"):
        split_datasets([a, b], tmp_path / "split.json", seed="unit")


class PixelRecognizer:
    def warmup(self):
        pass

    def recognize(self, pixels):
        # Injected recognition evidence, not an OCR accuracy claim.
        if int(pixels[0, 0, 0]) == 10:
            return []
        return [
            TextLine("AB23CD45EF", 0.99, Rect(5, 5, 150, 25)),
            TextLine("100% off", 0.99, Rect(5, 35, 150, 55)),
        ]


def test_memory_replay_counts_exact_and_never_uses_annotation_box_for_recognition(tmp_path):
    path = make_dataset(tmp_path / "data")
    result = evaluate(path, PixelRecognizer())
    assert result["accuracy"]["exact_copies"] == 1
    assert result["accuracy"]["incorrect_writes"] == 0
    assert result["live_end_to_end_ms"] is None
    assert result["events"][0]["writes"] == ["AB23CD45EF"]


def test_wrong_and_partial_writes_are_counted_not_hidden(tmp_path):
    wrong = evaluate(make_dataset(tmp_path / "wrong", code="XY23CD45EF"), PixelRecognizer())
    partial = evaluate(
        make_dataset(tmp_path / "partial", states=["baseline", "partial", "partial"]),
        PixelRecognizer(),
    )
    assert wrong["accuracy"]["incorrect_writes"] == 1
    assert wrong["accuracy"]["exact_copies"] == 0
    assert partial["accuracy"]["incorrect_writes"] == 1
    assert partial["accuracy"]["unsafe_partial_writes"] == 1


def test_snapshot_never_invents_confirmation_or_clipboard_events(tmp_path):
    result = evaluate(
        make_dataset(tmp_path / "data", states=["visible"], value=11), PixelRecognizer()
    )
    assert result["accuracy"]["snapshot_events"] == 1
    assert result["accuracy"]["positive_events"] == 0
    assert result["accuracy"]["raw_exact_frames"] == 1
    assert result["events"][0]["writes"] == []


def test_unknown_annotations_block_evaluation(tmp_path):
    path = make_dataset(tmp_path / "data", states=["unknown"])
    with pytest.raises(ValueError, match="unknown"):
        evaluate(path, PixelRecognizer())


def test_duplicate_roi_cannot_supply_second_confirmation(tmp_path):
    path = make_dataset(tmp_path / "data")
    data = json.loads(path.read_text())
    frame = deepcopy(data["frames"][1])
    frame["frame_id"], frame["source_index"] = "2", 2
    data["frames"][2] = frame
    path.write_text(json.dumps(data))
    result = evaluate(path, PixelRecognizer())
    assert result["accuracy"]["duplicate_roi_frames"] == 1
    assert result["accuracy"]["abstentions"] == 1
    assert result["events"][0]["writes"] == []
