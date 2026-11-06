# Phase 5.2 — Windows usability and GUI readiness

## Supervised clipboard batch helper, 2026-11-05 MYT

`scripts/manual_clipboard_batch.py` reuses `game_playback.py` with explicit native
clipboard selection, one code, baseline models and the existing arena-off settings.
It stores unique attempt directories and serializes concurrent helper sessions with a
Windows OS file lock. Interrupted attempts require retained manual evidence or are
saved as unconfirmed failures before retry. Progress begins with six recorded matches.
GUI clipboard behavior and G2 acceptance criteria are unchanged.

Automated checks use injected report data and input, without display or clipboard
access. They cover balanced scheduling, report and manual mismatch rejection,
nonzero or missing exit status, exclusive file creation, resume, and interrupted
attempt retention. `./scripts/check.ps1` passed in the existing Windows Python 3.12
workspace environment with 129 tests passed and 13 OCR integration skips. Native helper operation still requires the operator's first
supervised run. No additional manual matches have been recorded by implementation.

### Live console output follow-up (2026-11-04, MYT)

Live stdout shows lifecycle events, command responses, copy results, and errors.
The optional JSONL report retains frame records and the original timing summary.
The input reader exits on `stop` and requests a stop when stdin closes.
The command queue and its policy owner remain in use.

Windows workspace `.venv`: a direct focused pytest run hit a temporary-directory setup
error. The standard `./scripts/check.ps1` uses workspace-local `.tmp` and passed with
114 tests passed and 13 OCR integration tests skipped. The new tests exercise stdin
commands during simulated monitoring, stop and EOF, and the console/report split.
Interactive Windows capture and arming still require the operator's manual run. G2 is pending.

Date: 2026-11-03, Asia/Kuala_Lumpur. **G2 manual qualification remains pending; do not start
GUI implementation.** This phase prepares reproducible manual checks, inventories the
actual display configuration read-only and reruns automated quality checks. It does not
claim any unperformed manual paste, occlusion, lock or multi-monitor capture test passed.

## Performed configuration inspection

`scripts/display_inventory.py --report artifacts/phase52-display-inventory.json` exited 0
with no query errors. Three active desktop monitors and three available display targets:

| GDI device / position | DXcam device/output | Physical resolution | Scale | Refresh | HDR supported / user-enabled / active |
|---|---|---:|---:|---:|---|
| DISPLAY1 / left | 0 / 1 | 1920x1080 | 125% | 144 Hz | false / false / false |
| DISPLAY2 / center primary | 0 / 0 | 1920x1080 | 100% | 75 Hz | false / false / false |
| DISPLAY3 / right | 0 / 2 | 1920x1080 | 100% | 60 Hz | false / false / false |

All are landscape, active SDR, eight bits per channel. WTS client protocol 0 and false
SM_REMOTESESSION/SM_REMOTECONTROL identify the current process as a local-console session,
not RDP. This cannot rule out third-party screen sharing. No requested configuration field
was unavailable. Physical desktop rectangles are `[-1920,5,0,1085]`, `[0,0,1920,1080]`,
`[1920,-2,3840,1078]`; application ROIs remain **output-local**, not these global offsets.

An initial DPI-unaware diagnostic returned a virtualized 1536x864 rectangle for the left
screen. The process-aware query and physical display mode both returned 1920x1080. This
is a coordinate-selection hazard, not a newly demonstrated runtime capture defect: the
existing DXcam adapter already sets per-monitor process DPI awareness. The snapshot tool
lets the user verify actual pixels before arming. DXcam output 0 maps to DISPLAY2, not
DISPLAY1; ordinal numbers must never be assumed interchangeable.

Inventory uses EnumDisplayMonitors/GetMonitorInfo, EnumDisplaySettings, GetScaleFactorForMonitor,
read-only QueryDisplayConfig/DisplayConfigGetDeviceInfo and WTSQuerySessionInformation.
HDR uses the newer advanced-color-info-2 supported/user-enabled/active fields rather than
misreporting generic advanced color as HDR. DXcam's installed 0.3.0 factory metadata
supplies the device/output mapping without creating a capture camera. Setting DPI awareness
affects only this diagnostic process's coordinates; **no Windows display or power settings
were changed**, and no keep-awake request was made in this phase.

