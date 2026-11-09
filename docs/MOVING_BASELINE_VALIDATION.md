# Moving baseline investigation and validation

2026-11-09 MYT. Develop worktree based on `2f70efd`. The Windows TradingView result
is recorded below. Operator verification on the large moving TikTok region remains pending.

## Cause and implementation

The producer timestamps owned BGR frames, discards identical ROI pixels and keeps
only the newest pending frame. The owner takes that frame, checks its age and runs
the same full-ROI OCR used during monitoring. Before this change, a baseline result
over the default 1000 ms deadline was rejected unless capture had seen no intervening
pixel change. Any background motion defeated the static revalidation branch, even
when the recognized code and its context stayed constant. Readiness already compared
recognized code sets, but the early age gate could prevent that comparison entirely.

The measured dense fixture reproduced the stall before code changes. All five
completed baseline attempts before the deadline were rejected. One additional OCR
call completed as the run deadline expired and did not qualify as a baseline attempt.
The model did receive and process frames. The bottleneck was primarily text recognition
work as the number of detected lines increased.

The existing baseline key and stability interval remain. For moving content, two
matching accepted code sets spanning at least 500 ms establish readiness. A bounded
2500 ms result window covers the measured moving baseline workload with headroom.
An explicitly larger existing frame-age configuration retains its previous allowance.
Capture must be healthy at completion. Input frames still have to pass the original
pre-OCR freshness check. The existing static revalidation path remains available.

Baseline OCR is suppression-only. Its recognized code strings accumulate monotonically
even if a completed read exceeds the readiness budget. That read increments rejection,
restarts the stability interval and cannot confirm or copy anything. This conservative
choice can suppress a code seen only briefly during setup. Codes missed by OCR or
never sampled cannot be learned. Detection, source quality and ambiguity rules,
armed freshness, independent changed-frame confirmation, copy deduplication, readback
and consent stay on their existing paths. No change to OCR scaling, models or ROI coverage.

The GUI shows accepted/rejected baseline reads and the last OCR duration. An over-budget
read suggests a smaller ROI. Session metrics include baseline OCR wall time and result age.
Readiness event observation count remains the stable run count, while the new accepted
counter covers all accepted baseline reads.

## Measured comparison

The benchmark uses a 30 fps synthetic source, the real latest-frame worker, live session,
local CPU RapidOCR baseline model at its default scale 2 and two threads, and memory
clipboard. Moving pixels are confined to a strip away from the text. The existing code
is visible during setup. The new code appears near the right edge after the arm event.
No DXcam or real clipboard is involved in this benchmark. These are synthetic workloads
with a small number of samples, not real-stream qualification.

The before and after runs used the same three scene configurations and a 10-second
session limit. Model warmup occurs before the Start timer. OCR p50/p95 below exclude
the separately recorded preprocessing. Confirmation latency is first eligible OCR
recognition to successful memory copy.

| ROI and distractor lines | Run | Start to Ready ms | Accepted / rejected | Baseline OCR p50 / p95 ms | Recognition to copy ms | First new capture to copy ms |
|---|---|---:|---:|---:|---:|---:|
| 760 × 140, 0 | Before | 697.6 | 6 / 0 | 109.8 / 144.4 | 122.5 | 395.2 |
| 760 × 140, 0 | After | 589.5 | 6 / 0 | 89.9 / 127.1 | 127.6 | 355.4 |
| 1920 × 1000, 12 | Before | 1294.1 | 2 / 0 | 640.9 / 753.4 | 542.4 | 1743.5 |
| 1920 × 1000, 12 | After | 1454.1 | 2 / 0 | 720.3 / 848.1 | 597.4 | 1795.3 |
| 1920 × 1000, 76 | Before | No Ready | 0 / 5 | 1916.6 / 2201.3 | — | — |
| 1920 × 1000, 76 | After | 4157.6 | 2 / 0 | 2070.6 / 2204.0 | — | — |

