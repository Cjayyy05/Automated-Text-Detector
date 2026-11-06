# Instant Stream Code Capture — project specification

Status: offline foundation plus live console integration. Python 3.12, Windows 11 x64.
An explicit `game` detection profile now shares this pipeline; `discount` remains the
default. Game requires nearby redemption/expiry context, 8–20 uppercase ASCII characters
with optional internal hyphens, both letters and digits, and the same lifecycle safeguards.
Its additional policy guard prevents hyphens/longer strings bypassing O/0 or source-size
restrictions. No OCR/model changes. See `GAME_PROFILE_VALIDATION.md`; simulated captured
playback is a functional test of reused slides, not general livestream qualification.
Real DXcam -> OCR -> native clipboard passed three generated-screen events; a separate
30-event real-capture dry-run passed. The operator signed off G2 for the limited
personal-use scope below on 2026-11-05 MYT, after 30 exact manual native paste matches.
Phase 6 now supports explicit per-session GUI native-copy opt-in, with dry-run startup.
GUI integration paste validation remains separate from the signed-off pipeline evidence.
The final G3 and G4 requirements continue to apply.

Phase 5.2 reviews remaining G2 usability evidence and inventories current Windows displays
read-only. See `PHASE52_VALIDATION.md`, `PHASE52_MANUAL_CHECKLIST.md` and the blank manual
results record. Inventory and automated clipboard readback are not manual ROI/paste passes.
Limited-scope G2 sign-off does not complete the broader display matrix or G3/G4.

Phase 4 adds configuration/second-model diagnostics and a reproducible captured short-exposure
matrix for both profiles. An opt-in CPU configuration improves the reused game-slide latency
without replacing models or weakening confirmation. Default behavior is retained pending
representative validation. New timing fields separate candidate-validation/confirmation CPU
work from first-recognition-to-confirmation elapsed time. See `PHASE4_VALIDATION.md` for
measurements, the legacy harness disarm artifact, and actual versus nominal exposure timing.

Phase 2 retains the default model and adds opt-in tiny/cascade CPU experiments, stage/ORT
profiling, pre-OCR stale rejection, notified latest-frame delivery and precise Windows pacing.
The varied corpus exposed high-confidence O/0 errors above the original resolution floor:
runtime now explicitly abstains on code-like strings containing either glyph. It does not
substitute characters. This loses valid-code recall and is not a recognition fix. The original
three challenge xfails and G3 block remain. See [Phase 2 evidence](PHASE2_VALIDATION.md).
Activity filtering is optional and must force periodic OCR despite background motion;
pending confirmations bypass it. Fallback must never override a quality rejection.

Phase 3 provides offline source preparation, exact labelling, session/identity/hash-disjoint
splits and separate raw-recognition versus clipboard-policy scoring. No runtime recognition
or safety threshold changes were justified by the available synthetic data. Representative
real-video qualification is blocked on user-provided media and independent labels. The Phase 3
exploratory target is >=90% exact recall with zero observed incorrect writes; the stricter
G3 release criteria below remain unchanged. See `DATASET_WORKFLOW.md` and `PHASE3_VALIDATION.md`.

## User outcome and requirements

A streamer briefly displays a one-use promotional code within a video. The user watches
the stream on the Windows PC; pixels from a phone screenshot are only a visual reference.
The desired example is tiny, slightly slanted chart text above product/discount text.
A large permanent `40% OFF — USE CODE: JORDY` banner, live chat, and chart prices are
distractors. The implementation must find *new chart codes*, not the first uppercase word.
Example strings are not runtime allowlists or denylists.

1. Select a chart-area ROI in physical source-image pixels. Exclude the top banner and chat.
   Detect text positions automatically inside that ROI; no absolute target-code coordinates.
2. Recognize pixels locally using warmed RapidOCR/ONNX models. Upscale small text, use
   detector quadrilaterals and RapidOCR's perspective crop for recognition of slanted lines.
3. Preserve exact ASCII uppercase alphanumeric codes. Initial format: 8–16 characters,
   at least one letter and digit. Require nearby promotional context below the code.
   The opt-in game profile extends this to 8–20 characters with internal hyphens and
   nearby redemption/expiry context. Other formats remain unsupported; O/0 abstains.
4. Start disarmed. Observe a baseline before arming. Suppress baseline codes regardless
   of nearby context; require exact agreement on two distinct, consecutive observations.
   Ambiguity, stale/out-of-order frames, blank frames, and changed text reset agreement.
