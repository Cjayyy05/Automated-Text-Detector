# Instant Stream Code Capture

Python 3.12 / Windows 11 application for recognizing a transient promotional code
**inside video pixels**, within a user-selected chart region, then copying it for
manual redemption. No DOM scraping, cloud OCR, redemption or mouse automation.

## v0.2.0

Discount and Game use the same single-observation policy. A static reveal can copy on its
first eligible OCR read. The detector preserves case and accepts O and 0 as read. The
live frame-age limit is 3 seconds. Both profiles use baseline suppression, one copy
per explicit arm, and exact native clipboard readback. The Windows GUI provides ROI
selection, decision diagnostics, and optional custom WAV notifications. The
[Livestream Code Simulator](#livestream-code-simulator) provides timed, formatted
text reveals for testing.

The operator reported a **PASS** for native Windows clipboard copying on the build
prepared as v0.2.0. The existing personal-use native GUI scope is center primary output 0,
1920 × 1080, 100% scale, SDR, local Windows console and fixed display topology.
[Operator result](docs/WINDOWS_VALIDATION.md#v020-operator-clipboard-test)

In paired replay, exact copies increased from 52 to 78 across 111 positive cases.
The revised policy also copied 15 wrong transcriptions and wrote in 3 of 37 negative
cases. O/0 errors and tiny or compressed text remain limitations. The three strict
challenge xfails, representative livestream accuracy, broader display qualification,
and the sub-100 ms latency goal remain open.
[Detection policy validation](docs/DETECTION_POLICY_VALIDATION.md)

## v0.1.0 baseline

The baseline introduced offline image and replay tools, live DXcam capture, Discount
and Game profiles, and the PySide6 GUI. The earlier Windows sign-off included 30 manual
native paste matches and later Discount and Game GUI paste smoke checks.
[Baseline validation](docs/BASELINE_VALIDATION.md) · [G2 sign-off ledger](docs/PHASE52_MANUAL_RESULTS.md) ·
[Phase 6 GUI validation](docs/PHASE6_VALIDATION.md)

The offline and **live DXcam console pipelines** use real local RapidOCR models. Phase 5's
native screen-test matrix made 160 correct copies with matching clipboard readbacks and
48 O/0 abstentions; it observed zero incorrect or stale-frame writes. The two-profile
Windows failure/recovery probes passed 14/14. These are fixture-based functional results,
not production readiness. Tiny compressed O/0 recognition
remains unresolved, and measured live event latency is well above 100 ms. See
[Phase 2 measurements](docs/PHASE2_VALIDATION.md), [Phase 1 validation](docs/PHASE1_VALIDATION.md)
and the [foundation record](docs/VALIDATION.md).

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
confirmation rules describe that experiment. The fixture results leave representative
accuracy and <100 ms qualification open. See
[Phase 4 measurements and short-exposure tests](docs/PHASE4_VALIDATION.md).

[Phase 5 native qualification](docs/PHASE5_VALIDATION.md) records the explicit Windows
comparison, failure probes and negative monitoring. The native harness requires
`--native-clipboard`; omitting it keeps writes in memory. The application now rechecks
the accepted frame's freshness immediately before the clipboard handoff, including after
waiting for the control/write lock. Those Phase 5 runs used a 1000 ms age limit.
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

## Livestream Code Simulator

From the repository root, with the PySide6 GUI dependency installed, run:

```powershell
.\.venv\Scripts\python.exe scripts/livestream_code_simulator.py
```

Enter any multiline text in the single editor and choose its font, size, style, colors,
and alignment. Formatting applies to the whole draft. Press **Start** to hide the draft
for the selected countdown (five seconds by default). The same window displays the
formatted text when the countdown ends. **Reset** or **Esc** returns to the draft.
Press **Reset** in input mode to clear the draft and restore the defaults.

Run the detector separately and point its ROI at the simulator's display area. Start
the countdown before collecting the detector's baseline so the draft is hidden. The
simulator appends UTC and monotonic timestamps to
`artifacts/livestream-simulator-reveals.jsonl` without saving the text. The timestamps
mark the Qt display transition. One fresh frame can trigger confirmation.

## Detection profiles

`--profile discount` is the default. Both profiles accept 6–24 ASCII characters with
at least one letter and digit. Game also accepts internal hyphens. An explicit code
label or nearby offer can support short codes and codes with the letters and digits
in separate blocks. A standalone token needs at least eight characters, two digits,
and a digit between letters. This filters common username shapes, at the cost of some
bare codes. OCR confidence and source-size floors apply to each candidate. Game also
recognizes nearby redemption or expiry text. [Earlier Discount layout results](docs/DISCOUNT_LAYOUT_VALIDATION.md)

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

OCR can still misread characters at high scores, including O and 0, or treat a
code-shaped ID as a redemption code. Two different eligible strings in the same
observation cause the detector to wait. The three strict tiny-text challenge xfails
remain. [Detection policy validation](docs/DETECTION_POLICY_VALIDATION.md)

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

`--activity-gate-ms 100` is an opt-in scheduling experiment. Bright neutral text changes
trigger an immediate scan. The newest deferred frame receives a scan after 100 ms when
the consumer is available, even if it stays static. Continuous candle motion cannot reset
this deadline.
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
2. Wait for `ready` after at least 500 ms of disarmed baseline collection. A healthy static
   region can use its initial recognized image. Moving regions need two current reads
   across the interval, and the code sets may differ. The GUI shows baseline progress.
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

The default freshness budget is 3000 ms (`--max-frame-age-ms`). Small ROIs
help. Large regions keep full-frame text detection and may reuse pixel-identical
recognition batches containing only unrelated text. Dense, changing text can still
exceed the deadline. See [armed ROI measurements](docs/ARMED_ROI_VALIDATION.md).
Native success requires an exact Unicode readback. Write or readback failure disarms
and requires an explicit rearm.

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
budget; `--age-budget-ms 3000` uses the live default age budget.

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

The source quality floor is 10 original image pixels per character, measured along
the detector box's top edge. Each candidate must also score at least 0.96.
Diagnostics preserve OCR text, including rejected readings. The detector never repairs
or normalizes the extracted text.

An intentional image-to-Windows-clipboard test needs `--clipboard windows --arm` and a
separate baseline image. The command can write on the first eligible observation.
[Windows validation](docs/WINDOWS_VALIDATION.md#available-now-file-pixels-to-real-clipboard)

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
