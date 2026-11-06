# Phase 5.2 — manual results

Record actual results after following `PHASE52_MANUAL_CHECKLIST.md`.
Use PASS / FAIL / NOT_RUN / BLOCKED / DEFERRED. Give a reason for anything other than PASS. Retain
failed attempts. Automated readback alone never fills the manual-paste column.

Operator: _not recorded_  
Date/time/timezone (Test 1 inventory): 2026-11-04 15:53:18 MYT (UTC+08:00)  
Evidence directory: `artifacts/manual-phase52-01`  
Power source/mode (observed, not changed): _not recorded_  
Third-party remote/screen-sharing software, if any: _not recorded_  
Runtime configuration/arena: _not recorded_  
Exact commands and model hashes (paste report or linked artifact): _not recorded_  
Source video/fixture and independently known labels: _not recorded_

Read-only inventory on 2026-11-03: three active 1920x1080 SDR monitors, left 125%/144 Hz
(device 0 output 1), primary 100%/75 Hz (output 0), right 100%/60 Hz (output 2), local
console. Re-enumerate if changed. **This inventory is not a manual verification result.**

| Check | Profile | Output / ROI | Actual observation and evidence path | Result |
|---|---|---|---|---|
| Manual Test 1 — evidence preparation and display inventory | — | Device 0, outputs 0–2 | Operator reported PASS. `artifacts/manual-phase52-01/display.json` records three active 1920 × 1080 monitors: left at 125% (output 1), center at 100% (output 0), and right at 100% (output 2). `errors: []`. Local console with no Remote Desktop session detected. | PASS |
| Manual Test 2 — full physical ROI, center primary | — | 0 / `0 0 1920 1080` | Operator confirmed the saved 1920 × 1080 PNG shows the center monitor, with the video visible and no unexpected cropping. Metadata reports `error: null` and shape `[1080,1920,3]`. Evidence: `artifacts/manual-phase52-01/primary-full/roi.png` and `capture.json` in the same directory. | PASS |
| Cropped physical ROI, primary | — | 0 / `320 320 1120 860` | Operator confirmed the 800 × 540 PNG shows only the selected video region, excluding the browser toolbar and taskbar. Metadata reports `error: null` and shape `[540,800,3]`. Evidence: `artifacts/manual-phase52-01/primary-crop/roi.png` and `capture.json` in the same directory. | PASS |
| Manual Test 2 — full physical ROI, left 125% | — | 1 / `0 0 1920 1080` | Operator confirmed the saved 1920 × 1080 PNG shows the left monitor, with the video visible, correct colors, and no unexpected cropping. Metadata reports `error: null` and shape `[1080,1920,3]`. Evidence: `artifacts/manual-phase52-01/left-full/roi.png` and `capture.json` in the same directory. | PASS |
| GUI preview and cropped physical ROI, left 125% | Not reported | Output 1 / ROI bounds not reported | Operator reported a correct preview and aligned crop. | PASS (operator-reported) |
| Manual Test 2 — full physical ROI, right | — | 2 / `0 0 1920 1080` | Operator confirmed the PNG shows the right monitor with the video visible and no unexpected cropping. Metadata reports `error: null` and shape `[1080,1920,3]`. Evidence: `artifacts/manual-phase52-01/right-full/roi.png` and `capture.json` in the same directory. | PASS |
| GUI preview and cropped physical ROI, right 100% | Not reported | Output 2 / ROI bounds not reported | Operator reported a correct preview and aligned crop. Displayed processing time temporarily rose to about 500 ms, then returned to normal. | PASS (operator-reported) |
| Startup / premature arm / baseline / arm / disarm, initial attempt | discount | 0 / `320 320 1120 860` | `artifacts/manual-phase52-01/controls-discount-primary-quiet-01.jsonl` confirms disarmed startup, premature arm rejection, and readiness after 513.344 ms and seven observations. The source watchdog stopped the session before a successful arm or disarm. | FAIL |
| Startup / baseline / arm / disarm / stop, controlled retest | discount | 0 / `320 320 1120 860` | `artifacts/manual-phase52-01/controls-discount-primary-quiet-02.jsonl` confirms disarmed startup, readiness after 558.0921 ms and four observations, dry-run arm, disarm, and a final summary with `failure: null`. Operator also reported premature arm rejection, which is present in `quiet-01` but absent from `quiet-02`. | PASS for the logged sequence |
| Startup / premature arm / baseline / automatic disarm | game | 0 / `320 320 1120 860` | `artifacts/manual-phase52-01/g2-game-controls-combined-01.jsonl` confirms premature arm rejection, dry-run Game startup, readiness after 527.6218 ms and four observations, three explicit arms, and automatic disarm after each confirmation. Explicit Disarm control retains the existing operator-reported GUI evidence. | PASS for the logged sequence |
| Persistent baseline / one-shot / repeat / new code | discount | 0 / `320 320 1120 860` | `artifacts/manual-phase52-01/g2-discount-controls-combined-01.jsonl` verifies A suppression, B confirmation, B suppression after rearm, C confirmation, and automatic disarming after each confirmation. See detailed audit below. | PASS (log evidence and operator report) |
| Persistent baseline / one-shot / repeat / new code | game | 0 / `320 320 1120 860` | Combined report verifies baseline A suppression, B confirmation, B suppression after rearm, then C and D confirmation under separate arms. See detailed audit below. | PASS (log evidence and operator report) |
| Stop / Ctrl+C / healthy static capture / fresh restart | both | 0 / `320 320 1120 860` where recorded | Game Stop and Discount Ctrl+C while disarmed have operator observations and clean summaries. Phase 6 records healthy pause/resume. `g2-game-recovery-01.jsonl` verifies fresh startup, baseline acquisition, suppression, explicit arm, new-code confirmation, and clean summary. Exact mid-OCR races retain existing timestamped native probes. | PASS within the recorded evidence |
| Moving occlusion under the previous automatic-disarm criterion | memory only | Not recorded | Operator reported that the GUI continued running when another moving video covered the selected region. The approved screen-region scope supersedes the automatic-disarm criterion for healthy capture. | FAIL (operator-reported, historical) |
| Minimize / restore with healthy monitor capture | memory only | — | Approved screen-region scope treats replacement pixels as visible content. Actual capture invalidation still requires fail-closed recovery. | Previous automatic-disarm criterion superseded |
| Windows lock / unlock | Discount GUI, dry-run | Not recorded | Reached Running · Ready · Armed. Locked with Win+L for approximately 10 seconds, then unlocked. GUI showed Stopped · Disarmed and `RuntimeError: Capture invalidated: Output changed/access loss detected`. Last confirmed code: None. No automatic rearming observed. | PASS (operator-reported) |
| Left/right GUI controls, mixed DPI | Not reported | Outputs 1 and 2 | Operator reported Start, Ready, Arm, Disarm, and Stop worked without errors on both monitors. | PASS (operator-reported) |
| Physical monitor disconnect/reconnect | memory only | Not exercised | Operator declined physical disconnection. Injected access-loss and blank-frame tests plus the real lock/unlock pass provide related fail-closed evidence. Physical hotplug remains outstanding unless a substitute or scope exception is explicitly approved. | DEFERRED |
| Changed resolution / 150% / 200% / rotation | memory only | fill | Requires separate approval; not exercised | NOT_RUN |
| HDR-on | fill | fill | Not supported on current reported display paths | BLOCKED |