5. Copy once per explicit arm. Remember copied strings for the process lifetime, including
   across rearm. Do not retry a failed clipboard write without rearming. Report failures.
6. Consume the newest available captured frame, with at most one pending frame and one
   inference in flight. Drop obsolete pending frames; never accumulate an OCR queue.
7. Do not redeem, click, submit, bypass DRM, scrape DOM, send frames remotely, or phone home.
8. Provide image CLI, deterministic generated fixtures and ground truth, headless unit
   tests, real offline OCR integration, and repeatable benchmark inputs before GUI work.
9. Eventually validate real DXcam frames -> this recognizer/policy -> Windows clipboard.
   File replay and mock clipboard tests cannot satisfy the live gate.

## Architecture

```mermaid
flowchart LR
    FILE[Local image / generated sequence] --> ROI[Chart ROI crop]
    DX[DXcam region capture producer] --> SLOT[Capacity-one newest owned frame]
    SLOT --> ROI
    ROI --> OCR[Upscale + text detection + perspective recognition]
    OCR --> POLICY[Baseline / context / exact agreement / freshness]
    ARM[Explicit arm or disarm] --> POLICY
    POLICY --> CLIP[Clipboard interface]
    CLIP --> MEM[Memory clipboard: tests and replay]
    CLIP --> WIN[pywin32: explicitly selected image command]
    POLICY --> TIMING[Structured decisions and stage timings]
```

| Component | Contract / ownership |
|---|---|
| `Frame` | Owned uint8 BGR image, increasing sequence, monotonic acquisition timestamp |
| `Rect` | Exclusive right/bottom, validated in frame coordinates; crop copies memory |
| `Recognizer` | `warmup()` and `recognize(image) -> list[TextLine]`; boxes ROI-relative |
| `RapidRecognizer` | One reusable engine; local pinned models; fails on missing requested provider |
| `TextLine` | Exact text, OCR confidence, axis-aligned envelope of detector quadrilateral |
| `DecisionPolicy` | Single-thread owner; baseline, arm, observe, committed, disarm |
| `Pipeline` | Crop -> OCR -> decision -> clipboard; no async inference queue |
| `Clipboard` | `write(text)` returns on success, raises on failure; memory or pywin32 |
| `LatestFrame` | Lock-protected capacity-one pending slot, replaces oldest, counts drops |
| `synthetic` | Seeded renderer, ground-truth manifest, separate from recognition |
| `CaptureWorker` / `DxcamSource` | DXGI polling, owned BGR frames, duplicate ROI suppression, capacity-one handoff |
| `LiveSession` / `Controls` | Console lifecycle; single-owner policy; urgent stop/disarm write inhibition |
| `Metrics` | Bounded last-10000 samples per stage, p50/p95/max and sample counts |
| CLI | Generate, image, replay, live; JSON stdout; memory clipboard and disarmed by default |

ROI must remain fixed for a policy session. Construct a new session after resizing the
source or changing ROI; do not carry candidate coordinates or baseline across unrelated
scenes. Console commands are marshalled to the policy owner. An inhibition event/generation
and a lock around the native write linearize stop/disarm against in-flight inference.
The live producer owns its DXGI resources; policy/OCR has a single separate owner.

The pinned DXcam `grab(copy=True, new_frame_only=True)` API is polled by our producer
instead of using DXcam's blocking buffered reader. DXGI calls are nonblocking in 0.3.0.
Acquisition-call start and completion use `perf_counter_ns`; there is no inferred conversion
from DXGI presentation timestamps. Identical ROI pixels are dropped even if the desktop
changed elsewhere. Our handoff has one pending frame and no inference queue. Any DXcam
warning invalidates the session. A blank image or 2500 ms without a completed capture poll
also stops capture. Successful polls with no update or identical ROI pixels keep the session
alive without publishing an OCR observation. Live baseline readiness may use a valid
recognized frame followed by at least the configured baseline interval of healthy,
unchanged capture polls. Any newer pending changed frame must be processed first.
Idle stability never supplies an armed code-confirmation observation.
If baseline OCR exceeds the frame-age budget, its suppression-only result may be
learned only when capture reports no intervening ROI change and a successful poll is
within the existing freshness limit. Changed or unhealthy capture rejects the result.
Armed recognition and clipboard writes always retain the original frame deadlines.
Camera initialization has a separate bounded 10-second allowance and is reported separately.
Window identity/occlusion and fast content changes are not fully detected; see manual matrix.

