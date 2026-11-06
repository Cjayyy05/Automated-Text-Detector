# Phase 3 — recognition qualification tooling and synthetic diagnostics

Date: 2026-10-31, Asia/Kuala_Lumpur. Same Windows/Python 3.12 environment and pinned local
RapidOCR 3.10.0 / ONNX Runtime 1.31.1 / OpenCV wheel 5.0.0.93 (module reports 5.0.0).
CPU inference only. No dependency/model changes, network OCR, product GUI, packaging,
commits, pushes, native clipboard writes or simulated chart windows in this phase.

**Phase 3 acceptance is not passed; real-video qualification is blocked.** The user confirms
the real screenshot has not been added to the workspace or independently transcribed.
Repository inspection found generated sample sets and no local livestream recordings.
No real-world accuracy or new live latency result can be claimed. The default recognizer,
optional cascade, thresholds, latest-frame handoff and native capture/clipboard code are
unchanged. A new method was not promoted on inadequate data.

## Delivered tooling and safety

- `src/stream_code_capture/dataset.py`: local sequential video decode, image imports,
  lossless extracted frames, source/frame/pixel hashes, CSV labels, strict annotation audit,
  immutable manifests, and deterministic group splits. Session, exact target identity,
  identical source and identical decoded pixels are joined transitively. Runtime inference
  never imports this module or reads labels. Inputs are existing local media files, not URLs.
- `src/stream_code_capture/evaluation.py`: existing OCR -> policy -> **MemoryClipboard**
  replay, distinct-ROI confirmation, raw/candidate/event metrics, partial-write failures,
  overlap diagnostics and process CPU/stage timing. Unknown labels block scoring. Snapshots
  remain disarmed; missing baselines are not silently manufactured. Each event starts a fresh
  policy session, so cross-event lifetime dedup is tested by existing tests, not this score.
- Scripts: `dataset.py`, `evaluate_dataset.py`, `generate_qualification.py`,
  `benchmark_labelled_crops.py`, `diagnose_errors.py`. No native clipboard option or screen
  window exists in these tools. Existing explicit live commands remain available unchanged.
- `tests/test_dataset.py`: 19 headless regressions for real local codec decode, annotation
  round trips, exact case/separators, bounds/order/identity, hashes, path containment, split
  leakage, snapshots, duplicate confirmations, unknown labels and incorrect/partial writes.

Label code boxes are used only for scoring overlap and clearly marked **oracle-crop**
diagnostics. Normal replay uses only the selected chart ROI and source pixels. No target
code, target length, fixture seed, banner rejection string or background template enters
the production recognizer. No O/0 or I/1 substitutions or confidence thresholds changed.

New synthetic fixtures vary full-alphabet values, sizes, slant, actual italic font,
JPEG compression, blur, brightness, positions, chart/gradient/moving-shape backgrounds,
partial visibility, permanent promotions and chat. Formats include lowercase, hyphenated,
six-character and twelve-character values. Labels preserve all of them. Runtime still
supports only its documented uppercase 8–16 alphanumeric profile: broader inputs are
counted as misses, not silently normalized or excluded. Universal background/format support
is not claimed.

## Data and partition provenance

`samples/phase3-synthetic`, seed 20261031: three generated sessions, 12 events and 36 frames
per session, **108 frames total**. Each session has 10 fully visible positive events,
one partial-only event and one permanent-code negative event; every event includes baseline.
`artifacts/phase3-split.json`, seed `phase3-frozen-1`, was created before comparisons.
Sessions 00/01 are tuning; session 02 is holdout. No shared code/session/source/exact pixels
cross the split. This is a **new synthetic, session-disjoint comparison**, not representative
real-video qualification. The code rendering family is shared; the held-out session uses
the moving-shape background. The sample is small and any subsequent method tuning on its
results would consume its holdout status. Do not claim statistically established 90% recall.

All existing Phase 1/2 fixtures/reports are preserved. The old 60-event Phase 2 holdout is
already a regression corpus, not an unseen test. Its repeated result remains **22 exact,
0 incorrect, 38 abstentions**. Original challenge cases remain unchanged and expected failing.

## Recognition methods and exact-copy results

Final frozen synthetic comparison, 10 positives + 2 negative/partial-only events:

| Whole ROI method | Raw exact visible frames | Exact event copies | Incorrect writes | Abstentions | Recall |
|---|---:|---:|---:|---:|---:|
| Baseline v6 small, guarded | 20/20 | 4/10 | 0 | 6/10 | 40% |
| Tiny + verified baseline cascade | 20/20 | 4/10 | 0 | 6/10 | 40% |
| v4 English mobile, guarded diagnostic | 16/20 | 2/10 | 1 | 8/10 | 20% |

