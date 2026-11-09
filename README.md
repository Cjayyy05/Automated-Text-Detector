# Instant Stream Code Capture

Python 3.12 / Windows 11 foundation for recognizing a transient promotional code
**inside video pixels**, within a user-selected chart region, then copying it for
manual redemption. No DOM scraping, cloud OCR, redemption or mouse automation.

## v0.1.0 baseline status

This initial Git baseline includes the offline image/replay tools, live DXcam console,
Discount and Game profiles, and PySide6 GUI with ROI selection, explicit arm/disarm,
status and stop controls. Optional native copying requires per-session consent;
verified-copy sound and a remembered local WAV selection are available. Auto-arm is
not implemented: startup is disarmed and every successful copy requires explicit rearm.

G2 is signed off only for supervised personal use on center primary output 0,
1920 × 1080, 100% scale, SDR, local Windows console and fixed display topology.
The signed-off ledger includes 30 manual native paste matches and subsequent GUI
Discount/Game paste smoke checks. Full G3 representative accuracy/recall and latency
qualification remains unmet; full G4 UX/display/release qualification remains incomplete.
O/0 and insufficient-source-resolution inputs abstain, the three strict challenge
xfails remain, and <100 ms performance is not achieved. Detailed ROI/resize/reload,
broader display/source transitions and audible/custom-sound manual checks remain pending;
physical hotplug is deferred under the approved G2 evidence substitution.

See [current GUI qualification](docs/PHASE6_VALIDATION.md),
[the G2 sign-off ledger](docs/PHASE52_MANUAL_RESULTS.md), and
[baseline validation](docs/BASELINE_VALIDATION.md). Older phase records below retain
their historical pending statuses; they do not revoke the later limited-scope sign-off.

The offline and **live DXcam console pipelines** use real local RapidOCR models. Phase 5's
native screen-test matrix made 160 correct copies with matching clipboard readbacks and
48 O/0 abstentions; it observed zero incorrect or stale-frame writes. The two-profile
Windows failure/recovery probes passed 14/14. These are fixture-based functional results,
not production readiness. Tiny compressed O/0 recognition
remains unresolved, and measured live event latency is well above 100 ms. See
[Phase 2 measurements](docs/PHASE2_VALIDATION.md), [Phase 1 validation](docs/PHASE1_VALIDATION.md)
and the [foundation record](docs/VALIDATION.md).
Phase 6 adds a local PySide6 GUI that starts in dry-run mode. Limited personal-use G2
sign-off is recorded. Optional native copying requires per-session consent and the
approved center-monitor configuration; GUI paste validation is tracked separately.

## Launch the Windows dry-run prototype

From the repository root in PowerShell, install the pinned Qt dependency once, then launch:

```powershell
.\.venv\Scripts\python.exe -m pip install PySide6==6.12.0
.\.venv\Scripts\python.exe -m stream_code_capture.gui
```

Choose the monitor and Discount or Game profile. Move the app clear of the video, click
**Load preview**, and drag a rectangle around the code area and nearby context. Click
**Start**, wait for **Ready**, then **Arm**. An exact confirmation shows the code and disarms
the session. Use **Disarm** or **Stop** to end monitoring. See the
[Phase 6 validation and manual checks](docs/PHASE6_VALIDATION.md).

The optional **Play sound when code is copied** checkbox starts unchecked. In native
mode, a Windows notification sound follows a successful copy only when background
clipboard readback matches. Dry-run confirmations stay silent.

Use **Choose sound** to select a local PCM WAV such as your downloaded Mixkit
Success software tone, then **Test sound** to hear it. The selected path is remembered
between launches. **Default** clears the custom selection. Missing or unreadable files
fall back to the Windows sound. Keep downloaded audio in a personal folder outside
the repository.

For native copying, select **Use Windows clipboard for this session** before Start and
accept the warning. It replaces clipboard contents after a confirmed new code. Codes
in covering windows can also qualify; disarm before covering, moving or minimizing the
source. Native mode requires center primary output 0 at 1920 × 1080, 100%, SDR and a
local console, with fixed topology. Stop or session completion resets the checkbox.