## Priority manual checks

1. Verify a selected region around the code and context label on each monitor, starting
   with the center. Save the cropped PNG and metadata in new directories. Use monitor-local
   physical pixels, check the expected width and height, and visually confirm the complete
   code and label are inside the crop. This is checklist step 3.
2. Run one native clipboard case from checklist step 8 and manually paste into Notepad
   before copying anything else. Record the exact expected and pasted strings and the
   report path. Review the first attempt before continuing toward 30 varied matches across
   both profiles. Retain misses and mismatches in the ledger.

## Minimal GUI development plan

The current specification requires G2 sign-off before implementation. The plan below
describes a local dry-run prototype if the proposed exception is adopted.

1. Add a PySide6 window that lists monitors mapped to DXcam device/output pairs. Select a
   rectangle on a still preview before monitoring starts. Convert the selection to
   monitor-local physical pixels with exclusive right and bottom bounds, and check the
   mapping at 100% and 125%. Lock monitor and region selection until Stop completes.
2. Run the existing `LiveSession` on a dedicated owner thread. Send Start, Arm, Disarm,
   and Stop through `Controls` and deliver status to the UI via queued Qt signals. Start
   disarmed and enable Arm after baseline readiness. Route Stop and window close through
   the existing shutdown path. A new session acquires a fresh baseline.
3. Show baseline, ready, armed, and stopped states, plus the last confirmed detection or
   error. A `would_copy` event updates the display and reflects automatic disarming. Keep
   detailed frame events in the report and send only state changes and significant results
   to the UI. Reuse the existing OCR, policy, and memory clipboard. Test control wiring
   with injected capture and recognition, then smoke-test the UI in dry-run on Windows.

### Proposed addition to PROJECT_SPEC.md, G4

> A local PySide6 prototype may be implemented and tested before G2 sign-off once real
> Windows selected-region capture, the dry-run control sequence, and a manual native
> paste for each profile have recorded evidence. The prototype must use the existing
> pipeline and memory clipboard, preserving baseline readiness, explicit arming,
> one-shot copy, deduplication, freshness, source-loss handling, and shutdown safeguards.
> Full G2 qualification, including all outstanding manual checks, is required before
> enabling native writes in the GUI or releasing it. G4 desktop smoke tests remain
> release requirements, and G3 still gates accuracy and latency claims.

