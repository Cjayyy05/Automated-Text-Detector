# Windows manual validation

The v0.1.0 baseline earned G2 sign-off for the limited center-primary-display
personal-use scope, including 30 manual paste matches. Subsequent Discount/Game GUI
paste smoke checks are recorded in [Phase 6](PHASE6_VALIDATION.md). G3 and full G4 remain
incomplete. Earlier pending entries below are historical procedures/checkpoints; use the
[sign-off ledger](PHASE52_MANUAL_RESULTS.md) and [baseline review](BASELINE_VALIDATION.md)
to distinguish completed, deferred and still-unqualified checks.

These procedures distinguish **file input**, **real clipboard**, and **real capture**.
Unit tests and replay never alter the Windows clipboard and need no display.

## v0.2.0 operator clipboard test

**PASS (operator-reported), recorded 2026-11-18 MYT.** The operator manually tested
the current detector with native Windows clipboard copying, reported that it worked
correctly, and approved the current detection behavior for v0.2.0. The profile,
input, display, copy count and latency are unrecorded. Broader G2, G3 accuracy and
latency, and full G4 qualification remain open.
[Detection policy validation](DETECTION_POLICY_VALIDATION.md)

## Verify v0.2.0 on Windows

1. On the supported primary display, open two PowerShell windows at the repository
   root. Launch the simulator in one and the detector in the other.

   ```powershell
   ./.venv/Scripts/python.exe scripts/livestream_code_simulator.py
   ./.venv/Scripts/python.exe -m stream_code_capture.gui
   ```

2. In the simulator, type a throwaway mixed-case token of eight or more characters
   with letters interleaved with two or more digits. Include both uppercase O and zero.
   Use a readable font at 34 pt and a countdown long enough to select the region and arm,
   such as 20 seconds. Optionally put `Use code:` before the token on the same line.
3. Press **Start** on the simulator to hide the draft. In the detector, select Discount,
   load the preview, choose the simulator's text area, and click **Start**. Wait for
   **Ready**, then click **Arm** before the countdown ends. Leave the screen still.
   The new result should appear once and the detector should disarm. Compare every
   character, including case, O and zero. Dry-run uses the memory clipboard.
4. Rearm while the same code is visible. Reveal that same token again and verify that
   it cannot copy twice. With a fresh detector session, show a token during baseline
   collection, then arm and reveal it again. It should be suppressed. Then try a new
   token, a plain sentence, a price, a timestamp, and a username with a leading `@`.
   Repeat in Game with a new code containing an internal hyphen.
5. To test native delivery, stop the dry run. In a new detector session, enable
   **Use Windows clipboard for this session** and accept the warning. Repeat the static
   reveal. Paste into a text editor and compare every character. Select a custom WAV
   if you also want to verify the copy notification. A success should disarm and
   keep the same token suppressed after rearm.
6. Try a larger region with motion. Record misses, wrong strings and unexpected writes.
   Disarm or Stop while OCR is in flight and check that no write starts after the
   control is accepted. Logs distinguish frame age from the simulator's display
   transition. For the measured replay and captured tests, see
   [detection policy validation](DETECTION_POLICY_VALIDATION.md).

**Start here for Phase 5.2:** follow the [numbered manual checklist](PHASE52_MANUAL_CHECKLIST.md)
and copy the [blank results template](PHASE52_MANUAL_RESULTS.md). It targets the read-only
detected three-monitor 1920x1080, 100%/125% SDR configuration without changing Windows
settings. [Current status](PHASE52_VALIDATION.md) separates inventory, historical automated
evidence and still-unperformed manual checks. Do not rerun the long Phase 5/5.1 commands
below unless a new finding specifically requires it. Native tests remain explicit opt-in.

## Phase 5.1 arena comparison

See [PHASE51_VALIDATION.md](PHASE51_VALIDATION.md) for the allocation investigation and
paired results. Run one test at a time on an unlocked desktop with the primary display
active and the test region unobscured. Disable competing OCR jobs; record power mode and
whether running on battery. Lock, sleep, a blank capture or an incomplete schedule invalidates
a paired latency comparison even if it reports zero wrong writes. The driver now aborts
on these failures; retain failed artifacts and retry complete pairs in a new directory.

