# Phase 2 — latency and exact-copy investigation

Date: 2026-10-30, Asia/Kuala_Lumpur. Windows 11, Python 3.12.14, existing pinned
RapidOCR 3.10.0 / ONNX Runtime 1.31.1 / DXcam 0.3.0 / pywin32 312 environment.
CPU: AMD Ryzen 5 5600H with Radeon Graphics, 12 logical processors; Windows build
10.0.26200. Available ORT providers were AzureExecutionProvider and CPUExecutionProvider;
all measurements used CPUExecutionProvider. CIM hardware lookup was denied; the processor
name was read from the Windows hardware registry and logical count from .NET instead.
No dependency upgrades, application GUI, packaging, commit or push. Benchmark models
are explicitly provisioned locally; inference remains offline. See the historical
[Phase 1 record](PHASE1_VALIDATION.md) for the prior measurements and unfinished G2 matrix.

The measurements and commands below describe the Phase 2 source revision. Develop now
uses a single observation and accepts O/0. For current reproduction and observed
incorrect copies, see [detection policy validation](DETECTION_POLICY_VALIDATION.md).

## Decision

**The Phase 2 acceptance gate fails.** Faster local inference is demonstrated, but the
100 ms first-captured-code-frame-to-correct-native-copy target is not established and
exact-code recall remains inadequate. All three original strict challenge xfails remain.
The original `baseline` model profile remains the default. The tiny/cascade and activity
gate modes are opt-in experiments. Native smoke success is not production qualification.

**Final implementation adds independent candidate verification.** A fresh holdout exposed
a fast-model leading-glyph deletion after the initial speed experiments. With
`--fallback-baseline`, an eligible fast candidate now needs exact agreement from the baseline
recognizer on a wider pixel crop before policy sees it. Disagreement vetoes, without replacing
the fast text or inventing a score. `verification_text` and `verification_confidence` are raw
second-model evidence. Tiny-only/v4 native copying is refused by the public CLI. Earlier
cascade timings below are explicitly pre-verification; final timing results are recorded
at the end. The safest measured default remains the guarded baseline, not the fast profile.

**New safety behavior:** any code-like recognition containing O or zero abstains with
`unresolved_O0_glyph`, unless already rejected by the source-resolution floor. There is
no substitution, target-code dictionary, spelling correction or invented confidence.
This deliberately rejects correctly recognized codes containing these characters too.
The public image/replay/live CLI has no bypass; diagnostic Python scripts can compare
the old behavior using a memory clipboard only. Other character confusions remain possible.

## Profiling before optimization

`scripts/profile_phase2.py samples/smoke/manifest.json` ran the original implementation
before behavior changes, over the 540 x 165 ROI, with five calls per case (three positive,
one negative), after warmup. `artifacts/phase2-profile-before.json` contains the records.
This mixed positive/negative workload differs from Phase 1's 15 positive-call benchmark.

| Measurement | p50 ms | p95 ms | Worst ms | Samples |
|---|---:|---:|---:|---:|
| Original recognition wall | 193.70 | 270.61 | 311.36 | 20 |
| Actual ORT detector `run` | 102.29 | 124.78 | 162.17 | 20 |
| Actual ORT recognizer `run` | 70.01 | 121.95 | 130.43 | 15 |
| External preprocessing | 0.70 | 1.09 | 1.46 | 20 |
| Aggregate process CPU | 453.13 | 616.41 | 750.00 | 20 |

The detector was the largest verified computation bottleneck on this small ROI. In the
historical full chart ROI, recognizing many unrelated text lines was also expensive.
CPU time can exceed wall time because it adds scheduled CPU across ONNX worker threads;
it is not a measurement of elapsed latency. No GPU inference measurement is available.

A fresh three-event live baseline (seed 31) with detailed instrumentation measured
639.74 / 657.73 / 659.72 ms first-capture-to-memory-copy (p50 / p95 / worst). Its capture
read p50 was 2.08 ms, handoff 33.72 ms, preprocessing 0.45 ms, policy 0.014 ms, and memory
write 0.017 ms. Thus tiny crop/write optimizations could not explain or fix the delay.
This baseline already included borrowed live ROI views and the publication notification;
do not attribute its improvement over Phase 1 solely to those small changes.