Proposal pending adoption. The project specification and release gates remain in force.

## Manual paste ledger

The optional supervised helper launches from the repository root with
`./.venv/Scripts/python.exe scripts/manual_clipboard_batch.py`. It starts from the six
matches recorded below and stores further attempts under `artifacts/g2-supervised`.
Resume using the same command and directory. Its append-only attempt folders contain
the harness report, console output, exit status, and literal operator-entered paste.
Every run requires RUN confirmation, then a manual Notepad paste and typed response.
Failures remain saved and the same planned seed is retried with a new report. Only a
successful report plus an exact operator-entered paste advances the counter. The helper
does not edit this ledger automatically. Review its saved results when updating the ledger.
Seeds 20261301–20261313 provide 13 Discount cases; 20261204–20261214 provide 11 Game
cases. Existing randomized fixture appearances and rotating 2/5/10-second exposures
are used. Each launch contains one generated code. G2 remains pending after 30 matches
until its other requirements are reviewed.

Record all attempts. Suggested rows 1–15 discount, 16–30 game; vary seed/position. Record
literal expected text and literal pasted text, not just “matched.” A failed/missing copy
is a failed attempt, not an empty success. Add rows for retries with new filenames.

| Attempt | Profile / seed | Report path | Expected text | Actual Notepad paste | Result |
|---:|---|---|---|---|---|
| 1 | discount / `20261111` | `artifacts/manual-phase52-01/paste-1.jsonl` | `Q8MQ36D2BR` | `Q8MQ36D2BR` | PASS |
| 2 | discount / `20261112` | `artifacts/manual-phase52-01/paste-20261105-175438-704.jsonl` | `GSNZHVD2PF` | `GSNZHVD2PF` | PASS (operator-reported, exact character match confirmed) |
| 3 | discount / `20261301`, 2000 ms | `artifacts/g2-supervised/attempt-8c103f7f9ad445a08ccb9c9578188426/report.jsonl` | `Y9XEAGUY5A` | `Y9XEAGUY5A` | PASS (saved operator confirmation; report verified) |
| 4 | discount / `20261302`, 10000 ms | `artifacts/g2-supervised/attempt-beba9a62ba97477cbd50a4a62d5a5ebc/report.jsonl` | `DKMLGWGAW4` | `DKMLGWGAW4` | PASS (saved operator confirmation; report verified) |
| 5 | discount / `20261303`, 5000 ms | `artifacts/g2-supervised/attempt-361d452d7e4d4236ae4f7f8d1d83b9f8/report.jsonl` | `BRU4NZSFXH` | `BRU4NZSFXH` | PASS (saved operator confirmation; report verified) |
| 6 | discount / `20261304`, 2000 ms | `artifacts/g2-supervised/attempt-e3de84379c174e8aaab794ce92897610/report.jsonl` | `7H8Q6BTNRH` | `7H8Q6BTNRH` | PASS (saved operator confirmation; report verified) |
| 7 | discount / `20261305`, 10000 ms | `artifacts/g2-supervised/attempt-f1c5080faf2f45808a38e18f998fd8d2/report.jsonl` | `VRQDANEN7J` | `VRQDANEN7J` | PASS (saved operator confirmation; report verified) |
| 8 | discount / `20261306`, 5000 ms | `artifacts/g2-supervised/attempt-6ae3f50e3f1f4b03b9775b1b780dfd64/report.jsonl` | `HLHW7V8UDG` | `HLHW7V8UDG` | PASS (saved operator confirmation; report verified) |
| 9 | discount / `20261307`, 2000 ms | `artifacts/g2-supervised/attempt-039dd85b22244ea7918c21f89998d1bd/report.jsonl` | `VR626YS2NV` | `VR626YS2NV` | PASS (saved operator confirmation; report verified) |
| 10 | discount / `20261308`, 10000 ms | `artifacts/g2-supervised/attempt-28e6b026f6e54265bfe9dadca8e3ddc3/report.jsonl` | `YFWNYCQL5L` | `YFWNYCQL5L` | PASS (saved operator confirmation; report verified) |
| 11 | discount / `20261309`, 5000 ms | `artifacts/g2-supervised/attempt-ed6f0a98bcdc4ee8bbceac611673902a/report.jsonl` | `N4658EG89X` | `N4658EG89X` | PASS (saved operator confirmation; report verified) |
| 12 | discount / `20261310`, 2000 ms | `artifacts/g2-supervised/attempt-47bb7acc72b64351b5e1ec056680e7a5/report.jsonl` | `B8VP8VB72W` | `B8VP8VB72W` | PASS (saved operator confirmation; report verified) |
| 13 | discount / `20261311`, 10000 ms | `artifacts/g2-supervised/attempt-3800255fa74345838f11d652188b9873/report.jsonl` | `W83YWXT7S5` | `W83YWXT7S5` | PASS (saved operator confirmation; report verified) |
| 14 | discount / `20261312`, 5000 ms | `artifacts/g2-supervised/attempt-ddb1ba3c8f8e4cc6b174234f4635f579/report.jsonl` | `LL3VBXLTEA` | `LL3VBXLTEA` | PASS (saved operator confirmation; report verified) |
| 15 | discount / `20261313`, 10000 ms | `artifacts/g2-supervised/attempt-11e077af3c6043c8bbe25507cf16dcf2/report.jsonl` | `TJ263AJA9R` | `TJ263AJA9R` | PASS (saved operator confirmation; report verified) |
| 16 | game / `20261126` | `artifacts/manual-phase52-01/paste-16.jsonl` | `3T85NMMRCZ` | `3T85NMMRCZ` | PASS |
| 17 (Batch 1, Test 1) | game / `20261201`, 2000 ms | `artifacts/manual-phase52-01/game-20261105-180056-618.jsonl` | `E8EG9C7HL6` | `E8EG9C7HL6` | PASS (operator-reported exact match; report verified) |
| 18 (Batch 1, Test 2) | game / `20261202`, 2000 ms | `artifacts/manual-phase52-01/game-batch1-test2-01c47c86526241ac85e6e0ed11d7d66f.jsonl` | `NXUERMJR8P` | `NXUERMJR8P` | PASS (operator-reported exact match; report verified) |
| 19 (Batch 1, Test 3) | game / `20261203`, 2000 ms | `artifacts/manual-phase52-01/game-batch1-test3-84dedd53ac26459c8e0821f6ddf1b3bc.jsonl` | `6BFJC6ECT7` | `6BFJC6ECT7` | PASS (operator-reported exact match; report verified) |
| 20 | game / `20261204`, 5000 ms | `artifacts/g2-supervised/attempt-50d51be06a35436595abba45cb385a03/report.jsonl` | `ZAC2DSTMTL` | `ZAC2DSTMTL` | PASS (saved operator confirmation; report verified) |
| 21 | game / `20261205`, 2000 ms | `artifacts/g2-supervised/attempt-f086d4a1559e4e7c807523c99e8ccb6c/report.jsonl` | `APAWN7FS4W` | `APAWN7FS4W` | PASS (saved operator confirmation; report verified) |
| 22 | game / `20261206`, 10000 ms | `artifacts/g2-supervised/attempt-da722c65cecc418e8104ddb59ff60e2a/report.jsonl` | `VC2WL36NHQ` | `VC2WL36NHQ` | PASS (saved operator confirmation; report verified) |
| 23 | game / `20261207`, 5000 ms | `artifacts/g2-supervised/attempt-bcac0d12991d4abba92abfa1114230ba/report.jsonl` | `837EWKCCUL` | `837EWKCCUL` | PASS (saved operator confirmation; report verified) |
| 24 | game / `20261208`, 2000 ms | `artifacts/g2-supervised/attempt-727b8e239b654362aac4a43078aafeac/report.jsonl` | `5C2UXBALZ4` | `5C2UXBALZ4` | PASS (saved operator confirmation; report verified) |
| 25 | game / `20261209`, 10000 ms | `artifacts/g2-supervised/attempt-0ba3956f8d6d4b51ac1be56d3f139009/report.jsonl` | `K2M9TJW2L3` | `K2M9TJW2L3` | PASS (saved operator confirmation; report verified) |
| 26 | game / `20261210`, 5000 ms | `artifacts/g2-supervised/attempt-561180e1f27d4ec39308611861f4cf70/report.jsonl` | `4KRXPK3TE8` | `4KRXPK3TE8` | PASS (saved operator confirmation; report verified) |
| 27 | game / `20261211`, 2000 ms | `artifacts/g2-supervised/attempt-d334eb985c7c4572afd64585ffbda45c/report.jsonl` | `RDKNP4GVGG` | `RDKNP4GVGG` | PASS (saved operator confirmation; report verified) |
| 28 | game / `20261212`, 10000 ms | `artifacts/g2-supervised/attempt-87b16a9f347c4c58a9d4abaedb294cb3/report.jsonl` | `JKD6Y8WV3C` | `JKD6Y8WV3C` | PASS (saved operator confirmation; report verified) |
| 29 | game / `20261213`, 5000 ms | `artifacts/g2-supervised/attempt-cda45a74b90a4b8c8c6fd301b03952b9/report.jsonl` | `KKSR25UDMG` | `KKSR25UDMG` | PASS (saved operator confirmation; report verified) |
| 30 | game / `20261214`, 2000 ms | `artifacts/g2-supervised/attempt-bf2dc7127ac94ee695c1bf30d07d72f5/report.jsonl` | `CL6H8XKTWA` | `CL6H8XKTWA` | PASS (saved operator confirmation; report verified) |

