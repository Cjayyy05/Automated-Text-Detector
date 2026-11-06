# Phase 4 — measured CPU configuration and confirmation diagnostics

Date: 2026-11-02, Asia/Kuala_Lumpur. Windows build 10.0.26200, Python 3.12.14,
AMD Ryzen 5 5600H, CPUExecutionProvider. Installed versions checked again: RapidOCR 3.10.0,
ONNX Runtime 1.31.1, NumPy 2.5.4, OpenCV headless 5.0.0.93, DXcam 0.3.0, pywin32 312,
pytest 9.2.0, Ruff 0.17.3, mypy 2.4.1. No dependencies or model files changed/downloaded.
Model SHA256 records are in the configuration matrix and new playback reports.

**Measured improvement is demonstrated on these fixtures. No faster setting is promoted
to a default or qualified for arbitrary livestreams. Under 100 ms remains unmet.** Both
detection profiles, OCR baseline, two fresh confirmations, O/0 abstention, source-quality
guards, one-shot arming, deduplication and stale/control/clipboard-error safeguards remain.
No native clipboard writes, application GUI, packaging, commits or pushes occurred.
Visible stimulus windows were launched only by explicit playback test commands.

## Root causes and decisions

1. Recognition of multiple text lines dominates cost. Frame capture and policy computation
   are much smaller. A second full fresh-frame OCR call supplies confirmation; its cost
   appears again between first recognition and clipboard success. The handoff remains
   capacity one, so slow OCR drops frames rather than building a FIFO.
2. Freshness is checked before and after OCR. A correctly transcribed result can exceed
   the 1000 ms budget and reset agreement. A stale observation is not evidence for a later
   copy. There is no age-budget increase or one-observation shortcut in this work.
3. The legacy playback controller also sends `disarm` at disappearance, cancelling otherwise
   fresh in-flight results. This is a harness effect, separate from OCR staleness. Legacy
   comparable runs are preserved. A test-only `--drain-ms 1000` keeps the scene code-free
   and leaves the app armed briefly before the next event. It does not supply/copy cached
   labels, replay old frames or override policy freshness. Captured-frame association allows
   valid in-flight copies to be scored even after the current display becomes blank.
4. Legacy `Event.wait(1/30)` stimulus pacing made nominal 250 ms exposures roughly 300 ms.
   Opt-in `--precise-stimulus` uses Python's high-resolution sleep with a bounded 60 Hz
   interval and deadline-aware pacing. Paint-completion transitions report actual exposure
   length. They are host GDI timestamps, not calibrated physical panel presentation times.
   The first drain comparison also exposed a moving-strip bug: the strip could leave the
   ROI for roughly 500 ms, making the captured ROI identical. The producer correctly
   suppressed these duplicates, leaving a short event without a second observation. The
   final precise stimulus keeps motion inside the configured ROI; a regression test checks
   every consecutive frame across 180 ticks. Earlier failed reports remain intact.
5. Models and resize buffers were already reused, and the live ROI was already borrowed
   from an owned DXcam frame. No extra cache, worker pool or tracking framework was needed.
   The useful optimization is an explicit existing CPU configuration, with the same model:
   `--scale 1 --threads 4 --cpu-arena --no-spinning --det-limit 640`.

The alternative confirmation diagnostic uses the locally installed v4 recognition model
to read a wider crop around a baseline-detected candidate. It does not receive expected text
or create confidence values. It read 19/20 strings exactly, but only 6/20 baseline-eligible
inputs met exact agreement and the existing >=0.96 score requirement. One reading included
neighboring text; thirteen otherwise exact readings were below the threshold.
This different-model reading took about 23–37 ms but was rejected as a production shortcut.
Different models are not proof of statistically independent errors. Two fresh observations
remain required; no confidence threshold was lowered to make the diagnostic agree.

## Offline configuration comparison

`scripts/phase4_benchmark.py` runs without capture, display or clipboard access. It reuses
one warmed engine per configuration on 8 previously evaluated game screenshots and 16
new generated profile observations (8 discount, 8 game; some values shared across profiles).
Generated scenes vary values, code positions, simple/duplex fonts, moderate text sizes,
line/gradient backgrounds, JPEG compression and game hyphens. Four O/0 observations remain
in the denominator. These are synthetic diagnostics, not independent broadcast qualification.