## Decisions and temporal semantics

Candidate extraction uses whole OCR lines, not substring guesses: exact format, score >=
0.96, promotional context score >=0.75, horizontal alignment within two code heights,
and context no more than ten code heights below. It recognizes `N% off`, `promo`, or
`use code`, without requiring the reference product name. No O/0, I/1, B/8 repairs.
These conservative rules can miss real codes and can still accept a plausible wrong OCR
string. Confidence is a model score, not a guarantee. Two correlated errors may agree.

Current source-quality guard: code-like lines with detector top-edge pitch <10 original
pixels/character carry `insufficient_source_resolution` and cannot become candidates.
This is an explicit conservative restriction motivated by the challenge O/0 failure,
not a validated universal threshold or an OCR correction. It sacrifices tiny-code recall.
Upsampling does not increase source pitch. Raw text/confidence remain available.
Exact-recall regression tests for all three challenge cases are strict expected failures;
separate regression tests require no wrong accepted transcription. Held-out G3 evidence
is required before lowering this guard or claiming supported tiny-chart performance.

Baseline suppression is monotonic within a session. A code already displayed when armed
is intentionally ineligible. A single baseline image is the offline minimum; live collection
requires recognized baseline text plus stable code observations or healthy unchanged
pixels over >=500 ms, then displays readiness. Disarmed
observations continue adding persistent codes to suppression. Baseline OCR
misses can defeat suppression, so live validation must include them. Same exact code at
multiple positions is one candidate. Two different eligible codes cause abstention.

Production defaults allow 1000 ms frame age and agreement gap as conservative development
limits, not latency success. Phase 2 must set a measured live age budget <=100 ms before
claiming the latency gate. Offline replay explicitly uses 10000 ms limits so inference
speed does not obscure its accuracy test; it reports this setting. No replay timing is
reported as screen-capture latency. One image cannot meet default two-frame confirmation;
an explicit `--confirmations 1` is available only for manual image/clipboard diagnostics.

## Timing definitions and instrumentation

Use `perf_counter_ns()` on one host. Record first eligible captured-frame acquisition
`t0`, capture completion, inference start/end, policy end, clipboard API success and close
`t_clip`. **Primary latency = t_clip - t0**, including dropped frames and confirmation
delay, not just the last accepted frame's processing time. If the first visible frame is
dropped, retain its timestamp in a capture-side validation trace. Do not substitute the
first OCR detection time. Physical video presentation latency is a separate metric.

| Stage | Definition | Initial budget hypothesis |
|---|---|---:|
| Capture/transfer | PC frame availability to owned ROI pixels | 8 ms |
| Handoff + crop/preprocess | Capture timestamp to inference-ready image | 4 ms |
| First OCR | Detection, perspective crop and recognition | 32 ms |
| Confirmation | Wait for and recognize next distinct frame | 40 ms |
| Decision | Pattern/context/baseline/agreement checks | 1 ms |
| Clipboard | Open/empty/set/close successful transaction | 5 ms |
| Reserve | Scheduling and jitter | 10 ms |

Budgets are engineering hypotheses totaling 100 ms, not measurements. First startup/model
warmup is measured separately and excluded only after the ready indicator. Phase-1 reports
capture-call duration, crop, preprocessing, OCR, detection/recognition substage times when
available, policy, clipboard, process, handoff age and per-frame result time. Live reports
include p50/p95/max and sample counts, bounded to the last 10000 samples per metric. Generic
`first_observed_to_clipboard` is a lower bound that excludes earlier dropped/rejected code
frames. Only the controlled screen-test marker records the true first captured code frame
before handoff drops, independent of OCR, and yields the primary latency measurement.
Startup/warmup is excluded. Add deadline misses, CPU/GPU load and memory for G3. Record
ROI size, display scale/Hz,
video resolution/FPS/bitrate, model hashes, package versions and target PC hardware.

## Dependencies and model provisioning

Versions/API checked on 2026-10-29 against PyPI and installed source (see validation).
Use `rapidocr`, not the legacy `rapidocr_onnxruntime` API. It returns an object with
`boxes`, `txts`, `scores`; no-text results contain `None`. The current wheel bundles
PP-OCRv6 small detection and recognition models and embedded recognition dictionary.
Explicit local paths and dictionary preflight prevent fallback downloads. Network-blocked
integration tests exercise initialization, warmup and recognition.