## Existing automated evidence (not new manual passes)

Batch 1, Test 3 report confirms one correct native write and matching readback,
184.8687 ms first-captured-frame-to-clipboard latency, and copy completion before
disappearance. Incorrect writes, readback mismatches, late writes, and errors were all
zero, with no session failure. The literal Notepad paste is operator-reported.

Batch 1, Test 2 report confirms one correct native write and matching readback,
201.1632 ms first-captured-frame-to-clipboard latency, and copy completion before
disappearance. Incorrect writes, readback mismatches, late writes, and errors were all
zero, with no session failure. The literal Notepad paste is operator-reported.

Batch 1, Test 1 report confirms one correct native write and matching readback,
159.9588 ms first-captured-frame-to-clipboard latency, and copy completion before
disappearance. Incorrect writes, readback mismatches, late writes, and errors were all
zero, with no session failure. The literal Notepad paste is operator-reported.

Latest paste follow-up: the operator confirmed expected and pasted text both equal
`GSNZHVD2PF`, associated with `paste-20261105-175438-704.jsonl`. The exact manual match
is confirmed by operator report. Four completed reports were reviewed: `paste-2.jsonl`,
`paste-3.jsonl`, `paste-20261105-175042-780.jsonl`, and
`paste-20261105-175438-704.jsonl`. All use seed 20261112 and expected code `GSNZHVD2PF`.
Each records exactly one correct native write, matching readback, zero incorrect or late
writes, no session failure and no errors. Continued disarmed processing produced no
additional writes. Their schedules contain one new event and a negative event, with no
rearmed repeat-code event. Cross-arm duplicate suppression therefore relies on the
previous dedicated recovery probes, rather than these one-shot reports. Repeated runs
of this same generated code are not counted as additional varied manual matches.