API definitions were verified against installed pywin32/DXcam and primary references:
[Microsoft SDK header](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/wingdi.h),
[monitor scale API](https://learn.microsoft.com/en-us/windows/win32/api/shellscalingapi/nf-shellscalingapi-getscalefactorformonitor),
[WTS session query](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsquerysessioninformationw).

## G2 evidence review

| Requirement | Evidence already available | Remaining manual evidence |
|---|---|---|
| Real pixels through OCR/policy/native clipboard | Phase 5/5.1 matched native capture runs | 30 recorded literal manual paste comparisons, both profiles |
| Correct physical ROI / display configurations | Current read-only inventory; historical primary-screen fixtures | User-inspected PNGs and live checks on all three current outputs, especially 125% |
| Disarmed startup, baseline, arm/disarm/stop | Unit tests and 14/14 real-screen recovery probes | Actual console usability and cleanup observations |
| One-shot / repeat / persistent banner suppression | Unit/policy tests and real-screen duplicate probes | Controlled-source manual observations with both profiles |
| Capacity-one handoff / freshness | Unit tests; native no-late-write measurements | Retain existing evidence; repeat only for a new finding |
| Negative monitoring / memory | 1800-second arena-off soak, zero writes, +14.1 MiB | No repeat needed absent a new regression/source-specific finding |
| Busy clipboard / mid-OCR controls | Real native contention and timestamped race probes | No repeat needed absent a new finding; manual paste still separate |
| Occlusion / minimization / source identity | Known fixed desktop-ROI limitation | Dry-run reproduction; do not certify fail-closed behavior on unrelated moving pixels |
| Lock/unlock / monitor loss / display changes | Injected and static/blank probes only | Actual lock/unlock; approved physical/configuration-change tests |
| Model/provider/stage provenance | Existing hash/session/timing reports | Attach commands and configuration to each manual observation |

`PHASE52_MANUAL_CHECKLIST.md` supplies 12 numbered steps and exact opt-in commands.
`PHASE52_MANUAL_RESULTS.md` is a blank record, including 30 paste rows; none are prefilled
as passing. Existing configuration inventory is completed, **manual functional checks: 0**.
The current 100%/125% three-monitor setup can be tested without any settings changes.
Other scales, rotation, HDR-on and remote sessions are not declared supported merely from
enumeration. Broader G2 requirements are not waived; changes need separate user approval.

## Runtime choice and preserved tradeoff

For sustained manual monitoring, recommend explicitly selecting the existing arena-off
bundle: `--scale 1 --threads 4 --no-spinning --det-limit 640`. It passed the memory gate;
this is a test recommendation, **not a new default or a claim of equivalent performance**.
Arena on remains available by adding `--cpu-arena`. Both choices keep the same baseline
OCR model, confirmation count, confidence/quality restrictions, freshness and deduplication.

| Phase 5.1 measurement | Arena on | Arena off |
|---|---:|---:|
| 30-minute private growth | 77.8 MiB (historical Phase 5; fail) | 14.1 MiB (pass) |
| Discount long copy p50/p95 ms | 229.8 / 271.5 | 267.8 / 322.5 |
| Game long copy p50/p95 ms | 244.2 / 266.8 | 256.8 / 335.3 |
| Screenshots first pair p50/p95 ms | 493.6 / 593.9 | 624.1 / 849.0 |
| Screenshots reversed pair p50/p95 ms | 461.0 / 517.0 | 581.1 / 634.9 |

These historical paired measurements are not rerun in Phase 5.2. Each arena setting had
100/128 exact copies across completed repeats, zero wrong/late/mismatched writes; 28 O/0
abstentions per setting remain. The original three challenge xfails and the roughly 26%
screenshot p50 tradeoff remain unresolved. G3 representative accuracy and <100 ms remain
unmet; a minimal GUI would not fix them.

## Changes and checks

New diagnostics: `scripts/display_inventory.py` (read-only settings) and
`scripts/capture_roi.py` (explicit `--capture`, saves one owned BGR ROI as PNG plus metadata,
no OCR/clipboard/viewer). The snapshot tool always labels manual validation NOT_RUN and
refuses an existing evidence directory. Its headless tests inject pixels; **no real snapshot
or manual visual verification has been run in Phase 5.2**.

New `tests/test_phase52.py` covers capture opt-in, cleanup/error evidence, no fabricated
manual-pass result, overwrite refusal and Windows structure layouts. No runtime `src/`,
models, dependency pins, thresholds or defaults changed. Both detection profiles and arena
options are preserved. No GUI, package, native clipboard operation, long benchmark,
display/power change, commit or push was performed.

Initial unchanged checks: `./scripts/check.ps1` exited 0 (107 passed, 13 opt-in skips,
5.09 s); `./scripts/check.ps1 -Ocr` exited 0 (117 passed, three strict challenge xfails,
31.67 s). Pip, Ruff lint/format and strict mypy all passed. Outputs are
`artifacts/phase52-check.txt` and `artifacts/phase52-check-ocr.txt`.

The first direct focused pytest invocation had four setup errors because the sandbox's
default temp directory was not writable; one ABI test passed. The approved exact rerun
outside the sandbox passed all five tests in 0.45 s. This was an environment failure,
not an OCR/application failure. Initial new-script Ruff formatting/UTC-alias issues were
fixed. Final full post-change checks:

```powershell
./.venv/Scripts/python.exe scripts/display_inventory.py --report artifacts/phase52-display-inventory.json
./.venv/Scripts/python.exe -m pytest -q tests/test_phase52.py
./.venv/Scripts/python.exe scripts/capture_roi.py --help
./.venv/Scripts/python.exe scripts/display_inventory.py --help
./scripts/check.ps1 *> artifacts/phase52-check-final.txt
./scripts/check.ps1 -Ocr *> artifacts/phase52-check-final-ocr.txt
```

Both help commands exit 0 without capture/settings/clipboard access. The final checks
both exited 0: **112 passed, 13 opt-in skips** in 4.44 s; **122 passed, three original
strict challenge xfails** in 31.12 s with real local OCR enabled. Pip dependency check,
Ruff lint, Ruff format (75 discovered Python files) and strict mypy (16 runtime source
files) all pass. No new assertion failure or runtime regression was observed. No original
xfail, threshold or timing budget was changed. Direct diagnostic smoke and the five new
headless tests do not substitute for real ROI capture or human observation.

Files added: `scripts/display_inventory.py`, `scripts/capture_roi.py`,
`tests/test_phase52.py`, `docs/PHASE52_MANUAL_CHECKLIST.md`,
`docs/PHASE52_MANUAL_RESULTS.md`, and this validation record. Documentation links/status
updated in `README.md`, `docs/PROJECT_SPEC.md`, `docs/WINDOWS_VALIDATION.md`. New inventory
and check artifacts use the `artifacts/phase52-*` prefix. The pre-existing untracked tree
was preserved; no unrelated code or historical benchmark artifacts were rewritten.

## GUI-readiness verdict

**Not ready to approve minimal GUI implementation yet.** Automated functional evidence is
substantial, but required manual paste, mixed-DPI ROI and physical source-change results
are missing. Fixed-ROI capture has no video-window identity binding; a moving occluder or
minimized source can remain healthy. This is a known reliability limitation confirmed by
source review, not a newly performed live failure test. It remains a G2 source-loss concern
even if a particular occlusion produces no wrong copy.

Next: perform and return the numbered manual record, beginning with the current three
outputs and memory-only controls, then explicitly opt into the individual native paste
tests. Resolve recorded failures/source-identity scope before G2 sign-off. Do not weaken
the gate implicitly. The specification makes G2 the prerequisite for G4 minimal UX;
full G3 accuracy/<100 ms claims remain separately blocked. No need to repeat the long
arena benchmarks merely to decide whether manual usability evidence is complete.