## Timing definitions and coverage

All elapsed timestamps use `perf_counter_ns`, never civil wall-clock timestamps.

- `capture_read`: actual DXcam grab call, including native wait/copy. Captured frames use
  the call start as their conservative timestamp. It is not a compositor presentation timestamp.
- `capture_filter_publish`: duplicate comparison and publication. Capture history is bounded.
- `capture_idle_wait`: actual producer pacing wait. `capture_thread_cpu` measures the producer
  thread's scheduled CPU, excluding time asleep and other threads; Windows resolution is coarse.
- `frame_wait`: consumer wait for publication; includes timeout samples with no frame. It does
  not belong in a per-frame additive sum. Publication wakes the consumer immediately.
- `handoff`: delivery to processing start. `queue_age` is capture-call start to processing
  start, so includes acquisition and handoff. There is still only one pending frame.
- Final reports additionally separate `queue_wait` (delivery to dequeue),
  `frame_age_at_dequeue`, and live `input_validation` (age/blank-image checks). Legacy
  `handoff` includes this validation and optional activity work before Pipeline starts;
  do not call it exclusive queue waiting. Native final reports contain these fields.
- `crop`, `preprocess`, `ocr`, `policy` and `clipboard`: separately timed elapsed stages.
  `ocr` includes RapidOCR preprocessing, localization, line crops, inference and decoding.
  `--profile-inference` additionally measures `text_det_inference` and `text_rec_inference`
  around actual ORT calls. `detection` / `text_recognition` are broader library stages.
- `ocr_process_cpu`: process CPU while recognition runs, including concurrent capture/test
  threads in live runs. It is not exclusive inference computation; do not add it to wall time.
- `frame_to_result`: age of the processed frame at completion. `first_observed_to_clipboard`
  starts at the first eligible OCR-observed frame; both exclude earlier dropped/missed frames.
- The **live smoke marker** observes the first real captured target frame even when the
  handoff drops it. Only `test_result.timings.first_captured_to_clipboard` reports that event
  interval. Expected strings/marker IDs are scoring instrumentation, never recognition inputs.
- Replay timings are sequential file processing, not capture-to-copy latency. Baseline/warmup
  are excluded from hot-path distributions. Percentiles include sample counts and maxima;
  medians of different stages are not additive. A fallback sums inference stages and separately
  exposes `fast_path` and `fallback` wall time, without manufacturing zero samples.

## Model, input and ONNX configuration experiments

The initial matrix used eight fixed images (standard three positives + one negative,
challenge three positives + one negative), two repetitions each. Existing quality thresholds
were retained. Candidate accuracy was 2/6 positive exact candidates for most configurations;
these snapshots are not the moving-video event recall. All three tiny compressed challenges
abstained. The v4 2x/960 configuration found the third standard case but fixed no challenge.

| Configuration | p50 ms | p95 ms | Worst ms |
|---|---:|---:|---:|
| Baseline, 2x, detector limit 960, 2 threads | 184.89 | 214.11 | 271.47 |
| Baseline, 1x, limit 640, 2 threads | 106.79 | 143.70 | 156.66 |
| Tiny, 1x, limit 640, 2 threads | 36.54 | 45.42 | 51.20 |
| Tiny, 2x, limit 960, 2 threads | 78.32 | 103.25 | 118.23 |
| V4 English mobile, 2x, limit 960, 2 threads | 176.22 | 367.05 | 415.19 |
| Tiny, 1x, limit 640, arena on, 4 threads (40 calls) | 29.98 | 36.62 | 37.55 |
| Same tiny, worker spinning disabled (40 calls) | 32.73 | 54.44 | 56.33 |