The v4 incorrect decision was in the partial-only event, in addition to the 10 positive
events. It is counted as an unsafe write even though it was to memory. V4 is already refused
for native copying by the public CLI; that restriction remains. A diagnostic exit zero means
the benchmark completed, not that this accuracy passed.

For baseline/cascade the six positive abstentions comprise one source-resolution rejection,
two O/0 rejections and three unsupported formats (lowercase, hyphenated, short). Raw exact
strings are **not** proof that removing those guards is safe: the older varied corpus and
three challenge errors show their purpose. Baseline remains the default; no relaxation.

Independent diagnostic on the same holdout uses the known annotation box, without automatic
localization. Scores below are raw recognitions on 20 visible frames, **not clipboard recall**.
Timing has 22 samples including two partial frames; model setup/template construction excluded.

| Oracle-box method | Exact visible strings | p50 / p95 / worst ms |
|---|---:|---:|
| Baseline recognition only, tight BGR crop | 18/20 | 42.71 / 45.46 / 47.78 |
| Baseline recognition only, padded BGR crop | 18/20 | 41.70 / 45.70 / 46.60 |
| Baseline recognition only, grayscale crop | 18/20 | 42.60 / 46.60 / 48.74 |
| Baseline recognition only, Otsu crop | 20/20 | 42.59 / 45.28 / 48.34 |
| Connected-component glyph prototypes, A–Z/0–9 | 6/20 | 3.35 / 4.71 / 6.59 |

The lightweight glyph method thresholds/segments pixels and chooses normalized generic
Hershey Simplex prototypes by MSE. It never gets target text or length. Segmentation, font
variation and unsupported lowercase/separator prototypes limit it severely. Distances are
pixel evidence, not fabricated confidence. A fast 30% raw exact rate is unsuitable for copying.
Otsu's 20/20 is insufficient for adoption: the boxes are provided, partial safety and live
latency are not proved, and full default OCR already returned 20/20 raw strings here.

Existing whole-line template matching was rerun against the original Phase 2 cached
localizations: **17/22** exact top matches, **5 wrong**, 51.73 / 98.88 / 224.11 ms search.
This matches its previous accuracy, versus historical 58.79 / 122.54 / 259.25 ms. It searches
O/0 variants from observed text with measured NCC; no expected text selects templates.
These are reused synthetic data and cached detections, not new independent OCR or live results.
The known-font template methods remain diagnostics only.

The other two sessions were also evaluated as **tuning**, not additional holdout data:

| Background | Baseline exact / 10 | Cascade exact / 10 | Wrong writes, both | Baseline p50/p95/worst ms | Cascade p50/p95/worst ms |
|---|---:|---:|---:|---:|---:|
| Candlestick chart | 2 | 2 | 0 | 176.31 / 189.46 / 190.37 | 193.91 / 222.36 / 246.73 |
| Gradient | 6 | 6 | 0 | 170.40 / 191.43 / 198.37 | 55.84 / 195.95 / 206.80 |

Each session also includes two negative/partial-only events, both without writes. There
are 24 measured post-baseline frames per session. Total across all three synthetic sessions
is 12/30 exact events for baseline and cascade, with zero incorrect writes; this pooled
number mixes tuning and holdout and is not a qualification score. The chart session makes
the cascade's latency regression particularly clear. Background-independent accuracy and
consistent end-to-end improvement remain unproved.

## Root causes and original challenge status

`diagnose_errors.py` compares original detected crops, the same tight pixel crop read by
different models, and wider crops. These controls separate evidence of recognition errors
from mere failure to find text. They do not assume all disagreements are localization errors.

| Original case | Detected transcription | Wider baseline reading | Finding |
|---|---|---|---|
| 0 | `Y2SS09KFJJ` | `Y2SSO9KFJJ`, score 0.91976 | Crop-sensitive glyph reading; correct wider result still below threshold and source guard; promotional context also corrupted |
| 1 | `N020D010XK` | Same wrong text, score 0.98060 | Character confusion survives wider crop and increased confidence |
| 2 | `6428IT020E` | Same wrong text, score 0.99610 | Correlated high-confidence O/0 error; existing guard remains necessary |

All three have detected code lines. Tight rec-only and wider controls do not fix exact
**accepted** recall. Low source resolution, compression/slant and character decoding are
the primary observed issues, with additional context corruption in case 0. These are not
three entirely missed detector boxes. All three strict xfails remain, without weaker assertions.

