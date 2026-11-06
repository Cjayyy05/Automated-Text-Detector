# Game redemption-code profile and captured playback validation

Date: 2026-11-01, Asia/Kuala_Lumpur. Existing Windows 11 / Python 3.12.14 environment,
AMD Ryzen 5 5600H, CPUExecutionProvider, pinned RapidOCR 3.10.0 / ONNX Runtime 1.31.1 /
DXcam 0.3.0 / pywin32 312. No dependency, model or OCR algorithm changes. No native
clipboard writes, application GUI, packaging, commits or pushes in this work.
The explicitly invoked playback harness opened temporary test-stimulus windows.

**Functional support is implemented; repeatable playback, <100 ms latency and general
livestream qualification have not passed. GUI development remains deferred.**
One narrow-ROI run copied 8/8, but a second seed copied 7/8. Zero wrong writes were
observed in either run. Eight previously evaluated images cannot establish general accuracy.

## Implementation and safeguards

- `--profile discount` remains the default for image, replay and live commands. Original
  discount format/context behavior and all existing tests remain intact.
- `--profile game` accepts exact uppercase ASCII alphanumeric strings, with optional
  internal single hyphens, 8–20 characters including separators, containing a letter and
  digit. Nearby recognized expiry/redemption context is required: English `Expiry Date`
  or `Redemption Code`, Japanese `有効期限`, or Chinese `有效期至` / `兑换码` / `兌換碼`.
  Other wording, lowercase, purely alphabetic/numeric codes and arbitrary formats are
  unsupported. There is no screenshot code, streamer or background allowlist.
- Game context may be beside, above or below the code; maximum horizontal and vertical
  box gaps are four and two code-line heights respectively. Context must have a real OCR
  score >=0.75 and no quality rejection. Code score remains >=0.96. These scores are not
  calibrated probabilities of exact correctness.
- Game applies O/0 abstention and a >=10 source-pixel average character pitch explicitly,
  including hyphenated/long strings outside the adapter's original discount format.
  Existing OCR rejection reasons cannot be overridden. Characters are never repaired.
- Existing DXcam source, capacity-one handoff, single-owner pipeline, baseline-before-arm,
  two distinct fresh observations, one-shot copy, lifetime deduplication, 1000 ms freshness,
  stop/disarm inhibition and clipboard-error handling are reused. No runtime OCR queue,
  template matching, model change, threshold relaxation or label-assisted recognition.
- Game currently requires the baseline OCR model through the CLI. Experimental tiny/v4
  modes are refused because existing fallback candidate verification is discount-specific.
- Dataset evaluation accepts `--profile`; it remains memory-only and keeps standalone
  screenshots disarmed. Recognition/candidate counts are distinct from copy counts.
- New tests exercise profile selection, malformed/uncertain strings, proximity, source
  quality, multiple candidates, baseline suppression, confirmations, rearm/dedup, CLI
  model restrictions and a newly generated hyphenated code through real OCR to memory.
  That synthetic hyphen check uses the existing generous offline accuracy timing budget;
  it is not captured latency or proof of broadcast hyphen accuracy.

## Harness and measurement definition

`scripts/game_playback.py` loads the existing audited split, resizes its screenshots to
960x540, shuffles their order and schedules gaps of 1.2–2.1 seconds and appearances of
2.5–4.5 seconds. A seed makes the schedule reproducible; the recognizer does not receive
the seed, schedule, expected text or labels. Exposure ends on time, regardless of success.
The last two events repeat the first code and show a new generated bare code without
redemption context. Existing reward/date text remains in the captured band. Top chat is
outside it. Small moving pixels keep the display changing while the code image is static.

This is simulated playback of still images, **not an independently recorded livestream**.
Changing pixels exercise fresh capture/duplicate filtering, but repeated slide glyphs are
not independent evidence against systematic OCR errors. The test controller explicitly
disarms and rearms between appearances; the product does not automatically rearm.

Pixels reach OCR only through the actual Windows display and DXcam. The default test ROI
is `(200,400,960,540)` relative to the test window at `(50,50)`, or physical
`(250,450,1010,590)` on the primary output. These fixture coordinates are configurable via
`--roi`; production capture has no default code coordinates or assumed background.