- Phase 5.1 completed native pairs: 200/256 exact, 56 O/0 abstentions, zero wrong/late/
  mismatched writes. Reused fixtures, not general real-video accuracy.
- Arena-off recovery probes: 14/14, six matching native recovery writes/readbacks.
- Arena-off 1800-second negative soak: zero writes, 14.1 MiB growth, original gate passed.
- Latest-frame capacity, stale rejection and urgent control races: automated tests.

## Review

Confirmed exact manual matches: 30 / 30 (15 Discount, 15 Game), all distinct codes. No further paste matches are required.  
Incorrect copies / duplicate writes / late writes: 0 / 0 / 0 across all 30 confirmed ledger rows. Readback mismatches: 0. The 24 supervised attempts have no failed or unfinished attempts, missing copies, frame errors, or session failures. Earlier startup-stall and historical occlusion failures remain recorded above.  
Missing or uncertain detections (including O/0): _not recorded_  
Display evidence: center crop previously recorded. Left 125% and right 100% GUI preview, crop alignment, and controls passed by operator report. Profile-specific secondary-monitor coverage was not reported.  
Failures and follow-up actions: The initial discount controls run hit the former 2.5-second changed-ROI delivery watchdog. Its report cannot distinguish `None` grabs from identical ROI frames at the end of the run. The controlled retest completed with no session failure, and the subsequent Windows pause/resume pass is in `PHASE6_VALIDATION.md`. Physical monitor loss and display-transition checks remain pending.  
Reviewer/date: Codex evidence audit, 2026-11-05 MYT; operator limited-scope sign-off recorded below  
G2 verdict: **SIGNED OFF by the operator, 2026-11-05 MYT, for the approved limited personal-use scope and evidence substitution**  
GUI native clipboard readiness: **IMPLEMENTED WITH EXPLICIT OPT-IN — Discount and Game GUI/Notepad smoke PASS (operator-reported), exact fixture matches verified; remaining G4 checks pending**


## Supervised batch audit, 2026-11-05 MYT

All 24 attempt directories in `artifacts/g2-supervised` were inspected, including
`attempt.json`, `exit.json`, `manual-result.json`, and every JSONL event.
All planned task indexes 0–23 occur once. All exits are zero, all saved manual
confirmations exactly match the scheduled code and native readback, and all reports pass.
Each report has one new-code event and exactly one copied frame/write. All 24 copies
completed before disappearance. Exposure coverage is eight cases each at 2, 5, and
10 seconds. All use the native Windows adapter and the same recorded model hashes.
These 13 Discount and 11 Game matches supplement the six previously verified matches.
The six earlier report files were re-read and matched against their recorded manual
pastes. The 30 codes are distinct.

The saved manual text is operator evidence. Harness evidence independently verifies
recognition, writes, readbacks, and timing. The helper's initial six-match offset was
checked against the existing ledger. Completed paste tests need no repeat.

