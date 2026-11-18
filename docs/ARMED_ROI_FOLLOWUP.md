# Large armed ROI follow-up

These results describe the detector before the v0.2.0 policy change.
[v0.2.0 validation](DETECTION_POLICY_VALIDATION.md)

## Operator result

**FAIL (operator-reported).** On Windows, the operator selected (36, 124) to
(1209, 994), or 1173 × 870. The GUI was Running, Ready and Armed. It reported
2799.6 ms processing, a `stale` decision and no confirmed code. The operator saw
`LIMITED TIME OFFER` in the annotation and reported an OCR line as `Code` at 0.987
along with the generic context/quality message. The original source pixels and
full OCR report were unavailable during this investigation.

## Real capture profile

Six changed frames at the reported coordinates on output 0 went through the normal
DXcam producer, newest-frame handoff and pinned CPU baseline OCR with whole-batch
reuse. The probe performed no clipboard operations and saved no pixels or OCR text.
The live desktop sample had zero exact limited-offer headings and zero eligible
lines. It cannot establish the OCR evidence for the operator's annotation. This is
a real capture measurement of the workload in that ROI, with separate validation
of the reported annotation mechanism below.

| Stage or observation | p50 / p95 (ms) |
|---|---:|
| DXcam polling, including polls without a new frame (539 polls) | 2.42 / 16.41 |
| Capture age when OCR began | 32.62 / 62.44 |
| External resize and preprocessing | 3.01 / 3.37 |
| Text detection wall time | 253.21 / 356.10 |
| Detector ONNX inference | 213.25 / 307.77 |
| Text recognition wall time | 1144.43 / 2430.34 |
| Recognizer ONNX inference, summed per observation | 1083.73 / 2333.24 |
| OCR processing wall time | 1411.96 / 2802.14 |
| Age when OCR finished | 1467.72 / 2814.58 |

All six observations detected 55 crops. Five exceeded 1000 ms of age. The cold frame
took 3241.7 ms and reused zero of ten groups. Warm frames reused 5–8 groups each,
with 2–5 misses. The cache was active for every frame and used 2.61–2.62 MB of crop
bytes against its 8 MiB limit. Between 9 and 22 crops in the missed warm groups still
matched individual crops from the previous cache. No missed warm group consisted
entirely of previously cached crops in a different grouping. A group can be forced
to run again by one changed crop. Pixel changes and detector-crop jitter can both
cause that difference. The retained metrics cannot separate them for the original
TradingView observation.

The expensive group contained six rows and padded each input to 1522–1594 pixels
wide. Its ONNX call took 565–785 ms on four warm observations and 1001 ms when cold.
Narrow width-320 groups in the same profile generally took around 94–141 ms. Whole-
group reuse saves some work but can leave a single wide miss consuming most of the
deadline. OCR scale, model settings, capture age, and clipboard policy were unchanged.

## Reuse experiment

The offline probe keyed reuse by exact crop bytes, shape and original padded input
width. It reran only misses and always reran a crop whose earlier output looked
like a code. It changed the number of rows in an ONNX batch, while keeping the
original padded width. The same six frames per suite were fed to both approaches.
The desktop frames were collected using DXcam and retained in memory for the paired
replay. These are replay processing times, separate from the simultaneous DXcam/OCR
profile above. Neither approach performed copies in the probe.

| Replay input | Whole-batch p50 / p95 (ms) | Per-crop p50 / p95 (ms) | Frames over 1000 ms, whole → per-crop |
|---|---:|---:|---:|
| Generated, some quote rows changing | 724.6 / 1813.8 | 328.2 / 1568.4 | 1/6 → 1/6 |
| Generated, every quote row changing | 1548.6 / 1991.7 | 1390.8 / 1789.5 | 6/6 → 6/6 |
| Paired DXcam desktop snapshots | 1627.1 / 3272.4 | 1130.1 / 2622.8 | 6/6 → 4/6 |

Text, coordinates, quality rejections, scores and candidate sets matched on all 18
paired frames. The generated frames included a code, while the captured snapshots
had no candidates. The experiment materially reduced repeated work when some rows
were stable. It still missed the deadline on every dense changing-label frame and
four desktop snapshots. Per-crop reuse remains an offline experiment because there
is insufficient evidence for a native-copy path and the dense deadline remains unmet.
Geometry-only filtering would risk hiding a valid code or the context that supports
it. The runtime retains full-region detection and its existing whole-batch strategy.

## Validation diagnostics

A literal OCR reading of `Code` contains no token and fails exact format before
context matters. A valid separately recognized token near a limited offer still
needs a recognized and spatially attached code label. `Code` without its colon does
not satisfy that label rule. The old wording `context or quality requirements not
met` was emitted only after the line parsed as a code and passed its first score and
adapter checks. The wording and a literal `Code` are therefore insufficient to identify
the exact failed gate on the original screenshot. The visible heading alone does not
establish how OCR read it, its box, or its score.

The GUI now displays the policy's exact gate, the text and box coordinates, and
prioritizes recognized context and nearby lines. It shows expiry independently from
candidate assessment. The candidate predicates stayed the same and matched all 312
archived Discount observations checked. The profile report records the pre-recognition
crop count, reuse counters and actual ONNX wall time per executed batch. The new
tests cover the literal label versus split-label cases, stale diagnostics, crop and
batch counts, and reuse bypass at the byte limit. Freshness and confirmation remain
1000 ms. Baseline suppression, O/0, deduplication and clipboard behavior are unchanged.

## Reproduction and next Windows test

Run from the Windows desktop terminal. The sandboxed native probe received DXGI access
denied. Retrying with desktop access succeeded. The first focused pytest invocation
had setup errors with the default temporary directory. It passed all 80 tests with
the repository-local `TEMP`/`TMP` used by `scripts/check.ps1`.

`./scripts/check.ps1` passed with 219 tests and 18 OCR skips. The final
`./scripts/check.ps1 -Ocr` passed with 234 tests and the three existing challenge
xfails in 72.19 seconds. Dependency checks, Ruff lint and formatting, strict mypy
and `git diff --check` passed. Logs are in `artifacts/armed-roi-followup-check.txt`
and `artifacts/armed-roi-followup-check-ocr-final.txt`.

```powershell
./.venv/Scripts/python.exe scripts/profile_captured_ocr.py --capture --roi 36 124 1209 994 --frames 6 --report artifacts/armed-roi-followup-native.json
./.venv/Scripts/python.exe scripts/probe_crop_reuse.py --report artifacts/armed-roi-followup-crop-probe.json
./.venv/Scripts/python.exe scripts/probe_crop_reuse.py --capture --roi 36 124 1209 994 --frames 6 --report artifacts/armed-roi-followup-native-crop-probe.json
```

To diagnose the original gate, leave the annotation visible with the chart moving and
run the capture profiler with `--include-text` and a new report path. Inspect the
annotation lines, `reason`, `box`, `limited_heading_count` and `result_age_ms` for the
same sequence. This opt-in saves raw ROI OCR text locally. No pixels are written.
Share only the annotation entries and timing if needed. The GUI remains available
in dry-run mode with **Show last OCR results** to check the same reasons.