For the Phase 2 omitted-prefix regression, tiny outputs `YTBWMCLU9` at 0.99599. Baseline
reads `0YTBWMCLU9` from the **same tight detected pixels** at 0.99957; tiny reads the full
string from a wider crop at 0.96797. The leading glyph was therefore available within the
detected axis-aligned crop: this is recognition/crop sensitivity, not evidence of total
detector exclusion. The raw detections undergo perspective handling in full OCR, so this
control does not isolate every resizing/rectification detail. Existing independent verifier
veto remains intact; no prefix is repaired or accepted based on these diagnostic scores.

## Latency, fallback and resources

Final new synthetic ROI recognition timing, excluding startup/baseline/file decode:

| Method | Frames | p50 ms | p95 ms | Worst ms |
|---|---:|---:|---:|---:|
| Baseline | 24 | 174.12 | 184.05 | 191.74 |
| Verified cascade | 24 | 125.40 | 202.53 | 203.38 |
| v4 | 24 | 181.06 | 395.43 | 397.16 |

Cascade verification: 7 calls, **28.69 / 31.09 / 31.24 ms**. Full fallback: 12 calls,
**169.23 / 175.06 / 175.50 ms**. Actual ORT detector inference, including fallback where
used: p50 58.00 ms; recognition inference p50 46.25 ms. Slow full fallback remains the
dominant tail cost; copying/policy is not the verified bottleneck. Per-stage medians cannot
be added to estimate event latency. The cascade improves median but worsens tail relative
to baseline on this small workload, with no recall gain; it is not promoted.

An earlier run of identical methods/data measured 248.43/266.71 ms baseline and
195.06/339.41 ms cascade p50/p95, with identical accuracy. Those preliminary reports remain
`phase3-baseline.jsonl` / `phase3-cascade.jsonl`. Final `*-final.jsonl` files include the final
overlap metadata and fallback model hashes. Timing variation is not attributed to any
runtime optimization: no recognition implementation changed. These are small sequential
CPU measurements, not controlled power/temperature or long-soak studies.

Like-for-like 15-call positive-only original small-ROI cascade benchmark:

| Measurement | Phase 1 p50/p95/worst ms | Phase 2 final | Phase 3 recheck |
|---|---:|---:|---:|
| Small ROI processing | 234.82 / 289.85 / 347.53 | 63.80 / 233.93 / 275.40 | 54.14 / 200.27 / 221.70 |
| 30 real-screen dry events | 695.40 / 1749.96 / 2027.72 | 186.00 / 1160.55 / 1411.93 | Not rerun |
| 3 native events | 1025.29 / 1798.56 / 1884.48 | 1351.92 / 1885.99 / 1945.33 | Not rerun |

Small ROI snapshot accuracy remains 2/3 positives, zero wrong, one abstention. Phase 1 used
the old default model; Phase 2/3 use the same verified cascade flags. No new speedup is
claimed from code changes; the Phase 2 native regression remains unresolved. The 60-event
existing regression replay measured process 28.96 / 216.62 / 464.88 ms over 264 frames;
Phase 2 was 46.04 / 349.93 / 483.07. Both are sequential file replays, not end-to-end latency.

Final process resource snapshots (Windows native process counters, includes native models):

| Method | Evaluation CPU seconds | Loop wall seconds | Peak working set bytes |
|---|---:|---:|---:|
| Baseline | 11.938 | 6.423 | 201834496 |
| Cascade | 9.922 | 5.201 | 241504256 |
| v4 | 13.797 | 7.727 | 182022144 |

CPU is scheduled process CPU summed across threads, not elapsed time. Loop totals include
baseline/file decoding but exclude model startup; peak working set includes startup/warmup.
These are snapshots, not leak/30-minute stability evidence. No GPU tested. File reports
contain legacy pipeline capture/queue placeholders and observed-frame timestamps; they do
not measure Windows frame age or first-captured-code-to-copy. `live_end_to_end_ms` is null.

## Commands and automated checks

All commands executed from the repository root; reports are ignored local artifacts.
Use fresh output paths to rerun: tools refuse overwrite. Existing pins/models were reused.