One/two/four threads and none/grayscale/CLAHE preprocessing were evaluated separately.
At two threads, grayscale/CLAHE did not improve exact recall; their medians were 39.11 /
36.83 ms versus 38.30 ms for unchanged BGR. One thread was slower (44.31 ms); four threads
without arena were inconsistent (48.21 ms BGR). Keep BGR; do not assume more threads win.
Arena with four threads gave the best initial small-model median/tail. Spinning disabled
was not faster for the single engine, but mattered when keeping the fallback engine warm.

The fallback is narrowly triggered: fast OCR has localized text, no usable candidate, and
no quality-rejected code line. Empty fast output does not trigger a slow full scan. Quality
rejections are never overridden. On the 54-case varied snapshot, tiny + fallback recovered
16 exact candidates versus 9 for tiny alone after the O/0 guard. No wrong candidate remained
in that sample. With spinning disabled, cascade wall p50/p95/max was 34.70/244.69/330.73 ms.
An earlier spinning-on exploratory run had a 712.91 ms p95 (also overlapped development
checks); treat it as diagnostic, not an isolated causal estimate. Keep `--no-spinning` in
the documented cascade command. The slow fallback remains a tail-latency cost.

Model sessions are created once, warmed and reused. The recognizer's metadata-check session
is reused for inference rather than loaded twice. CPU arena, sequential execution and thread
counts are explicit; ORT spinning is benchable. Scale 1 avoids a resize allocation; other
scales reuse a destination buffer. Live uses a view into an owned captured ROI; the adapter
does not mutate input pixels. Offline callers retain copy-by-default semantics.

## Accuracy, challenge investigation and templates

The frozen varied corpus uses seed 20261030: 48 new full-alphabet codes, six negative events,
five frames per event. It spans standard/strong JPEG compression/small blurred text/large
duplex font/serif font/dim contrast, angles to +/-6 degrees, moving candles and unrelated
banner/chat. Sizes, strings and expected values are fixture metadata only. It is synthetic,
not a representative licensed broadcast corpus; tuning and subsequent scoring on it are not
an independent release holdout.

| Full two-observation memory policy replay | Exact copies / 48 | Incorrect writes | Abstentions | Process p50 / p95 / max ms |
|---|---:|---:|---:|---|
| Phase 1 policy/model behavior | 27 | 8 | 13 | 190.28 / 288.65 / 342.50 |
| Baseline with explicit O/0 abstention | 16 | 0 | 32 | 203.28 / 231.14 / 281.24 |
| Tiny + baseline fallback + O/0 abstention | 16 | 0 | 32 | 32.58 / 241.45 / 320.45 |

The cascade copied the **same 16 cases** as the guarded baseline, not just the same count.
All six negative events remained empty. O/0 safety sacrifices 11 previously correct copies
to remove eight wrong writes; it must not be described as an exact-recall fix. The old-policy
comparison is available only through `evaluate_replay.py --profile phase1-policy` using
`MemoryClipboard`. Default runtime safeguards cannot be bypassed by CLI fallback selection.

Original seed-19 challenge diagnoses remain:

1. Tiny slanted compressed code has O/0 corruption plus broken/missing promotional context;
   no eligible candidate. Larger upsampling cannot restore the lost source pixels.
2. Multiple O/0 substitutions and sometimes incomplete context; mean line confidence and
   repeated agreement do not establish exactness.
3. The original dangerous case produces a wrong final O/0 character at ~0.9966 confidence;
   the source-resolution guard still prevents copying. The new larger-font regressions show
   that a source-pitch floor alone is insufficient for other inputs.

No example string or banner value is hardcoded into runtime. Strict xfails for all three
original exact-recall gates stay intact. The safety tests remain separate passing checks.

`benchmark_templates.py` measures actual normalized cross correlation of rendered generic
font templates against OCR-localized pixels. O/0 alternatives are generated from OCR text,
never expected values. It selected the correct string in 17/22 cases; all five wrong selections
were in the different duplex style. Search p50/p95/max: 58.79/122.54/259.25 ms. This is neither
fast enough nor font-independent enough for automatic copying. NCC is not a probability.
The template experiment remains a diagnostic script; no template score enters the policy.