```powershell
# Fresh-process offline allocation diagnostics: no windows or clipboard writes.
./.venv/Scripts/python.exe scripts/phase5_memory.py --cpu-arena --report artifacts/manual-arena-on-memory.json
./.venv/Scripts/python.exe scripts/phase5_memory.py --no-cpu-arena --report artifacts/manual-arena-off-memory.json
# Real capture, memory clipboard by default. This explicitly opens a test surface.
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --suite matrix --comparison arena --output artifacts/manual-arena-memory
# Explicit native opt-in: this replaces clipboard contents and checks readback.
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --native-clipboard --suite matrix --comparison arena --output artifacts/manual-arena-native
./.venv/Scripts/python.exe scripts/analyze_arena.py artifacts/manual-arena-native --output artifacts/manual-arena-analysis.json
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --no-cpu-arena --report artifacts/manual-arena-off-recovery.jsonl
# Both profiles, real screen capture, memory clipboard only, unchanged 50 MiB limit.
./.venv/Scripts/python.exe scripts/negative_soak.py --show-window --no-cpu-arena --seconds 1800 --report artifacts/manual-arena-off-soak.jsonl
```

The public live/playback CLI disables arena by omitting `--cpu-arena`; the historical
memory/soak/recovery diagnostics use `--no-cpu-arena` to explicitly override their retained
arena-on defaults. Compare scale 1, four threads, disabled spinning and detector limit
640 for both sides. Do not compare this with the slower public defaults and attribute
all differences to arena. Actual warmed ONNX options are included in the new reports.

The matrix intentionally retains O/0 inputs and returns exit 1 when exact recall fails.
Inspect recall, missing indexes and capture completion alongside wrong/late/readback
failures. `analyze_arena.py` audits identical schedules, ROI, model hashes, versions and
session settings, and refuses interrupted pairs. Latency percentiles cover successful
copies only; misses are separate. `--cohorts` permits complete-pair retries, and
`--reverse-pairs` reverses order without changing test inputs. Keep all repeat results.

The optional `scripts/qualification_awake.py --request-display --seconds 3600 --stop-file
.tmp/manual-awake.stop --report artifacts/manual-awake.jsonl` holds a temporary execution
request in a separate terminal. Use new paths and create the named stop file after testing;
verify its `released` event. It changes no power plan and does not prevent manual locking
or sleep. Timeout is checked while the helper process is running, not while suspended.

Manual paste, physical display/DPI/source-change tests and representative independently
labelled stream samples below remain required even after a passing arena-off soak.

## Phase 5 repeatable native qualification

See [PHASE5_VALIDATION.md](PHASE5_VALIDATION.md) for the current evidence and outstanding
gates. The commands below open temporary test surfaces on the primary display at (50,50)
through (1010,590). Keep that region unobscured. These are screen-stimulus tests, not
representative livestream accuracy. Use a new output path each time.

```powershell
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --suite smoke --output artifacts/manual-phase5-smoke
./.venv/Scripts/python.exe scripts/phase5_qualification.py --show-window --native-clipboard --suite matrix --output artifacts/manual-phase5-native
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --report artifacts/manual-phase5-failures-memory.jsonl
./.venv/Scripts/python.exe scripts/windows_failures.py --show-window --native-clipboard --report artifacts/manual-phase5-failures-native.jsonl
./.venv/Scripts/python.exe scripts/negative_soak.py --show-window --seconds 1800 --report artifacts/manual-phase5-negative.jsonl
```

The native flag intentionally replaces the clipboard with generated codes; preserve any
needed content before running it. Defaults are memory-only. Native success requires exact
CF_UNICODETEXT readback and accepted-frame completion age <=1000 ms. The matrix records
40 generated appearances per profile/configuration at 2000 ms (including ten intentional
O/0 cases), optimized short exposures and both configurations on the eight reused screenshots.
Intentional abstentions still fail its full-recall result; require zero incorrect, mismatched
or late writes independently. Do not silently change the assertions to make this matrix green.

The failure harness uses real OCR and captures, with test-only urgent commands, a frozen/
black stimulus and a separate process holding OpenClipboard with an explicit hidden owner
window. A null-window holder was ineffective on the qualification host. Require every `probe_result`
to pass; the normal session must fail closed for black/stalled input. Expected faults are
not successful detection events. Contention must disarm without a copy commit or automatic
retry; only the test controller explicitly rearms for a fresh code after releasing the lock.
The negative soak is always memory-only. Require the full requested duration, both profiles
armed, no error/write attempt, and bounded memory; early termination is a failed soak.

