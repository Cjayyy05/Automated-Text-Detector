# Phase 6 GUI and G4 validation

## Successful-copy sound

An unchecked-by-default **Play sound when code is copied** checkbox enables the Windows
SystemAsterisk notification, or the selected local WAV, for native sessions. Each committed native copied event is
identified by its frame sequence and acquisition timestamp. The notifier consumes that
identity once and starts a background worker. It reads CF_UNICODETEXT once and compares
the literal value with the copied code before initiating asynchronous playback.

Dry-run events, failed writes, stale/duplicate decisions and stopped/disarmed notification
work are silent. The generation check cancels pending playback after an explicit control
change. Automatic one-shot disarming after a successful commit still permits the sound.
Clipboard mismatch, clipboard contention or unavailable audio skips the notification,
logs the reason and never retries a write or changes the committed detection.

Verification occurs after the successful clipboard operation and outside the detection
thread. Playback uses `winsound.PlaySound("SystemAsterisk", SND_ALIAS | SND_ASYNC |
SND_NODEFAULT)`, following the
[Python 3.12 winsound API](https://docs.python.org/3.12/library/winsound.html).
No audio device or Windows sound setting is changed by the app.

Changed files are `notifications.py`, `gui.py`, `tests/test_notifications.py`,
`tests/test_gui.py`, README and this record. Automated tests inject clipboard/audio
functions and cover asynchronous verification ordering, exact readback, duplicate event
suppression, ineligible events, cancellation, read/audio failures and GUI option routing.

Windows audible playback verification is **PENDING**. Run one controlled, newly generated
code appearance on the approved center monitor. Enable the sound checkbox and explicitly
consent to native copying. Start, wait for Ready, Arm and reveal the code once. Expect
one confirmation, automatic disarm and one short sound. Paste into Notepad and compare
the exact string. Leave the same code visible and verify no second sound occurs.

Validation commands passed:

- `./scripts/check.ps1` — 170 passed, 13 opt-in OCR skips, 41.61 seconds.
- `./scripts/check.ps1 -Ocr` — 180 passed, three existing challenge xfails,
  56.39 seconds. Output saved in `artifacts/copy-sound-check-ocr.txt`.
- `python -m pytest -q tests/test_gui.py tests/test_notifications.py` — 29 passed
  in 5.47 seconds after simplifying the GUI option forwarding.
- Final Ruff lint/format and strict mypy passed over 20 runtime source files.

Existing recognition, native-copy consent/scope checks and clipboard write code are
retained. The new readback is solely for notification eligibility and performs no writes.

### Custom local notification sound

Choose sound opens a WAV file picker and validates that the selected file contains
readable PCM WAV audio. The GUI stores only its path using per-user QSettings. The
Default button clears it. An unavailable saved file is labelled in the GUI and playback
falls back to SystemAsterisk. Invalid new selections preserve the previous preference.
Settings write failures leave the sound selected for the current run and display an error.
Native consent is still reset per session, independently of the sound-path preference.

Test sound uses a separate background Qt job and asynchronous Windows file playback.
It works while monitoring is stopped, without initializing OCR or reading/writing the
clipboard. It is an explicit audio preview and does not depend on the automatic-sound
checkbox. Completion leaves session options intact. Close requests cancellation and waits
for the background call to return. Verified-copy notification uses the session's captured
sound-path preference with the existing event deduplication and cancellation checks.

The source page lists Success software tone. The user downloads and selects it locally.
No third-party audio file was downloaded, copied into the project, or bundled.
[Mixkit tones page](https://mixkit.co/free-sound-effects/tones/)

Automated coverage uses generated temporary WAV fixtures, isolated settings files and fake
audio APIs. It covers custom/default playback flags, missing/invalid files, playback
failure fallback, custom paths after verified readback, choosing/reloading/resetting a
preference and preview isolation. An initial direct pytest run hit sandbox temp-directory
setup failures. The approved rerun passed 37 focused tests in 5.23 seconds. Initial
formatting/type issues were corrected before repository checks.

Manual Windows test is **PENDING**. Download Success software tone to a personal folder
and ensure it is a PCM WAV. Launch the GUI, choose that WAV and click Test sound.
Close and reopen the GUI to confirm the filename is retained. Then use the existing
controlled source for one consented native copy. With the sound checkbox enabled,
expect one selected sound after the verified copy, matching Notepad paste and automatic
disarm. Leave the code visible and require no duplicate sound. Existing native display
restrictions and G3/G4 limitations remain applicable.

Final custom-sound checks both exited 0. `./scripts/check.ps1` reported 178 passed
and 13 opt-in OCR skips in 42.25 seconds. `./scripts/check.ps1 -Ocr` reported
188 passed and the three existing strict challenge xfails in 58.29 seconds.
Dependency checks, Ruff lint/format and strict mypy over 20 source files passed.
Outputs are `artifacts/custom-sound-check.txt` and
`artifacts/custom-sound-check-ocr.txt`. No audible playback or native clipboard
operation was performed by these automated checks.

## Static-startup real-backend follow-up

Static-screen startup and arming are **PASS (operator-reported)** after the Windows
manual retest below. Existing-code suppression remains manually unverified in this
retest. The previous static-startup fix did not cover slow
baseline OCR expiring its only captured image. On the reported 1336 × 605 ROI, real
Windows DXcam delivered frames, but all eight baseline OCR attempts were discarded as
stale. There were 63 changed captures, 359 identical ROI drops, no accepted baseline
and no Ready event in the 12-second diagnostic. This desktop diagnostic did not control
all visible motion. Evidence is `artifacts/static-startup-real-direct-before-native.jsonl`.

The first CLI attempt terminated on closed stdin before capture began. A direct
LiveSession probe then encountered sandbox DXGI access denial. An approved elevated
retry exercised the actual backend. These attempts are retained separately and are not
successful baseline validation.

Installed DXcam 0.3.0 source confirms that normal idle reads return None and that
`new_frame_only=False` can only reuse an already captured cached image. It does not
force an initial image. Healthy idle polling alone cannot establish readiness without
a recognized, valid baseline image. No cached images were introduced into confirmation.

The live owner now accepts slow baseline OCR only if the capture generation still
matches its input frame and the successful poll heartbeat is fresh. Any intervening
changed frame retains the stale-baseline rejection. The baseline is suppression-only,
and this current-content validation never supplies an armed confirmation. Old queued
frames still fail the pre-OCR age check. Confirmation and native clipboard deadlines
remain unchanged.

The GUI now receives baseline progress events showing changed captures, accepted
observations and the reason for waiting. Reasons distinguish first-frame waiting,
baseline recognition, stability waiting and expiry while pixels changed. Progress is
limited to one idle update per second, plus OCR state transitions.

`scripts/diagnose_static_startup.py --show-window --report artifacts/static-startup-real-fixture-after.jsonl`
was run outside the sandbox with an explicit visible static test surface. It used real
DXcam, the existing local recognizer and memory-only clipboard mode on the same ROI.
It reached Ready at 1191.8206 ms of baseline stability with one accepted observation,
then exited without failure. Later screen captures did change during the run, so this
is evidence for real first-frame delivery and successful startup on a rendered static
surface, not a claim that every captured frame remained identical for the full duration.
No physical Windows settings or native clipboard content were modified by these probes.

Regression coverage adds 1500 ms baseline OCR with and without an intervening pixel
change, and GUI baseline-progress/Ready delivery. Earlier static-startup, preexisting
code suppression, new-code confirmation, pause/resume and capture-fault tests remain.
The operator subsequently completed the static-screen startup and arming retest on
Windows. The originally requested suppression subcheck is not included in that report.

### Windows static-screen manual retest result

2026-11-05 MYT. All results below are **operator-reported**:

- Static screen → Start → Ready: **PASS**.
- Arm button became enabled: **PASS**.
- Armed successfully while the screen remained static: **PASS**.
- No errors or unexpected stopping: **PASS** for the observed session.

No session report or trace was supplied for this manual observation. These results
close the reported static-startup/readiness/arming usability issue within the tested
conditions. They do not establish that an existing eligible code was visible, recognized,
or suppressed. **Existing-code suppression was not manually verified by this retest**.
Its automated regression evidence and earlier separately recorded manual evidence
remain distinct. No new detection, native clipboard, accuracy or latency result is
inferred. G3 and broader G4 qualification remain incomplete.

Documentation-only recording check in the existing Windows Python 3.12 environment:
`./scripts/check.ps1` passed dependencies, Ruff, formatting, strict mypy and 157 tests,
with 13 opt-in OCR skips. No application code or safeguards changed.

Final follow-up checks both exited 0. `./scripts/check.ps1` reported 157 passed and
13 opt-in OCR skips in 41.72 seconds. `./scripts/check.ps1 -Ocr` reported 167 passed and
the three original strict challenge xfails in 58.48 seconds. Dependency checks, Ruff,
formatting and strict mypy over 19 source files passed in both runs. Exact outputs are
`artifacts/static-startup-check-final.txt` and
`artifacts/static-startup-check-final-ocr.txt`. Changed files for this follow-up are
`live.py`, `gui.py`, `tests/test_static_startup.py`, `tests/test_gui.py`,
`scripts/diagnose_static_startup.py`, `docs/PROJECT_SPEC.md`, and this record.

## Static-startup baseline fix

Root cause was confirmed before the implementation change. The producer drops identical
ROI pixels, while live readiness previously required two OCR observations spanning 500 ms.
A region already static at Start therefore produced one baseline observation and remained
unready, even with healthy capture polling.

The owner session now checks baseline stability during an empty handoff wait. A successfully
recognized baseline may become Ready after the configured interval of healthy unchanged
polls, provided every newer changed frame has already been consumed. Baseline suppression
is learned before readiness. The code-confirmation policy receives only actual changed
frames, and keeps its existing freshness and two-observation requirements. Baseline events
report the actual OCR observation count plus the idle-stability reason.

Changed implementation is in `live.py`, with regression coverage in
`tests/test_static_startup.py`. README and specification describe the corrected readiness
semantics. `./scripts/check.ps1 -Ocr` passed dependency checks, Ruff lint/format, strict
mypy over 19 source files, and **164 tests with three existing challenge xfails** in
58.31 seconds. New tests cover static startup using both idle polls and identical pixels,
moving-to-static baseline establishment, suppression of a preexisting code, subsequent
new-code confirmation, exclusion of repeated pixels from OCR evidence, and rejection of
idle readiness with pending changes or a capture fault. Existing capture-loss and pause
tests also passed.

The later Windows manual retest above passes static-screen readiness and arming by
operator report. The originally proposed known-code suppression and subsequent new-code
sequence are not confirmed by that retest and remain unverified for this specific static
startup scenario. Prior consent/shutdown usability passes remain recorded separately.

The Windows PySide6 GUI is available for local user testing. The operator signed off
G2 for the approved limited personal-use scope on 2026-11-05 MYT. Both Discount and Game native
GUI/Notepad smoke checks passed by operator report with exact matching verified against
fixture evidence. G3/G4 release requirements remain outstanding. Existing G2
evidence is tracked in [Phase 5.2 manual results](PHASE52_MANUAL_RESULTS.md).

Current assessment after the combined usability result: **functionally ready for routine,
supervised personal use within the approved center-monitor-only configuration**.
This is a limited workflow-readiness assessment. Representative real-stream accuracy,
the G3 performance gates and full G4 release qualification remain incomplete.

## Launch

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install PySide6==6.12.0
.\.venv\Scripts\python.exe -m stream_code_capture.gui
```

The first command is a one-time dependency installation. The GUI runs local OCR with the
baseline CPU settings. Each Start creates a new session, warms its model and builds a new
disarmed baseline. The existing policy owns confirmation, freshness and deduplication.
The default clipboard target is memory. Native copying requires checking the session
opt-in and accepting a warning at Start. Consent resets when the session finishes or
monitor selection changes.

## Native GUI paste result and remaining G4 requirements

**Discount native clipboard operation — PASS (operator-reported).** The operator
reported pasting `ZES3444LHB` into Notepad using Ctrl+V, automatic disarming after
detection, and no GUI errors. Exact character matching is now **VERIFIED** against
`artifacts/gui-native-smoke-source.json`, which records seed 4051840236, Discount,
and expected `ZES3444LHB`. Re-running the existing renderer with that seed and profile
independently regenerated the same expected string. This confirms the equality of
the expected code and the operator-reported pasted text.

**Game native clipboard operation — PASS (operator-reported).** The operator reported
pasting `ERTWDE5FRR` into Notepad, automatic disarming after detection, and no GUI errors.
The saved record is
`artifacts/gui-clipboard-stimuli/game-00ed8b0104ee4a09aeb5eec3dc725dde.json`.
It records Game, seed 3546502313, expected `ERTWDE5FRR`, and fixture ROI
`320 320 1120 860`. Exact character matching is **VERIFIED** by comparing the saved
expected string with the literal operator-reported paste and independently regenerating
the same string through `phase4_scenes.scenes(seed, 1, "game")`. Automatic disarming,
successful native copying, and no GUI errors remain operator observations.

Game follow-up validation changed documentation only. Fixture regeneration and literal
comparison passed. `./scripts/check.ps1` passed dependency, Ruff, formatting and strict
mypy checks with 149 tests passed and 13 OCR opt-in skips. The prior real-OCR result
of 159 passed and three existing strict challenge xfails remains applicable.

No persisted GUI session log was found. Inspection of `gui.py` confirms that frame
events are forwarded to the UI without a JSONL writer. Consequently, no independent
GUI write/readback trace, timing, exact write count, or shutdown/error event sequence
can be recovered for either GUI smoke session. Successful native operation, automatic disarming,
and no GUI errors remain operator observations. The existing G2 harness reports retain
their independent native-write/readback evidence. No new accuracy or latency claim is
made from this GUI smoke test.

| Remaining item | Current evidence and next requirement |
|---|---|
| Both-profile native GUI pastes | COMPLETE for these smoke checks: Discount and Game operator-reported pastes exactly match saved and regenerated fixture truth. No repeat is needed. |
| Native opt-in and reset UX | PASS by operator report for Cancel leaving monitoring stopped and repeated warnings on retry and stop/restart. Automated tests additionally cover memory-mode reset/default dry-run. |
| ROI editing and session reset UX | Basic editing, updated blue rectangle and coordinates PASS by operator report. Reverse/edge drags, overlay alignment after GUI resizing, and preview reload/reset are not specifically confirmed by that report and remain pending for full G4. Automated mapping/reset evidence is retained. |
| Shutdown during inference in the GUI | Closing while armed and processing in dry-run PASS by operator report, without freezing or visible errors. There is no timing trace proving an exact mid-OCR instant. Existing queued close/cleanup tests and native timestamped Stop/Disarm race probes provide separate evidence. |
| Provider diagnostics in the GUI | Implemented. Shows verified provider, model filenames, capture device/output, physical ROI, clipboard target and errors. Stopped provider/model details are labelled as the last session. Manual visual confirmation remains pending. |
| G4 display and transition matrix | Some 100%/125% monitor checks and lock/unlock pass. 150%/200%, remaining source-resize/transition observations, and full profile-specific coverage remain incomplete for broad G4 qualification. These do not expand the approved center-only native scope. |
| G3 representative accuracy and latency | Held-out representative corpus/independent labels and required accuracy/latency gates remain unmet. O/0 and source-resolution abstentions remain in force. |

The approved limited-scope personal-use native workflow has passing Discount and Game
smoke checks and a passing combined usability observation. The readiness review below
accepts routine supervised use within that scope. Broader
G4 qualification and G3 product-readiness gates remain separate and incomplete. Reuse
existing lock/unlock, pause/resume, control, soak, and recovery evidence without routine
repetition. Physical hotplug remains deferred under the approved G2 substitution.

G4 verdict: **PARTIAL — both native smoke checks and reported combined usability checks PASS; broader UX/display/release qualification pending**.
G3 verdict: **PENDING**. G2 limited-scope sign-off remains in force.

### Controlled Game native GUI test preparation

Launch `./.venv/Scripts/python.exe scripts/gui_clipboard_stimulus.py --profile game`
from the repository root, after stopping any active GUI session and closing the old
stimulus. The helper reuses `phase4_scenes.scenes` and `draw_motion`, generating one
standard-alphabet code from a new random seed. It saves profile, seed, expected string
and fixture ROI in a new exclusive JSON file under `artifacts/gui-clipboard-stimuli`.
Fixture placement is the center-monitor rectangle `320 320 1120 860`, 800 × 540.
The code and context are initially hidden, while a bottom marker supplies movement.
Space reveals the code and prints the expected string; Escape closes the stimulus.

Select Game, center output 0 and the whole stimulus in the GUI. Opt in to native
copying, Start, accept the warning, wait for Ready and Arm before revealing with Space.
After detection, record Last confirmed code, automatic disarming and any error, and
paste with Ctrl+V into a new Notepad tab before copying anything else. Supply the literal
paste and expected-record path for comparison and fixture regeneration. Game native
GUI validation was pending at preparation; the completed operator observations and
exact fixture comparison are recorded above.

The helper has no OCR or clipboard adapter. Production recognition, policies and native
handoff are unchanged. Offscreen Qt tests exercise hidden baseline, Space reveal,
one-time expected-text output and Escape for both profiles. `./scripts/check.ps1 -Ocr`
passed dependency checks, Ruff, formatting, strict mypy and 159 tests, retaining the
three existing strict challenge xfails. The later Game native GUI result is recorded above.

### Shortest practical personal-use readiness path

1. Verify the implemented provider/session diagnostics during the combined manual exercise.
2. Combine the remaining UX observations in one short center-monitor exercise. Reject
   the native confirmation dialog and confirm no session starts. Start native mode but
   leave it unarmed, then Stop and check that consent resets to dry-run. Exercise reverse
   and edge ROI drags, GUI resizing, preview reload clearing the ROI, and selection locking
   during a session. Use dry-run for these selection checks. Close during warmup or
   processing and confirm cleanup, then relaunch and verify disarmed dry-run startup.
   This checks GUI integration without repeating G2 code matches or loss/soak probes.
3. Review the resulting evidence for the approved center-only personal-use scope. Keep
   full G4 display/source-resize coverage pending where unperformed, including excluded
   configurations, and retain G3 as an unmet product-readiness gate. Source-size/position
   changes still require Stop, a new ROI, fresh baseline and explicit arm.

The scope enforcement, native opt-in, covering-window warning, exact confirmation,
freshness, baseline/deduplication, source-quality/O0 abstention and clipboard-error
disarming safeguards remain in force. The 30 native G2 matches, both GUI smoke pastes,
prior controls, lock/unlock, pause/resume, contention, race and soak evidence need no
routine repetition. This plan proposes no scope expansion or automatic G4/G3 sign-off.

Follow-up checks in the existing Windows Python 3.12 environment: renderer regeneration
and literal equality assertion passed. `./scripts/check.ps1` passed dependency, Ruff,
format and strict mypy checks, with 147 tests passed and 13 OCR opt-in skips. This
follow-up changed validation records only; the prior real-OCR 157-pass/three-xfail
result remains the model integration evidence.

## Native GUI integration follow-up, 2026-11-05 MYT

The existing WindowsClipboard, guarded handoff, LiveSession and detection policy remain
in use. Native sessions check primary device 0/output 0, 1920 × 1080, 100%, landscape,
SDR and local-console state. The existing display-inventory implementation is shared
with the runtime. Native capture checks topology/configuration every 500 ms and every
write revalidates scope before the guarded freshness/inhibition handoff. Qt display-change
signals still stop the session. Unknown or unsupported states fail closed. A real
read-only scope check passed, with one warmed check measuring 0.633 ms; this is a
configuration-query measurement, not end-to-end code-copy latency.

Review found that the diagnostic's optional physical desktop rect becomes unavailable
after DPI awareness is already set. Scope fingerprints now use DEVMODE position and
resolution consistently and omit that optional diagnostic rect. A regression test covers
this transition. The new tests also cover denied consent, consent reset, native result
forwarding, clipboard errors, topology/remote/unknown-state rejection and inhibition
during scope checks. Adapters and capture are injected for unit tests, without OS writes.

An initial Ruff line-length failure was corrected. Initial GUI drag tests used widget
coordinates that fell outside the smaller preview after adding the warning; they now
derive drag points from the painted image bounds. Initial injected session fixtures
were uniform images and correctly triggered blank-capture safety; contrast was added
to the fixture. All original safety assertions remain.

The updated GUI and a generated Discount stimulus were opened for an integration check.
Windows computer-use failed twice to bind to the GUI, reporting an ownership mismatch
with identical displayed owner IDs. No GUI detection or Notepad paste has been certified
by this attempt. Test stimulus metadata is in `artifacts/gui-native-smoke-source.json`.
Integration completion requires an actual GUI detection followed by Ctrl+V into a new
Notepad tab and a literal exact comparison with that metadata. The previously opened
GUI must be restarted to load the final fixes. The test window starts with a blank code
area; reveal with Space only after Ready and Arm. GUI and Notepad must be kept outside
the test rectangle. That automated attempt required operator assistance; the subsequent
operator paste and fixture comparison are recorded above.

API checks use the installed PySide6 6.12.0 and pywin32 APIs and the primary
[Qt message-box documentation](https://doc.qt.io/qt-6/qmessagebox.html) and
[pywin32 DEVMODE reference](https://mhammond.github.io/pywin32/PyDEVMODEW.html).

`./scripts/check.ps1` passed with 146 tests and 13 OCR skips. After adding the idle
scope-check regression, `./scripts/check.ps1 -Ocr` passed with 157 tests and the three original strict challenge
xfails. Dependency validation, Ruff, formatting and strict mypy (19 runtime files) pass.
Code review checked that scope validation precedes the existing guarded handoff, so
freshness and urgent inhibition are checked after the configuration query. Consent
cannot persist into another session, and a display-change signal during the confirmation
dialog prevents session startup. No recognition models, policies, thresholds, or native
adapter retry semantics changed. The subsequent Notepad paste result is recorded above.

The still preview uses the same DXcam source as live capture. The selection maps from the
painted image rectangle in Qt widget coordinates to the screenshot's physical pixel
dimensions. This uses the actual displayed extent including margins, with no separate
monitor scale multiplier. Right and bottom are exclusive. Screenshot work and session
processing run in background threads. Stop and window close request cancellation and
leave the GUI responsive while in-flight work returns and the capture source releases.
The statistics show the latest processed frame number, dropped frames and processing
duration. Frame statistics are limited to four GUI updates per second.

The repository contained G4 design notes and Phase 5.2 evidence. No standalone GUI
implementation proposal was found. Phase 6 requirements and G4 notes guided the design.

## Manual checks

1. Start the GUI and confirm the DRY RUN label, both profiles and all three monitor outputs.
   The inventory on the test PC reports center output 0, left output 1 and right output 2.
2. Move the GUI away from the video area. Load a preview on the center monitor at 100%,
   the left at 125% and the right at 100%. Confirm that each still shows the correct screen.
3. Drag around a known region, including the code and its contextual label. Compare the
   physical pixel coordinates shown by the GUI with coordinates from a full-size screenshot.
   Try a reverse drag and drag to an edge. Resize the GUI and confirm that the overlay
   remains on the selected content. A fresh preview or monitor selection clears the region.
4. With a moving local video visible, press Start. Verify Arm becomes available after Ready.
   Arm, disarm and stop. Repeat with both profiles. Use a controlled source with a known
   eligible code appearing after arming. Confirm the exact code appears once, the GUI
   disarms and no new value appears in a local paste check of a preexisting clipboard value.
   Rearm and verify the same code remains suppressed within that session.
5. Pause the video while armed for at least 30 seconds. Verify the session remains ready
   and armed without new OCR observations from identical pixels. Resume playback and
   confirm detection continues without Start or Arm. Close during warmup or processing and confirm the
   window exits after cleanup. Restart the app after any monitor or DPI configuration change.

## Operator-reported results

### Pause/resume regression follow-up

**PASS (operator-reported).** On Windows, the GUI remained Running · Ready · Armed
while playback was paused for at least 30 seconds. Detection resumed when playback
continued. The watchdog previously measured time
since the last changed ROI. Installed DXcam 0.3.0 treats DXGI wait timeout as a normal
idle poll and reports access loss separately. The watchdog now uses completed capture
polls for liveness. Only changed pixels advance the observation sequence, with the
original acquisition timestamp and existing baseline and confirmation rules.

`./scripts/check.ps1 -Ocr` passed dependency checks, Ruff, formatting, strict mypy and
135 tests, with three existing challenge xfails. The new threaded tests use an injected
source that alternates idle polls and identical frames. They cover 30 actual seconds of
static time followed by detection on resume, injected monitor access loss while static,
and Stop and Disarm while static. The revised visible Windows harness was not run in
this follow-up. The GUI remains memory-only.

2026-11-05 (MYT)

- **Game Mode exact-code detection — PASS (operator-reported).** The operator compared
  Last confirmed code with Expected game code in PowerShell and reported a
  character-for-character match.
- **Discount Mode detection — PASS (operator-reported).** The generated code was
  detected automatically. Exact matching was not independently confirmed.
- **Basic GUI controls — PASS (operator-reported).** Start, Arm, Disarm, and Stop
  worked in the dry-run GUI.
- **Normal displayed processing time — approximately 200 ms (operator-reported).**
  Observed without Snipping Tool interference. End-to-end detection latency was not
  measured in this check.

This earlier dry-run checkpoint preceded the limited-scope G2 sign-off recorded above.

## Limitations

Capture uses fixed desktop pixels. Move the GUI clear of the source, and stop before
moving, covering or minimizing the source. A moving occluder can keep the region active.
Shutdown waits for an in-flight native OCR or DXGI call to return. A hung native call can
delay exit while the interface remains responsive. The 100% and 125% mapping cases pass
offscreen tests. Physical preview alignment, window behavior and complete live GUI
operation still need the manual checks above.

## Automated evidence

- `./scripts/check.ps1` passes Ruff, formatting, dependency checks and strict mypy over
  17 source files, including the GUI. Pytest reports 121 passed and 13 OCR opt-in skips.
- `./scripts/check.ps1 -Ocr` passes the same quality checks and reports 131 passed
  and the three existing strict challenge xfails.
- The seven Qt cases exercise 100% and 125% mapping, drag interaction, both profiles,
  memory-only live-session controls, Stop and close cleanup, and preview/worker errors.
  They use offscreen Qt and injected capture pixels.
- A read-only DXcam metadata probe returned three physical 1920 × 1080 outputs.
- A sandboxed PySide6 install hit DNS restrictions. The approved retry installed the
  existing 6.12.0 pin. Qt uses the documented
  [QImage BGR format](https://doc.qt.io/qt-6/qimage.html) and
  [QThread lifecycle](https://doc.qt.io/qt-6/qthread.html).

## Session diagnostics usability follow-up

The GUI forwards provider and model identity after existing recognizer warmup verifies
both local ONNX session providers. The compact diagnostics group shows capture device,
output, monitor resolution, physical region, clipboard target and existing error messages.
Before initialization, provider identity is pending. Stopped model/provider text is marked
as the last session. Clipboard selection before Start shows that consent is still required.

Changed files are `src/stream_code_capture/gui.py`, `tests/test_gui.py`, and this record.
The baseline/native scope enforcement and guarded clipboard implementation continue to
apply. Tests cover provider/model display, capture identity, edited region coordinates,
error visibility and memory-mode reset after explicit native consent.

`./scripts/check.ps1` exited 0. Dependency checks, Ruff lint/format and strict mypy over
19 runtime source files passed. Pytest reported **150 passed, 13 opt-in OCR skips** in
39.47 seconds. GUI tests used offscreen Qt and injected adapters. This follow-up changed
GUI diagnostics and tests, with no new OCR/policy/fixture behavior to qualify.

The following was the requested combined exercise. The operator's completed observations
and their precise coverage are recorded in the final review below. Unmentioned subchecks
remain unverified.

1. With the GUI stopped, select center output 0 and a valid region on a moving code-free
   source. Select native copying, click Start, then Cancel in the warning. Verify the
   session stays stopped, Arm is disabled, and the clipboard retains its previous content.
2. Start again, explicitly accept consent, leave the session disarmed, then Stop. Verify
   the checkbox resets and diagnostics show the memory target. Confirm another native
   session requires a fresh opt-in and confirmation.
3. In dry-run, edit the region with reverse and edge drags. Resize the GUI and check
   overlay alignment. Reload the preview and verify Start requires a new valid region.
   Confirm editing is locked while a session runs.
4. Start disarmed processing on the code-free source and close during warmup or processing.
   Verify return to the launching PowerShell prompt and no subsequent clipboard changes.
   Relaunch and verify stopped, disarmed, dry-run startup.

## Combined usability result and personal-use readiness review

2026-11-05 MYT. The operator reported the following successful observations:

| Observation | Result and evidence |
|---|---|
| Cancel native consent | PASS (operator-reported): monitoring remained stopped. |
| Retry after cancellation | PASS (operator-reported): consent warning appeared again. |
| Accept, Stop, and restart | PASS (operator-reported): native consent warning appeared again. This supports renewed consent; automatic checkbox/memory reset also has separate automated coverage. |
| Edit selected region | PASS (operator-reported): blue rectangle and coordinates updated correctly. No reverse/edge/resize subcase is inferred. |
| Close while armed and processing in dry-run | PASS (operator-reported): GUI closed without freezing or showing errors. Exact mid-inference timing and absence of every possible post-close event are not independently logged. |

There is no persisted GUI session trace for this exercise. These observations remain
operator evidence. The two native paste strings are separately verified against saved
and regenerated fixture truth; successful OS paste and automatic disarm are operator
observations. The signed-off G2 ledger retains 30 exact native manual matches, native
failure/contention/race evidence, the negative soak, lifecycle/recovery observations,
and the explicitly approved physical-hotplug evidence substitution. No completed G2
test needs routine repetition.

Code review confirms that diagnostics display the provider/model identity emitted after
recognizer warmup, selected capture device/output/resolution, physical ROI, clipboard
mode, processing statistics and errors. Stopped provider/model details are labelled as
the last session. Existing automated tests cover these displays. Manual visual
confirmation of every diagnostic field is not newly claimed from the operator's report.

**Readiness decision:** the functional GUI/native-copy workflow is ready for routine,
supervised personal use on the approved center primary output 0 at 1920 × 1080, 100%,
SDR and the local Windows console, with fixed topology during a session. No unresolved
functional blocker was identified for that limited workflow in this review. Explicit
per-session native consent, the covering-window warning, scope enforcement and all
existing pipeline/clipboard safeguards continue to apply. Stop before moving/resizing
the source or changing display configuration, then select a fresh ROI and baseline.

Remaining limitations and qualification work:

- G3 representative real-video accuracy/recall and latency requirements are unmet.
  Generated-fixture successes do not establish reliable recognition of arbitrary
  broadcasts. O/0 and insufficient-source-resolution inputs deliberately abstain, and
  measured processing/copy times do not establish the <100 ms target. This blocks
  product-readiness/performance claims under the specification, while limited personal
  workflow use remains explicitly scoped as above.
- Full G4 still lacks the unconfirmed detailed ROI/resize/reload observations, complete
  display/source-transition matrix and broader release review. 150%/200%, rotated/HDR
  and other excluded native configurations remain unqualified. These are outside the
  approved routine-use configuration and are not recorded as passes.
- Physical hotplug remains deferred/unverified under the approved G2 evidence
  substitution. Moving occluders can supply eligible code pixels. Disarm before covering,
  moving or minimizing the intended source. This known scope limitation still applies.
- No persistent GUI JSONL audit is available for independent reconstruction of these
  operator sessions. Native inference can delay shutdown until its current call returns.

G2 limited-scope sign-off remains valid. **G3 and full G4 remain incomplete.** No scope
expansion, application-code change, commit or push is part of this documentation review.

Validation for this review: `./scripts/check.ps1` passed dependency checks, Ruff,
formatting, strict mypy and 150 tests, with 13 opt-in OCR skips. No live G2 test or
manual paste sequence was repeated.
