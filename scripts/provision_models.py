"""Explicit setup-only download from the pinned RapidOCR registry; verifies every SHA256."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import rapidocr
import yaml


def main():
    registry = yaml.safe_load(
        (Path(rapidocr.__file__).parent / "default_models.yaml").read_text(encoding="utf-8")
    )["onnxruntime"]
    root = Path(__file__).resolve().parents[1] / "models"
    root.mkdir(exist_ok=True)
    records = []
    for version, task, key in [
        ("PP-OCRv6", "det", "multi_PP-OCRv6_det_tiny"),
        ("PP-OCRv6", "rec", "multi_PP-OCRv6_rec_tiny"),
        ("PP-OCRv4", "det", "ch_PP-OCRv4_det_mobile"),
        ("PP-OCRv4", "rec", "en_PP-OCRv4_rec_mobile"),
    ]:
        spec = registry[version][task][key]
        url, expected = spec["model_dir"], spec["SHA256"]
        path = root / url.rsplit("/", 1)[1]
        if path.exists():
            data = path.read_bytes()
        else:
            with urlopen(url, timeout=90) as response:
                data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest.lower() != expected.lower():
            raise RuntimeError(f"Model checksum mismatch: {path.name}")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(data)
        records.append({"file": path.name, "url": url, "sha256": digest, "bytes": len(data)})
        print(json.dumps(records[-1]), flush=True)
    (root / "provenance.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