| Configuration | Exact candidates / 24 | Wrong candidates | Abstentions | OCR pipeline p50 / p95 / worst ms |
|---|---:|---:|---:|---|
| Baseline, scale 2, threads 2, arena off, spinning on | 20 | 0 | 4 | 163.2 / 592.7 / 645.7 |
| Same scale, threads 4, arena on, spinning off (`cpu_reuse`) | 20 | 0 | 4 | 97.6 / 282.9 / 292.4 |
| Above + scale 1, detector limit 640 (`scale1`) | 20 | 0 | 4 | 66.5 / 170.4 / 226.7 |
| Above + smaller 635x115 ROI | 18 | 0 | 6 | 64.5 / 462.2 / 540.2 |
| Scale1 + grayscale | 19 | 0 | 5 | 74.1 / 180.9 / 254.3 |
| Scale1 + CLAHE | 19 | 0 | 5 | 65.3 / 290.2 / 352.9 |
| Tiny model diagnostic, scale1 settings | 18 | 0 | 6 | 29.0 / 62.7 / 62.9 |

The smaller crop and alternate preprocessing/model lost recall and are not recommended
from this evidence. The CPU configuration bundles several settings; this experiment does
not isolate each setting's individual causal contribution. Startup/warmup is separate;
model/session reuse existed in the baseline. Tiny game recognition is diagnostic only and
remains refused by the public game CLI's existing model guard.

A further frozen comparison used seed 20261120, selected after choosing the CPU settings:
8 reused screenshots plus 32 generated profile observations. Both baseline and scale1
produced **32/40 exact candidates, zero wrong candidates, 8 abstentions**. All abstentions
contained O/0. Wall p50/p95/worst was 158.1/489.4/587.9 ms for baseline versus
62.1/154.0/223.0 ms for scale1. This is additional synthetic-code evidence from the same
renderer family, not a representative real-world holdout. See `phase4-config-newseed.jsonl`.

## Comparable real-capture game replay

Same imported screenshots, legacy 760x140 ROI, RNG seed 20261102, baseline model, schedule,
confidence/confirmation/freshness limits, memory clipboard and ORT profiling in both runs.
The repeated-code and new bare-code negative events caused no writes in either run.

| Run | Correct / 8 | Wrong | Abstentions | First captured frame to memory copy p50 / p95 / worst ms |
|---|---:|---:|---:|---|
| Historical game-profile seed 20261102 | 7 | 0 | 1 | 1343.2 / 2314.3 / 2503.7 |
| Phase 4 baseline repeat | 8 | 0 | 0 | 956.1 / 1384.8 / 1416.3 |
| Phase 4 explicit CPU configuration | 8 | 0 | 0 | 501.8 / 545.3 / 561.9 |

The same-day comparison improves median by about 47.5% and p95 by about 60.6%. Historical
run-to-run variation is visible and must not be attributed entirely to the new settings.
This first baseline exploration overlapped a brief static mypy check. Final paired repeats
of both original seeds were therefore run after all automated checks, without other OCR,
tests or static checking running concurrently; see the final repeat results below.
First accepted recognition to confirmation p50/p95 fell from 392.1/611.4 to 224.8/254.3 ms.
These are eight reused slides with long exposures, not evidence of general game accuracy.

Final paired repeats after all automated checks, using the same legacy long-exposure
stimulus for each baseline/configuration pair:

| Seed | Baseline correct -> CPU correct | Wrong / abstentions (both) | Baseline p50 / p95 / worst ms | CPU p50 / p95 / worst ms |
|---|---|---|---|---|
| 20261101 | 8/8 -> 8/8 | 0 / 0 | 1072.1 / 1873.9 / 2174.7 | 492.1 / 519.8 / 521.7 |
| 20261102 | 8/8 -> 8/8 | 0 / 0 | 877.3 / 1345.6 / 1366.9 | 485.2 / 700.6 / 812.3 |

All four reports have `passed: true`, ten captured events, no repeat/negative writes and
no capture errors. Median improved 54.1% and 44.7%, respectively. The varying tail is retained,
not hidden by selecting the best run. These legacy comparisons retain the original moving
strip/pacing; gaps in distinct ROI frames can still delay confirmation. In seed 20261101
baseline, one pending sequence restarted (nine confirming observations for eight writes).
First accepted recognition to confirmation p50/p95/max was 384.7/543.0/565.1 ->
211.1/236.1/237.3 ms for seed 20261101, and 369.0/598.5/609.3 -> 219.8/479.5/579.7 ms for
seed 20261102. Earlier raw exact recognition, before a restart, can precede these timestamps.

Final seed 20261102 stages on the 16 confirming/copying observations per configuration:

| Scope | Baseline p50 / p95 ms | CPU configuration p50 / p95 ms |
|---|---|---|
| Acquisition | 1.17 / 4.97 | 1.39 / 11.74 |
| Age at processing entry | 24.87 / 70.58 | 22.71 / 60.98 |
| Preprocessing | 0.926 / 1.799 | 0.014 / 0.024 |
| OCR wall time | 445.28 / 646.20 | 214.86 / 230.23 |
| Detector ORT inference | 80.35 / 100.50 | 28.28 / 29.98 |
| Recognizer ORT inference | 330.59 / 533.85 | 166.19 / 179.31 |
| Candidate validation | 0.046 / 0.076 | 0.041 / 0.067 |
| Confirmation/dedup computation | 0.013 / 0.018 | 0.012 / 0.022 |
| Successful memory write (8 samples) | 0.014 / 0.022 | 0.010 / 0.023 |

Frame-wait p50/p95 was 30.15/31.73 vs 0.18/31.62 ms across all wait calls, including idle
waits; it is not an added per-copy cost. Capture/queue/handoff distributions, process CPU,
raw text and status traces remain in `phase4-final-game-summary.json` and the raw reports.
Capture/age, OCR/inference and confirmation elapsed scopes overlap and must not be summed.
`ocr_process_cpu` aggregates scheduled CPU across process threads during OCR (including
concurrent test/capture work), unlike elapsed wall time. No GPU timing is claimed.

## Final short-exposure results

The final matrix uses seed 20261103, four events per nominal duration, both profiles,
1-second absent drain and precise stimulus motion confined to the ROI. Both baseline and
CPU configuration captured all 16 positive events, recognized all 16 exact strings in at
least one processed frame, and had zero incorrect or negative writes. Four codes per profile
contain O/0 and intentionally abstain. These remain in all denominators. There are no
repeat events in the short matrix: a delayed first copy of a previously missed code would
not meaningfully test deduplication. Repeat qualification remains in the eight-slide tests.

| Profile/configuration | Correct / 16 | Abstentions | Successful p50 / p95 / worst ms | First raw exact recognition to copy p50 / p95 ms |
|---|---:|---:|---|---|
| Discount baseline | 10 | 6 | 425.0 / 569.4 / 632.2 | 186.7 / 203.4 |
| Discount CPU configuration | 12 | 4 | 247.2 / 281.3 / 284.1 | 97.0 / 117.1 |
| Game baseline | 10 | 6 | 449.7 / 568.7 / 637.2 | 178.6 / 210.0 |
| Game CPU configuration | 12 | 4 | 236.6 / 269.6 / 270.2 | 96.7 / 102.4 |
| Game CPU + existing 100 ms activity gate | 12 | 4 | 197.1 / 230.6 / 243.9 | 97.4 / 105.4 |

The gate can reduce OCR on irrelevant frames and reduce delay when a new neutral text shape
arrives. It remains off by default: these bright neutral fixtures do not qualify colored,
dim or arbitrary broadcast inputs. Existing tests preserve forced scans despite continuous
background motion and bypass the gate for pending confirmation. Faster gate timing here
is not a general recommendation to enable it. The final gated run skipped 782 irrelevant
frame scans. First accepted recognition to completed confirmation (excluding clipboard)
p50/p95 was 186.7/203.4 -> 97.0/117.1 ms for discount and 178.6/210.0 -> 96.7/102.3 ms
for game. The corresponding maximum delays were 206.3 -> 118.7 and 217.9 -> 103.0 ms.

Per-exposure results below compare baseline to CPU settings **without** the activity gate.
Each cell's recall denominator is four. The 1000/2000 ms groups each contain two O/0 cases.

| Nominal exposure ms | Discount exact baseline -> CPU | Game exact baseline -> CPU | Discount CPU p50 / p95 / worst ms | Game CPU p50 / p95 / worst ms |
|---:|---|---|---|---|
| 250 | 2/4 -> 4/4 | 2/4 -> 4/4 | 247.2 / 280.0 / 284.1 | 247.0 / 266.5 / 269.1 |
| 500 | 4/4 -> 4/4 | 4/4 -> 4/4 | 263.0 / 276.9 / 279.1 | 209.5 / 229.3 / 232.6 |
| 1000 | 2/4 -> 2/4 | 2/4 -> 2/4 | 216.1 / 218.4 / 218.7 | 254.3 / 268.6 / 270.2 |
| 2000 | 2/4 -> 2/4 | 2/4 -> 2/4 | 241.0 / 261.8 / 264.1 | 231.6 / 242.2 / 243.4 |