Phase 4 measured a faster **opt-in configuration of the same baseline model**:
`--scale 1 --threads 4 --cpu-arena --no-spinning --det-limit 640`. On a comparable eight-slide
DXcam/memory repeat, p50/p95 copy latency fell from 1072/1874 ms to 492/520 ms with 8/8 exact
copies in both. A second seed also passed 8/8, improving p50 from 877 to 485 ms. Defaults and
confirmation/safety rules remain unchanged. This is fixture
evidence, not representative accuracy or <100 ms qualification. See
[Phase 4 measurements and short-exposure tests](docs/PHASE4_VALIDATION.md).

[Phase 5 native qualification](docs/PHASE5_VALIDATION.md) records the explicit Windows
comparison, failure probes and negative monitoring. The native harness requires
`--native-clipboard`; omitting it keeps writes in memory. The application now rechecks
the accepted frame's freshness immediately before the clipboard handoff, including after
waiting for the control/write lock. This does not change the 1000 ms age limit.
On matched native runs, discount p50 improved from 583 to 270 ms, game from 520 to 249 ms,
and the eight imported screenshots from 947 to 488 ms, with unchanged exact recall.
The optimized CPU arena also increased memory allocations; defaults remain unchanged.
The 30-minute two-profile negative soak produced zero writes, but failed its memory-growth
gate (+77.8 MiB versus 50 MiB).

[Phase 5.1 arena qualification](docs/PHASE51_VALIDATION.md) reproduced that retention in
fresh-process diagnostics and passed the same 30-minute memory gate with arena disabled:
**+14.1 MiB**, zero negative writes. Native arena-on/off comparisons preserve exact recall
and all safeguards, but show a workload-dependent latency penalty when disabling arena.
No runtime default or OCR algorithm has changed. For the optimized settings with arena
disabled, omit `--cpu-arena`: `--scale 1 --threads 4 --no-spinning --det-limit 640`.
This remains an explicit configuration choice, not a promoted default or a <100 ms claim.

[Phase 5.2 manual checklist](docs/PHASE52_MANUAL_CHECKLIST.md) covers the remaining Windows
usability gate, with a [manual results record](docs/PHASE52_MANUAL_RESULTS.md). Read-only
inventory found three 1920x1080 SDR screens at 125%/100%/100% scale and a local session;
this does not qualify multi-monitor capture. The explicit `scripts/capture_roi.py --capture`
diagnostic saves a chosen ROI for inspection without OCR or clipboard access. Manual
paste, ROI and source-change entries in that earlier checkpoint are historical; see the
later [G2 sign-off ledger](docs/PHASE52_MANUAL_RESULTS.md) for completed and deferred checks.

The reproducible short-exposure matrix requires an explicit visible-test command:

```powershell
./scripts/phase4_playback.ps1 -ShowPlayback -OutputDirectory artifacts/manual-phase4-short -Count 4 -Seed 20261103 -WithActivityGate -DrainMs 1000 -PreciseStimulus
```

It tests both profiles at nominal 250/500/1000/2000 ms, records actual painted durations,
uses new generated values/backgrounds, and writes only to memory. The drain interval permits
fresh in-flight results after disappearance; it does not extend runtime freshness or replay
cached frames. O/0 cases intentionally remain in the recall denominator and can make a run
exit nonzero. The original imported-image playback command remains available below.

## Detection profiles

`--profile discount` is the default and retains the original temporary chart-discount
rules. `--profile game` accepts exact uppercase ASCII codes of 8–20 characters including
optional internal hyphens, with both a letter and digit, and requires nearby redemption/
expiry context. It does not depend on a chart background. Select an ROI containing the
code **and** its label (e.g. `Expiry Date`, `有効期限`, `有效期至`). The game profile keeps
the O/0 abstention, quality floor, two fresh confirmations, baseline, one-shot arm and dedup.
Lowercase, arbitrary formats, and ambiguous glyph correction are not supported.