These scripts do not operate the lock screen or change monitor/DPI settings. Complete the
physical display, manual-paste and source-identity checks below separately. Run one visible
test at a time, with no other OCR benchmark competing for CPU or obscuring the fixture.

Phase 4 adds the explicit `scripts/phase4_playback.ps1 -ShowPlayback` matrix, with generated
250/500/1000/2000 ms exposures, actual painted-duration traces and memory-only writes. See
[PHASE4_VALIDATION.md](PHASE4_VALIDATION.md) for exact commands, failed recall gates and
comparable baseline/configuration results. `-DrainMs 1000 -PreciseStimulus` removes premature
test-controller disarm and improves stimulus pacing without changing runtime freshness.
These new captured simulations do not satisfy native clipboard or real-broadcast gates.

Phase 3 file preparation/evaluation is documented in `DATASET_WORKFLOW.md`. It launches no
stimulus windows and offers no native clipboard option. No new real-capture or native test
was performed in Phase 3; the numbers below and in Phase 1/2 are preserved historical evidence.
Only run visible test harnesses when intentionally requesting their test surfaces. Native tests
require the explicit `--clipboard windows` command and replace clipboard contents: preserve
anything needed yourself first. There is no automatic clipboard restore that might overwrite
an intervening user copy. Real footage and independent labels are still missing.

## Game profile: subsequent simulated capture check

The subsequent [game-profile validation](GAME_PROFILE_VALIDATION.md) exercised real DXcam
with the eight imported game screenshots on a temporary playback surface and a memory-only
clipboard. Narrow-ROI runs copied 8/8 and 7/8, with zero wrong/repeated/negative writes.
This is simulated slide playback, not real livestream qualification; no new native clipboard
test was performed. Run the test explicitly from an interactive Windows desktop:

```powershell
./.venv/Scripts/python.exe scripts/game_playback.py datasets/gamecode_starter/GameCode_OCR_StarterPack/session_split.json --seed 20261103 --roi 200 400 960 540 --report artifacts/manual-game-playback-new.jsonl
```

Keep the primary-display area `(50,50)` to `(1010,590)` unobscured. The ROI above is relative
to this fixture window. Expect ten captured events, eight correct memory writes, zero wrong
or repeated writes, `passed: true` and exit 0. A miss remains a failed run even if latency
for the successful subset is good. Phase 5 added an explicit `--clipboard windows` option;
the historical game-profile runs above were memory-only.

For actual game video, use the existing live CLI with `--profile game` and select an ROI
containing the code and its nearby expiry/redemption label; do not assume fixture coordinates:

```powershell
./.venv/Scripts/python.exe -m stream_code_capture live --profile game --roi 300 250 1060 390 --dry-run --report artifacts/manual-game-stream-new.jsonl
```

Replace these example screen coordinates. Enter `start`, wait for `ready`, then `arm`.
Rearm explicitly after a successful copy; use `disarm` before moving the video and `stop`
to finish. Game uses the baseline OCR model. The v0.2.0 policy accepts 6–24 ASCII
characters with letters and digits, including optional internal hyphens. Mixed case
and O/0 are preserved.
Native testing still requires explicitly replacing `--dry-run` with `--clipboard windows`,
then manually pasting/comparing results locally. Complete the G2 matrix below before GUI
development; no automatic redemption or submission is part of any test.

Historical Phase 1 evidence includes 3/30-event dry-runs and three native readbacks.
Phase 5 adds 160 correct native copies in 208 appearances, with 48 O/0 abstentions,
zero wrong/mismatched/late writes, and 14 passed Windows failure/recovery probes.
See `PHASE5_VALIDATION.md` for the extended negative-run result and memory issue.
Physical monitor/DPI/lock/hotplug tests and manual paste comparisons remain unverified.

## Live console procedure (implemented)

Run from an interactive PowerShell desktop session, with the video visible on the PC.
Choose a physical-pixel chart ROI relative to the selected DXcam monitor. Exclude the
banner/chat and do not move the source window while armed. To list outputs:

```powershell
./.venv/Scripts/python.exe -c "import dxcam; print(dxcam.output_info())"
```

