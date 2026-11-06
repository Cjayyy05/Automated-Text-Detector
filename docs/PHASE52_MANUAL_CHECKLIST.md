# Phase 5.2 — numbered Windows checklist

Status: **manual tests NOT RUN**. Configuration inventory was performed read-only on
2026-11-03. A detected configuration is not a passed capture or usability test. Record
actual observations in `PHASE52_MANUAL_RESULTS.md`; never infer a manual pass from unit
tests or automated clipboard readback. No GUI implementation is included.

## Your detected setup

| Screen position / GDI name | DXcam arguments | Physical resolution | Windows scale | Refresh | HDR |
|---|---|---:|---:|---:|---|
| Center primary / DISPLAY2 | `--device 0 --output 0` | 1920x1080 | 100% | 75 Hz | Off; unsupported on current path |
| Left / DISPLAY1 | `--device 0 --output 1` | 1920x1080 | 125% | 144 Hz | Off; unsupported on current path |
| Right / DISPLAY3 | `--device 0 --output 2` | 1920x1080 | 100% | 60 Hz | Off; unsupported on current path |

Windows reports three active monitors and three available display targets. WTS protocol
0 identifies the local console; remote-session/control metrics are false. This does not
detect every third-party screen-sharing application. If using one, note it in the record.
Landscape orientation and SDR/8-bit active color were reported for all three paths.
Evidence: `artifacts/phase52-display-inventory.json`. Re-enumerate after any topology change;
DXcam output numbers are not Windows display numbers and can change.

No settings changes are necessary for the current 100%/125% mixed-DPI matrix. Do not
change scale, resolution, HDR, rotation, power settings or monitor connections as part of
the initial pass. 150%/200%, HDR-on and rotated configurations remain unverified; these
require a separately approved configuration change or suitable hardware. They are not
silently waived from the broader G2 matrix.

## Steps

1. **Prepare evidence and keep the source visible.** Open an interactive PowerShell in
   the repository. Open Notepad yourself for manual paste, outside the selected video
   region. Keep Windows unlocked. Use one test at a time. Create a new evidence folder:

   ```powershell
   $phase52Root = 'artifacts/manual-phase52-01'
   New-Item -ItemType Directory -Path $phase52Root
   ./.venv/Scripts/python.exe scripts/display_inventory.py --report "$phase52Root/display.json"
   ```

   Use a different folder name if it exists. Copy the results template to a new file in
   that folder. Record date, operator, power source, profile, arena choice, exact command,
   source, output index and ROI. Do not rerun the 30-minute soak or performance matrix.

2. **Check actual captured pixels on each existing monitor.** Place a permitted moving
   video on the screen being checked. Run the explicit snapshot command, one screen at a
   time, then open the saved PNG yourself. This launches no viewer and never touches the
   clipboard. Full-screen images contain whatever is visible on that monitor.

   ```powershell
   ./.venv/Scripts/python.exe scripts/capture_roi.py --capture --device 0 --output 0 --roi 0 0 1920 1080 --directory "$phase52Root/primary-full"
   ./.venv/Scripts/python.exe scripts/capture_roi.py --capture --device 0 --output 1 --roi 0 0 1920 1080 --directory "$phase52Root/left-full"
   ./.venv/Scripts/python.exe scripts/capture_roi.py --capture --device 0 --output 2 --roi 0 0 1920 1080 --directory "$phase52Root/right-full"
   ```

   Each directory must contain `roi.png` and `capture.json`, with `error: null` and
   shape `[1080,1920,3]`. Manually match the displayed screen and its edges/colors to
   the PNG. Metadata success alone is insufficient. Black, wrong-monitor, clipped,
   stretched or color-corrupted images fail the relevant configuration.