## Historical remaining G2 review before the combined sessions

- Complete the pending controlled persistent-baseline, rearmed same-code suppression,
  and new-code sequence for both profiles in dry-run. Single-code batch sessions do not
  establish this manual sequence. Retain existing native duplicate probes as supporting
  evidence. Game premature-arm rejection also lacks a profile-specific manual record.
- Record the remaining Ctrl+C/in-flight shutdown and clean fresh-baseline restart
  observations. Basic Stop, pause/resume, and lock/unlock already have operator passes.
  The former static-timeout expectation is superseded by the approved healthy-idle-poll
  behavior recorded in Phase 6.
- Resolve physical monitor loss (currently DEFERRED) and display-transition coverage.
  Injected access loss and the real lock/unlock pass are related evidence, but no approved
  substitution for physical hotplug is recorded. Physical 150%/200%, resolution changes,
  and rotation remain untested, and HDR-on is blocked by the reported hardware.
  Any limited supported configuration or alternative evidence requires an explicit
  specification decision and sign-off. No such exception is assumed in this audit.
- Clarify both-profile secondary-monitor coverage, which was not recorded in the
  otherwise passing mixed-DPI preview/control observations. Fill operator/session
  provenance still marked unrecorded where needed for final review.
- Reuse `artifacts/phase51-windows-failures.jsonl` (14/14 passing native recovery,
  duplicate, busy-clipboard, and timestamped Stop/Disarm probes), and
  `artifacts/phase51-negative-1800.jsonl` (1800.067 s, passed, zero writes in both
  profiles, memory clipboard). Capacity-one/latest-frame and stale-result tests remain supporting
  automated evidence. Repeat these only for a relevant regression or new finding.
- After the missing evidence or explicitly approved scope decisions are recorded,
  obtain G2 sign-off. Then implement an explicit GUI native-clipboard opt-in with
  the specified warning that eligible codes in covering windows can be copied, using
  the existing adapter and safeguards. Validate that GUI wiring before enabling it
  for use. G3 accuracy/latency and G4 release requirements remain separate gates.

G2 remains **PENDING**. The GUI continues in dry-run mode.

## Proposed efficient completion plan (pending approval where noted)

Reuse the 30 exact paste matches, native recovery/contention probes, negative soak,
latest-frame/freshness tests, manual GUI controls, lock/unlock, pause/resume, and preview
checks. No repeat is planned absent a new relevant failure.

Use three memory-only live CLI launches with controlled generated pixels and new JSONL
reports. The GUI stays dry-run throughout.

1. Game combined sequence. Confirm premature Arm rejection before Start. Start with code
   A already visible, wait for Ready, then Arm and verify baseline suppression. Reveal
   new B and require one `would_copy` and automatic disarm. Hide B, rearm, reveal B again,
   and require suppression. While still armed reveal distinct C and require one copy
   decision and automatic disarm. Continue processing and interrupt with Ctrl+C. Record
   cleanup, final summary, and observed exit delay. This human interruption does not
   independently establish exact mid-inference timing; retain the existing race probes.
2. Game fresh-process recovery. Leave C visible before Start, verify initial disarmed
   state, acquire a fresh baseline, and explicitly Arm. C must be suppressed. Reveal
   distinct D and require one `would_copy`, then Stop cleanly. This completes the manual
   restart observation without another native paste test.
3. Discount combined sequence. Use generated Discount-context A/B/C and repeat the
   baseline, new-code, same-code rearm, and distinct-code sequence from step 1. Reuse
   already passing basic controls. End with Stop. Record the literal expected strings
   and all decisions, including misses, rather than inferring pass from elapsed time.

### Proposed personal-use support scope

Pending explicit user approval, qualify initial GUI native copying only on the center
primary monitor, device 0/output 0 as re-enumerated, at 1920 × 1080, 100%, SDR, local
unlocked Windows console, with unchanged monitor topology during each session. Stop
before configuration changes and re-enumerate/reselect the ROI afterward. Existing
secondary-monitor 100%/125% results remain evidence, with native secondary-monitor
qualification pending. HDR, rotation, 150%/200%, remote sessions, and live topology or
display changes are outside this proposed initial supported scope.

Proposed explicit evidence substitution for initial personal-use sign-off: retain the
operator's real lock/unlock access-loss result, injected monitor-loss/blank-frame tests,
and native recovery probes in place of the deferred physical unplug/replug exercise.
Physical hotplug stays DEFERRED and unverified. Approval would accept this evidence
combination, not record an unperformed hotplug pass.

Mandatory protections still apply to every session, including an unexpected unsupported
transition: detected capture invalidation, access loss, capture errors, blank capture,
and poll-watchdog expiry must stop and disarm. Recovery needs a fresh baseline and explicit
arm. Exact agreement, latest-frame ownership, O/0 abstention, source-resolution and
freshness guards, baseline suppression, deduplication, one-shot copy, clipboard-error
disarming, and source-rectangle warning/opt-in remain mandatory. GUI native mode must
enforce the approved supported scope rather than merely relying on this document.