A small colored test marker identifies the event at capture, before frames can be
overwritten in the latest slot. End-to-end time is first marker-containing acquisition
start to completion of the successful **memory** clipboard write, including dropped-frame
delay and confirmation. Acquisition start is a local monotonic timestamp before `grab`,
not an exact video presentation timestamp. Markers are scoring metadata, never code targets.
Stage measurements remain in the normal LiveSession JSONL events. First-observed latency
in the session summary is different from this first-captured event metric.

Every code event counts toward recall, including misses. Latency percentiles describe only
successful writes, with sample counts shown; a miss has no finite clipboard latency.
No test changes confidence, confirmation or age limits to pass. A nonzero exit and
`test_result.passed: false` retain failed playback results.

## Results

Fresh evaluation of the original eight full-resolution files with the new game profile:
**8/8 raw exact, 8/8 eligible exact, zero writes** (snapshots intentionally disarmed).
The frozen split has six tuning and two holdout files, but all eight were already evaluated
previously and inspected for this feature. The partition name does not make this an unseen
game-domain qualification set. Imported labels retain their original visual-review limits.

| Captured simulated run | Correct / 8 | Wrong writes | Abstentions | Successful p50 / p95 / worst, ms |
|---|---:|---:|---:|---|
| Initial 960x140 ROI, faulty overlay | 4 | 0 | 4 | 1092.8 / 1146.1 / 1152.9 (n=4) |
| Corrected overlay, 960x140 ROI | 6 | 0 | 2 | 1087.9 / 1419.1 / 1472.6 (n=6) |
| 760x140 ROI, seed 20261101 | 8 | 0 | 0 | 1007.4 / 1412.5 / 1443.0 (n=8) |
| 760x140 ROI, seed 20261102, stronger negative | 7 | 0 | 1 | 1343.2 / 2314.3 / 2503.7 (n=7) |

All runs captured all ten scheduled events and recorded zero repeated-code or negative
writes. The first three runs used baseline chat as the negative event; the final run
strengthened it to a **new** generated bare alphanumeric string, actually recognized by OCR
but rejected without redemption context. This is a small negative sample, not a soak test.
Across the two narrow-ROI runs: 15/16 successful positive events, zero wrong writes.

| Published/visually reviewed code | Full image raw / eligible | Narrow seed 20261101 | Narrow seed 20261102 |
|---|---|---|---|
| `7A324EYX6SHT` | exact / eligible | copied | copied |
| `SAJ4KLZLDMW3` | exact / eligible | copied | copied |
| `WTK9Z6EMQPEP` | exact / eligible | copied | copied |
| `YTKQGE27H57T` | exact / eligible | copied | abstained |
| `NBJ8HEJNZ5NF` | exact / eligible | copied | copied |
| `UT38ZEJPY573` | exact / eligible | copied | copied |
| `CSJ882LL4BHF` | exact / eligible | copied | copied |
| `7T3R83MMMTY3` | exact / eligible | copied | copied |

The initial harness overlaid chat/motion on the top of some code glyphs. This was a test
stimulus defect; moving overlays outside the code bands corrected it without changing OCR.
Wide-ROI misses included correct strings rejected as stale while OCR processed sidebar
text. The configurable narrower ROI reduced irrelevant text but did not eliminate timing
failures. In the final seed, `YTKQGE27H57T` was read exactly on all four processed code
frames: first stale (1086 ms age), then confirming, then disarmed as the scheduled exposure
ended, then stale. No wrong transcription was substituted and no freshness limit relaxed.

Final-run stage timings for the 61 frames with eligible code candidates (including
disarmed/repeat observations), milliseconds:

| Stage | p50 | p95 | Worst |
|---|---:|---:|---:|
| Capture | 1.68 | 10.57 | 20.32 |
| Frame age at processing entry (`queue_age`) | 47.90 | 82.54 | 297.10 |
| Preprocessing | 0.88 | 6.66 | 40.88 |
| OCR wall time | 418.59 | 856.11 | 1316.66 |
| Text recognition substage | 295.17 | 712.40 | 1162.74 |
| Policy | 0.021 | 0.114 | 0.139 |

Seven successful memory writes cost p50 0.0136 / p95 0.0304 / worst 0.0336 ms. OCR,
especially recognition of multiple text lines, remains the largest measured cost. Stage
percentiles are overlapping scopes, not additive totals. These game slides and ROIs differ
from Phase 1/2 chart fixtures; this is not a controlled claim of speedup over those baselines.
No GPU or native clipboard timing was measured here. Under 100 ms is plainly **unmet**.

