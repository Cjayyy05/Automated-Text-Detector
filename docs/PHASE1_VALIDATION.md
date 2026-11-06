# Phase 1 — live functional integration validation

Dates: 2026-10-29–30 (Asia/Kuala_Lumpur). This extends the foundation record in `VALIDATION.md`.
Same Windows 11 / Python 3.12.14 CPU environment and pinned models/dependencies. No
dependency changes, GUI application, packaging, commit or push. The native test intentionally
left the final generated test code in the Windows clipboard.

## Result and remaining gates

**Functional path verified:** real visible chart pixels -> DXcam -> capacity-one handoff ->
warmed local RapidOCR -> baseline/context/exact-agreement policy -> native pywin32 clipboard.
Three native writes matched their generated targets and CF_UNICODETEXT readbacks exactly.
A separate 30-event dry-run with another seed matched all 30 codes and did not use the OS
clipboard. These tests use moving on-screen generated charts, not mocked capture or direct
file input to the recognizer. JORDY and unrelated chat remain outside the configurable chart
ROI. Runtime has no target-code string or banner-specific denylist.

**Full G2 qualification is not complete:** 30 native/manual-paste cases, 30-minute negative
soak, actual clipboard contention and the lock/hotplug/DPI/occlusion matrix remain manual.
**G3 fails:** challenge exact-code recall is unresolved and measured latency is far above
100 ms. Functional tests display each code until accepted; they do not prove capture of
100 ms appearances. Do not interpret test process exit 0 as production accuracy readiness.

## Changes

- `capture.py`: one DXGI owner thread, monitor-relative configurable ROI, BGR owned copies,
  no reused cached frames, identical ROI suppression, acquisition timing and source errors.
- `live.py`: explicit start/stop and arm/disarm, dry-run by default, stable >=500 ms baseline,
  continued disarmed suppression, bounded commands, deadline/source-health write guards,
  one-shot native copying and clean shutdown. Stop/disarm also gate in-flight OCR results.
- `metrics.py`: bounded rolling p50/p95/max/sample counts, no unbounded sample history.
- `domain.py`, `ocr.py`, `pipeline.py`, `policy.py`: capture metadata, separately measured
  preprocessing/OCR/substages/policy/clipboard, absolute event timestamps, quality rejection,
  and first-eligible-observation-to-result timing. Existing small interfaces are retained.
- `cli.py`: live console command, device/output/FPS/ROI controls, dry-run/native switch,
  bounded duration and optional exclusive-create JSONL report. No GUI controls added.
- `scripts/investigate.py`: reproducible scale/ROI timing and challenge diagnostics.
- `scripts/live_smoke.py`: opt-in visible test stimulus, actual screen capture and optional
  native readback, with a test-only marker to timestamp the first captured code frame even
  when it is dropped before OCR. This is a validation harness, not an application GUI.
- Tests: live controls/handoff/baseline/failures, native adapter contract with mocked OS calls,
  and explicit challenge safety/recall regressions. Documentation updated for actual commands.

## Commands and results

All commands run from repository root. Files under `artifacts/` are local and git-ignored.