The user explicitly approved the limited scope and evidence substitution on 2026-11-05
MYT, now recorded in PROJECT_SPEC.md. The proposed scope above is adopted. Physical
hotplug remains DEFERRED and unverified, with the approved substitute evidence accepted
for this initial personal-use scope. Excluded display configurations stay unverified.
G2 and GUI native enablement remain pending until the three sequences and final evidence
sign-off are recorded. The documentation check passed with 129 tests and 13 OCR skips.

## Game combined session audit

The operator reported successful baseline suppression, B detection, same-code rearm
suppression, C/D detection, and Stop. The entire
`artifacts/manual-phase52-01/g2-game-controls-combined-01.jsonl` was reviewed.
It contains 5706 JSONL records, including 5695 frame events and one final summary.

- Line 2 records premature-arm rejection with reason `not ready/healthy`.
  Lines 3–4 record Game dry-run startup and readiness after 527.6218 ms and four
  observations. A (`S9T2TXQU95`) is recognized in 293 disarmed frame events before
  the first Arm, and then suppressed in 1785 armed observations without confirmation.
  The baseline collection's raw OCR lines are not individually emitted, so the log
  directly demonstrates pre-arm visibility and subsequent suppression.
- B (`NV3CMFNLUJ`) has one confirming observation and exactly one `would_copy` at
  line 2086. The following frames and status record show disarmed processing. After
  rearm at line 3853, B remains recognized in 585 observations without another copy.
  These records verify suppression while B is visible after rearm. They do not log
  stimulus key presses or independently establish a hide/reveal transition.
- C (`2B4AKD9SDU`) has one confirming observation and exactly one `would_copy` at
  line 4440. D (`7PBGH54S8B`) likewise confirms once at line 5237 after another explicit
  arm. All three confirmations exactly match the operator's expected strings. All
  following frame results are disarmed until a subsequent arm. No other code confirms.
- No frame errors, error events, stale results, or session failures occur. The last
  record is a dry-run summary with `failure: null`. Stop is operator-reported and this
  summary supports clean shutdown. The report contains no stop-command timestamp,
  exit-delay measurement, or shutdown cause, so Ctrl+C and exact mid-inference shutdown
  are not established by this report. Memory decisions do not add native paste matches.

Game baseline/rearm/new-code checks are complete within the evidence above. Basic
Stop is complete with operator observation and the clean summary. Interrupted shutdown
and fresh-process baseline recovery remain pending. To retain three total planned
launches, run the Discount combined sequence next and end it with Ctrl+C while processing,
then run the final Game fresh-process recovery sequence. Retain existing timestamped
Stop/Disarm race probes for exact mid-inference guarantees. G2 remains PENDING and
the native manual paste total remains 30/30.

## Discount combined session audit

All 1948 JSONL records in
`artifacts/manual-phase52-01/g2-discount-controls-combined-01.jsonl` were reviewed.
There are 1940 frame events, two explicit arms, two status responses, and one final
summary. The operator reported A suppression, B/C confirmation, B suppression after
rearm, automatic disarming, and Ctrl+C while running but disarmed, followed by
`stopped` with `failure: null` and return to the PowerShell prompt.

- Lines 2–3 verify Discount dry-run startup and readiness after 511.2045 ms and four
  observations. A (`K6ZRWKVB6F`) appears in 104 disarmed frame observations before
  Arm at line 108. It remains recognized but suppressed in 259 subsequent armed
  observations, without a `would_copy` for A. Raw baseline-collection OCR lines are
  not emitted separately, so baseline visibility also relies on the operator observation.
- B (`ADWSD2ZXDB`) has one confirming observation followed by exactly one `would_copy`
  at line 369. Subsequent frames and status show disarmed processing. After rearm at
  line 972, 317 observations recognize B without any additional confirmation or copy.
- C (`UCGDZ885HY`) has one confirming observation followed by exactly one `would_copy`
  at line 1291. All 655 subsequent frame events are disarmed. The exact confirmed
  strings match the operator-provided expected B and C, and no other code confirms.
- There are no frame errors, error events, or stale frame results. Line 1948 is the
  final dry-run summary with `failure: null`. This supports clean shutdown. The report
  does not record the shutdown cause, keypress time, process exit code, or exit delay.
  Ctrl+C and return to the prompt are operator-reported. The last recorded state is
  disarmed. Active-OCR interruption cannot be inferred from this log. Existing native
  timestamped Stop/Disarm race probes remain the separate mid-inference evidence.

