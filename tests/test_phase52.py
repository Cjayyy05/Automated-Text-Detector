"""Headless diagnostic guards; fake capture is never reported as live validation."""

import ctypes
import json
import sys
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def capture_tool(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import capture_roi

    return capture_roi


def args(monkeypatch, directory, *, capture=True):
    monkeypatch.setattr(
        sys,
        "argv",
        ["capture_roi", "--roi", "0", "0", "20", "10", "--directory", str(directory)]
        + (["--capture"] if capture else []),
    )


def test_snapshot_requires_opt_in_before_creating_evidence(capture_tool, tmp_path, monkeypatch):
    destination = tmp_path / "evidence"
    args(monkeypatch, destination, capture=False)
    with pytest.raises(SystemExit) as result:
        capture_tool.main()
    assert result.value.code == 2
    assert not destination.exists()


@pytest.mark.parametrize("fail", [False, True])
def test_snapshot_releases_source_and_never_claims_manual_pass(
    capture_tool, tmp_path, monkeypatch, fail
):
    closed = []

    class Source:
        def __init__(self, *args):
            pass

        def grab(self):
            if fail:
                raise RuntimeError("capture unavailable")
            return np.full((10, 20, 3), 37, np.uint8)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(capture_tool, "DxcamSource", Source)
    destination = tmp_path / "evidence"
    args(monkeypatch, destination)
    assert capture_tool.main() == int(fail)
    assert closed == [True]
    result = json.loads((destination / "capture.json").read_text())
    assert result["manual_result"] == "NOT_RUN"
    assert bool(result["error"]) is fail
    assert (destination / "roi.png").exists() is not fail


def test_snapshot_refuses_existing_evidence(capture_tool, tmp_path, monkeypatch):
    sentinel = tmp_path / "roi.png"
    sentinel.write_bytes(b"user data")
    args(monkeypatch, tmp_path)
    with pytest.raises(FileExistsError):
        capture_tool.main()
    assert sentinel.read_bytes() == b"user data"


def test_read_only_inventory_displayconfig_abi(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import display_inventory as inventory

    assert ctypes.sizeof(inventory.Source) == 20
    assert ctypes.sizeof(inventory.Target) == 48
    assert ctypes.sizeof(inventory.DisplayPath) == 72
    assert ctypes.sizeof(inventory.Header) == 20
    assert ctypes.sizeof(inventory.ColorInfo2) == 36