```powershell
./.venv/Scripts/python.exe -m stream_code_capture live --profile game --roi 300 250 1060 390 --dry-run
```

Replace those coordinates with the actual code/label area on your monitor. Enter `start`,
wait for `ready`, then `arm`; `disarm` and `stop` retain their existing behavior. Native
clipboard use still requires explicit `--clipboard windows` and arming. Game currently uses
the default baseline OCR model; experimental cascade verification is discount-specific and
cannot be selected for game through the CLI. OCR models/algorithm were not changed.

The explicit simulated playback test below opens a temporary test window and feeds **real
DXcam pixels** to the existing pipeline with a memory clipboard by default. Phase 5 adds an
explicit `--clipboard windows` test option that replaces clipboard contents and checks
readback. It requires the imported starter pack and an unobscured primary-screen area of at
least 1010x590 pixels. The code-band ROI is configurable in test-window coordinates.

```powershell
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --report artifacts/manual-game-playback.jsonl
```

See [game-profile validation](docs/GAME_PROFILE_VALIDATION.md) for failures, final measured
results and limits. These reused slides do not qualify general game livestreams or tiny
TikTok codes.

Phase 3 adds [local recording/screenshot preparation and labelling](docs/DATASET_WORKFLOW.md),
session/code-disjoint split audits, memory-only evaluation and crop/character diagnostics.
Eight game-code screenshots now have visual labels and local tests; representative labelled
livestream recordings are still missing, so **real-video qualification is blocked**.
No new OCR strategy is promoted. See [Phase 3 results](docs/PHASE3_VALIDATION.md)
for synthetic comparisons, unchanged challenge failures and exact check commands.

**Current safety limitation:** code-like OCR strings containing `O` or `0` now explicitly
abstain (`unresolved_O0_glyph`), even at high confidence and larger source sizes. New tests
found systematic errors in both directions that survived two-frame agreement. This prevents
known wrong writes but also rejects valid codes. It does not fix recognition or establish
production accuracy; the original three challenge expected failures remain.

## Experimental fast CPU path

The original small-model profile remains the default. Provision optional models explicitly
(official pinned-release downloads with SHA256 checks; no downloads during recognition):

```powershell
./.venv/Scripts/python.exe scripts/provision_models.py
./.venv/Scripts/python.exe -m stream_code_capture live --roi 300 250 840 415 --dry-run --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/fast-dry.jsonl
```

Replace the example ROI with the chart region on your monitor. Start/arm/stop behavior is
unchanged. With `--fallback-baseline`, fast eligible candidates also require an independent
baseline recognizer to read the exact same string from a wider source-pixel crop. Disagreement
or low verification confidence abstains; neither string is repaired or substituted. Actual
verification text/confidence and cost are reported. This caught a leading-glyph deletion
that survived two fast observations. Experimental native copying requires this mode.

The optional full fallback tries the baseline model when fast OCR localizes unusable text;
it never overrides a quality rejection. Empty fast detections do not trigger it, so it is
not a completeness guarantee. The verified cascade returned 22/60 exact copies, zero wrong
writes and 38 abstentions on the new regression corpus, versus 25/60 for the guarded baseline.
It remains opt-in, with no broadcast qualification. `--preprocessing none|gray|clahe`, `--threads`,
`--det-limit`, `--cpu-arena` and `--no-spinning` support controlled experiments. No GPU result
is claimed. `v4` is a benchmark alternative, not the recommended fast path.

`--activity-gate-ms 100` is an opt-in scheduling experiment. Bright neutral text changes and
pending confirmations scan immediately; other frames receive a forced scan at least every
100 ms while the consumer is available. Continuous candle motion cannot reset this deadline.
Colored/dim text can wait for that scan; keep the gate disabled when optimizing first-copy
latency. OCR is single-thread-owned and the capture handoff still holds only the newest frame.