```powershell
./.venv/Scripts/python.exe scripts/generate_qualification.py samples/phase3-synthetic --seed 20261031 --sessions 3
./.venv/Scripts/python.exe scripts/dataset.py split samples/phase3-synthetic/session_00/labelled.json samples/phase3-synthetic/session_01/labelled.json samples/phase3-synthetic/session_02/labelled.json --seed phase3-frozen-1 --output artifacts/phase3-split.json
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/phase3-split.json --partition holdout --no-spinning --profile-inference --report artifacts/phase3-baseline-final.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/phase3-split.json --partition holdout --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase3-cascade-final.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/phase3-split.json --partition holdout --model-profile v4 --no-spinning --profile-inference --report artifacts/phase3-v4-final.jsonl
./.venv/Scripts/python.exe scripts/benchmark_labelled_crops.py artifacts/phase3-split.json --partition holdout --report artifacts/phase3-crops-baseline.json
./.venv/Scripts/python.exe scripts/benchmark_templates.py artifacts/phase2-varied-baseline.jsonl --report artifacts/phase3-templates.json
./.venv/Scripts/python.exe scripts/diagnose_errors.py samples/challenge/manifest.json --report artifacts/phase3-challenge-crop-control.json
./.venv/Scripts/python.exe scripts/diagnose_errors.py samples/phase2-holdout/manifest.json --cases 20 --model-profile tiny --report artifacts/phase3-prefix-crop-control.json
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-holdout/manifest.json --profile cascade --no-spinning --report artifacts/phase3-phase2-regression.jsonl
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --manifests samples/smoke/manifest.json --profiles tiny --scales 1 --limits 640 --threads 4 --arena --no-spinning --fallback-baseline --positives-only --repeats 5 --report artifacts/phase3-small-roi.jsonl
./scripts/check.ps1 -Ocr
./scripts/check.ps1
```

Additional tuning commands (both exited zero and reported accuracy limitations):

```powershell
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/phase3-split.json --partition tuning --no-spinning --profile-inference --report artifacts/phase3-tuning-baseline.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/phase3-split.json --partition tuning --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase3-tuning-cascade.jsonl
```

The first baseline/cascade/v4 comparison also ran with the same flags and output paths
without `-final`. Diagnostic crop controls first ran without the tight-crop comparison,
with outputs `phase3-challenge-diagnosis.json` and `phase3-prefix-diagnosis.json`, then were
extended and rerun as listed. Targeted `pytest tests/test_dataset.py -q` passed 19 tests.
Full OCR check: **90 passed, 3 strict xfailed in 22.44 s**; pip check, Ruff lint/format
(48 files) and strict mypy (16 modules) passed. Output: `artifacts/phase3-check-ocr.txt`.
Default display-free check: **83 passed, 10 opt-in OCR tests skipped in 2.47 s**; pip,
Ruff lint/format and strict mypy passed. Output: `artifacts/phase3-check-default.txt`.

Development failures fixed: initial formatting/line-length findings and OpenCV's broad
decoded-array type required explicit uint8 conversion for strict mypy. No test assertion,
confidence threshold, source guard or expected failure was weakened. Local MJPEG encoder/
decoder integration passed on actual video bytes without a display or clipboard access.
Existing offline OCR integration exercises real models with network access blocked.

OpenCV APIs were checked against installed 5.0.0 callable docs and primary references:
[VideoCapture](https://docs.opencv.org/4.13.0/d8/dfe/classcv_1_1VideoCapture.html),
[video I/O properties](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html),
[connected-component statistics](https://docs.opencv.org/4.13.0/d3/dc0/group__imgproc__shape.html).
The official `4.x` documentation redirects to 4.13.0; actual installed behavior was additionally
tested, rather than assuming the documentation version equals the pinned wheel. Installed
RapidOCR `TextRecInput` was checked; existing provisioned model hashes/provenance remain in
Phase 2 docs and the final evaluation report headers.

## Files changed and next gate

Added: two source modules, five scripts and one test module listed above;
`docs/DATASET_WORKFLOW.md` and this report. Modified: `.gitignore` (private datasets),
`README.md`, `docs/PROJECT_SPEC.md`, `docs/WINDOWS_VALIDATION.md`. Existing runtime files,
dependency pins, original tests, fixtures and Phase 1/2 records were preserved. Git still
reports the pre-existing repository scaffold as untracked; that does not mean it was all
created in this phase. Nothing committed/pushed or deleted.

Next: obtain original-resolution permitted real media and independent labels, use the
documented workflow to freeze session/code-disjoint data, then qualify crop/character
methods on an untouched representative holdout. At least 30–50 diverse appearances across
several sessions are useful for the next diagnosis, but not enough to claim the full G3 gate.
The exact media/label request and larger release criteria are in `DATASET_WORKFLOW.md`.

Until then: no representative >=90% recall result, no new native/live latency measurement,
no under-100 ms success, no runtime promotion, no GUI readiness. Existing Windows manual
paste/native contention, 30-event native, 30-minute negative soak, and monitor/DPI/access-loss
matrix remain in `WINDOWS_VALIDATION.md`. Those actions must be explicitly initiated;
Phase 3 never overwrote the user's clipboard to obtain a benchmark.
