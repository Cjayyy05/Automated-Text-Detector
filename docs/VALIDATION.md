# Validation record — 2026-10-29

For the current v0.1.0 Git baseline checks and qualification summary, see
[BASELINE_VALIDATION.md](BASELINE_VALIDATION.md). This file preserves the foundation
results; its pending statuses describe that earlier checkpoint.

This is the preserved **foundation/Phase 0 record**. See
[Phase 1 validation](PHASE1_VALIDATION.md) for live capture/native clipboard results,
new regression tests, source-quality guard and current latency measurements.

## What was actually verified

Empty repository inspected before writing: only `.git`, clean status, unborn `main`.
No user source files were overwritten. No commit, push, live capture, or real clipboard
write was performed. The offline foundation gate G1 passes; G2/G3/G4 do not pass yet.

Host: Windows 11 build 26200, AMD64 Family 25 Model 80 Stepping 0. Interpreter:
Python 3.12.14 from the Codex bundled runtime, then repository `.venv`. Normal `python`
and `py` Store aliases were unusable. This is an execution-host observation, not a
certified benchmark of the user's target streaming configuration.

Installed/verified: RapidOCR 3.10.0, ONNX Runtime 1.31.1, NumPy 2.5.4,
opencv-python-headless 5.0.0.93, DXcam 0.3.0, pywin32 312, pytest 9.2.0,
Ruff 0.17.3, mypy 2.4.1. PySide6 6.12.0 and hatchling 1.33.0 were checked against
PyPI; PySide6 is an uninstalled optional future GUI dependency. Build isolation used
the pinned hatchling. The exact installed transitive CPU/dev/Windows set is in
`requirements-lock.txt` (a constraints file, not a portable GPU lock).

Available ORT providers: AzureExecutionProvider and CPUExecutionProvider. Actual warmed
detector and recognizer sessions were checked to use CPUExecutionProvider. Azure was
not selected or used. Missing CUDA request failed with exit 2 rather than falling back.

## Commands and results

Commands ran at repository root. Native commands are checked individually by the final
PowerShell scripts; a later successful shell command must not conceal an earlier failure.

| Exact command | Result |
|---|---|
| `git status --short`; `git log -1 --oneline`; `Get-ChildItem -Force` | Empty working tree, no commits, only `.git` |
| `python --version`; `py -0p` | Failed: inaccessible Windows Store aliases |
| `& 'C:\Users\Teoh Chung Jay\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' --version` | Python 3.12.14 |
| Same executable with `-m venv .venv` | Initial ensurepip failed on sandbox temp permissions |
| `$env:TEMP = Join-Path (Get-Location) '.tmp'; $env:TMP = $env:TEMP; ./.venv/Scripts/python.exe -m ensurepip --upgrade` | Passed after creating `.tmp` |
| `./.venv/Scripts/python.exe -m pip install --disable-pip-version-check -e '.[dev,windows]'` | Installed successfully after network-enabled execution |
| `./.venv/Scripts/python.exe -m pip uninstall -y opencv-python` | Removed initially selected conflicting OpenCV distribution |
| `./.venv/Scripts/python.exe -m pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93` | Repaired shared cv2 files; project now depends only on headless |
| `./.venv/Scripts/python.exe -m pip install -e '.[dev,windows]'` | Refreshed final metadata successfully |
| `./.venv/Scripts/python.exe -m pip freeze --exclude-editable` | Saved exact resolution as `requirements-lock.txt` |
| `./scripts/setup.ps1 -Python 'C:\Users\Teoh Chung Jay\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'` | Final setup script verified, exit 0; frozen constraints installed, pip check clean |
| `./scripts/check.ps1 -Ocr` | Exit 0; pip check clean; Ruff lint/format clean; strict mypy clean (10 source modules); **35 tests passed in 23.94 s** |
| `./.venv/Scripts/python.exe -m stream_code_capture generate samples/smoke --seed 7 --count 3` | Exit 0; 20 PNGs, 3 positive cases + 1 negative case and manifest |
| `./.venv/Scripts/python.exe -m stream_code_capture replay samples/smoke/manifest.json --arm` | Exit 0; 3 exact one-shot memory writes, zero negative/JORDY writes |
| `./.venv/Scripts/python.exe -m stream_code_capture generate samples/challenge --seed 19 --count 3 --challenge` | Exit 0; harder generated fixtures |
| `./.venv/Scripts/python.exe -m stream_code_capture replay samples/challenge/manifest.json --arm` | **Exit 1, accuracy failure:** 2 missed codes and 1 wrong code; negative-only case had zero writes |
| `./.venv/Scripts/python.exe -m stream_code_capture image samples/smoke/case_000_1.png --roi 70 170 420 300` | Exit 0, disarmed, exact candidate recognized, no OS clipboard access |
| Previous image command with `--provider cuda` | Exit 2, requested CUDA provider not installed |

The first unit test run hit default sandbox temp-directory permissions. Scripts now use
the repository `.tmp` directory and restore environment variables afterward. Initial
Ruff formatting/default-argument findings and OpenCV ndarray typing errors were fixed.
Network-restricted PyPI lookup failed DNS; network-enabled PyPI queries and install then
succeeded. No automatic approval rejection blocked the final implementation.

The first real replay used the normal 1000 ms freshness limit and failed on stale frames.
This exposed slow inference. Final **offline** replay uses a reported 10000 ms freshness
and agreement budget. The runtime development defaults remain 1000 ms; the live gate still
requires a much shorter measured deadline. No live performance assertion was relaxed.