Timing JSON distinguishes capture, frame waiting, handoff/age, preprocessing, OCR, policy,
and clipboard. `--profile-inference` additionally times actual ORT detector/recognizer calls.
`ocr_process_cpu` is scheduled process CPU across threads, not exclusive OCR CPU or wall time.
Only the live validation harness can observe the first captured target frame, including
dropped frames. Ordinary session timings must not be presented as that end-to-end latency.

## Setup (PowerShell)

Install Python 3.12 x64, then run from this repository:

```powershell
./scripts/setup.ps1
# If py is unavailable, supply a real Python 3.12 executable:
./scripts/setup.ps1 -Python 'C:\path\to\Python312\python.exe'
./scripts/check.ps1
./scripts/check.ps1 -Ocr
```

Setup creates `.venv`, installs pinned CPU/dev/Windows packages and checks compatibility.
It needs network access for package installation. OCR thereafter uses bundled local models;
missing models fail startup. No activation or machine-wide execution-policy change is
required. The PySide6 GUI extra is pinned but not installed by default. Do not install both
`opencv-python` and `opencv-python-headless` into this environment.

## Live Windows chart capture

Choose a chart ROI in **physical pixels relative to the selected monitor**, excluding the
banner and chat. These sample coordinates are illustrative; replace them for your own PC.

```powershell
./.venv/Scripts/python.exe -m stream_code_capture live --roi 300 250 840 415 --output 0 --dry-run --report artifacts/live-dry.jsonl
```

After OCR warmup, enter commands in the console, each followed by Enter. The console
shows lifecycle events, status, copy results, and errors. Use `--report` to save detailed
frame diagnostics and the final timing summary in JSONL.

1. `start` begins capture and disarmed baseline collection.
2. Wait for `ready` after at least 500 ms of baseline stability. A healthy unchanged
   region can establish readiness from its recognized initial image.
   Moving regions use matching recognized code sets, with a bounded baseline-only
   allowance for slow OCR. The GUI shows accepted/rejected reads and the last OCR time.
3. `arm` enables one new-code decision. Dry-run emits `would_copy` and uses memory only.
4. `disarm` inhibits writes, including results from OCR already in flight.
5. `status` reports current state. `stop` or Ctrl+C stops capture and exits.

For intentional native clipboard writes, use `--clipboard windows` **instead of** `--dry-run`.
It remains disarmed until `arm`. Successful copy disarms; rearm is explicit. `--start`
starts capture after warmup but does not arm. `--duration 60` bounds a session. Closed stdin
stops it. Report paths refuse overwrite. Run from an interactive desktop terminal; sandbox
or remote-session restrictions can deny DXGI access.

The producer retains only the newest pending frame and discards identical ROI images.
A blank capture, source exception, DXcam recovery warning, or 2.5 seconds without a completed
capture poll stops the session. A healthy static region keeps its current state, and OCR
resumes on the next changed frame. The ROI does not follow moved windows. Stop and
restart with new coordinates if the video moves. Window occlusion/minimization cannot be
reliably identified from arbitrary desktop pixels yet.
Camera initialization has a separate 10-second allowance, before the running-source timeout.

The development freshness budget remains 1000 ms (`--max-frame-age-ms`); it is not the
100 ms performance target. Small ROIs help. No failed clipboard write is retried automatically.

## Generate and replay a chart sequence

```powershell
./.venv/Scripts/python.exe -m stream_code_capture generate samples/demo --seed 7 --count 3
./.venv/Scripts/python.exe -m stream_code_capture replay samples/demo/manifest.json --arm
```

Generation produces three varied positive sequences and one negative-only sequence, PNGs
and a JSON manifest containing ROI, per-frame target and expected writes. The large JORDY
banner stays fixed; candles and chat change; a smaller slanted code appears briefly above
product/discount text. The code reappears after copying to exercise suppression. Reusing
the output directory fails to protect existing samples. Use a new seed/directory for variants.