| Command | Result |
|---|---|
| `./.venv/Scripts/python.exe -m stream_code_capture replay samples/challenge/manifest.json --arm > artifacts/phase1-challenge-before.json` | Exit 1: reproduced 2 misses + 1 incorrect accepted O/0 code before mitigation |
| `./.venv/Scripts/python.exe scripts/investigate.py samples/challenge/manifest.json --scales 1 2 3 --repeats 2 > artifacts/phase1-investigation.json` | Exit 0 diagnostic; all three scales retained incorrect transcriptions. Run before source-quality guard was added; reproduce raw behavior now with `--raw` |
| DXcam `create(output_color='BGR')` then `grab(region=(0,0,160,120), copy=True, new_frame_only=True)` probe | Sandbox: COM access denied. Desktop-enabled rerun: real `(120,160,3)` pixels; one cold capture call 86.397 ms, not a steady-state measurement |
| `./.venv/Scripts/python.exe scripts/investigate.py samples/smoke/manifest.json --scales 1 2 --repeats 5 --roi 70 160 610 325 > artifacts/phase1-small-roi.json` | Exit 0; 15 measured calls per scale; detailed figures below |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --report artifacts/phase1-live-dry.jsonl` | Exit 0: 3/3 exact memory decisions from real capture; initial dry-run before duplicate ROI filtering |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --report artifacts/phase1-live-native.jsonl` | Exit 1: app write succeeded, but immediate test readback hit OpenClipboard access denied |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --report artifacts/phase1-live-native-retry.jsonl` | Exit 0: 3/3 exact native writes/readbacks after bounded **readback-only** retry; no app write retries |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --count 30 --seed 31 --report artifacts/phase1-live-30-dry.jsonl` | Exit 0: 30/30 exact dry-run events; no native writes; new varied codes/positions |
| `./.venv/Scripts/python.exe -m stream_code_capture replay samples/challenge/manifest.json --arm > artifacts/phase1-challenge-after.json` | Exit 1: all 3 challenge positives abstain; zero wrong copies; negative-only case passes |
| `./.venv/Scripts/python.exe -m stream_code_capture live --help` | Exit 0; live arguments/controls documented |
| `./scripts/check.ps1 -Ocr` | Final exit 0: pip check clean, Ruff lint/format clean, strict mypy clean (13 modules); **54 passed, 3 strict expected failures**, 30.26 s |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --count 1 --report artifacts/phase1-live-final-dry.jsonl` | Exit 1: no frames before startup was incorrectly counted against running stall timeout; zero writes |
| `./.venv/Scripts/python.exe scripts/live_smoke.py --count 1 --report artifacts/phase1-live-final-dry-retry.jsonl` | Exit 0 after startup timer fix: exact dry-run event, initialization 2116.155 ms, first-captured event latency 824.608 ms |

The three expected failures are `test_challenge_exact_recall_release_gate[0..2]`. They are
visible release blockers, not successful accuracy tests. Strict expected-failure mode makes
unexpected recovery fail the test run until the regression expectation is reviewed. The
original standard real-OCR integration still passes. Default tests require no display and
do not touch the clipboard; the actual screen/clipboard harness is always opt-in.

## Challenge investigation

At the original 2x scale, before the quality guard:

| Case | Ground truth | OCR text / score | Cause |
|---|---|---|---|
| 0 | Y2SSO9KFJJ | Y2SS09KFJJ / 0.95512 | O misread as zero; score below 0.96. Nearby discount text was also corrupted (`100%offT`) |
| 1 | N02OD01OXK | N020D010XK / 0.94025 | Multiple O/0 substitutions; below confidence requirement |
| 2 | 6428IT02OE | 6428IT020E / 0.99655 | High-confidence correlated error passed repeated agreement |

At scales 1 and 3, case 2 still reads `6428IT020E` (scores 0.99455 / 0.99224). Case 1 at
3x recovers one O but remains wrong. No scale recovers all exact strings. Lowering confidence
would admit additional incorrect strings; repeated or multi-scale agreement is not proof.

Mitigation: OCR marks code-like detections with <10 original pixels/character of top-edge
pitch `insufficient_source_resolution`. Policy abstains regardless of confidence while
retaining exact observed text. All three challenge cases are undersampled and now abstain.
This is a conservative support restriction, **not an O/0 fix or a universally calibrated
threshold**. Its threshold is not inferred from confidence, and no O/0 replacement is done.
Standard fixtures still pass, but held-out real-video precision/recall is not established.
The fixture generator, expected truth and confidence threshold were not changed.

## Timing measurements

All milliseconds; CPU, two ORT threads. Same warmed engine reused. Source model hashes
are unchanged from `VALIDATION.md`. Small image ROI is 540x165 source pixels. Percentiles
below are descriptive for these small runs, not performance guarantees.

| Offline small-ROI stage | 1x p50 / p95 (15 calls) | 2x p50 / p95 (15 calls) |
|---|---:|---:|
| Preprocess | 0.046 / 0.131 | 0.860 / 1.026 |
| OCR total | 145.180 / 184.821 | 234.817 / 289.846 |
| Detection | 45.173 / 53.633 | 141.976 / 170.681 |
| Text recognition | 98.559 / 132.060 | 91.500 / 119.239 |

Both small-ROI settings produce accepted candidates for only 2/3 static positive probes;
moving live frames eventually produced all three. A faster scale is not automatically a
better accuracy setting, so the default was not silently changed. Full-chart challenge
at 2x had OCR p50 1088.787 ms, detection p50 347.268 ms and text recognition p50 737.546 ms.
**Largest bottleneck is OCR**: text recognition dominates a full chart with many number
lines; at 2x small ROI, detection is the largest individual substage. Capture, preprocessing,
policy and clipboard are much smaller. Context/OCR misses add event-level delay beyond
two inference calls. Next optimizations must benchmark detector resolution/model choice
and targeted recognition crops while preserving exact-code accuracy.

Native live run, 40 processed frames, 3 successful clipboard writes:

| Stage/metric | p50 ms | p95 ms |
|---|---:|---:|
| Capture call | 1.232 | 8.968 |
| Handoff age | 31.321 | 62.427 |
| Crop | 0.041 | 0.102 |
| Preprocess | 0.756 | 0.915 |
| OCR total | 152.495 | 321.584 |
| Policy | 0.016 | 0.058 |
| Native clipboard transaction | 0.222 | 0.246 |
| Per-frame process | 153.606 | 323.188 |
| Capture-call-start to that frame's result | 198.601 | 366.344 |
| First eligible OCR-observed frame to clipboard (lower bound) | 675.383 | 685.806 |
| **First captured code frame to clipboard, including dropped frames** | **1025.292** | **1798.563** |

Actual native event totals: **675.380, 1025.292, 1884.482 ms**. Earlier rejected/dropped
code frames make the true total much worse than the generic observed-candidate lower bound.
This is why the latter is never substituted for the target metric.

The separate 30-event dry-run measured first captured code frame to **memory decision**:
p50 **695.397 ms**, p95 **1749.956 ms**, max **2027.719 ms**. Its per-frame process p50/p95:
**159.043 / 320.594 ms** (477 processed frames). It published 1484 unique ROI frames,
discarded 830 identical captures and replaced 1002 pending frames. No FIFO backlog formed.
The negative/blank intervals in the live runs make frame-level OCR medians lower than the
all-positive offline benchmark; do not compare them as like-for-like speed improvements.

Generic session metrics retain the last 10000 samples per stage. RapidOCR omits substage
timings on some no-text results; detection/recognition sample counts are therefore smaller
and explicitly reported. Total OCR wall time is recorded for every processed frame.
Clipboard timing is sampled only when a write is attempted, not padded with disarmed zeros.

The test marker is checked on **all real capture reads before the newest-frame handoff**;
its first capture timestamp is retained even if OCR drops that frame. It never supplies
the recognition target. Normal arbitrary livestreams do not have this marker, so the
generic log exposes only observed-candidate latency. The harness's separate draw timestamp
was found to have a cross-thread bookkeeping race between events and has been guarded;
the first-captured marker measurements above do not use that draw timestamp.

## Unverified Windows behavior and readiness

Final verification fixed a cold-start timeout bug: camera initialization now has a bounded
10-second allowance; the 2.5-second running-source timeout starts after initialization.
This is covered by a new regression test and the final one-event real-screen dry-run.
Initialization duration is now reported separately and excluded from warmed event latency.

- Actual lock/unlock, hotplug, multi-monitor ROI/DPI matrix, HDR/rotation and source occlusion.
- Actual locked-clipboard write failure (mocked transaction/propagation tests pass; transient
  readback lock occurred live). No automatic retry of failed writes.
- 30-minute negative-only soak and real livestream corpus/short appearance durations.
- Manual paste/redemption outcome; only CF_UNICODETEXT readback was automated. No redemption.
- GPU performance/accuracy. Available CPU provider remains the only validated backend.
- Automatic window identity tracking: the ROI is fixed desktop pixels. Moving or obscuring
  the video may expose unrelated pixels, and a nonblank change cannot always be detected
  as source loss. User must disarm before such changes.

See `WINDOWS_VALIDATION.md` for exact commands and expected outcomes for each manual check.
Ready for the remaining G2 qualification and focused OCR/performance work; not ready for
deployment, tiny-code accuracy claims, <100 ms claims or extensive GUI development.

## Files changed this phase

Modified: `README.md`, `docs/PROJECT_SPEC.md`, `docs/VALIDATION.md`,
`docs/WINDOWS_VALIDATION.md`, `src/stream_code_capture/domain.py`, `ocr.py`, `pipeline.py`,
`policy.py`, `cli.py`.

Added: `docs/PHASE1_VALIDATION.md`, `src/stream_code_capture/capture.py`, `live.py`,
`metrics.py`, `scripts/investigate.py`, `scripts/live_smoke.py`,
`tests/test_live.py`, `tests/test_clipboard_adapter.py`, `tests/test_challenge_regression.py`.

Existing foundation tests, generator, latest-slot implementation, native clipboard adapter,
dependency pins, setup scripts and AGENTS rules were preserved.