## Commands and checks

From the repository in PowerShell, these commands were executed. Files named `final`
retain their historical names even where a later run exists; none was overwritten.

```powershell
# Initial and overlay-corrected harness iterations (then-default 960x140 ROI):
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --report artifacts/game-playback-live.jsonl
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --report artifacts/game-playback-final.jsonl
# Narrow configurable ROI, then final stronger negative and a different schedule:
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --roi 200 400 960 540 --report artifacts/game-playback-small-roi.jsonl
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --seed 20261102 --report artifacts/game-playback-negative-final.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --profile game --partition tuning --report artifacts/game-profile-images-tuning.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --profile game --partition holdout --report artifacts/game-profile-images-holdout.jsonl
./scripts/check.ps1 -Ocr *> artifacts/game-profile-final-check-ocr.txt
./scripts/check.ps1 *> artifacts/game-profile-final-check.txt
```

Playback process exit codes were **1, 1, 0, 1**, in table order. Both file evaluations exited
0. Final OCR-inclusive check exited 0: pip dependency check clean, Ruff lint/format clean
(51 files), strict mypy clean (16 source modules), **104 passed, 3 xfailed in 34.61 s**.
The three original `test_challenge_exact_recall_release_gate` cases remain strict expected
failures for unresolved tiny compressed O/0 exact recall; none was removed or weakened.
The standard headless check also exited 0: **96 passed, 11 skipped in 3.94 s**, with the same
clean pip, Ruff and strict mypy checks. Its opt-in OCR skips are expected; see
`artifacts/game-profile-final-check.txt`.
An earlier OCR-inclusive check passed 103 tests before the additional CLI profile regression.
Initial Ruff line-length failures were fixed; no assertions were relaxed.

## Manual follow-up and readiness

1. Run the harness from an interactive Windows desktop with the primary output and the
   physical `(50,50)`–`(1010,590)` area unobscured. It opens only its temporary stimulus
   window, closes it on completion and has no native clipboard option. Use a new report
   filename, new seed and, if needed, explicit test-relative ROI on every run. Require
   all eight exact writes, zero wrong/repeat/negative writes and ten captured events.
2. For permitted real game video, choose a physical monitor ROI covering code and expiry/
   redemption label. Use `live --profile game --roi L T R B --dry-run --report NEW.jsonl`;
   enter `start`, wait for `ready`, then `arm`. Rearm explicitly after each successful copy.
   Disarm before moving the source. Record independent labels and appearance timestamps,
   including misses, uncertain glyphs and negative-only scenes.
3. Native game clipboard behavior has **not** been tested. It remains explicitly opt-in:
   replace `--dry-run` with `--clipboard windows` only when intentionally testing actual
   clipboard replacement. Preserve clipboard content first, manually paste each result
   locally, never submit/redeem automatically. Complete the 30-event native, 30-minute
   negative soak, contention, stop/disarm, DPI/monitor and capture-loss matrix in
   [WINDOWS_VALIDATION.md](WINDOWS_VALIDATION.md).
4. Obtain previously unseen, independently labelled recordings from different games,
   streamers/backgrounds, text sizes, compression and formats, including hyphenated and
   ambiguous-character codes. The eight shared-layout slides are insufficient. Real
   livestream qualification stays blocked until representative recordings/labels exist.

The next engineering step is a controlled measurement on additional labelled playback
with smaller user-selected ROIs containing the necessary context, followed by repeatable
native qualification. Any OCR optimization needs separate held-out evidence. The remaining
chart challenge defects, intermittent game exposure misses, ~1–2.5 s copy latency and
unfinished G2 Windows matrix prevent GUI readiness under the existing project gates.

Changed source files: `policy.py`, `live.py`, `cli.py`, `evaluation.py` and
`scripts/evaluate_dataset.py`. Added `scripts/game_playback.py` and `tests/test_profiles.py`.
Updated README, PROJECT_SPEC, WINDOWS_VALIDATION and this validation record. Existing
capture/OCR/clipboard implementations, imported assets, labels, dependency pins and prior
benchmark artifacts were preserved. Reports above are new local artifacts.
