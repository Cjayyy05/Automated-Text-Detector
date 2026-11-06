# Phase 5 — native Windows qualification

Date: 2026-11-02, Asia/Kuala_Lumpur. This record distinguishes actual DXcam/native
clipboard measurements on generated or reused screen stimuli from representative
livestream accuracy. The latter remains unverified: independently labelled TikTok LIVE
recordings have not been supplied. No GUI, packaging, model downloads, commits or pushes.

## Scope and implementation

Both detection profiles use the existing capacity-one capture handoff, warmed RapidOCR
instance, exact two-observation policy and clipboard adapter. The optimized configuration
is `--scale 1 --threads 4 --cpu-arena --no-spinning --det-limit 640`; the original defaults
remain available and unchanged. O/0 abstention and the source-resolution floor remain.

A deterministic regression exposed a freshness gap: policy validation used the timestamp
from before the control check. A slow control check could therefore allow an expired frame
to write. Validation now uses the current post-control timestamp; the pipeline checks the
frame deadline again before writing, and the live clipboard guard checks it under the same
lock that serializes disarm/write. Failure clears the deadline and does not commit a copy.
No age limit, confidence threshold or confirmation count was loosened.

The default 1000 ms freshness limit applies to the **accepted confirming frame**, not to the
first appearance of the code. OS clipboard APIs cannot provide a hard real-time completion
guarantee: a thread could be descheduled after the last check. Native probes measure actual
completion age, count writes beyond the limit as failures and stop on them.

Test tooling:

- `game_playback.py` retains memory-only default; explicit `--clipboard windows` adds actual
  write timing, CF_UNICODETEXT readback, mismatch and completion-age assertions.
- `phase5_qualification.py` runs sequential comparable default/optimized screen tests.
  `--show-window` is required; native writes additionally require `--native-clipboard`.
  It stops the matrix on a wrong write, readback mismatch or late completion. Misses remain
  failures even when intentional abstentions; they are never omitted from recall.
- `windows_failures.py` probes premature arm, repeat suppression, stop/disarm during real
  OCR, real black/static capture, clipboard contention and fresh-session recovery.
  Native contention and writing require the explicit native flag.
- `negative_soak.py` uses real DXcam and real OCR with a memory clipboard, testing both
  profiles sequentially on captured negative scenes with persistent codes and moving
  backgrounds. This is a loaded two-profile reliability test, not a latency comparison.
- `analyze_playback.py` includes native `copied` events in confirmation-stage summaries.

Fixtures know their labels solely for rendering/scoring. Runtime recognition/policy never
receives those labels or fixture coordinates. Clipboard contents are not automatically
restored; restoration could overwrite a later user copy.

## Measurement definitions

The test marker records the first code-containing DXcam acquisition **before** the latest
slot can discard frames. Native end-to-end latency ends after successful clipboard API
completion; readback end-to-end additionally includes the separate verification read and
reporting overhead between write and read. Readback retries a transient lock for up to one
second; application writes never retry. Display paint times are host GDI timestamps, not
calibrated panel presentation times. Misses have no successful-copy latency sample.

Capture-read/idle/CPU, frame-wait, handoff/queue age, crop/preprocessing, OCR, validation,
confirmation and clipboard timings remain separate. Wall times are not CPU utilization.
Confirmation elapsed time includes another OCR pass; adding overlapping stage percentiles
does not reconstruct end-to-end percentiles.

## Commands and results