Replace the illustrative ROI with your actual chart coordinates:

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
./.venv/Scripts/python.exe -m stream_code_capture live --roi 300 250 840 415 --output 0 --dry-run --report artifacts/manual-dry.jsonl
```

Enter `start`, wait for `ready`, then enter `arm`. Require `would_copy` only for a new
chart code; verify the OS clipboard remains unchanged. `disarm` prevents pending OCR
results from writing. `status` reports state; `stop`/Ctrl+C exits and releases DXGI.
The report file must be new. Closed stdin stops the process. `--start` skips only the
start command, not baseline or arming; `--duration 60` imposes a stop deadline.

For the native path, preserve clipboard content you need and repeat with
`--clipboard windows` instead of `--dry-run`. Explicitly `arm` after `ready`, then manually
paste into Notepad and compare every character. Never auto-redeem. Success disarms and
remembers the code for this process; rearming must not recopy it. Stop starts a new session
only by launching the command again. A new process has a new in-memory deduplication set.

The v0.2.0 default age limit is 3000 ms. If baseline frames are stale, narrow the chart ROI and
inspect timings. Do not silently enlarge it to pass a performance gate. A 100 ms limit
currently prevents useful operation; the under-100 ms target is not achieved.
DXcam initialization is allowed up to 10 seconds. The capture-poll watchdog starts afterward.

## Repeatable real-screen test harness

`scripts/live_smoke.py` is an opt-in test surface, not a product GUI. It renders generated
scenes in a temporary 960x540 window at primary-screen (50,50), captures a 540x165 chart
ROI through real DXcam, and closes the window after the run. It never feeds generator
pixels directly to OCR. Keep that primary-screen region unobscured, at >=1010x590 usable
resolution. Do not interact with the test surface. The surface stays visible until each
event copies; this tests functionality, not 100 ms appearances. The test stops on timeout.

```powershell
./.venv/Scripts/python.exe scripts/live_smoke.py --report artifacts/manual-screen-dry.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --report artifacts/manual-screen-native.jsonl
./.venv/Scripts/python.exe scripts/live_smoke.py --count 30 --seed 31 --report artifacts/manual-screen-30.jsonl
```

The native variant deliberately writes test codes, and verifies CF_UNICODETEXT readback.
Only readback retries a transient clipboard lock (up to one second); app writes do not retry.
A test-only pixel marker identifies the first captured code frame before the capacity-one
handoff can drop it. Marker/code coordinates exist only in the test harness, never in live
recognition or policy. The final `test_result.passed` must be true and process exit must be 0.

## Available now: file pixels to real clipboard

1. Run `./scripts/setup.ps1`, then `./scripts/check.ps1 -Ocr`. Generate `samples/manual`
   using seed 7, count 3. Open its `manifest.json` and note the first expected code.
2. Preserve any clipboard content you need. Open Notepad yourself for manual paste.
3. Run the disarmed image command first. It must show `disarmed`; clipboard stays unchanged.
4. The following explicitly armed diagnostic uses a tighter chart ROI that includes the
   generated first code and context, but no banner/chat. These are **fixture coordinates**,
   not runtime defaults. The policy can confirm from this single image:

```powershell
./.venv/Scripts/python.exe -m stream_code_capture generate samples/manual --seed 7 --count 3
./.venv/Scripts/python.exe -m stream_code_capture image samples/manual/case_000_1.png --roi 70 170 420 300
./.venv/Scripts/python.exe -m stream_code_capture image samples/manual/case_000_1.png --roi 70 170 420 300 --baseline samples/manual/case_000_0.png --arm --clipboard windows
```

5. Require `status: copied` and manually paste into Notepad. Compare every character to
   ground truth. A `stale`, `no_candidate` or clipboard-error result is a failed diagnostic,
   not permission to claim a live success. Record output, hardware, timing and exact paste.
6. Repeat with another generated seed and choose its ROI from the actual image. No hardcoded
   code strings may enter the recognizer. Each CLI process is a new session; repeat suppression
   across frames/rearm is tested by replay and unit tests, not across CLI processes.
7. Clipboard contention: in an isolated test, hold the clipboard open in another test
   process, then run the armed diagnostic. Expect failure, no copied-state commit and
   disarming. Release the lock. Do not assume previous content survives an Empty/Set failure.

This procedure is **not automatically run** by repository checks. Native clipboard behavior
and contention have automated Phase 5/5.1 evidence; the required manual paste comparisons
remain unperformed. The image diagnostic covers file input. Use the real-capture checks above
to verify the live path.

## G2: remaining qualification matrix

Use the implemented live command above and retain its JSONL report. The full gate requires:

1. Display a locally rendered video/fixture sequence on the Windows PC. The source must
   be actual on-screen pixels, not directly loaded frames handed to OCR. Use varied codes
   and positions, persistent banner, chat, moving candles; independently record appearance
   times and truth. For streaming validation, play permitted video visibly on the PC.
2. The CLI enables per-monitor DPI awareness. Choose monitor and physical chart ROI via
   arguments; review recognized boxes while disarmed. A visual picker is not implemented.
3. Current capture uses `grab(copy=True, new_frame_only=True)` on a dedicated DXGI owner
   thread. Acquisition-start/finish are measured in the local monotonic clock. Identical
   ROI images are discarded; no cached frame counts as a fresh confirmation. Confirm the
   expected physical ROI at 100/125/150/200% DPI and on each monitor. No cursor automation.
4. Warm detector and recognizer; collect >=500 ms stable disarmed baseline; show ready.
   Explicitly arm. Feed real captured ROI BGR arrays to `Pipeline` (ROI then spans the
   already-cropped frame). No direct generator-to-pipeline shortcut satisfies this gate.
5. Observe 30 varied appearances. For each copy manually paste/compare all characters.
   Never auto-redeem. Require one copy per arm, no repeat after rearm for the same code.
   Require zero disarmed, banner/chat and negative-only copies during a 30-minute run.
6. Deliberately slow OCR. Confirm at most one pending frame, increasing dropped count,
   newest available frame after inference, and stale-frame rejection. A stale result
   must not overwrite a newer clipboard decision. Record capture-side first-visible
   acquisition timestamps even when that frame gets dropped.
7. Exercise stop, disarm mid-inference, lock/unlock, display resize/DPI/monitor change,
   genuine access loss and busy clipboard. Require fail-closed behavior and a fresh
   baseline and explicit rearm after capture invalidation. Minimize/restore and
   occlusion follow the approved screen-region scope below.
8. Save stage events, t0-to-clipboard latency, CPU/GPU/provider info and model hashes.
   G2 proves functionality, **not** <100 ms. Execute the larger G3 accuracy/latency matrix
   from PROJECT_SPEC before making either production claim.

Concrete remaining checks:

- Negative soak: play a 30-minute chart-only/chat/banner sequence while armed. Expected:
  zero `copied`/`would_copy`; any such event fails. Re-arm only after investigating a copy.
- Stop/disarm race: arm, then issue `disarm` or `stop` while inference runs. Expected: no
  write begins after that command is accepted; report disarmed/summary. A write already
  completed before command acceptance cannot be undone.
- Clipboard contention: run the explicit `windows_failures.py --show-window
  --native-clipboard --report artifacts/manual-failures-new.jsonl` command above. Its
  separate helper process owns a hidden window and holds the clipboard until the failed
  write is observed, then releases it before explicit rearm. Expect `clipboard_failed`,
  disarmed, no retry and no copied-set commit, followed by a correct recovery readback.
  Do not use the previous null-window OpenClipboard one-liner as proof of contention:
  it did not effectively block writing on this host.
- Capture loss: lock/unlock Windows and disconnect/reconnect a secondary monitor.
  Expected: capture stops on error, recovery warning or capture-poll timeout;
  no subsequent write until a fresh process/baseline/arm. Actual lock/unlock/hotplug is untested.
- Window minimize/occlusion: the selected monitor rectangle remains the source while
  capture is healthy. A covering window can supply a code eligible for native copying.
  Disarm before moving, covering, or minimizing the intended content. If a transition
  invalidates capture, the genuine capture-loss requirement applies. The original
  moving-occlusion failure is preserved in the manual ledger. No repeat is required
  under the approved scope.
- GUI native clipboard mode requires full G2 qualification, a clear warning that eligible
  codes from covering windows can be copied, and explicit user opt-in.
- Repeated code: show the same code again after a successful copy and rearm. Expected:
  no repeated write. A different eligible code needs a fresh observation.
- Shutdown: Ctrl+C during OCR and when the video is static; expected prompt return after
  in-flight OCR exits, no later write, and capture cleanup. Native inference is not forcibly
  interrupted. The producer join is bounded to three seconds and reports a cleanup failure.

If a video is protected/black in capture, report unsupported input and disarm. Do not
attempt DRM bypass. A phone screenshot does not validate Windows screen capture.

## Phase 2 comparison and manual release gates

The Phase 2 settings and observations below describe that earlier revision.

Read [PHASE2_VALIDATION.md](PHASE2_VALIDATION.md) before interpreting experimental profile
results. The target is first **captured code-containing frame** to successful native write,
not OCR time or the first frame the recognizer happened to accept. O/0 strings in those runs
abstained, even if their confidence is high; this is an intentional safety limitation.

The final `--fallback-baseline` mode also verifies eligible fast candidates against a wider
crop using the warmed baseline recognizer. Disagreements abstain, with both raw strings and
scores recorded. Tiny-only and v4 native modes are refused by the public CLI. This reduces
known errors but does not establish production safety; the final native three-event sample
was slower than Phase 1. See the final-results section of the Phase 2 record, not its earlier
pre-verification timing table.

From an interactive PowerShell in the repository, provision optional local models once:

```powershell
./.venv/Scripts/python.exe scripts/provision_models.py
./scripts/check.ps1 -Ocr
./.venv/Scripts/python.exe scripts/live_smoke.py --count 30 --seed 31 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/manual-fast-dry.jsonl
```

Keep the visible test surface unobscured; do not move/resize it. Expected: 30 exact memory
copies, zero incorrect copies and zero abstentions for this standard fixture. This generated
alphabet excludes ambiguous glyphs and is not the varied full-alphabet accuracy gate. The
test displays each code until copied. Use a new report filename on every run.

Then intentionally test native writes (this replaces the clipboard with generated codes):

```powershell
./.venv/Scripts/python.exe scripts/live_smoke.py --clipboard windows --count 3 --seed 7 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/manual-fast-native.jsonl
```

Expected: three exact codes and three matching CF_UNICODETEXT readbacks. Readback retries
are test-only reads, never application write retries. Manually paste the final clipboard
into a local text editor and compare with the report. Repeat with 30 native events for G2;
three successful writes are a smoke check only. Always check `failure`, exact copies,
incorrect writes and abstentions, not just latency of successful cases.

For a **nominal** 100 ms single-event exposure probe:

```powershell
./.venv/Scripts/python.exe scripts/live_smoke.py --count 1 --seed 31 --visible-ms 100 --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/manual-short-exposure.jsonl
```

The stimulus loop can overrun the nominal exposure; this is a smoke probe, not a calibrated
100 ms presentation guarantee. Missing a code is an explicit failed test/abstention, not
an excluded latency sample. Native writes remain disabled unless explicitly requested.

For the user's real stream, select a chart ROI in physical monitor coordinates and run:

```powershell
./.venv/Scripts/python.exe -m stream_code_capture live --roi 300 250 840 415 --dry-run --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/manual-stream-dry.jsonl
```

Replace those illustrative ROI coordinates with the actual chart; exclude banner/chat.
Enter `start`, wait for `ready`, then `arm`. Check at least 30 manually labelled new
appearances, including O/0, I/1, B/8, small/slanted text, compression, colored text and
candle crossings. Re-arm after successful copy. A persistent code must be in the disarmed
baseline, never newly copied; disarm while changing the ROI/window/source. Record misses
as well as exact copies. Ordinary session reports cannot independently timestamp a target
that every OCR observation missed. Use labelled source video/capture annotations for G3.

Compare `baseline` and tiny/cascade on identical playback/input settings. Compare the
activity gate with and without `--activity-gate-ms 100`, including colored/dim codes and
continuous candle motion; it must not suppress scans indefinitely. Keep it off if it adds
unacceptable appearance delay. Do not change confidence, confirmations or freshness limits
to manufacture a faster result.

Still required: independent broadcast holdout (>=1000 appearances, >=10000 negative
frames), zero wrong writes, required exact recall, the project's p95/p99 latency gates,
a passing memory-growth gate, manual paste, monitor/DPI/lock/hotplug/HDR/rotation/occlusion
matrix. Phase 5 verified native contention with an explicit clipboard-owner helper; its
full negative-run evidence is recorded separately. No GPU backend has been benchmarked; install a compatible
backend in a separate pinned environment and run the same accuracy and latency protocol
before comparing it. These requirements are unverified, not assumed passes.