## Frame scheduling changes

Already-stale/future frames are rejected before OCR and pending confirmation is cleared.
The post-OCR age check still applies. A condition notification replaces the consumer's 5 ms
polling; capacity remains one, with overwritten frames counted, not queued. Windows producer
pacing uses Python 3.12's high-resolution sleep in <=20 ms stop-check chunks. An isolated
40-sample 10 ms wait probe measured Event.wait p50/p95/max 15.46/16.25/20.96 ms versus sleep
10.31/10.55/10.74 ms. No global timer-resolution or process-priority changes are made.

The optional activity hint compares bright neutral strokes, allowing colored candle motion
to skip OCR between forced scans. Its deadline is based on the last **scan**, never reset by
skipped motion. A new neutral stroke or pending confirmation bypasses it. Colored/dim text
may wait for a deadline, so it remains disabled by default. It is a scheduling hint, not a
recognition-confidence signal. Unit tests cover continuous motion and bounded rescanning.

## API and provenance checks

Installed package sources verified RapidOCR's Enum parameters, custom `OrtInferSession`
support, its metadata dictionary path, lazy models, and ORT `run` calls. Optional downloads
use the registry shipped in pinned RapidOCR 3.10.0, validate every SHA256, refuse mismatched
cached models and write `models/provenance.json`.

| File | Bytes | SHA256 |
|---|---:|---|
| PP-OCRv6_det_tiny.onnx | 1829618 | f42c0fbd294d95eac1a550e131b277dac97462c8025fa4b6c3cec1b7894bd3d5 |
| PP-OCRv6_rec_tiny.onnx | 4489813 | e16e242de5937ad92609223f19bc2aff3727ee40b095f996907c24749bad251b |
| ch_PP-OCRv4_det_mobile.onnx | 4745517 | d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9 |
| en_PP-OCRv4_rec_mobile.onnx | 7653044 | e8770c967605983d1570cdf5352041dfb68fa0c21664f49f47b155abd3e0e318 |