Working directory is the repository root. Commands use the existing `.venv`.
All report destinations must be new; no historical artifacts were overwritten.

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/test_phase5.py
./.venv/Scripts/python.exe -m pytest -q tests/test_phase5.py tests/test_pipeline.py tests/test_live.py tests/test_phase4.py
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --suite smoke --output artifacts/phase5-memory-smoke
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --native-clipboard --suite matrix --output artifacts/phase5-native-matrix
```

The original freshness test failed (1 failed, `phase5-freshness-before.txt`), demonstrating
the defect. After the fix the focused suite passed 25 tests (`phase5-freshness-after.txt`);
the expanded three freshness/cleanup tests passed (`phase5-freshness-final.txt`).
All four memory-only screen smoke jobs passed 1/1 each with zero wrong/late writes.
Their single-event latencies are diagnostics, not a benchmark distribution.

## Native default versus optimized measurements

Environment: Windows 11 build 10.0.26200, Ryzen 5 5600H (12 logical processors), Python
3.12.14, CPUExecutionProvider. Same installed pins/models as Phase 4: RapidOCR 3.10.0,
ORT 1.31.1, NumPy 2.5.4, OpenCV headless 5.0.0.93, DXcam 0.3.0, pywin32 312.
Each report's `test_config` contains model SHA256 hashes and complete CLI options.
No GPU benchmark, provider substitution or OCR algorithm change.

All eight runs used seed 20261105, a 760x140 physical-pixel ROI, 60 Hz test pacing,
`--profile-inference --precise-stimulus --drain-ms 1000`. Comparisons use identical
labels/exposure schedules and sequential processes. This is an interactive desktop
measurement, not a thermally controlled laboratory experiment. No concurrent OCR benchmark
ran; lightweight source/lint work occurred during qualification.
Default OCR settings were scale 2, two threads, detector limit 960, arena disabled and
spinning enabled; optimized settings change only the explicit bundle stated above.

| Screen input | Configuration | Exact copies / appearances | Native copy p50 / p95 / max (ms) | Native readback end-to-end p50 / p95 / max (ms) |
|---|---|---:|---:|---:|
| Generated discount, 2000 ms | Default | 30/40 | 583.5 / 767.9 / 784.7 | 586.6 / 785.2 / 822.4 |
| Same discount sequence | Optimized | 30/40 | 269.6 / 413.9 / 435.4 | 272.7 / 426.7 / 442.1 |
| Generated game, 2000 ms | Default | 30/40 | 520.3 / 628.4 / 870.8 | 533.5 / 631.8 / 875.4 |
| Same game sequence | Optimized | 30/40 | 249.3 / 277.6 / 337.5 | 252.8 / 294.2 / 393.7 |
| Eight imported game screenshots | Default | 8/8 | 947.4 / 1351.9 / 1357.3 | 974.9 / 1389.9 / 1409.0 |
| Same eight screenshots | Optimized | 8/8 | 488.0 / 542.9 / 569.4 | 497.9 / 586.2 / 621.2 |
| Discount, mixed short exposures | Optimized | 12/16 | 255.2 / 322.3 / 365.3 | 272.3 / 336.6 / 366.6 |
| Game, mixed short exposures | Optimized | 12/16 | 218.9 / 254.1 / 261.1 | 223.5 / 278.8 / 298.8 |

Matrix total: **160/208 correct copies, 48 abstentions, zero incorrect writes, zero readback
mismatches, zero completion-age violations**. All 48 missed labels contain O/0. This is
not 100% overall recall; eligible-alphabet success cannot substitute for the full denominator.
Every positive appeared in real captured pixels. The six generated jobs exit 1 because
their full-recall assertions include the unsupported glyph cases; the two screenshot jobs
exit 0. Matrix exit 1 is preserved. No false-positive assertion was relaxed.

The copied event can be older than 1000 ms from first appearance while the confirming frame
is still fresh: the default screenshot maximum was 1357.3 ms, with zero accepted-frame
age violations. Do not conflate these two clocks or present the former as <1000 ms.
The largest accepted confirming-frame age at native completion across all 160 matrix copies
was 625.3 ms, below the configured 1000 ms freshness limit.

The eight source screenshots are reused evaluated inputs, not an independent accuracy
holdout. The generated cases broaden values/positions/backgrounds but remain synthetic.
The optimized configuration is therefore **not promoted to default**.

### Short appearances

Each nominal duration contains four new generated values per profile. All 16 are captured
and at least once transcribed exactly in raw OCR in each optimized run. Safeguards prevent
the four O/0 strings from being accepted, despite correct raw observations.

| Nominal exposure | O/0 cases (of 4) | Discount copies; before disappearance | Game copies; before disappearance |
|---:|---:|---:|---:|
| 250 ms | 0 | 4; 1 | 4; 3 |
| 500 ms | 2 | 2; 2 | 2; 2 |
| 1000 ms | 1 | 3; 3 | 3; 3 |
| 2000 ms | 1 | 3; 3 | 3; 3 |

| Nominal exposure | Discount native copy p50 / p95 / max (ms) | Game native copy p50 / p95 / max (ms) |
|---:|---:|---:|
| 250 ms | 261.3 / 284.5 / 287.2 | 218.6 / 244.7 / 248.4 |
| 500 ms | 259.4 / 271.7 / 273.0 | 236.3 / 258.6 / 261.1 |
| 1000 ms | 257.0 / 354.5 / 365.3 | 245.5 / 247.4 / 247.6 |
| 2000 ms | 247.6 / 259.6 / 261.0 | 211.4 / 239.8 / 243.0 |

Several valid 250 ms copies complete during the absent drain interval, using captured
confirming frames still within the original freshness limit. Nominal 250 ms paint durations
actually had p50 256.3 ms (discount) and 264.3 ms (game); maxima 259.8 and 265.6 ms.
These are not proof of exact 250 ms physical-panel exposure performance. All exposure
distributions and failed labels remain in `phase5-native-analysis.json`.

### Verified remaining bottleneck

Below are p50 wall times on the exact confirming/copy evidence frames, in milliseconds.
The recognition rows include separate native inference components; these measurements
overlap and must not be added indiscriminately.

| Stage | Discount default / optimized | Game default / optimized | Screenshots default / optimized |
|---|---:|---:|---:|
| Frame age entering pipeline | 29.3 / 38.7 | 29.3 / 27.8 | 24.2 / 24.7 |
| Preprocessing | 1.07 / 0.02 | 0.91 / 0.02 | 0.89 / 0.02 |
| OCR wall time per evidence frame | 232.0 / 106.6 | 214.2 / 96.2 | 467.6 / 218.5 |
| Detector inference | 105.3 / 34.4 | 93.8 / 29.0 | 83.5 / 29.3 |
| Text recognition inference | 85.1 / 53.5 | 84.1 / 51.3 | 356.2 / 167.5 |
| Candidate validation | 0.024 / 0.027 | 0.033 / 0.031 | 0.058 / 0.042 |
| Confirmation/dedup computation | 0.013 / 0.013 | 0.013 / 0.013 | 0.014 / 0.013 |
| First recognition to confirmed decision | 227.9 / 109.4 | 204.8 / 99.9 | 384.0 / 217.4 |
| Native clipboard API | 0.204 / 0.336 | 0.218 / 0.223 | 0.438 / 0.245 |

OCR plus the next fresh OCR observation dominates. Confirmation logic itself is tiny;
its elapsed delay is predominantly the second inference. On optimized screenshot evidence,
text recognition inference is 167.5 ms p50 versus detector 29.3 ms. A single OCR observation
is already above the whole 100 ms target for many inputs. Confidence or repeated identical
glyph readings still do not prove exact correctness; confirmation was not reduced.

Capture-read p50 was approximately 1.1–1.3 ms, with roughly 16 ms pacing waits. Frame-wait
p50 was 0.02 ms: a newer pending frame was normally available after OCR. Dropped captures
in the four long runs were 3453/2366 (discount default/optimized), 3603/2715 (game), without
an OCR FIFO. Process CPU time exceeds wall time due to native worker threads; capture-thread
CPU samples quantize to zero at p50 and should not be interpreted as zero CPU use.
Native clipboard tails can contribute: optimized game write max 83.2 ms; readback lock
retries often add about 50 ms. Stage p95/max and all status counts are retained in the
analysis artifact, alongside bounded capture-statistic sample counts.

## Windows failure and recovery probes

The final `phase5-windows-failures-owned-lock.jsonl` passed **14/14** probes (seven per
profile): premature arm rejection plus successful baseline/start, one-shot duplicate
suppression across rearm, disarm during real OCR, stop during real OCR, blank capture,
static-source timeout, clipboard contention/rearm recovery and fresh-session recovery.
The per-profile duplicate probe also checks premature arm, hence seven cases cover all
these assertions. Six recovery/positive native writes had exact readbacks; urgent control
timestamps lie strictly inside the recorded actual OCR interval. Blank/stalled sessions
returned expected failures and disarmed; the qualification harness correctly treats those
as passed failure-handling probes. These are physical captured stimuli, not injected OCR.

Two initial contention harness attempts failed and remain recorded in
`phase5-windows-failures.jsonl` and `phase5-windows-failures-process-lock.jsonl`.
An `OpenClipboard(NULL)` holder, first in another thread and then another process, did not
establish effective contention in this environment. Each app write matched the code actually
displayed, but the probe incorrectly expected its later recovery code and failed scoring;
the holder also reported CloseClipboard error 1418. These are **invalid contention trials**,
not demonstrated recognition errors or passes. The corrected helper uses a separate process,
an explicit hidden owner window and verifies a non-null `GetOpenClipboardWindow` before
arming. Both profiles then produced `clipboard_failed`, no commit and disarming while busy,
followed by a correct fresh-code copy only after explicit test-controller rearm.

```powershell
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --report artifacts/phase5-windows-failures.jsonl
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --report artifacts/phase5-windows-failures-process-lock.jsonl
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --report artifacts/phase5-windows-failures-owned-lock.jsonl
$reports = Get-ChildItem artifacts/phase5-native-matrix -Filter '*.jsonl' | ForEach-Object FullName
./.venv/Scripts/python.exe scripts/analyze_playback.py $reports --output artifacts/phase5-native-analysis.json
```

## Extended negative monitoring

The preliminary 30-second negative smoke completed 30.19 seconds with zero memory writes
and no capture/control error. Each profile recorded 46 `no_candidate` and 23 `ambiguous`
decisions. However, private bytes increased from 618,405,888 to 686,878,720 (+65.3 MiB),
failing the unchanged 50 MiB growth check. The failed artifact is retained; it is not a
passed long-run memory qualification. A full 1800-second run was then started explicitly
to distinguish initial allocation from continuing growth. No runtime memory defaults were
changed to make the test pass.

```powershell
./.venv/Scripts/python.exe scripts/negative_soak.py --show-window --seconds 30 --report artifacts/phase5-negative-smoke.jsonl
./.venv/Scripts/python.exe scripts/negative_soak.py --show-window --seconds 1800 --report artifacts/phase5-negative-1800.jsonl
./scripts/check.ps1
./scripts/check.ps1 -Ocr
```

The repository checks and the offline allocation probes ran during the negative soak as
additional background CPU load; they did not overlap the completed native performance matrix.
No other visible test surface or native clipboard test ran during the soak. Samples retain
private bytes, working set, processed status counts and dropped captures every minute.

The full run completed **1800.20 seconds**. Both profiles remained armed and made zero
memory clipboard writes, with no capture/control errors and clean shutdown. Each processed
4,212 decisions: discount 2,894 `no_candidate`, 1,309 `ambiguous`, 9 `confirming`; game
2,943 `no_candidate`, 1,260 `ambiguous`, 9 `confirming`. The nine single-observation candidate
decisions per profile never became confirmed copies. This is evidence against reducing
the confirmation requirement merely for speed, not proof of arbitrary-stream precision.
The shared producer captured 46,848 changed frames and discarded 42,632 superseded frames;
there was no growing capture queue. These are two policy evaluations of each consumed
frame, not 8,424 independent real-video examples.

**The overall soak failed its memory gate (exit 1, `passed: false`).** Private bytes grew
from 620,572,672 to 702,148,608: **+77.8 MiB**, exceeding the unchanged 50 MiB threshold.
At the one-minute sample, private bytes were already 691,081,216; subsequent growth through
completion was another 10.6 MiB. The trace fluctuates and does not establish an unbounded
leak, but it also does not pass the defined growth gate. The passing no-write/failure-free
subresults must not be presented as a fully passed soak. Final working set was 291,168,256
bytes; private commit and resident working set are different measurements.

### Memory-growth investigation

Two fresh-process, memory-only offline diagnostics isolate the arena setting, with all
other optimized settings and the 60 negative inputs held constant. They do not qualify
native performance or accuracy and did not alter the running soak or application defaults.

```powershell
./.venv/Scripts/python.exe scripts/phase5_memory.py --cpu-arena --report artifacts/phase5-memory-arena.json
./.venv/Scripts/python.exe scripts/phase5_memory.py --no-cpu-arena --report artifacts/phase5-memory-no-arena.json
```

From warmed baseline to final allocation: arena enabled **+66.2 MiB**, arena disabled
**+1.1 MiB** (peak +1.5 MiB). This controlled diagnostic attributes most of the observed
startup growth to the CPU arena setting for these inputs. It does not prove an unbounded
leak or prove that disabling the arena preserves native latency; that needs its own matched
native comparison. The requested optimized bundle remains opt-in, including its arena flag.

## Automated checks

- `./scripts/check.ps1`: exit 0; dependency check clean, Ruff lint/format clean, strict mypy
  clean for all 16 source files; **103 passed, 11 opt-in OCR skips** in 7.63 seconds.
- `./scripts/check.ps1 -Ocr`: exit 0; dependency/lint/format/type checks clean;
  **111 passed, 3 strict xfailed** in 46.17 seconds. All original tiny/compressed/O/0 exact
  recall failures remain present; no xfail was removed or relaxed.
- After adding the allocation diagnostic, `./scripts/check.ps1 -Ocr` ran again: exit 0,
  **111 passed, 3 xfailed** in 43.99 seconds; all 64 Python files pass Ruff formatting,
  lint passes, strict mypy passes all 16 source files, and `pip check` is clean.
- New deterministic regressions cover control-check delay causing expiry, expiry while
  waiting for the clipboard/control lock, and deadline cleanup/disarming on write failure.
- Initial lint issues in the new failure script (formatting, unused import, loop-closure
  bindings) were fixed by formatting and a per-probe function before final checks. Initial
  test-harness contention failures and the negative-smoke memory failure are documented
  above, separately from the passing unit/integration checks.

Exact outputs: `artifacts/phase5-check.txt`, `artifacts/phase5-check-ocr.txt`,
`artifacts/phase5-check-final-ocr.txt`.

## Files changed in this phase

- Runtime: `src/stream_code_capture/pipeline.py`, `src/stream_code_capture/live.py`.
- Regression tests: `tests/test_phase5.py`.
- Test/analysis scripts: `scripts/game_playback.py`, `scripts/analyze_playback.py`,
  `scripts/native_readback.py`, `scripts/phase5_qualification.py`,
  `scripts/windows_failures.py`, `scripts/negative_soak.py`, `scripts/phase5_memory.py`.
- Documentation: `README.md`, `docs/PROJECT_SPEC.md`, `docs/WINDOWS_VALIDATION.md`,
  this record. New reports are in `artifacts/phase5-*`.

The repository still has its pre-existing untracked project tree, so `git status` is not
a phase-specific diff. No existing dataset, ZIP, model or historical report was deleted.
Dependencies, OCR algorithm and default runtime configuration were not changed.

## Outstanding release evidence

**Phase 5 demonstrates native speed improvement without an observed accuracy regression
on the matched fixtures, but full qualification has not passed. Do not begin GUI development
or promote the optimized bundle yet.** Native readback and the automated failure probes
are verified; the memory-growth gate, manual G2 evidence and representative G3 accuracy
remain unresolved. Under-100 ms performance is not achieved.

Recommended next engineering step: benchmark the same optimized bundle **without**
`--cpu-arena`, using the same native matrix and a fresh 1800-second soak, before choosing
a memory/performance tradeoff. Do not assume the offline allocation improvement preserves
native latency. Then complete the manual G2 display/paste matrix below and obtain real
independently labelled videos before broader accuracy tuning or GUI work.

Read the exact manual steps in `WINDOWS_VALIDATION.md`. Automated native readback does not
replace the specified manual-paste checks. Lock/unlock, monitor hotplug, DPI/rotation/HDR,
source occlusion/minimization and physical multi-monitor ROI correctness require separate
interactive qualification. Generic changed desktop pixels do not prove source identity.
All three original challenge regressions remain visible. General real-stream accuracy and
under-100 ms latency are not established. Optimized settings remain opt-in pending broader
representative evidence, and GUI work remains deferred until the remaining G2 gates pass.
