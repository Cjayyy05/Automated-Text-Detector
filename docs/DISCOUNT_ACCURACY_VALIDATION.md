# Discount recognition follow-up

This follow-up used the earlier O/0 abstention and confirmation policy.
[v0.2.0 validation](DETECTION_POLICY_VALIDATION.md)

## Audit of the 11 original misses

The two observations per event in `artifacts/discount-layouts-final.json` all returned
`no_candidate` and no write. The rerun before the change reproduced 20/31 exact copies.
The benchmark starts with an empty baseline. None of these misses was caused by baseline
suppression, age expiry or an incomplete confirmation. The source below is generated,
including the recreation of the reported TradingView annotation.

| Case | Expected | OCR text | Verified cause |
|---|---|---|---|
| `left-1` | `KKJVX34232` | `KKJVX34232 25% off` | One merged OCR box. Whole-line candidate extraction rejected the line, which had no distinct code label. |
| `glyph-O-0` | `GNOUJ45323` | `GN0UJ45323` | O→0 transcription error, rejected by the O/0 guard. |
| `glyph-0-0` | `GN0UJ45323` | `GN0UJ45323` | Exact transcription, rejected by the O/0 guard. |
| `glyph-O-1` | `YPOWX64975` | `YP0WX64975` | O→0 transcription error, rejected by the O/0 guard. |
| `glyph-0-1` | `YP0WX64975` | `YP0WX64975` | Exact transcription, rejected by the O/0 guard. |
| `glyph-O-2` | `MXOMH43446` | `MX0MH43446` | O→0 transcription error, rejected by the O/0 guard. |
| `glyph-0-2` | `MX0MH43446` | `MX0MH43446` | Exact transcription, rejected by the O/0 guard. |
| `challenge-0` | `Y2SSO9KFJJ` | `Y2SS09KFJJ` | Transcription error and insufficient source resolution. Both scores fell below 0.96, and the offer was corrupted in both observations. |
| `challenge-1` | `N02OD01OXK` | `N020D010XK` | Transcription errors and insufficient source resolution. Both scores fell below 0.96, and the offer was missing from the second observation. |
| `challenge-2` | `6428IT02OE` | `6428IT020E` | Transcription error and insufficient source resolution even with scores above 0.99 and intact offer text. |
| `reported-layout` | `680J6BN7JX` | `680J6BN7JX` | Exact transcription, rejected by the O/0 guard. The offer below the code remains supported. |

The merged row remains an abstention. The same text pattern can be produced by an
unrelated code-shaped identifier beside a percentage offer. Accepting unlabelled
substrings based on that one fixture would remove a useful distinction.

## O/0 pixel experiments

On the six original rendered O/0 rows and eight held-out rows, the same local CPU
recognizer was tested at full-image scales 1, 2 (default) and 3, as well as recognition
on the detected line crop with original pixels, Otsu binarization and grayscale CLAHE.
A fixture region selected the target line for scoring. Neither expected text nor code
length was passed to OCR. Each reading is scored by exact whole token. All methods
returned text on every row, and all errors in this experiment were O→0.

| Method | Original exact / wrong | Held-out exact / wrong | Held-out wall p50 / p95 (ms) |
|---|---:|---:|---:|
| Full frame, default scale 2 | 3 / 3 | 5 / 3 | Measured in pipeline below |
| Full frame, scale 1 | 3 / 3 | 5 / 3 | 76.3 / 87.3 |
| Full frame, scale 3 | 3 / 3 | 5 / 3 | 154.8 / 192.9 |
| Line crop, unchanged pixels | 3 / 3 | 6 / 2 | 19.6 / 25.9 |
| Line crop, Otsu | 4 / 2 | 5 / 3 | 17.9 / 19.9 |
| Line crop, CLAHE | 3 / 3 | 4 / 4 | 18.2 / 20.5 |

Crop timings cover the extra recognition and any transform after extraction. The best
held-out variant recovered one token and still made two errors. All six variants read
`TE4TO2YM39` as `TE4T02YM39` and `T2YBO64J59` as `T2YB064J59`, with scores above 0.99
for each reading. The earlier second-model and template experiments also had wrong
reads. No safe O/0 exception or additional production OCR pass was justified. The
exact-recall challenge xfails remain, and the broad OCR settings stayed in place.

## Implemented change and replay results