Use only `opencv-python-headless`: RapidOCR depends on it, and installing another OpenCV
wheel beside it creates a shared `cv2` conflict. PySide6 owns future UI display.
Core/dev/Windows direct dependencies are exact-pinned; `requirements-lock.txt` freezes the
tested Windows transitive resolution. Optional GUI is pinned but deferred and not installed.
Setup may access PyPI; recognition takes local files/arrays only.

CPU is validated first. Adapter flags `--provider cpu|cuda|directml`, `--threads`, `--scale`
allow identical replay benchmarks. GPU runtime packages must be installed in a **separate**
environment with only one ONNX Runtime distribution; GPU wheels/drivers are not part of the
validated CPU lock. Check provider availability and actual detector/recognizer sessions;
fail instead of silently benchmarking CPU fallback. Compare accuracy as well as timings.

## Assumptions and risks

| Risk / assumption | Impact | Mitigation and release evidence |
|---|---|---|
| Text too small/compressed/occluded | Wrong or missed exact code | Challenge corpus, abstain, scale/ROI tuning, held-out real clips |
| Perspective and slope | OCR loss | Detector quadrilateral crop; test +/-6 degrees and beyond |
| Moving candles overlap text | False movement localization | Do not treat all pixel change as new text; use text/content tracking later |
| Banner/chat accidentally in ROI | Wrong copy | User ROI preview; baseline and context; full-scene distractor tests |
| Baseline OCR misses permanent code | New-code false positive | Multi-frame stable baseline and negative soak before live release |
| Code present before arming | Miss by design | Explicit readiness/status, user knows baseline behavior |
| Two frames share OCR mistake | Wrong exact code | No confidence-only accuracy claim; held-out precision gate |
| Current v6 small CPU cost | >100 ms latency | Measure; smaller detector/recognizer, recognition crops, providers next |
| Video frame reused as confirmation | False certainty | DXcam video_mode=False; presentation timestamp dedupe |
| Capture access loss / minimized / protected video | Black/stale frame | Disarm, show unavailable, no DRM workaround |
| DPI/multi-monitor/rotation/HDR | Wrong ROI/colors | Physical-pixel ROI, DPI awareness and live matrix testing |
| Clipboard locked or later changed by another app | Failed/lost copy | Immediate failure/disarm; manual verification; no overwrite retry loop |
| EmptyClipboard succeeds then Set fails | Previous clipboard may be lost | Report failure; do not promise atomic preservation |
| Baseline/copy set grows | Memory over very long session | Explicit session lifecycle; bounded retention design if needed |
| Synthetic fixtures differ from stream | Overstated accuracy | Separate smoke from real held-out corpus; never train/tune on holdout |
| Repeated runs differ across hardware | Threshold instability | Pin models; record hashes/providers; allow no fuzzy exact-code scoring |

## Phased roadmap and pass/fail gates

**G1 — Foundation (established).** Pass iff installation resolves with `pip check`; Ruff
lint/format and strict mypy pass; all headless unit tests pass; network-blocked real OCR
integration recognizes all three seeded standard chart targets exactly and writes each
once to memory, with zero writes for the negative-only sequence and zero JORDY writes.
Generator must vary codes by seed and refuse to overwrite fixtures. Fail on any assertion,
network attempt, incorrect copy or unreported skipped integration check. This is a smoke
gate only. Challenge failures are recorded, not mislabeled as passed accuracy.

**G2 — Real Windows path (implemented; full qualification pending).** Require DXcam region capture into latest-frame handoff,
owned BGR copies and timestamps, explicit arm/disarm/stop, stable baseline readiness,
source-loss disarming, and structured latency tracing. On target PC, a local test video
rendering generated scenes must feed *real captured frames* into this exact pipeline and
the real clipboard. Pass iff 30 randomly positioned/code-varied events produce exact
manual paste matches, no duplicate or disarmed writes, no banner/chat writes in a 30-minute
negative run, capture loss disarms, busy clipboard failure is reported, and backlog is <=1
pending frame under deliberately slow OCR. Log evidence. No live gate passes by file replay.

**G2 source scope.** The source is a fixed rectangle of desktop pixels on a selected
monitor. Covering, moving, or minimizing a window can change the pixels in a healthy
capture. A covering window can display a code that meets the confirmation rules and
is copied in native mode. Users must disarm before moving, covering, or minimizing
the intended content. Before enabling GUI native clipboard mode, require full G2
qualification, a clear warning about this risk, and explicit user opt-in.

