# v0.2.0 detection policy validation

The operator manually tested native Windows clipboard copying on the build prepared
as v0.2.0 and reported **PASS** on 2026-11-18 MYT. The measurements below retain
their original test scopes. [Operator result](WINDOWS_VALIDATION.md#v020-operator-clipboard-test)

2026-11-18 MYT. Windows 11 build 26200, AMD Ryzen 5 5600H, Python 3.12.14, RapidOCR
3.10.0, ONNX Runtime 1.31.1, PySide6 6.12.0, DXcam 0.3.0 and pywin32 312. The
default warmed PP-OCRv6 small detector/recognizer ran on CPU at scale 2 with two
intra-op threads, default detector limit 960 and the CPU arena disabled. Model SHA256
values matched the bundled-model record. [Model identity](VALIDATION.md#model-identity)

## What changed

| Previously | v0.2.0 |
|---|---|
| Exact agreement across two distinct changed frames | Copy from the first fresh read with one eligible new code. A static reveal needs one pixel change from the baseline to the reveal. |
| Blanket O/0 rejection in OCR and policy | Preserve both glyphs and letter case as recognized. |
| Uppercase only, 8–16 in Discount and 8–20 in Game | 6–24 ASCII characters with letters and digits. Game retains internal hyphens. |
| Mandatory separate promotional context and directional layout checks | An attached label can qualify by itself. Nearby offer, code-heading or Game redemption text can support a token. A standalone token needs at least eight characters, two digits, and one digit between letters. |
| A moving baseline needed matching code sets | Two usable observations spanning at least 500 ms can establish readiness with different code sets. Healthy static baseline polls retain the initial-read path. All observed code-shaped baseline tokens remain suppressed. |
| 1000 ms frame age and agreement interval | 3000 ms frame-age limit with checks before OCR, after OCR and at the clipboard handoff. The agreement interval was removed. |

The 0.96 code confidence floor, 0.75 context floor and 10 original pixels per
character source floor still apply. The current OCR source guard also covers Game
formats and all newly recognized shapes. Multiple eligible new strings cause
abstention, case-sensitive dedup lasts for the session, and a successful copy
automatically disarms. Live arming discards queued pre-arm frames. Stop, disarm
and capture invalidation inhibit in-flight results. Native copying requires consent.
The native adapter now verifies exact CF_UNICODETEXT readback in the same open
clipboard transaction before reporting success. A write or readback error disarms.
Custom sounds retain their separate background check and playback.
[pywin32 readback API](https://mhammond.github.io/pywin32/win32clipboard__GetClipboardData_meth.html) ·
[pywin32 clipboard example](https://github.com/mhammond/pywin32/blob/main/win32/Demos/win32clipboardDemo.py)

The default detector runs one OCR pass per selected frame. The opt-in fast model vetoes unverified
fast readings and respects source quality rejection. The optional activity gate now
scans a deferred static reveal at its deadline if the ROI has stayed unchanged.

## Paired offline results

The before run imported a snapshot of the **existing uncommitted develop implementation**
made before edits. It includes the prior labelled Discount and armed ROI work. The after
run imports the revised code. The evaluator used the same seeded frames, Qt-rendered
simulator reveals, generated chart manifests and labelled game screenshots in both runs.
Input digests and truth labels matched case by case. The game stills use a one-pixel
change for the second observation and a synthetic blank baseline. Other dataset cases
use the first two post-baseline frames. The simulator cases have a single reveal frame.

The existing fixture's `other-label` cases contain a literal generic `Code:` next to
market commentary. Their labels remain negative under the original benchmark. All three
copies are counted below. The baseline and repeat probes are scored against zero
unexpected writes. A wrong transcription is counted separately from a positive event
with no write. Totals count scenarios, which can share a rendered token across cases.

| Suite | Positive / negative | Exact before → after | No copy on positive before → after | Wrong on positive before → after | Negative writes before → after |
|---|---:|---:|---:|---:|---:|
| Simulator static | 8 / 2 | 0 → 7 | 8 → 1 | 0 → 0 | 0 → 0 |
| Simulator previously visible | 0 / 1 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| Simulated slow OCR | 1 / 1 | 0 → 1 | 1 → 0 | 0 → 0 | 0 → 0 |
| Large moving ROI, 1137 × 841 | 4 / 1 | 0 → 3 | 4 → 0 | 0 → 1 | 0 → 0 |
| Existing Discount layout generator | 24 / 24 | 16 → 19 | 8 → 2 | 0 → 3 | 0 → 3 |
| Standard smoke | 3 / 1 | 3 → 3 | 0 → 0 | 0 → 0 | 0 → 0 |
| Tiny compressed challenge | 3 / 1 | 0 → 0 | 3 → 3 | 0 → 0 | 0 → 0 |
| Phase 2 synthetic holdout | 60 / 6 | 25 → 37 | 35 → 12 | 0 → 11 | 0 → 0 |
| Game starter screenshots | 8 / 0 | 8 → 8 | 0 → 0 | 0 → 0 | 0 → 0 |
| **Total** | **111 / 37** | **52 → 78** | **59 → 18** | **0 → 15** | **0 → 3** |

The simulator's static successes include uppercase and lowercase standalone codes,
mixed-case O/0, an offer above a code, and a mixed-case Game code with a hyphen. One
bare letters-then-digits code remained ineligible. The same shape qualified with an
offer. No simulator negative or baseline case copied. The after repeat probe copied
once, then rearmed and read two changed frames showing the same code without another
write. The before implementation missed the initial static reveal, so its rearm
probe had no initial copy. No repeated write occurred in either run.

The injected replay clock added 1300 ms or 3200 ms after real OCR returned. The
revised policy copied the 1300 ms case after 1482 ms of combined measured and
simulated time and rejected the 3200 ms case as stale. Both were stale before.
The artificial delays are excluded from timing percentiles.

Thirteen of the 15 wrong transcriptions changed O to zero. One changed I to 1 and
one repeated a trailing L. The raw reports show the exact accepted strings and their
OCR scores. The incorrect copies and generic-label false
positives are part of the measured precision cost. The three strict tiny-text recall
xfails and their separate safety tests still reproduce.

| Replay latency in ms | Before p50 / p95 | After p50 / p95 | Samples per version |
|---|---:|---:|---:|
| Processing time for first post-baseline input | 136.4 / 688.6 | 134.1 / 639.4 | 146 |
| First input to memory write, exact in both runs | 278.4 / 1001.1 | 134.1 / 631.4 | 52 paired |
| First input to memory write, all exact replay results with measured time | 278.4 / 1001.1 | 135.3 / 681.7 | 52 / 77 |
| First input to memory write, exact large-ROI results | — | 1390.1 / 1423.1 | 0 / 3 |
| First input to memory write, exact static simulator results | — | 213.8 / 347.9 | 0 / 7 |

Replay time starts immediately before submitting the first armed frame. It includes
sequential processing and the memory write, excluding warmup, initial decoding, the
Qt countdown, display presentation, DXcam and Windows clipboard latency.

## Real DXcam smoke comparison

Two initial runs failed with DXGI COM `Access is denied` and zero captures in the
sandbox. The same commands outside the sandbox completed. Both used real DXcam
capture of moving generated Windows scenes and memory writes only. Both copied
3/3 exactly, with zero incorrect copies. One pair, three long-lived appearances,
seed 7, 540 × 165 ROI. The harness marked the first captured code frame before the
latest-frame handoff.

| Milliseconds | Before | After |
|---|---:|---:|
| First captured code frame to memory write, individual events | 366.8, 1639.3, 1405.6 | 208.7, 307.8, 213.3 |
| First captured code frame to memory write, p50 / p95 | 1405.6 / 1615.9 | 213.3 / 298.3 |
| Live pipeline process p50 / p95 | 96.9 / 198.3 | 92.7 / 192.7 |

The generated-screen timing run used memory writes. The operator's separate PASS
covers native clipboard copying. Manual sound playback, representative livestream
accuracy and the sub-100 ms gate remain open.

The real DXcam memory-only failure suite passed all 12 probes across both profiles.
It verified duplicate prevention, stop and disarm during OCR, blank-capture failure,
healthy idle capture and exact copying in a fresh session.

## Reproduction and checks

The local snapshot is in `.tmp/policy-before`. An independent reproduction needs
that exact source snapshot or an equivalent copy of the pre-edit develop worktree.
Run these from the repository root with unused report filenames.

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) '.tmp/policy-before'
./.venv/Scripts/python.exe scripts/benchmark_detection_policy.py --report artifacts/policy-comparison-before.jsonl
Remove-Item Env:PYTHONPATH
./.venv/Scripts/python.exe scripts/benchmark_detection_policy.py --report artifacts/policy-comparison-after.jsonl
./scripts/check.ps1
./scripts/check.ps1 -Ocr
```

- Main raw replay reports were `artifacts/detection-policy-before.jsonl` and
  `artifacts/detection-policy-after.jsonl`. The original standalone fixture accidentally
  placed all digits at the end. Corrected static, suppression and delay rows come from
  `--simulator-only` runs in `artifacts/detection-policy-simulator-{before,after}.jsonl`.
  The current script generates the corrected fixtures in its full run.
- On an interactive Windows desktop, run `scripts/live_smoke.py --report <new-file>`
  through the project interpreter for both source versions. The completed reports are
  `artifacts/detection-policy-dxcam-{before,after}-retry.jsonl`.
- `./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --report artifacts/detection-policy-windows-failures.jsonl`
  exercised the real-capture failure suite with the memory clipboard.
- The first lint run flagged four long test lines. Ruff formatting fixed them.
  The default repository check passed 229 tests with 18 opt-in OCR tests skipped.
  The v0.2.0 release check (`./scripts/check.ps1 -Ocr`) passed **244 tests with
  3 strict challenge xfails** in 73.39 seconds. Dependency validation, Ruff lint
  and format, and strict mypy on all 20 source files passed. The package metadata
  and runtime version both reported 0.2.0. The release check log is in
  `artifacts/v0.2.0-check-ocr.txt`.
- [Windows manual verification](WINDOWS_VALIDATION.md#verify-v020-on-windows)
  covers the actual simulator display, optional native readback and manual paste.