Primary references checked: [RapidOCR model routes](https://rapidai.github.io/RapidOCRDocs/main/en/model_list/),
[model provenance policy](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/),
[ORT threading controls](https://onnxruntime.ai/docs/performance/tune-performance/threading.html),
and [Python 3.12 Windows sleep](https://docs.python.org/3.12/library/time.html#time.sleep).
Only CPU inference was measured; CUDA/DirectML availability still fails explicitly when absent.

## Files changed

- Runtime: `ocr.py`, `cli.py`, `capture.py`, `latest.py`, `live.py`, `pipeline.py`, `domain.py`;
  new small `activity.py` scheduling hint. Existing clipboard/policy contracts retained.
- Fixtures/tests: extended `synthetic.py` optional styles; `test_pipeline.py` gives its
  inference-failure case a fresh timestamp; new `test_phase2.py` tests the new safety and
  scheduling behavior, real local tiny model, no network, and borrowed-input immutability.
- Scripts: new `profile_phase2.py`, `provision_models.py`, `benchmark_ocr.py`,
  `benchmark_templates.py`, `generate_varied.py`, `evaluate_replay.py`; extended
  `benchmark_verification.py` padded-crop evidence, `investigate.py` raw diagnostics and
  `live_smoke.py` configurable OCR/finite exposure.
- Documentation: README, AGENTS, this record, PROJECT_SPEC and WINDOWS_VALIDATION.
- Dependency pins and lock file unchanged. Samples, downloaded models and raw reports are
  git-ignored local artifacts. Existing files were inspected; no user artifact was deleted.

## Validation status

The initial `./scripts/check.ps1 -Ocr` passed with 67 tests and three expected failures.
After the final verification/regression changes it passes again: pip check clean, Ruff
lint/format clean for 39 Python files, strict mypy clean for 14 source modules,
**71 passed and 3 expected failures** in 32.64 s. The expected failures
are the unchanged three exact-recall challenge gates. Models are blocked from network access
inside the real-OCR integration tests. No unit test captures the display or writes the OS clipboard.

The display-free default check `./scripts/check.ps1` also passed: **64 passed, 10 opt-in OCR
tests skipped**, in 2.41 s, with pip/Ruff/strict mypy passing. Optional-model integration tests
skip explicitly when the setup-only tiny models are absent; the verified run had them installed.

Intermediate issues fixed: model selection requires RapidOCR Enum values rather than strings;
OpenCV resize typing needed an explicit uint8 view; Ruff formatting/import findings were fixed.
An initial no-spinning command had an accidental space in the report filename and failed
argument parsing before executing any recognition. Interrupted output collection was rerun
and saved to `artifacts/phase2-checks.txt`; no pass was inferred from a lost process session.
The final check initially stopped on a nested-if Ruff warning; it was fixed, and the full
passing run is saved in `artifacts/phase2-final-checks-retry.txt`. Failed documentation patch
attempts matched no context and changed no files; the corrected patches were applied.

Live final comparisons, exact reproduction commands and remaining manual gates follow below.

## Real Windows comparison before independent candidate verification

All following tests used actual DXcam pixels from the visible moving-chart test surface,
owned frames, the production policy and either memory or native clipboard. They did not
inject fixture images into OCR. Warmup/acquisition initialization is separate. The historical
test-surface loop includes rendering plus a 1/30-second Event.wait, so actual source cadence
can be slower than 30 FPS; a captured-frame-to-copy measurement does not measure display onset.

| Test | Exact / events | Wrong writes | Abstentions | First-capture-to-copy p50 / p95 / worst ms |
|---|---:|---:|---:|---|
| Phase 1 dry-run, seed 31 | 30/30 | 0 | 0 | 695.40 / 1749.96 / 2027.72 |
| Phase 2 cascade dry-run, seed 31 | 30/30 | 0 | 0 | 133.45 / 963.50 / 1222.35 |
| Phase 1 native/readback, seed 7 | 3/3 | 0 | 0 | 1025.29 / 1798.56 / 1884.48 |
| Phase 2 native/readback, seed 7 | 3/3 | 0 | 0 | 120.63 / 893.90 / 979.82 |
| Fresh baseline dry-run, seed 31 | 3/3 | 0 | 0 | 639.74 / 657.73 / 659.72 |
| Tiny-only exploratory dry-run, coarse pacing, seed 31 | 3/3 | 0 | 0 | 233.47 / 313.09 / 321.94 |
| Final cascade dry-run, seed 31 | 3/3 | 0 | 0 | 116.86 / 117.21 / 117.25 |

The native run intentionally left the final generated test code in the OS clipboard.
Its Unicode readbacks all matched. This is measured native behavior on this PC, not an
inference from mocked clipboard tests. The native sample remains too small for qualification.
Timing comparisons include ordinary system/load variation and are not isolated causal
estimates for every individual code change. The 30-event tail is much worse than the easy
three-event sample; report both, never select only the fastest subset.

These cascade results precede the independent verification change. The subsequent holdout
found one incorrect shortened-code copy, so these faster results do not qualify that earlier
implementation for release. They remain in the record rather than being silently discarded.

The 30-event cascade processed 1049 frames, published 1203 unique frames, and overwrote
144 pending frames. Recognition p50/p95/max was 24.38/51.67/487.56 ms **including negative
frames**, so it cannot be directly compared with Phase 1's positive-only 235/290 ms OCR
benchmark. It made 29 slow fallback calls: p50 331.06, p95 410.45, max 435.37 ms. Capture
read p50 was 1.05 ms, handoff 0.38 ms, policy 0.016 ms, and memory write 0.010 ms.

In the native sample, true `queue_wait` p50/p95 was 0.197/0.458 ms; input validation was
0.161/0.239 ms. Native clipboard write p50/p95/max was 0.229/0.721/0.776 ms. Frame age at
dequeue was 1.29/9.48 ms p50/p95. These are not the large remaining bottlenecks.

The worst dry-run event (1222.35 ms) had a 393.58 ms confirming fallback, then a 405.09 ms
fallback with corrupted promotional context (`100%bff`) that reset confirmation, followed
by a 370.63 ms confirming fallback and a 49.59 ms fast confirming frame. This verifies that
fallback cost and intermittent localization/context errors now dominate the tail. We did
not weaken context, confidence, confirmation or freshness rules to conceal that delay.

An initial activity-gate comparison skipped 34/74 OCR opportunities but used 9.34 ms p50
for generic color-axis reductions. Its event latency worsened to 129.27/135.51/136.20 ms.
The implementation was then changed to mathematically equivalent pairwise min/max ufuncs;
the opt-in gate still cannot be assumed to improve first-copy latency for colored/dim text.

## Exact reproduction commands

Run from repository root in PowerShell; use fresh output paths because reports/fixtures
refuse overwrites. These are the executed benchmark/check commands (inspection-only shell
reads and formatting commands are not needed to reproduce the measurements).

```powershell
./.venv/Scripts/python.exe scripts/profile_phase2.py samples/smoke/manifest.json > artifacts/phase2-profile-before.json
./.venv/Scripts/python.exe scripts/provision_models.py
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-model-matrix.jsonl
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-tiny-tuning.jsonl --profiles tiny --scales 1 --limits 640 --threads 1 2 4 --preprocessing none gray clahe --repeats 3
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-tiny-arena.jsonl --profiles tiny --scales 1 --limits 640 --threads 2 4 --arena --repeats 5
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-no-spin.jsonl --profiles tiny --scales 1 --limits 640 --threads 4 --arena --no-spinning --repeats 5
./.venv/Scripts/python.exe scripts/generate_varied.py samples/phase2-varied
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-varied-baseline.jsonl --manifests samples/phase2-varied/manifest.json --profiles baseline --scales 2 --limits 960 --threads 2 --repeats 1
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-varied-tiny.jsonl --manifests samples/phase2-varied/manifest.json --profiles tiny --scales 1 --limits 640 --threads 4 --arena --repeats 1
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-varied-v4.jsonl --manifests samples/phase2-varied/manifest.json --profiles v4 --scales 2 --limits 960 --threads 2 --repeats 1
./.venv/Scripts/python.exe scripts/benchmark_templates.py artifacts/phase2-varied-baseline.jsonl --report artifacts/phase2-templates.json
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-varied-fallback.jsonl --manifests samples/phase2-varied/manifest.json --profiles tiny --scales 1 --limits 640 --threads 4 --arena --fallback-baseline --repeats 1
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-fallback-no-spin.jsonl --manifests samples/phase2-varied/manifest.json --profiles tiny --scales 1 --limits 640 --threads 4 --arena --no-spinning --fallback-baseline --repeats 1
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-varied/manifest.json --profile phase1-policy --report artifacts/phase2-policy-before.jsonl
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-varied/manifest.json --profile baseline --report artifacts/phase2-policy-baseline-guarded.jsonl
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-varied/manifest.json --profile cascade --no-spinning --report artifacts/phase2-policy-cascade.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 3 --seed 31 --profile-inference --report artifacts/phase2-live-baseline.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 3 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --profile-inference --report artifacts/phase2-live-tiny.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 3 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-cascade.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 3 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --activity-gate-ms 100 --profile-inference --report artifacts/phase2-live-gate.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 30 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-30.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --count 3 --seed 7 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-native.jsonl
./scripts/check.ps1 -Ocr
```

## Final measured results (candidate verification enabled)

| Measurement | Phase 1 p50 / p95 / worst ms | Final Phase 2 p50 / p95 / worst ms |
|---|---|---|
| Small ROI, 15 positive-image calls | 234.82 / 289.85 / 347.53 | 63.80 / 233.93 / 275.40 |
| Real-screen dry-run, 30 events, seed 31 | 695.40 / 1749.96 / 2027.72 | 186.00 / 1160.55 / 1411.93 |
| Native clipboard, 3 events, seed 7 | 1025.29 / 1798.56 / 1884.48 | 1351.92 / 1885.99 / 1945.33 |

**The final native sample is slower than Phase 1.** All three native strings and readbacks
were correct, but improved inference and dry-run medians did not establish an overall native
end-to-end performance win. Its individual first-capture-to-write times were 198.68,
1351.92 and 1945.33 ms. The safest/default baseline stays in place; faster experimental
profiles are not promoted. The final native run left its last generated test code in the clipboard.

The final small-ROI comparison uses the same three standard first-visible images, five
repeats each, excluding negatives. A fresh baseline on the current runtime measured
204.10/238.18/304.24 ms. Both profiles had two exact eligible snapshots and one abstention;
moving-event correctness is measured separately. The 63.80 ms median includes verification
where eligible and full fallback where triggered, not just a bare-model inference number.
The fastest tiny-only experimental 29.98 ms median is **not** the shipping safe-cascade latency.

In the final 30-event run, 1209 unique frames were published, 140 overwritten and 1058
processed after baseline. Queue wait p50 was 0.191 ms; input validation 0.167 ms; policy
0.013 ms. Verification (87 calls) was 41.72/48.18/59.68 ms, and full fallback (22 calls)
330.88/376.71/475.32 ms. Recognition including negative frames was 22.50/89.76/517.32 ms.
The largest tail costs remain slow fallback, context/character disagreements and obtaining
two valid fresh observations; native clipboard writing itself was 0.324 ms median in the
final native run. No confidence, context, confirmation or freshness threshold was lowered.

The corrected optional activity mask measured 0.621/1.322/4.607 ms versus the earlier
9.339/13.198/14.106 ms reduction implementation. Its final three-event dry-run skipped
34/73 OCR opportunities and copied 3/3 exactly, at 184.53/201.38/203.25 ms event latency.
That is not proof of a latency benefit across colored/dim/transient inputs. It stays off by default.

One nominal 100 ms exposure dry-run copied its single code correctly in 199.923 ms. The
surface loop can overrun nominal exposure, so this establishes neither calibrated 100 ms
visibility nor a <100 ms response. It is a successful brief-appearance smoke test only.

Final additional commands (all exit 0):

```powershell
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-final-small-baseline.jsonl --manifests samples/smoke/manifest.json --profiles baseline --scales 2 --limits 960 --threads 2 --positives-only --repeats 5
./.venv/Scripts/python.exe scripts/benchmark_ocr.py --report artifacts/phase2-final-small-verified.jsonl --manifests samples/smoke/manifest.json --profiles tiny --scales 1 --limits 640 --threads 4 --arena --no-spinning --fallback-baseline --positives-only --repeats 5
./.venv/Scripts/python.exe scripts/live_smoke.py --count 3 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --activity-gate-ms 100 --profile-inference --report artifacts/phase2-live-gate-final.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 1 --seed 31 --visible-ms 100 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-short.jsonl
./scripts/check.ps1
./.venv/Scripts/ruff.exe check .
./.venv/Scripts/ruff.exe format --check .
./.venv/Scripts/mypy.exe src
```

**Readiness: failed latency and exact-recall acceptance; ready for further engineering,
not GUI/product release.** Real capture and native writing are verified on the tested PC;
30 native/manual-paste events, negative soak, clipboard-contention and desktop-fault matrix,
GPU execution and an independent broadcast release holdout remain unverified.

The first snapshot runs preceded the new O/0 abstention. On current code add
`--allow-ambiguous` to `benchmark_ocr.py` to reproduce that diagnostic behavior, never
to the runtime CLI. Likewise the earliest matrix predates the shared-session setup and
buffer reuse; exact timing equality is not expected. Historical raw files remain intact.

## Next engineering gate

Keep the project at the accuracy/performance gate, without GUI or packaging work. Obtain
labelled real chart-video crops with the actual text sizes/fonts/codec artifacts. Evaluate
character-level evidence and a recognizer suited to alphanumeric codes, then qualify any
replacement/verification model on an independent full-alphabet holdout before removing the
O/0 abstention. Investigate localized recognition that avoids the full slow fallback while
retaining context and source-quality checks. Require the same first-captured-frame metric,
zero wrong writes, the specified exact recall, and p95/p99 gates; do not shorten confirmation
or loosen thresholds to reach 100 ms. Full G2 soak/desktop fault tests and G3 remain open;
the exact manual procedure is in [WINDOWS_VALIDATION.md](WINDOWS_VALIDATION.md).

## Fresh holdout and the final candidate-verification safeguard

After initial tuning, a separate seed 20261101 corpus was generated: 60 positive and six
negative events across the same six size/font/codec/background classes. It exposed a real
regression in the unverified fast path: a leading zero disappeared, leaving a nine-character
string that passed format, context, source pitch, ~0.996 confidence and two-frame agreement.
Blocking recognized O/0 alone cannot catch a character that OCR omits entirely.

| Full policy replay on seed 20261101 | Exact / 60 | Wrong writes | Abstentions |
|---|---:|---:|---:|
| Guarded baseline | 25 | 0 | 35 |
| Initial unverified cascade | 24 | 1 | 35 |
| Final verified cascade | 22 | 0 | 38 |

This dataset was untouched during initial tuning, but became a regression corpus once the
omission was investigated. Its final row is not an independent post-fix release holdout.
All six negative events stayed empty. Native copying is blocked for tiny-only and v4 public
CLI profiles; tiny native copying requires `--fallback-baseline` with verification.

Before changing runtime, `benchmark_verification.py` measured recognition-only inference
on source crops expanded horizontally by the detected line height and vertically by two
pixels, clipped to the user ROI. No target string or known code length informs the crop.
The baseline recognizer read the omitted zero from these pixels. Across 28 candidate crops,
verification p50/p95/max was 45.59/50.29/51.72 ms. It also found an I/1 disagreement on another
case; the final path abstains rather than trusting one model or substituting a character.

The final cascade verifies each eligible fast candidate using the already warmed baseline
recognition session, without a second detector pass. Exact strings must agree and the
second model must independently meet the existing 0.96 confidence threshold. The original
fast confidence remains unchanged; raw verification text/score are separate report fields.
No output means no verification score, not a fabricated zero-confidence prediction.
Disagreement rejects the original line (`verification_disagreement`); full fallback cannot
override that veto. Full fallback outputs retain baseline safeguards. Same-family models
can still share errors, so agreement is additional evidence, not a calibrated probability.

The concrete omission is now a passing real-OCR safety regression. All three original
exact-recall xfails remain. This improves safety at additional latency/recall cost; it does
not make the experimental cascade equal to the guarded default on accuracy.

The final 30-event real-screen dry-run (seed 31, verification enabled) copied **30/30**
correctly, with **zero wrong copies and zero abstentions**. First-capture-to-memory-copy:
**185.997 ms p50, 1160.550 ms p95, 1411.933 ms worst**. Compared with the same-seed Phase 1
dry-run (695.397/1749.956/2027.719 ms), both median and tail improved, but the latency gate
still fails. This standard fixture uses the restricted unambiguous alphabet and must not
be generalized to full-alphabet broadcast text.

Additional executed commands:

```powershell
./.venv/Scripts/python.exe scripts/generate_varied.py samples/phase2-holdout --seed 20261101 --per-style 10
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-holdout/manifest.json --profile cascade --no-spinning --report artifacts/phase2-holdout-cascade.jsonl
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-holdout/manifest.json --profile baseline --report artifacts/phase2-holdout-baseline.jsonl
./.venv/Scripts/python.exe scripts/benchmark_verification.py samples/phase2-holdout/manifest.json artifacts/phase2-holdout-cascade.jsonl --report artifacts/phase2-verification-probe.json
./.venv/Scripts/python.exe scripts/evaluate_replay.py samples/phase2-holdout/manifest.json --profile cascade --no-spinning --report artifacts/phase2-holdout-verified.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 30 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-verified-30.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --count 3 --seed 7 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/phase2-live-verified-native.jsonl
./scripts/check.ps1 -Ocr
```