3. **Choose and verify a small code ROI.** In the full-resolution PNG, use an image
   viewer/editor's pixel coordinates to choose left/top/right/bottom around the code
   area and its nearby context label. Exclude permanent banners/chat. Right/bottom are
   exclusive. Repeat the snapshot with those four coordinates in a new directory and
   check that the code and context are completely included. Record its dimensions.
   On the 125% screen, use the PNG's 1920x1080 physical pixels, not a DPI-virtualized
   1536x864 coordinate system. ROI coordinates start at `(0,0)` on the selected monitor;
   do not pass its negative desktop offset or multiply physical coordinates by 1.25.

4. **Check console start, readiness and disarm in memory mode.** Set the actual ROI and
   output below; keep movement inside the ROI. Use a local controllable video if available.
   A still image supplies no new observations. Use moving pixels to establish baseline readiness.

   ```powershell
   $phase52Output = 0  # Use 1 for left or 2 for right, after the snapshot check.
   $phase52Profile = 'discount'  # Repeat with 'game'.
   $phase52Roi = (Read-Host 'Physical ROI: L T R B, separated by spaces').Split(' ', [StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { [int]$_ }
   ./.venv/Scripts/python.exe -m stream_code_capture live --profile $phase52Profile --device 0 --output $phase52Output --roi @phase52Roi --dry-run --scale 1 --threads 4 --no-spinning --det-limit 640 --report "$phase52Root/controls-discount-primary.jsonl"
   ```

   Choose a new report name for every profile/screen/run. Type `status`: running/ready/
   armed must be false. Type `arm` before `start`: expect `arm_rejected`. Type `start`,
   wait for `ready`, then `status`: running/ready true, armed false. Readiness requires
   multiple stable observations over at least 500 ms. Type `arm`, `status`, `disarm`,
   `status`: armed must become true then false. No native write is possible in this mode.
   If the process exits on source loss, record the error and launch a fresh process;
   do not label that control sequence a pass.

5. **Check one-shot, baseline suppression and duplicates in memory mode.** With a
   controllable clip and known labels, include a permanent code before `ready`; it must
   remain suppressed after arming. Arm before a different new code appears; expect one
   `would_copy`, then `status` must show disarmed. Rearm and replay the same code within
   the same process: no second copy. A different new eligible code must still require
   fresh observations and explicit arm. Record both strings, event sequences and statuses.
   Codes seen while disarmed are added to the baseline; presenting a new target before
   arming can intentionally suppress it. O/0 and tiny/uncertain inputs should abstain.
   If no controllable source is available, mark this manual row BLOCKED, not PASS; the
   existing automated duplicate/baseline evidence remains separate.

6. **Check stop and recovery.** While the moving source is being processed, issue
   `disarm` and verify no later write decision; then `stop`. Require a summary and process
   exit with no cleanup failure. Stop exits the CLI: launch it again to restart, acquire
   a new baseline, and arm explicitly. Repeat with Ctrl+C during OCR and with a paused
   source. Native inference is not forcibly interrupted, so exit can wait for the current
   call. Record the observed delay; a hang/cleanup failure fails the check. A human keypress
   timestamp is not proof of an exact mid-inference race; retain the existing automated
   timestamped race probes for that claim.

7. **Apply the approved screen-region scope.** Disarm before moving, covering, or minimizing
   the intended content. A covering window can supply a code that meets the confirmation
   rules and is copied in native mode. Healthy capture may continue after a window change.
   The historical moving-occlusion failure is recorded under the previous criterion.
   Skip the repeat and continue with the genuine capture-loss checks.