Both lighter scenes copied the expected new code once and kept the baseline code
suppressed. The dense after-run reached Ready and armed, then rejected three expired
armed results with no writes. Armed OCR median was 1992.2 ms on that fixture.
Readiness is improved; dense armed recognition still needs to finish inside the
unchanged one-second deadline. There is no inference-speed improvement claim.
At the same 1920 × 1000 size, adding distractor text increased recognition work
substantially. Before-change text-recognition medians were 428.6 ms with 12 lines and
1739.6 ms with 76. Detection medians were 207.6 and 162.6 ms respectively.

A separate size control kept the text count fixed at zero distractor lines. In the
serial run after the OCR test suite exited, 760 × 140 versus 1920 × 1000 gave baseline
OCR medians of 79.5 versus 185.2 ms and detector medians of 46.3 versus 150.3 ms.
Both confirmed the new code. This isolates a size/aspect-ratio cost in addition to
the much larger text-density cost. The report is
`artifacts/moving-baseline-size-control-serial.jsonl`. An earlier size-control probe
overlapped the test suite and is retained separately, outside the serial comparison.

Benchmark command, run before and after the live-session change with fresh filenames:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_baseline.py --report artifacts/moving-baseline-after.jsonl
```

Reports are `artifacts/moving-baseline-before.jsonl` and
`artifacts/moving-baseline-after.jsonl`. They include stage statistics, events,
expected suppression and actual memory writes. The report schema gained explicit total
baseline counters after the before-run. Before counts above are reconstructed from Ready
and stale events.

## Automated checks

Regression coverage includes static and moving-to-static startup, static-to-moving
detection, simulated fast and slow moving baselines, observed codes before Start and
during setup, strict armed expiry, two fresh confirmations for a later code and duplicate
suppression after rearm. The slow-result test checks the moving budget boundary and the
existing healthy static path. Existing capture-fault, cleanup, pause and native consent
tests remain in the suite. The GUI test checks rejected counts and the OCR timing label.

`./scripts/check.ps1 -Ocr` exited 0 with 192 passed and the three existing challenge
xfails in 61.87 seconds. Dependency checks, Ruff lint/format and strict mypy passed.
Output is `artifacts/moving-baseline-check-ocr.txt`. The subsequent final readiness
progress emission was included in the final headless check. `./scripts/check.ps1`
exited 0 with 182 passed and 13 OCR opt-in skips in 42.25 seconds, plus passing
dependency, Ruff and strict mypy checks. Output is `artifacts/moving-baseline-check.txt`.

The develop commit review reran both suites after the labelled Discount changes.
Both passed. See [the commit review results](LABELLED_DISCOUNT_VALIDATION.md#automated-checks).

## Windows operator check

**PASS (operator-reported, 2026-11-09 MYT) for the TradingView moving-baseline
workflow.** On Windows the session reached the point where the operator could click
**Arm**, and Stream Code Capture then detected the exact new Discount code
`Q8M4Z7P2VK`. See [the labelled Discount retest](LABELLED_DISCOUNT_VALIDATION.md).
The operator did not report ROI dimensions, Start-to-Ready timing, baseline counters,
or clipboard verification. The separate large moving TikTok check below remains open.

1. Launch the current develop GUI with
   `./.venv/Scripts/python.exe -m stream_code_capture.gui`.
2. Keep native copying unchecked and place the GUI outside the selected region. Use
   the same large moving TikTok video region. Click Start while playback continues.
3. Record ROI dimensions, elapsed Start-to-Ready time, baseline counts and last OCR
   time. Pass readiness if Ready appears and Arm becomes available without pausing or
   shrinking the source. If it stalls, record the exact reason and rejection count.
4. If a known code was visible during setup, arm and check it remains suppressed.
   Use an independently known later code to evaluate actual confirmation, and record
   misses separately. Test in dry-run.

The broader G3 representative accuracy/latency gates remain open. This change is not
a claim that a full-screen dense livestream can satisfy the armed freshness limit.