The narrow improvement covers `Limited time offer` with a generic colon-bearing
code label in a different OCR box from the token. The label must be confidently
recognized immediately above or to the left, and the separate heading must qualify
near the token under the existing spatial rule. Whole-line token parsing, source
pitch and O/0 guards still apply. The label text does not enter the clipboard.
Baseline suppression, duplicate prevention, two fresh changed-frame observations,
clipboard consent and disarming still use the existing pipeline. The GUI and Game
profile were outside the change.

The new development and held-out suites used different seeds, tokens and rendered
font styles. The holdout includes compressed pixels with a different background.
Negatives reuse the comparable token positions with a wrong label, a far label, a
weak offer or no offer. Each event ran two distinct rendered frames through local
RapidOCR and the real policy with a memory clipboard. No DXcam or native clipboard
measurements were taken. This is a small synthetic holdout for the split-label change.

| Suite | Exact before → after | Misses before → after | Wrong on negatives before → after | Process p50 / p95 before → after (ms) |
|---|---:|---:|---:|---:|
| Original 31 positives | 20/31 → 20/31 | 11 → 11 | 0/26 → 0/26 | 167.5 / 560.7 → 162.2 / 471.1 |
| Development, 2 split-label and 4 O/0 | 0/6 → 2/6 | 6 → 4 | 0/8 → 0/8 | 193.1 / 272.4 → 185.2 / 257.2 |
| Held-out, 4 split-label and 8 O/0 | 0/12 → 4/12 | 12 → 8 | 0/16 → 0/16 | 174.7 / 238.3 → 163.2 / 257.4 |

There were zero incorrect copies on positive events. Clear original layouts stayed
at 17/18. The latest policy validation took 0.032 ms at p95 on the held-out suite,
versus 0.027 ms before. The sequential elapsed timing differences track the unchanged
OCR calls and do not establish a throughput improvement or regression. Recognition
on independently labelled livestreams, including O/0 in broadcast fonts and compression,
remains open. Keep unrelated identifiers out of the capture region.

## Reproduction and Windows retest

Windows with Python 3.12.14 and pinned local RapidOCR/ONNX Runtime CPU models. The six
`*-before.json` and `*-after.json` runs use the same fixtures and command with different
output files. The first holdout launch collided with an edit of the benchmark script
and failed with a syntax error. A fresh launch after the edit completed successfully
before the policy changed.

```powershell
foreach ($suite in @('legacy', 'development', 'holdout')) {
    ./.venv/Scripts/python.exe scripts/benchmark_discount_accuracy.py $suite --report "artifacts/discount-accuracy-$suite-after.json"
}
foreach ($suite in @('legacy', 'holdout')) {
    ./.venv/Scripts/python.exe scripts/benchmark_discount_accuracy.py $suite --probe --report "artifacts/discount-accuracy-$suite-probes.json"
}
./.venv/Scripts/python.exe -m pytest -q tests/test_discount_layouts.py tests/test_labelled_discount.py tests/test_policy.py --run-ocr
./scripts/check.ps1
./scripts/check.ps1 -Ocr
git diff --check
```

The targeted OCR and policy tests passed, 58 in 5.14 seconds. `./scripts/check.ps1`
passed with 212 tests and 17 OCR skips in 42.88 seconds. `./scripts/check.ps1 -Ocr`
passed with 226 tests and the three original strict xfails in 65.06 seconds. Both
passed dependency checks, Ruff lint and formatting, and strict mypy over 20 source
files. `git diff --check` passed. Check logs are in `artifacts/discount-accuracy-check.txt`
and `artifacts/discount-accuracy-check-ocr.txt`.

1. Launch `./.venv/Scripts/python.exe -m stream_code_capture.gui`. In **Discount**, keep
   **Dry Run** and enable **Show last OCR results**. Select the intended annotation area
   and a small changing part of the TradingView chart. With the test token absent, click
   **Start**, wait for **Ready**, then click **Arm**.
2. Add `LIMITED TIME OFFER` above `Code:` and a new 8–16 character uppercase alphanumeric
   token containing neither `O` nor `0`. Give the label and token their own text boxes,
   with `Code:` immediately above or to the left. Keep the chart moving within the ROI.
3. Expect the exact token in **Last confirmed code** and automatic disarming after two
   changed frames. OCR details should show the token, label and offer. Keep the raw OCR
   text and decision if it does not confirm.

This manual retest is pending.