All four events at every duration were captured in each run. At 250 ms, only **1/4 discount
and 0/4 game CPU copies completed before disappearance**; all four eventually copied from
fresh pre-disappearance frames. This is not a claim that all 250 ms codes were copied within
250 ms of presentation. The baseline copied 0/4 before disappearance at 250 ms. For CPU
settings the 500/1000/2000 ms pre-disappearance counts were 4/4, 2/4 and 2/4 in both profiles.

CPU painted-exposure medians were 256.2/509.6/1010.3/2003.7 ms (discount) and
249.3/503.3/1000.3/2004.4 ms (game), in nominal-duration order. Worst durations were
261.0/516.1/1022.7/2005.8 and 252.2/508.7/1013.3/2008.6 ms. OS scheduling, painting and
capture sampling still introduce jitter; timestamps are not physical-display measurements.
Final reports retain first-capture timestamps even for missed/guarded events.

Earlier fixture failures are retained, not replaced by the final results:

- `phase4-short`: immediate disarm and legacy motion/pacing; discount 7/16 -> 11/16,
  game 8/16 -> 11/16, gate 11/16; zero wrong writes.
- `phase4-short-drain`: drain/precise pacing but motion could leave ROI; discount 9/16 ->
  12/16, game 8/16 -> 11/16, gate 12/16; zero wrong writes. One game hyphen event received
  only one unique processed ROI before disappearing. Long waits for ROI change inflated
  successful-copy tails to 1042 ms in discount and 937 ms in game.
- `phase4-short-final`: corrected stimulus; all five processes still exit **1** because
  full 16/16 recall is not reached. The four intentional O/0 abstentions alone suffice to
  fail that gate. Script exit status was not weakened to call these passes.

## Measurement and safety scope

The marker timestamps the first captured code-containing test frame before latest-slot
drops. It is scoring instrumentation, not a runtime target. First-captured-to-memory-copy
includes confirmation and dropped-frame delay. Model warmup and baseline collection precede
exposure and are excluded. Primary event latency is separate from pipeline
`first_recognition_to_confirmation`, which begins at completion of the first accepted OCR
observation. Reports also retain first raw exact recognition to clipboard for diagnosis.
Latency percentiles include successful writes only; every miss remains in recall counts.

New production instrumentation adds `recognized_ns`, `control_check`, `candidate_validation`,
`confirmation_dedup` and `first_recognition_to_confirmation`. Candidate detection is still
real OCR localization. Validation timing measures actual pattern/context computation;
confirmation timing distinguishes CPU work from elapsed waiting plus repeated OCR.
`scripts/analyze_playback.py` extracts stages, status counts, misses and exposure results
from completed reports without opening any display or clipboard.

The short-exposure harness records capture, raw exact recognition, copies before disappearance,
all valid copies, O/0 cases, abstentions and measured painted duration per nominal exposure.
Every positive stays in the denominator; intentional O/0 rejection is not relabelled success.
Repeated identical glyphs in a changing slide are not independent evidence against systematic
OCR errors. Source-resolution and O/0 guards remain necessary and are not exactness proofs.

## Reproduction

Run from the repository in PowerShell. Use new artifact paths; reports refuse overwrite.
Ordinary checks and offline diagnostics open no windows and never use the native clipboard.

```powershell
./.venv/Scripts/python.exe scripts/phase4_benchmark.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --report artifacts/phase4-config-matrix.jsonl
./.venv/Scripts/python.exe scripts/phase4_benchmark.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --seed 20261120 --count 16 --configs baseline scale1 --report artifacts/phase4-config-newseed.jsonl
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --seed 20261102 --profile-inference --report artifacts/phase4-game-baseline.jsonl
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --seed 20261102 --scale 1 --threads 4 --cpu-arena --no-spinning --det-limit 640 --profile-inference --report artifacts/phase4-game-cpu.jsonl > artifacts/phase4-game-cpu-console.txt
# Legacy short-exposure comparison; immediate disarm at disappearance:
./scripts/phase4_playback.ps1 -ShowPlayback -OutputDirectory artifacts/phase4-short -Count 4 -Seed 20261103 -WithActivityGate
# Corrected stimulus; same guard limits, absent drain interval, measured 60 Hz pacing:
./scripts/phase4_playback.ps1 -ShowPlayback -OutputDirectory artifacts/phase4-short-drain -Count 4 -Seed 20261103 -WithActivityGate -DrainMs 1000 -PreciseStimulus
# Final short-exposure matrix after fixing the stimulus motion leaving the ROI:
./scripts/phase4_playback.ps1 -ShowPlayback -OutputDirectory artifacts/phase4-short-final -Count 4 -Seed 20261103 -WithActivityGate -DrainMs 1000 -PreciseStimulus
# Final original-seed pairs, sequential and after all automated checks:
./artifacts/phase4-compare-games.ps1 -ShowPlayback
./.venv/Scripts/python.exe scripts/analyze_playback.py artifacts/phase4-game-20261101-baseline.jsonl artifacts/phase4-game-20261101-cpu.jsonl artifacts/phase4-game-20261102-baseline.jsonl artifacts/phase4-game-20261102-cpu.jsonl --output artifacts/phase4-final-game-summary.json
```