Discount baseline/rearm/new-code checks are complete. The interrupted-shutdown user
observation is recorded specifically as disarmed Ctrl+C, with clean-summary support.
The remaining planned supervised session is fresh-process Game recovery: prepare a
Game-context code before Start, verify disarmed startup and a fresh Ready baseline,
explicitly Arm and verify baseline suppression, then reveal a distinct new Game code
and require one exact `would_copy` followed by automatic disarm and clean Stop.
G2 remains PENDING and native manual paste matches remain 30/30.

## Fresh-process Game recovery audit and prepared G2 sign-off

All 735 records in `artifacts/manual-phase52-01/g2-game-recovery-01.jsonl` were reviewed.

- Line 2 verifies `running: false`, `ready: false`, `armed: false`, and zero dropped
  frames. Lines 3–4 verify Game dry-run startup and a new Ready baseline spanning
  578.284 ms and six observations.
- C (`2B4AKD9SDU`) appears in 146 disarmed frame observations before explicit Arm
  at line 151, followed by 303 armed observations without a copy decision. There is
  no `would_copy` for C anywhere in the report.
- D (`7PBGH54S8B`) has one confirming observation followed by exactly one `would_copy`
  at line 456, matching the expected string. The remaining 278 frames are disarmed.
- No error events, frame errors, stale results, or session failure occur. Line 735 is
  the final dry-run summary with `failure: null`, verifying the value omitted from the
  operator's abbreviated stopped message. Stop was operator-reported. The summary
  supports clean shutdown but does not identify the triggering command or exit delay.

Fresh process launch and fixture placement are operator observations supported by the
new report's startup and baseline sequence. There is no OS process identifier in the
report. This session verifies memory decisions; the native paste count stays 30/30.

### Final evidence matrix for the approved limited scope

| G2 requirement | Accepted evidence | Review |
|---|---|---|
| Real Windows pixels, local OCR, exact native writes and manual pastes | Thirty distinct ledger codes, 15 per profile, with matching expected/write/readback/operator paste | PASS |
| Disarmed startup, premature-arm rejection, stable baseline, explicit arm/disarm/stop | Original controls, both combined-session audits, GUI operator checks, and recovery report | PASS within recorded log/operator scope |
| Persistent baseline, one-shot, same-code rearm suppression, distinct new codes | Both combined-session reports plus historical native duplicate probes | PASS |
| Human interrupted exit and fresh-baseline restart | Discount disarmed Ctrl+C operator observation, clean summary, and new Game recovery report | PASS within recorded scope |
| Stop/Disarm during OCR, no subsequent native write | Timestamped races in `artifacts/phase51-windows-failures.jsonl`, both profiles, command accepted between OCR start and end, zero writes | PASS |
| Busy clipboard disarms and recovery requires fresh state | Same native failure report, 14/14 passing probes | PASS |
| Negative/banner/chat monitoring | `artifacts/phase51-negative-1800.jsonl`, 1800.067 seconds, zero memory write decisions in both profiles | PASS, existing negative-soak evidence |
| Owned BGR/latest-frame capacity one, slow-OCR backlog and freshness | Existing capture/pipeline tests, capture timing reports and native no-late-write results | PASS, automated evidence |
| Capture invalidation, blank frames, access loss, idle polls and watchdog | Real lock/unlock operator pass, injected access-loss/blank-frame tests, native recovery probes, and Phase 6 pause/resume evidence | PASS with explicitly approved physical-hotplug evidence substitution |
| Current supported physical ROI | Center-monitor full/crop operator passes at 1920 × 1080, 100%, SDR | PASS |
| Provider/models and latency provenance | Native reports retain CPU provider/session options, model hashes, commands and captured-frame timing | PASS for measured configuration |

No additional mandatory test gaps were identified under the explicitly approved limited
personal-use scope. Physical hotplug remains DEFERRED and unverified. Secondary-monitor
native use, HDR, rotation, 150%/200%, remote sessions and live display/topology changes
remain unqualified. Earlier failures remain in this record. G3 accuracy/latency and G4
release requirements are still outstanding and are not passed by this G2 review.

Prepared sign-off for operator confirmation:

> I accept the recorded G2 evidence for personal use on the center primary monitor at
> 1920 × 1080, 100%, SDR, local Windows console, with fixed topology during each session,
> including the previously approved physical-hotplug evidence substitution. I confirm
> G2 sign-off for this limited scope. GUI native clipboard copying may be implemented
> using explicit opt-in, the covering-window warning, supported-scope enforcement, and
> the existing safeguards, followed by validation of the GUI integration.

Operator confirmation: **APPROVED, 2026-11-05 MYT**. The operator explicitly approved
G2 sign-off for the previously agreed limited personal-use scope and evidence substitution,
and authorized GUI native clipboard implementation. Explicit opt-in, covering-window
warning, scope enforcement, and GUI integration verification are required. G3/G4 remain
pending. The earlier pending entries are historical evidence-review checkpoints.