8. **Opt in to manual native paste checks, one code at a time.** Only run this step when
   you intend to replace your clipboard. Existing `game_playback.py` opens a temporary
   primary-screen test surface; it uses real DXcam and two-observation policy, then shows
   a repeat and a negative scene. Keep `(50,50)` through `(1010,590)` unobscured. It makes
   at most one correct new-code write for this command. First run with `--clipboard memory`
   if you want to rehearse; this does not count as a manual paste check.

   ```powershell
   $phase52Profile = 'discount'  # Change to 'game' for the game cases.
   $phase52Number = 1           # Use 1..30, never reuse an evidence filename.
   $phase52Seed = 20261110 + $phase52Number
   ./.venv/Scripts/python.exe scripts/game_playback.py --profile $phase52Profile --synthetic-count 1 --exposures-ms 10000 --seed $phase52Seed --precise-stimulus --drain-ms 1000 --scale 1 --threads 4 --no-spinning --det-limit 640 --clipboard windows --report "$phase52Root/paste-$phase52Number.jsonl"
   ```

   Read the displayed code, wait for the test to finish, and **paste into Notepad before
   copying any command or other text**. Record the pasted text exactly, then compare it
   with the report's `test_config.schedule` new-event expected string and your observation.
   Require `test_result.passed: true`, one exact copy, zero wrong/repeated/negative writes,
   zero readback mismatches, zero late writes, no session failure and exit 0. A miss or
   mismatched paste is a failed attempt; retain it, rather than silently replacing it.
   Complete the G2 minimum of **30 varied manual matches**, covering both profiles
   (suggested split: 15 discount, 15 game). Record all attempted events, including failures.
   One-event fresh processes do not test cross-arm deduplication: step 5 and historical
   probes cover that separately. This restricted fixture alphabet is not general accuracy
   evidence or a fix for O/0. Never use `--confirmations 1` for G2.

9. **Repeat the short ROI/control checks on left and right monitors.** Move the source
   only after stopping. Repeat steps 2–6 with output 1 at its current 125%, then output 2
   at 100%, and with both profiles. Use new ROI coordinates and a fresh baseline each time.
   The fixed primary-screen playback harness in step 8 does not validate secondary-monitor
   capture. Record a per-monitor result; one passing primary-screen run is not a blanket
   mixed-DPI pass. Do not change display settings to complete this step.

10. **Check lock/unlock recovery in memory mode, when convenient.** Save unrelated work,
    start/arm a dry-run session, then manually lock Windows and unlock it. Require source
    invalidation/stop and no continued eligible copy until a fresh process/baseline/arm.
    Retain the report; continued processing without invalidation fails this source-change
    check. No automation will lock your desktop. Physical unplug/replug, resolution/scale
    changes and rotation are separate pending tests requiring your approval; no settings
    or power changes are made by this checklist's commands.

11. **Attach existing evidence instead of rerunning long tests.** Cite Phase 5.1's
    1800-second arena-off soak (14.1 MiB growth, zero writes), 14/14 native recovery probes,
    and capacity-one/freshness unit tests. This is previously measured automated evidence,
    not a new manual pass. Busy-clipboard and precise mid-OCR races need repeating only
    if you discover a new failure; do not hold the clipboard open using improvised commands.

12. **Return the record for review.** Include the inventory, ROI PNGs/metadata, reports,
    30 paste rows, failures and per-monitor outcomes. Unknown/not-attempted items remain
    NOT_RUN or BLOCKED. No GUI-readiness pass is issued automatically by these tools.
    Full G2 still needs its manual/display/source-change requirements; G3 representative
    accuracy and <100 ms claims are separate gates, not prerequisites to documenting a
    limited G2 result. The known occlusion limitation cannot be hidden by a passing paste test.

## Configuration choice for these tests

Use `--scale 1 --threads 4 --no-spinning --det-limit 640` as an **explicit arena-off test
choice** for sustained monitoring. Add `--cpu-arena` if deliberately selecting the faster,
higher-retention option and record that choice. No defaults are changed and no automatic
switching is introduced. Preserve the baseline model, two observations, default 1000 ms
accepted-frame freshness, O/0 abstention, baseline suppression and deduplication.

Phase 5.1 paired copy p50: discount on/off 230/268 ms, game 244/257 ms; screenshots
494/624 ms and reversed repeat 461/581 ms. Historical arena-on soak growth was 77.8 MiB
(failed 50 MiB gate), versus arena-off 14.1 MiB (passed). The screenshot slowdown repeated
at about 26%; neither setting achieves <100 ms or representative livestream qualification.