`phase4_playback.ps1` refuses to launch without `-ShowPlayback`. It invokes and prints each
explicit Python command sequentially; there is no concurrent benchmark load or native
clipboard option. It keeps all reports and exits nonzero if any run lacks full recall,
including intentional O/0 abstentions. A full-recall failure is not silently converted to
a pass. The display area `(50,50)` to `(1010,590)` on the primary output must be unobscured.

For an explicitly selected dry-run CPU experiment on a real permitted stream:

```powershell
./.venv/Scripts/python.exe -m stream_code_capture live --profile game --roi 300 250 1060 390 --dry-run --scale 1 --threads 4 --cpu-arena --no-spinning --det-limit 640 --profile-inference --report artifacts/manual-phase4-stream.jsonl
```

Replace the illustrative coordinates with the actual code/context ROI. Select `discount`
for the original profile. Enter `start`, wait for `ready`, then `arm`; rearm explicitly after
each copy. Disarm before moving the source. This does not promote the configuration to a
production default. Native writes still require explicit `--clipboard windows` and arming;
none were performed here. Follow WINDOWS_VALIDATION for manual paste, 30 native events,
contention, negative soak and display-loss/DPI/monitor tests rather than inferring passes.

## Automated checks and changed files

Executed after all source/harness changes:

```powershell
./scripts/check.ps1 -Ocr *> artifacts/phase4-check-ocr.txt
./scripts/check.ps1 *> artifacts/phase4-check.txt
./scripts/phase4_playback.ps1
```

The first two commands exited 0. Pip dependency checks, Ruff lint/format (57 files), and
strict mypy (16 source modules) passed. OCR-inclusive pytest: **108 passed, 3 xfailed in
29.17 s**. Standard headless pytest: **100 passed, 11 expected OCR skips in 4.21 s**. The
three original tiny compressed O/0 exact-recall xfails remain strict and unresolved. Four
new unit tests cover elapsed confirmation timing, stale-evidence rejection, reproducible
varied fixtures and motion remaining inside the ROI. No test opens a display or OS clipboard.
The last command deliberately omitted `-ShowPlayback` and exited 1 before opening any
window, confirming the explicit test-driver guard. Initial Ruff help-string length errors
were fixed; no test assertion, confidence threshold or guard was relaxed.

Changed runtime files: `src/stream_code_capture/policy.py` and `pipeline.py` (timing only).
Extended `scripts/game_playback.py` with OCR flags, profile selection, generated exposures,
optional drain/precise stimulus and scoring. Added `scripts/phase4_scenes.py`,
`phase4_benchmark.py`, `phase4_playback.ps1`, `analyze_playback.py`, and `tests/test_phase4.py`.
Updated README, PROJECT_SPEC, WINDOWS_VALIDATION and this record. The original source tree
was already untracked; git status must not be interpreted as all files newly created here.
Imported images/labels, prior benchmark artifacts, model hashes/pins and other user work
were preserved. Capture, latest-frame handoff, OCR implementation and native clipboard
adapter were not changed.

## Limits and next gate

Representative independently labelled broadcast recordings remain unavailable. The eight
previously evaluated images are reused compatibility checks; the new varied scenes are
synthetic. O/0 rejection sacrifices valid-code recall; small/slanted/compressed chart text
and all three original strict challenge xfails remain unresolved. Zero wrong writes in a
small fixture sample does not establish zero false positives in the wild.

Continue targeted recognition/latency qualification rather than start GUI development.
The measured CPU configuration is a useful opt-in baseline for new data. Next obtain unseen
labelled short clips for both profiles, compare the exact same captured ROI/exposures, then
evaluate reducing recognition of irrelevant lines while preserving fresh context and
multi-candidate rejection. Do not infer safety from a single fast reading. Complete G2's
native clipboard/negative-soak/display matrix; G2 still gates GUI and G3 still gates accuracy
and latency claims. No automatic redemption or submission belongs in this workflow.
