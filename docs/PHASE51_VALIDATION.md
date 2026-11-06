# Phase 5.1 — memory and native performance qualification

Date: 2026-11-03, Asia/Kuala_Lumpur. Qualification completed. **Memory, observed safety,
recovery and automated checks pass; overall Phase 5.1 is not fully accepted because the
arena-disabled configuration has a material, repeated latency penalty.** No default is promoted.

Environment: the existing Windows 11 build 26200 host, Python 3.12.14 `.venv`, RapidOCR
3.10.0, ONNX Runtime 1.31.1 and DXcam 0.3.0; CPUExecutionProvider only. Installed APIs and
actual session options were checked locally. Detector SHA-256
`090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`, recognizer SHA-256
`6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` match across every pair.

## Fixed protocol

Compare the existing optimized configuration with only its CPU arena setting changed:
scale 1, four threads, detector limit 640, spinning disabled, same PP-OCRv6 small local
models and CPU provider. The public CLI's existing `--cpu-arena` enables the arena;
omitting that flag disables it. No runtime defaults or recognition/policy code change.

The arena comparison in `scripts/phase5_qualification.py` launches fresh sequential
processes with the same seed 20261105, 760x140 physical-pixel ROI, playback sequence,
`--profile-inference --precise-stimulus --drain-ms 1000`, and native write/readback checks.
Pair order alternates across cohorts to reduce systematic run-order bias. Both settings
receive the 40-event discount/game 2000 ms sequences, 16-event discount/game short-exposure
sequences, and eight imported screenshots. Unlike Phase 5, both configurations receive
the short tests: 240 positive appearances across ten runs, rather than 208 across eight.
This is simulated playback through actual DXcam, not a representative real-stream holdout.

Native writes require `--native-clipboard` on the matrix driver; memory remains its default.
Visible tests require the explicit screen-test command. The matrix stops on wrong writes,
readback mismatches or accepted-frame completion beyond the unchanged 1000 ms limit.
All O/0 misses remain in recall denominators and full-recall job exit codes remain failures.
The two-observation confirmation, quality guards, baseline, one-shot copy, deduplication,
freshness and failure-recovery behavior are unchanged.

The negative soak retains the original fixture/seed, paired-profile processing, first
monitoring snapshot and pre-cleanup final snapshot. Its original **50 MiB** private-byte
growth limit and 1800-second minimum duration are unchanged. No allocator trimming,
forced garbage collection, extra fixture warmup or delayed memory baseline is introduced.
The arena-disabled soak runs in a fresh process. Phase 5's arena-enabled 1800-second trace
is retained as historical evidence; fresh-process on/off allocation diagnostics are rerun.

New test-only telemetry records actual warmed detector/recognizer ONNX session options,
not just requested CLI flags. Playback memory samples occur after copy/readback processing
at five-second intervals. Those are sampled process allocations, not exhaustive transient
allocation peaks; the final playback summary follows capture cleanup. Soak measurements
remain before cleanup, preserving the original memory gate. Private commit and resident
working set are reported separately. Neither is interchangeable with OCR wall time.

## Commands

All commands run from the existing repository with its pinned `.venv`; report destinations
are new. No historical data is overwritten.

```powershell
./scripts/check.ps1
./scripts/check.ps1 -Ocr
./.venv/Scripts/python.exe scripts/phase5_memory.py --cpu-arena --report artifacts/phase51-memory-arena.json
./.venv/Scripts/python.exe scripts/phase5_memory.py --no-cpu-arena --report artifacts/phase51-memory-no-arena.json
```

## Initial checks and allocation diagnostics

`phase51-check.txt`: headless check exit 0, 103 passed / 13 opt-in skips in 6.82 s.
`phase51-check-ocr.txt`: exit 0, 113 passed / three original strict challenge xfails in
42.05 s; dependency checks, Ruff lint/format and strict mypy (16 source files) passed.
Two new OCR integration cases verify the requested arena flag on the actual warmed
detector and recognizer sessions, including four threads and disabled spinning.
Later harness-failure regressions will receive a final full check after qualification.

Fresh-process 60-input allocation diagnostics reproduced the earlier finding:

| Arena | Baseline-to-final private growth | Sampled peak growth |
|---|---:|---:|
| Enabled | 66.2 MiB | 66.3 MiB |
| Disabled | 0.9 MiB | 1.0 MiB |

Both reports record the actual ONNX session settings. These are offline synthetic
allocation measurements, not native latency or real-world accuracy evidence.

## Interrupted capture and test-driver correction

