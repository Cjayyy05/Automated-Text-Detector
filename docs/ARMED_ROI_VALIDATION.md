# Large armed ROI validation

These measurements used the earlier 1000 ms frame-age limit and confirmation policy.
[v0.2.0 validation](DETECTION_POLICY_VALIDATION.md)

## Root cause

The operator's 1137 × 841 TradingView region took 1632.7 ms per observation and
reported `stale`, even though OCR produced an eligible code. `DecisionPolicy.observe`
checks capture-to-decision age before it accepts confirmation evidence. Pipeline
diagnostics independently list eligible text, so a stale result can still show a
candidate. An expired frame cannot copy or complete a pending confirmation.

A generated region of the same size reproduced the delay at 1630.2 ms median and
1846.2 ms p95. Default CPU, scale 2, detector limit 960 and two threads were used.
The Windows host used Python 3.12.14, RapidOCR 3.10.0 and ONNX Runtime 1.31.1.
All 12 observations expired. Stage times below are milliseconds, p50 / p95. The
inference rows are components of the broader detection and recognition rows.

| Stage | 440 × 165 | 780 × 430 | 1137 × 841 |
|---|---:|---:|---:|
| Resize/preprocessing | 0.38 / 0.74 | 0.84 / 1.12 | 2.05 / 2.43 |
| Text detection | 82.0 / 104.1 | 171.2 / 186.7 | 252.5 / 281.8 |
| Detector ORT inference | 72.0 / 87.7 | 145.9 / 162.5 | 213.3 / 237.5 |
| Text recognition | 54.2 / 81.6 | 359.4 / 428.5 | 1346.9 / 1563.6 |
| Recognizer ORT inference | 51.7 / 79.0 | 342.9 / 415.0 | 1286.4 / 1498.8 |
| Policy | 0.025 / 0.036 | 0.048 / 0.058 | 0.005 / 0.006 |
| Total process | 140.3 / 171.8 | 537.9 / 616.3 | 1630.2 / 1846.2 |
| Median recognized lines | 2 | 14 | 56 |

The large workload ran OCR on every detected line, including 54 market rows. Even
the 1286 ms median ONNX recognition alone exceeded the freshness budget. RapidOCR
sorts perspective crops by aspect ratio and processes groups of six. Each group
pads to its widest normalized crop or the configured minimum width. More text
therefore means more padded inference work. The large policy timing mostly covers
the cheap stale rejection. A separate 4/6-thread probe with spinning off brought
median large processing to 1374.0 / 1141.8 ms, with 12/12 stale at each setting.
The runtime thread and model settings stayed at their existing values.

### Real Windows capture-only profile

DXcam on output 0, 60 Hz poll target, same origin (47, 122) and 1.25 seconds per
size. The tool sandbox initially received DXGI access denied. Running the same
capture-only probe with desktop access succeeded. This measured the current visible
desktop separately from synthetic OCR. It retained no pixels and touched no clipboard.

| ROI | Polls / changed publications | Grab p50 / p95 (ms) | Duplicate check and publish p50 / p95 (ms) |
|---|---:|---:|---:|
| 440 × 165 | 73 / 1 | 0.81 / 9.91 | 0.06 / 0.09 |
| 780 × 430 | 74 / 39 | 1.28 / 10.16 | 0.46 / 0.67 |
| 1137 × 841 | 74 / 53 | 2.09 / 9.98 | 1.23 / 1.89 |

Grab measurements include polls with no newly delivered frame. Producer pacing is
separate. These measurements are neither OCR while DXcam is active nor TradingView
capture-to-copy latency.

## Change and constraints

Baseline CPU OCR on regions of at least 750,000 physical pixels still detects text
over the entire frame with the same resize and model. After detection and perspective
cropping, it can reuse a prior group of recognition outputs if the complete current
group has exactly the same crop shapes, pixel bytes and padding group order. Output
boxes always come from the current detector. Groups containing a code-shaped raw
reading in either profile are always recognized again, including context-free,
low-confidence and ambiguous reads. Reuse stores only the last recognition call's
eligible groups, with at most 8 MiB of crop keys retained and at most 8 MiB of new
crop keys during comparison. It bypasses larger batches. A cold or complete miss
uses the original full recognition call.

This targets stable labels and other repeated text while chart pixels change. It
preserves the existing detection scale, crop pixels, source-resolution and O/0
guards. Every code still needs two independently captured changed frames with fresh
code recognition. Freshness and confirmation limits remain 1000 ms. Baseline
suppression, duplicate prevention, clipboard consent and readback remain on the
existing paths. No GUI control was added. Small/medium inputs, GPU and alternate
models continue with the original recognition path.

Spatial tiling would require overlapping borders to preserve small codes and their
context across seams. It would still need to recognize dense moving text and could
multiply detector work. Geometry-only filtering cannot safely tell a long price
label or nearby context from a possible code before recognition. This change keeps
both the detector coverage and the code decision path.

## Paired replay

Two local CPU runs used identical generated BGR frames and the real Pipeline with a
memory clipboard. Four positive appearances, including a smaller code near the
bottom-right edge and an explicitly labelled code near the bottom-left edge, and
two negative events per size. One negative contains a baseline code. The main suite
uses four distinct observations per event. It stamps each input at processing start,
so it exercises real 1000 ms compute expiry and confirmation but excludes live capture
and handoff delay. Stale rates count observations that started while armed. The
processing quantiles include all measured frames, even after a successful copy.
The changing-label control uses two observations per event with a different seed.