Replay always uses a **memory clipboard**. `--arm` enables decisions after frame 0 baseline;
without it the replay stays disarmed. The manifest's expected strings are used only to
score outcomes, never as OCR inputs. JSON includes recognized boxes/text, decisions,
expected/actual writes and timing percentiles. Exit 0 = expected writes matched, 1 = mismatch,
2 = configuration/input error. Replay uses an explicitly reported 10-second offline age
budget; `--age-budget-ms 1000` exercises the normal development freshness limit.

```powershell
./.venv/Scripts/python.exe -m stream_code_capture generate samples/harder --seed 19 --count 3 --challenge
./.venv/Scripts/python.exe -m stream_code_capture replay samples/harder/manifest.json --arm
```

Challenge fixtures include smaller glyphs, more slant, blur/JPEG and ambiguous characters.
They are characterization inputs, not a claim of supported real-stream accuracy.

## Inspect a local image

```powershell
./.venv/Scripts/python.exe -m stream_code_capture image samples/demo/case_000_1.png --roi 20 125 710 510
```

This is disarmed and prints candidates without touching the clipboard. Coordinates in
this example belong only to the generated fixture. For your own PC image, choose the chart
area in source-image pixels: left, top, exclusive right, exclusive bottom. Exclude the
permanent banner and chat. The detector finds text within that crop automatically.

Default policy requires uppercase ASCII alphanumerics, 8–16 characters, both letters and
digits, score >=0.96, nearby discount/promo context and two consecutive exact observations.
The OCR adapter also rejects code lines below 10 **source-image pixels per character**
(detector top-edge length / character count), reporting `insufficient_source_resolution`.
This conservative quality floor prevents the known challenge wrong-copy case; it does not
solve tiny-text recognition or prove that larger text is correct. Rejected text is retained
unchanged in diagnostics. Challenge exact-recall tests remain strict expected failures.
It does not correct OCR spelling or ambiguous characters. A baseline is required before
arming. A successful copy disarms; copied codes stay suppressed for the session.

Real image-to-Windows-clipboard diagnostics require `--clipboard windows --arm`, a separate
baseline and explicit one-frame confirmation override. Follow
[Windows validation](docs/WINDOWS_VALIDATION.md); this changes your clipboard. A single
image with the default two confirmations will only report `confirming`.

## Benchmarks and layout

Use the same replay manifest with `--threads 1`, `--threads 2`, or `--threads 4` and
`--scale 1`, `--scale 2`, `--scale 3`. `--provider cpu|cuda|directml` checks the requested
provider and actual warmed sessions, failing on unavailable providers. CPU is the only
validated environment here. GPU testing requires a separate compatible ONNX Runtime
environment; never mix runtime distributions or interpret silent CPU fallback as GPU speed.
File replay measures sequential offline processing, not captured-frame-to-clipboard latency.

| Path | Purpose |
|---|---|
| `src/stream_code_capture/` | Domain types, ROI/OCR, policy, pipeline, clipboard, latest slot, CLI, generator |
| `tests/` | Headless policy/ROI/clipboard/handoff tests and opt-in real offline OCR |
| `scripts/` | PowerShell setup/check commands |
| `docs/PROJECT_SPEC.md` | Requirements, architecture, timing definitions, risks and pass/fail gates |
| `docs/WINDOWS_VALIDATION.md` | Live commands, native clipboard diagnostics and remaining qualification |
| `docs/PHASE1_VALIDATION.md` | Real-capture results, regressions, timings and current limitations |
| `docs/VALIDATION.md` | Actual commands, measured results, limitations and dependency references |
| `AGENTS.md` | Rules for future engineering phases |

The native functional path and automated Windows failure probes have passed fixture tests.
The arena-disabled fixture soak passes the memory gate; arena-on growth, the performance
tradeoff and broader physical display matrix remain unresolved. Limited-scope manual paste
checks are signed off; G3 exact accuracy and <100 ms latency remain blocked, and full G4
is incomplete. See [manual steps](docs/WINDOWS_VALIDATION.md). No commit or push is
performed by setup or checks.