## Actual observations and limitations

Final standard replay (16 measured, sequential file-input frames, scale 2, threads 2):
p50 process **990.866 ms**, p95 **1162.896 ms**, p99 **1164.028 ms**. Challenge replay:
p50 **982.110 ms**, p95 **1175.628 ms**, p99 **1184.353 ms**. Tighter 350x130 image ROI:
process **363.309 ms** in the diagnostic run. These small samples are characterization,
not representative benchmark confidence intervals. They exclude startup/warmup and do
not measure capture, confirmation-to-first-frame latency, or real clipboard write time.
The under-100 ms goal is plainly **unmet** by this CPU baseline.

Challenge case 2 truth `6428IT02OE` was recognized as `6428IT020E`, with confidence 0.99655
on its first observation; repeated exact agreement did not catch the correlated O/0 error.
Cases 0 and 1 abstained/missed. This is a known wrong-copy risk in tiny, compressed text,
not just low recall. The challenge data and thresholds were not altered to conceal it.
The current policy cannot be advertised as reliable for the representative tiny chart
text until the held-out G3 gate passes. Default memory/disarmed CLI behavior prevents
unrequested OS writes, but explicit Windows clipboard diagnostics still use this imperfect
recognizer. There is no claim of calibrated OCR confidence or character-level certainty.

Generated standard fixtures use a less ambiguous alphabet; the challenge profile includes
all A–Z and 0–9. Standard results are therefore a **smoke test**, not evidence of universal
code accuracy. No real livestream screenshot/video was supplied as a local test asset.
The synthetic chart was visually inspected; the production application does not consume
fixture truth, seed, streamer name, JORDY denylist, or screenshot coordinates.

The integration test blocks Python socket connection calls through startup, warmup and
real inference. Unit tests use injected OCR lines to isolate policy behavior; those tests
are not counted as OCR accuracy. The real OCR test consumes generated pixels. The latest
slot's 100 publications/one take test shows 99 replaced pending frames; real capture-thread
and memory-pressure validation remain G2 work.

Raw JSON reports are local, regenerable, git-ignored artifacts:
`artifacts/smoke-replay.json`, `artifacts/challenge-replay.json`, and
`artifacts/image-preview.json`. Generated `samples/` and `.venv/` are also ignored.

## Model identity

SHA256 of the installed bundled models used in these runs:

| Model | SHA256 |
|---|---|
| PP-OCRv6_det_small.onnx | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |
| PP-OCRv6_rec_small.onnx | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` |

The recognizer verifies local model files and embedded dictionary, and warms real text
so lazy recognition initialization occurs before input. It checks actual provider lists
for both sessions. Hashes are recorded here for audit; runtime does not enforce these hashes.

## API/version evidence

Versions were queried directly from `https://pypi.org/pypi/<package>/json` for rapidocr,
onnxruntime, numpy, opencv-python, dxcam, pywin32, PySide6, pytest, ruff, mypy, Pillow and
hatchling; the headless OpenCV pin was then resolved/installed and checked. Primary references:

- [RapidOCR package 3.10.0](https://pypi.org/project/rapidocr/3.10.0/)
- [RapidOCR usage and output fields](https://rapidai.github.io/RapidOCRDocs/latest/install_usage/rapidocr/usage/)
- [DXcam package 0.3.0](https://pypi.org/project/dxcam/0.3.0/)
- [DXcam source and timestamp/latest-frame API](https://github.com/ra1nty/DXcam/blob/main/dxcam/dxcam.py)
- [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/)

Installed `rapidocr/config.yaml`, `main.py`, recognition dictionary loading,
`inference_engine/onnxruntime/main.py` and `provider_config.py` were inspected. This confirmed
explicit model-path parameters, BGR NumPy input, result fields, thread/provider flags, lazy
loading and session provider checks. Installed DXcam source confirmed `start`,
`get_latest_frame(copy=True, with_timestamp=True)` and `video_mode`; importing/inspecting
APIs is not live capture validation. pywin32 was installed; the clipboard adapter itself
was not exercised against the user's actual clipboard.

## Next gate

G2: implement and manually validate real Windows region capture through the newest-frame
handoff into OCR/policy and the real clipboard, with baseline readiness, arming, timestamp
traces and source-loss handling. Follow `WINDOWS_VALIDATION.md`. Keep the known G3 speed
and O/0 accuracy failures visible while evaluating smaller models/crops and CPU/GPU
alternatives. No extensive GUI, live capture success, or deployment readiness is claimed.

## Added file inventory

All source/documentation files below are new; the repository had no prior tracked source.

```text
.gitignore
AGENTS.md
README.md
pyproject.toml
requirements-lock.txt
docs/PROJECT_SPEC.md
docs/VALIDATION.md
docs/WINDOWS_VALIDATION.md
scripts/setup.ps1
scripts/check.ps1
src/stream_code_capture/__init__.py
src/stream_code_capture/__main__.py
src/stream_code_capture/domain.py
src/stream_code_capture/ocr.py
src/stream_code_capture/policy.py
src/stream_code_capture/pipeline.py
src/stream_code_capture/clipboard.py
src/stream_code_capture/latest.py
src/stream_code_capture/synthetic.py
src/stream_code_capture/cli.py
tests/conftest.py
tests/test_policy.py
tests/test_pipeline.py
tests/test_synthetic.py
tests/test_ocr_integration.py
```