| ROI and workload | Exact copies before → after | Wrong on negatives before → after | Armed stale before → after | Process p50 / p95 before → after (ms) |
|---|---:|---:|---:|---:|
| 440 × 165 | 4/4 → 4/4 | 0/2 → 0/2 | 0/16 → 0/16 | 129 / 161 → 128 / 148 |
| 780 × 430 | 4/4 → 4/4 | 0/2 → 0/2 | 0/16 → 0/16 | 472 / 518 → 471 / 502 |
| 1137 × 841, stable market labels | 0/4 → 4/4 | 0/2 → 0/2 | 24/24 → 4/19 | 1340 / 1548 → 330 / 1460 |
| 1137 × 841, stable labels, separate seed | 0/2 → 2/2 | 0/2 → 0/2 | 16/16 → 2/13 | 1341 / 1439 → 297 / 1373 |
| 1137 × 841, every market label changing | 0/4 → 0/4 | 0/2 → 0/2 | 12/12 → 12/12 | 1352 / 1481 → 1350 / 1392 |

The three cold first positive observations that expired in the optimized large run
were followed by two fresh observations and a correct copy. No run copied an incorrect
token on a positive event. This improvement needs time for new text to persist, and
the large-region p95 still exceeds 1000 ms. In the moving-text prototype, changing every
market line resulted in zero reusable groups. The paired moving replay confirmed that
all observations still expired. Reliable detection of short codes over dense, changing
text remains limited by full recognition speed.

## Reproduction and Windows retest

The native capture-only probe runs from a Windows desktop PowerShell terminal.

```powershell
@'
import json
from time import sleep
from stream_code_capture.capture import CaptureWorker, DxcamSource
from stream_code_capture.domain import Rect
for w, h in [(440, 165), (780, 430), (1137, 841)]:
    roi = Rect(47, 122, 47 + w, 122 + h)
    worker = CaptureWorker(lambda: DxcamSource(roi), fps=60)
    worker.start()
    try:
        worker.started.wait(3)
        sleep(1.25)
    finally:
        worker.stop()
    print(json.dumps(dict(roi=[w, h], error=worker.error, changed=worker.captured,
                          duplicates=worker.duplicates, timings=worker.metrics.summary())))
'@ | .\.venv\Scripts\python.exe -
```

The offline OCR commands use fresh report filenames.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --report artifacts/armed-roi-default.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --size large --threads 4 6 --no-spinning --report artifacts/armed-roi-thread-probes.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --observations 4 --report artifacts/armed-roi-paired-before.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --observations 4 --reuse --report artifacts/armed-roi-paired-after.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --size large --moving-text --seed 61903 --report artifacts/armed-roi-changing-before.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --size large --moving-text --seed 61903 --reuse --report artifacts/armed-roi-changing-after.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --size large --observations 4 --events 2 --seed 61903 --report artifacts/armed-roi-holdout-before.jsonl
.\.venv\Scripts\python.exe scripts/benchmark_armed_roi.py --size large --observations 4 --events 2 --seed 61903 --reuse --report artifacts/armed-roi-holdout-after.jsonl
```

Regression coverage includes exact byte matching, detector order, cache size limits,
independent OCR for code-like rows across both profiles, and exact line parity for a
large real-OCR fixture with a smaller code at the edge. The focused run
`./.venv/Scripts/python.exe -m pytest -q tests/test_ocr_batch_reuse.py --run-ocr`
passed all seven tests in 3.97 seconds.

`./scripts/check.ps1` passed with 218 tests and 18 OCR skips in 44.12 seconds.
`./scripts/check.ps1 -Ocr` passed with 233 tests and the three existing strict
challenge xfails in 63.54 seconds. Both runs passed dependency checks, Ruff lint and
format checks, and strict mypy over 20 source files. `git diff --check` passed.
Logs are in `artifacts/armed-roi-check.txt` and `artifacts/armed-roi-check-ocr.txt`.

For actual TradingView stage timings, the live CLI can run in a separate dry-run
session. Use the selected output index and a new JSONL path. Enter `start`, wait for
`ready`, and enter `arm` before adding the test code.

```powershell
.\.venv\Scripts\python.exe -m stream_code_capture live --output 0 --roi 47 122 1184 963 --dry-run --profile-inference --report artifacts/tradingview-armed-roi.jsonl
```

### GUI retest

1. Launch `.\.venv\Scripts\python.exe -m stream_code_capture.gui` on `develop`.
   Select **Discount**, keep **Dry Run**, and turn on **Show last OCR results**.
2. Select the same 1137 × 841 TradingView ROI, from (47, 122) to (1184, 963).
   Keep the annotation absent. Click **Start**, wait for **Ready**, then click **Arm**.
3. Add the valid annotation near an edge, with the offer still in the ROI. Keep the
   chart moving and the code visible over several OCR reads. Expect the exact token
   and automatic disarming if two fresh changed frames qualify. Record processing
   times and whether decisions remain `stale` if it stays armed.

The subsequent large TradingView retest failed. The operator reported an armed
1173 × 870 region, a 2799.6 ms observation, `stale` and no confirmation. See the
[follow-up capture profile and validation investigation](ARMED_ROI_FOLLOWUP.md).
Representative livestream qualification remains pending.