The initial matrix is retained in `artifacts/phase51-native-matrix`. The first arena-on
discount run copied 26 codes correctly, then failed closed with `Capture stalled`.
Subsequent early runs captured a blank frame or no test frames; their zero-copy results
cannot support an arena performance/accuracy comparison. There were no incorrect writes.
The desktop was confirmed unlocked/active again by the user; subsequent game-short and
screenshot pairs completed normally and are separately auditable valid comparisons.

Read-only `powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE` and
`powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE` showed a 180-second display timeout
and 600-second sleep timeout on battery. GetSystemPowerStatus reported battery operation
(82% at inspection). This is consistent with the observed capture outage; it is not proof
of the exact external event that caused it.

The old matrix driver checked wrong/late writes but continued after a capture failure
with zero writes. The corrected driver now stops on session failure, incomplete capture
coverage, missing schedule or harness errors, independently of the full-recall assertion.
Regression tests cover these cases. The paired analyzer also refuses interrupted runs.
Full-recall failures due to O/0 remain failures; they are not hidden by capture-health checks.

For the remaining screen tests, a separate bounded, explicitly invoked helper holds a
temporary display/system execution request. It does not edit power settings, enable away
mode, prevent manual sleep, disable screen savers or bypass locking. The stop file releases
it at qualification completion; timeout and Ctrl+C also release it. API behavior was
checked against [Microsoft's SetThreadExecutionState documentation](https://learn.microsoft.com/en-us/windows/desktop/api/winbase/nf-winbase-setthreadexecutionstate).

```powershell
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --native-clipboard --suite matrix --comparison arena --output artifacts/phase51-native-matrix
./.venv/Scripts/python.exe scripts/qualification_awake.py --request-display --seconds 5400 --stop-file .tmp/phase51-awake.stop --report artifacts/phase51-awake.jsonl
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --no-cpu-arena --report artifacts/phase51-windows-failures.jsonl
./.venv/Scripts/python.exe scripts/negative_soak.py --show-window --no-cpu-arena --seconds 1800 --report artifacts/phase51-negative-1800.jsonl
./.venv/Scripts/python.exe scripts/analyze_arena.py artifacts/phase51-native-matrix --cohorts game-short screenshots --output artifacts/phase51-valid-initial-pairs.json
```

The arena-disabled recovery run passed 14/14 probes with six exact native recovery/positive
copies and readbacks. Stop/disarm during real OCR, premature arm rejection, duplicate
suppression, blank/static capture, genuine clipboard contention and fresh-session recovery
are preserved. The completed soak and retries are recorded below; no concurrent OCR
benchmark ran during them. The interrupted pairs were rerun after the soak, in a new
directory. The screenshot pair was also repeated in reverse order because its initial
arena-disabled p50/p95 were 26%/43% slower despite unchanged 8/8 exact recall.

No new default is promoted. The three original challenge xfails, real-video accuracy and
manual physical monitor/DPI/lock/hotplug/paste qualification remain unresolved.

## Valid initial native pairs

The paired analyzer verified identical schedules, ROI, models/hashes, providers and
options apart from arena/report path, including actual warmed ONNX options. These four
runs completed after desktop capture resumed; the preceding six interrupted runs are
excluded from comparisons, not relabelled accuracy passes.

| Input | Arena | Exact | Copy p50 / p95 / max (ms) | Readback end-to-end p50 / p95 / max (ms) |
|---|---|---:|---:|---:|
| Game short exposures | On | 12/16 | 244.0 / 292.6 / 309.3 | 270.1 / 344.6 / 361.2 |
| Same game sequence | Off | 12/16 | 266.1 / 311.3 / 313.1 | 283.2 / 326.2 / 336.2 |
| Imported screenshots | On | 8/8 | 493.6 / 593.9 / 632.8 | 521.9 / 636.8 / 684.2 |
| Same screenshots | Off | 8/8 | 624.1 / 849.0 / 906.8 | 650.9 / 855.6 / 915.9 |

All four have zero wrong writes, readback mismatches and freshness violations. a
223.8 to 300.3 ms, with recognition inference 165.4 to 234.7 ms. Clipboard API p50 remained
below 1 ms. The observed slowdown is in recognition work, not an added clipboard delay.
The reverse-order repeat below is retained alongside these results, not substituted for
an unfavorable initial result.

Sampled native private-memory peak growth from baseline: game-short 24.3 MiB on versus
5.5 MiB off; screenshots 119.3 MiB on versus 2.2 MiB off. These are five-second samples
within finite playback jobs, not substitutes for the full-duration soak.

## Allocator interpretation

The controlled on/off experiments identify the arena setting as the dominant source of
excess allocation retention for these inputs. This is consistent with ONNX Runtime's
documented per-session arenas retaining allocated regions, rather than evidence that
captured frames are accumulating in a queue. ONNX Runtime also documents configurable
arena growth/shrinkage and allocator sharing; these are possible follow-up experiments,
not changes implemented or qualified here. See [ONNX Runtime memory management](https://onnxruntime.ai/docs/get-started/with-c.html#features).

The app's diagnostic deques are capped at 10,000 values per stage. They initially grow
while filling, even when OCR arena allocation is disabled. The soak now reports a
post-measurement upper-bound estimate for their retained float/deque storage; shared
values may be counted twice, so it is not a precise heap attribution. This calculation
occurs after the final memory sample and cannot change the pass/fail measurement.
A 30-minute trace can establish behavior over that interval, not prove absence of every
possible long-lived native allocation leak.

## Completed arena-disabled memory soak

`artifacts/phase51-negative-1800.jsonl` completed 1800.067 seconds, exit 0, `passed: true`,
with both profiles armed, zero memory-clipboard writes and no harness/capture errors.
It used real DXcam screen capture and sequential local OCR, not native clipboard writes.
The original first-monitoring/pre-cleanup baseline and 50 MiB threshold were preserved.

| Measurement | Arena on (Phase 5) | Arena off (Phase 5.1) |
|---|---:|---:|
| Duration | 1800.20 s | 1800.07 s |
| Initial private bytes | 620,572,672 | 515,440,640 |
| Final private bytes | 702,148,608 | 530,173,952 |
| Growth | 77.8 MiB | 14.1 MiB |
| Memory gate | Fail | Pass |
| Negative-scene writes | 0 | 0 |

The disabled run's sampled maximum growth was 15.3 MiB. Growth from the first sample
after 20 minutes to completion was 0.98 MiB, with intervening decreases rather than a
monotonic leak. Resident working set changed from 166.5 to 184.3 MiB. The process captured
46,295 frames and replaced 42,434 pending frames; it did not accumulate a frame backlog.
There were 3,857 discount and 3,854 game frame decisions, nine stale-result rejections
and three additional pre-OCR stale rejections. None reached the clipboard.

Post-measurement bounded diagnostic storage upper estimates were 1,292,512 bytes for
capture, 2,500,232 for discount and 2,498,792 for game (about 6.0 MiB combined); individual
stage deques retain at most 10,000 samples. This explains part, not all, of the remaining
growth. The finite trace supports bounded behavior over this run; it cannot attribute
every allocation or establish unlimited-duration stability.

The first temporary display request logged successful release. Its elapsed wall time
includes the long interruption before the conversation resumed; it was not a permanently
changed Windows power setting. A new bounded request covers the remaining retry tests.

## Final automated checks

```powershell
./scripts/check.ps1 *> artifacts/phase51-check-final.txt
./scripts/check.ps1 -Ocr *> artifacts/phase51-check-final-ocr.txt
```

Both exited 0. Headless: **107 passed, 13 opt-in skips**, 12.19 seconds. Real offline OCR:
**117 passed, three strict expected failures**, 42.96 seconds. Both ran `pip check`, Ruff
lint, Ruff format check (69 files) and strict mypy (16 source files), all passing. The
three failures are the unchanged tiny/compressed O/0 challenge exact-recall gates, not
new failures or assertions relaxed for this phase. Four new headless cases exercise
qualification capture-completion rejection; two new real-OCR cases check actual arena
and threading options on warmed detector and recognizer sessions.

The retry command, after the soak and checks finished, is:

```powershell
./.venv/Scripts/python.exe scripts/qualification_awake.py --request-display --seconds 3600 --stop-file .tmp/phase51-retry-awake.stop --report artifacts/phase51-retry-awake.jsonl
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --native-clipboard --suite matrix --comparison arena --cohorts discount-long game-long discount-short screenshots --reverse-pairs --output artifacts/phase51-native-retry
```

The keep-awake helper runs separately, not concurrently with another OCR workload. Its
timeout is checked while the process runs; it is not a wall-clock guarantee while Windows
or the process is suspended. After the final native job, creating
`.tmp/phase51-retry-awake.stop` released the request. Session exit was 0 and
`artifacts/phase51-retry-awake.jsonl` records `released: success=true` after 1209.906 seconds.
No execution request from these helpers remains active.

## Completed native comparisons

```powershell
./.venv/Scripts/python.exe scripts/analyze_arena.py artifacts/phase51-native-retry --output artifacts/phase51-retry-pairs.json
```

The analyzer exited 0 and verified every pair's schedule, ROI, models/hashes, installed
versions, provider and actual warmed session options. It found **no extra missed indexes
with arena disabled**. `artifacts/phase51-completed-summary.json` combines the four retry
pairs and two initially valid pairs without discarding either screenshot repeat.

Times below are milliseconds from the first captured target-containing frame. Triples
are **p50 / p95 / worst**, successful copies only. Readback includes actual write and
test readback/retry scheduling; it is not merely the clipboard API's duration. Each side
of a pair has the listed recall. Failed events do not disappear from the denominators.

| Input pair | Exact each | Arena on copy | Arena off copy | Arena on readback | Arena off readback |
|---|---:|---:|---:|---:|---:|
| Discount, 2000 ms | 30/40 | 229.8 / 271.5 / 284.2 | 267.8 / 322.5 / 423.3 | 238.5 / 285.4 / 305.1 | 271.2 / 351.4 / 479.8 |
| Game, 2000 ms | 30/40 | 244.2 / 266.8 / 276.0 | 256.8 / 335.3 / 540.6 | 251.6 / 286.2 / 294.6 | 259.0 / 361.7 / 543.3 |
| Discount, short | 12/16 | 241.3 / 326.3 / 334.7 | 261.7 / 281.9 / 282.7 | 263.0 / 334.3 / 336.8 | 270.7 / 293.7 / 305.4 |
| Game, short (initial valid pair) | 12/16 | 244.0 / 292.6 / 309.3 | 266.1 / 311.3 / 313.1 | 270.1 / 344.6 / 361.2 | 283.2 / 326.2 / 336.2 |
| Screenshots, first pair | 8/8 | 493.6 / 593.9 / 632.8 | 624.1 / 849.0 / 906.8 | 521.9 / 636.8 / 684.2 | 650.9 / 855.6 / 915.9 |
| Screenshots, reversed pair | 8/8 | 461.0 / 517.0 / 517.5 | 581.1 / 634.9 / 645.2 | 505.6 / 543.5 / 550.6 | 582.9 / 660.1 / 667.3 |

Across these 12 completed runs: **200/256 exact copies, 56 abstentions/misses, zero incorrect
writes, zero readback mismatches and zero late writes**. Each arena setting achieved
100/128. The five original cohort pairs account for 184/240; the additional screenshot
repeat contributes 16/16. These are repeated fixture appearances, not 256 independent
real-world examples. All synthetic misses contain O or 0 in their expected labels.
The guards intentionally abstain even when a raw OCR string happens to match; the
underlying ambiguous-glyph defect remains. The eight screenshots remain reused inputs.

Every retry captured the complete schedule and had no session/harness error. The six
generated retry jobs exited 1 because of unchanged full-recall assertions; both screenshot
jobs exited 0. The retry matrix therefore exited **1**, not an all-green accuracy pass.
The first six interrupted initial jobs remain invalid for paired comparisons; their 26
correct partial writes are not added to the completed-run accuracy/latency totals.

Short exposure results were identical for both profiles/settings: 4/4 exact at 250 ms,
2/4 at 500 ms, 3/4 at 1000 ms and 3/4 at 2000 ms. This small randomized sequence assigns
different codes/ambiguities to each duration, so it cannot establish a recall-versus-duration
curve. All 16 targets were captured. At 250 ms, copies completed before disappearance in
2/4 cases on versus 0/4 off for discount, and 2/4 on versus 1/4 off for game. Remaining
successful copies completed in the explicit 1000 ms drain with fresh source frames; the
runtime freshness limit was not extended. No result establishes under-100 ms performance.

## Stage and allocation comparison

The next table uses confirmation/copy-evidence frames. OCR wall time includes the local
OCR call; detector/recognizer inference values are separately instrumented ONNX calls.
They are not added to OCR time, and percentiles are not additive. Process CPU time sums
thread work and is not elapsed latency. Capture/handoff age measures waiting and source
freshness, not additional inference computation; all stage distributions remain in JSON.

| Pair | OCR wall p50 on/off | OCR wall p95 on/off | Detector inference p50 on/off | Recognizer inference p50 on/off | First raw exact recognition to copy p50 on/off | Sampled private peak growth MiB on/off |
|---|---:|---:|---:|---:|---:|---:|
| Discount long | 91.6 / 104.7 | 99.5 / 139.2 | 28.3 / 33.4 | 50.3 / 54.2 | 95.1 / 108.2 | 24.1 / 8.4 |
| Game long | 93.4 / 101.2 | 101.4 / 135.6 | 28.3 / 32.1 | 52.1 / 55.0 | 96.6 / 103.5 | 25.5 / 8.3 |
| Discount short | 97.6 / 101.3 | 123.4 / 113.9 | 29.7 / 32.0 | 52.0 / 56.5 | 99.5 / 102.5 | 18.8 / 3.8 |
| Game short | 104.0 / 110.7 | 120.3 / 132.7 | 31.0 / 34.8 | 55.7 / 61.8 | 105.0 / 111.5 | 24.3 / 5.5 |
| Screenshots first | 223.8 / 300.3 | 273.8 / 431.9 | 30.4 / 35.7 | 165.4 / 234.7 | 226.4 / 251.3 | 119.3 / 2.2 |
| Screenshots reversed | 215.0 / 250.8 | 236.2 / 308.7 | 27.9 / 31.7 | 166.0 / 201.0 | 213.8 / 229.4 | 123.7 / 6.1 |

Inference remains the dominant bottleneck. For example, arena-off discount preprocessing
p50 was 0.016 ms, policy 0.047 ms, clipboard handoff 0.313 ms, and source age at dequeue
26.9 ms, versus 104.7 ms OCR per observation. A second independent observation remains
required. Clipboard and scheduling tails are visible but cannot explain the repeated
recognizer inference slowdown on screenshots.

Relative to the historical Phase 5 optimized native p50s, arena-off discount was 267.8
versus 269.6 ms, game 256.8 versus 249.3 ms, and screenshots 581.1–624.1 versus 488.0 ms.
The fresh paired results are stronger comparisons: arena-off long-discount p50/p95 rose
16.6%/18.8%, long-game 5.1%/25.7%, and screenshot p50 rose about 26% in **both orders**
(p95 +22.8% and +42.9%). Other processes, power/thermal scheduling and finite samples
can affect tails; this experiment does not isolate every native allocation cost. The
repeated screenshot result is sufficient reason not to declare performance equivalence.

## Acceptance verdict and next gate

**Phase 5.1 is not fully passed.** The unchanged 1800-second memory gate passes with arena
off, observed exact recall matches arena on, no new wrong/stale writes occurred, recovery
passed 14/14 and all automated quality checks pass. However, latency is not uniformly
close to the optimized baseline: screenshot p50 is repeatedly about 26% slower and some
native tail latencies regress. No new numerical tolerance was invented after seeing the
data, and no default was promoted. Arena off is an explicitly measured memory-saving
option, not an unconditional replacement with equivalent performance.

Next engineering step: profile allocation behavior, then experimentally compare a bounded
arena-growth strategy or explicit arena shrinkage with both existing configurations.
Keep such an experiment opt-in; verify the installed Python/ONNX APIs, avoid trimming
in the timed critical path, and rerun matching accuracy, native latency and the full
unchanged memory gate before promotion. This is a recommendation, not implemented work.

Defer GUI development until the remaining G2 manual-paste/display/source-change checks
in `WINDOWS_VALIDATION.md` and this performance tradeoff are resolved. Three original
challenge xfails remain; representative TikTok LIVE accuracy, independent holdouts,
physical monitor/DPI/HDR/lock/hotplug qualification, GPU results and <100 ms latency remain
unverified or unmet. No cloud recognition, automatic redemption, packaging or GUI was added.

## Implementation scope

- `scripts/phase5_memory.py`: actual ONNX session-option evidence in fresh-process probes.
- `scripts/game_playback.py`: sampled process memory, session-option evidence and explicit
  capture-completion/failure fields in the result.
- `scripts/negative_soak.py`: explicit arena toggle, unchanged memory gate, actual session
  options and post-measurement bounded diagnostic-storage accounting.
- `scripts/windows_failures.py`: explicit arena toggle and actual session-option evidence.
- `scripts/phase5_qualification.py`: identical-input arena pairs, order reversal/selective
  pair retries and immediate abort on incomplete or failed capture.
- `scripts/qualification_metrics.py`: shared test-only memory/session inspection.
- `scripts/analyze_arena.py`: read-only paired-condition audit and latency/memory comparison.
- `scripts/qualification_awake.py`: explicit temporary execution request with release log.
- `tests/test_phase51.py`: session-option integration and capture-failure regressions.
- `README.md`, `docs/PROJECT_SPEC.md`, `docs/WINDOWS_VALIDATION.md` and this record:
  measured status, repeat commands and remaining gates.

`src/`, model files/hashes, dependency pins, runtime defaults, both detection profiles and
all recognition/confirmation/freshness/clipboard safeguards remain unchanged. The existing
repository contents were untracked before this work; no commit, push or artifact deletion
was performed. Raw Phase 5 and interrupted Phase 5.1 artifacts remain intact.
