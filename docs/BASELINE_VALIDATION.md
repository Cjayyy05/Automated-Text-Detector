# Stream Code Capture v0.1.0 baseline review

Date: 2026-11-06, Asia/Kuala_Lumpur. This is a version-control baseline of the
existing implementation, not a new accuracy, latency or desktop qualification.
The operator explicitly requested the initial local commit and annotated v0.1.0
tag, with no push and no Auto-arm implementation.

## Repository and inclusion review

Initial `git status --short --branch` showed unborn `main`, no commits and no
staged files. Source, scripts, tests, documentation, dependency pins and an imported
`GameCode_OCR_StarterPack.zip` were untracked. No existing implementation was changed.
Only ignore rules and current-status documentation were updated for this review.

The baseline includes project text files only: `.gitignore`, `AGENTS.md`, README,
`pyproject.toml`, `requirements-lock.txt`, `docs/`, `scripts/`, `src/` and `tests/`.
The staged inventory was checked for binary/media files, generated directories,
unexpected extensions, large files and credential/private-key patterns. No sensitive
credentials or unnecessary generated/media files were found. Historical local paths,
display inventories and operator evidence in validation documents are intentional
project records. They should receive a separate privacy review before any publication.

`.gitignore` now covers virtual environments, environment secrets, credential/key
files, local settings/editor preferences, caches/build outputs, datasets/models/samples,
artifacts, logs/JSONL, recordings/captures/downloads, audio and ZIP imports. Representative
paths were verified with `git check-ignore --`, including `.env.production`,
`settings.local.json`, `recordings/probe.mp4`, `downloaded.wav` and the starter-pack ZIP.
Downloaded audio is not bundled; WAV test fixtures are generated in temporary storage.
The ZIP and all existing local artifacts remain on disk, excluded from Git.

`git diff --cached --check` reported existing two-space Markdown hard breaks in
`docs/PHASE52_MANUAL_RESULTS.md`. They are intentional formatting, preserved without
rewriting the evidence ledger. `git -c core.whitespace=-blank-at-eol diff --cached
--check` passed. Git's LF-to-CRLF notices reflect the existing Windows configuration.
Initial staging was denied by the sandbox's read-only `.git` access; the approved
`git add` retry succeeded. This was a repository-metadata permission issue, not a test
failure. No files were deleted and no remote operation was requested.

## Environment and executed checks

Existing Windows 11 build 26200 environment, Python 3.12.14, RapidOCR 3.10.0,
ONNX Runtime 1.31.1, PySide6 6.12.0, DXcam 0.3.0, pywin32 312, pytest 9.2.0,
Ruff 0.17.3 and mypy 2.4.1. Dependencies were not upgraded or downloaded.

| Command | Result |
|---|---|
| `./scripts/check.ps1` | Exit 0; pip check, Ruff lint/format (89 files), strict mypy (20 source files); 178 passed, 13 opt-in OCR skips in 45.03 s |
| `./scripts/check.ps1 -Ocr` | Exit 0; same dependency/static checks; 188 passed, three original strict challenge xfails in 67.47 s |
| Installed baseline model SHA256 comparison | Both hashes match the foundation record in `VALIDATION.md` |

Full outputs are retained locally in ignored `artifacts/baseline-check.txt` and
`artifacts/baseline-check-ocr.txt`. Real offline local-model OCR was exercised, including
the network-blocked integration test. The three tiny/compressed exact-recall xfails
remain unchanged. No live capture, native clipboard write, audio playback or manual
desktop qualification was performed for this baseline. Test durations are test-run
wall times, not capture or copy latency measurements.

Verified model SHA256 values:

- `PP-OCRv6_det_small.onnx`: `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`
- `PP-OCRv6_rec_small.onnx`: `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`

## Features and unresolved gates

The baseline has offline image/replay tools, live DXcam console capture, Discount/Game
profiles, and a PySide6 GUI with monitor/ROI selection, baseline readiness, explicit
arm/disarm, status/diagnostics and stop. Native GUI copying requires per-session consent
and supported-display checks. Verified-copy notification and a remembered local PCM WAV
preference are implemented. Auto-arm is absent. Disarmed startup, baseline-before-arm,
two fresh exact observations, one-shot copy, process-lifetime deduplication, freshness,
O/0/source-resolution abstention and clipboard-error disarming remain intact.

G2 has operator sign-off only for supervised personal use on center primary output 0,
1920x1080, 100%, SDR, local console and fixed topology, including the recorded 30 manual
paste matches and approved hotplug evidence substitution. Subsequent Discount/Game GUI
paste smoke results and usability observations are documented in `PHASE6_VALIDATION.md`.
Earlier phase pending statuses are historical and do not reverse that limited sign-off.

G3 representative independently labelled holdout accuracy/recall and required p95/p99
latency remain unmet. The <100 ms target is not achieved. Synthetic/captured fixtures
do not qualify arbitrary broadcasts; tiny text and O/0 remain unsupported. Full G4
UX/display/source-transition and release qualification remains incomplete, including
unconfirmed detailed ROI/resize/reload observations and broader DPI/display coverage.
Physical hotplug is deferred/unverified. Audible/custom-sound manual checks are pending.
Covering windows can provide eligible pixels; disarm before covering/moving the source.
See `PROJECT_SPEC.md`, `PHASE6_VALIDATION.md` and `PHASE52_MANUAL_RESULTS.md` for exact
scope, evidence and remaining checks. This tag does not promote experimental profiles,
relax thresholds or establish production readiness.