Monitor loss, invalid capture, DXcam access loss, capture errors, and capture-poll watchdog
expiry must stop the session and disarm. Restart requires a fresh baseline and explicit
rearm. Healthy idle polls preserve session state, and identical pixels supply no new
confirmation evidence. Confirmation, freshness, duplicate suppression, and all other
G2 checks remain mandatory. The historical moving-occlusion failure remains in the
manual ledger under its original criterion.

**Approved personal-use G2 scope (2026-11-05 MYT).** Initial GUI native copying is
limited to the center primary monitor at 1920 × 1080, 100% scaling, SDR, on the local
Windows console, with monitor topology unchanged during a session. Re-enumerate outputs
and select a fresh ROI after configuration changes. Secondary-monitor native use, HDR,
rotation, 150%/200%, remote sessions, and live display/topology changes remain unqualified.
Existing secondary-monitor observations remain valid within their recorded scope.
For this initial personal-use G2 sign-off, the user explicitly accepts the real
lock/unlock access-loss pass together with injected monitor-loss/blank-frame tests
and native recovery probes in place of physical unplug/replug. Physical hotplug
remains deferred and unverified. The display-matrix requirements apply to any future
expansion of supported configurations. All capture invalidation and clipboard safety
protections above remain mandatory even during unexpected unsupported transitions.
The GUI must enforce this supported scope when native mode is implemented. The 30
manual matches and remaining control/recovery observations still require recorded
evidence and final sign-off. The operator confirmed G2 sign-off for this limited scope
on 2026-11-05 MYT. Native GUI integration requires explicit opt-in, the warning and
scope enforcement above, and separate integration validation. G3/G4 remain pending.

**G3 — Accuracy and latency.** Freeze a held-out corpus of >=1000 distinct code appearances
and >=10000 negative chart/chat/banner scenes from permitted real or representative PC
video, with independent transcription, 10–24 px text heights, slopes, compression, and
durations of 100/250/500/1000 ms. Require zero incorrect accepted strings, >=99% event
recall for declared supported conditions, zero negative-scene writes, and zero repeats.
Report excluded/unsupported conditions and confidence intervals; 0 errors is not proof
of perfect future accuracy. On target PC, 100 warmup events followed by >=1000 measured
events: p95 primary latency <100 ms, p99 <150 ms, and deadline miss rate at 100 ms <=5%,
with the same accuracy thresholds, capacity-one backlog and no monotonic memory growth
>50 MB over a 30-minute soak. Report worst case; do not claim every event is <100 ms.
CPU and any chosen GPU configuration must each pass accuracy; choose the fastest proven
configuration. Failure blocks performance claims and product readiness.

**G4 — Minimal desktop UX.** For qualification after G2, require PySide6 ROI selection, arm/disarm and obvious
state, start/stop, timing/provider diagnostics, and session reset. Pass smoke tests at
100/125/150/200% DPI, two monitors, source resize, lock/unlock, and shutdown during inference;
zero unintended clipboard writes. GUI cannot block capture or inference. G3 still gates
performance/accuracy claims. Packaging and broader capture are later work.

## Manual Windows validation

Phase 5 adds native write/readback timing and explicit failure/negative qualification
harnesses; see `PHASE5_VALIDATION.md`. Frame freshness is checked after controls and again
at the locked clipboard handoff. Native completion-age violations are reported as failures;
the Windows API is not a hard-real-time service. Neither this fix nor successful generated
screen tests relax the G2 manual/display checks or the G3 representative accuracy gate.

Phase 5.1 isolates arena allocation retention with otherwise identical session settings.
The arena-disabled 1800-second negative soak passes the unchanged harness memory gate
(14.1 MiB growth versus 50 MiB), compared with Phase 5's arena-on 77.8 MiB failure.
Native paired measurements expose a latency/memory tradeoff; see `PHASE51_VALIDATION.md`
for all completed comparisons, failures and recovery checks. No runtime default, model,
recognition rule or acceptance threshold is changed. A fixture memory pass does not satisfy
the independent accuracy, manual Windows or latency gates above.

See `docs/WINDOWS_VALIDATION.md` for current image-to-clipboard diagnostics and the explicit
remaining G2 qualification procedure. Do not call a phone screenshot or file replay live capture.
