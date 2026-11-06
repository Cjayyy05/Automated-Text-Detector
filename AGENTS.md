# Instant Stream Code Capture engineering rules

Read `docs/PROJECT_SPEC.md`, `README.md`, and `docs/VALIDATION.md` before changing behavior.
Also read `docs/PHASE2_VALIDATION.md` and `docs/WINDOWS_VALIDATION.md` for the current
benchmark limits and safety changes. Preserve all challenge xfails until exact recall is fixed.
Inspect existing work and `git status` first. Do not commit, push, delete user artifacts,
or rewrite unrelated work without a user request.

This is a Python 3.12 Windows desktop application. The source is displayed video pixels,
not DOM text. Begin with a user-selected chart ROI. Do not hardcode screenshot coordinates,
the example code, JORDY rejection, streamer names, or synthetic ground truth into runtime
recognition/policy. Fixture-only rendering coordinates and banner text are intentional.

No automated redemption, clicks, submission, DRM workarounds, cloud OCR, telemetry,
or network requests during recognition. Pin dependencies and verify APIs against installed
versions and primary documentation. Model provisioning is setup-time only; fail closed if
models or providers are missing. Keep a reproducible model hash record.

Preserve explicit disarmed startup, baseline-before-arm, conservative exact-string policy,
same-code deduplication, one-shot copy, stale rejection, and clipboard-error disarming.
Never silently change case or substitute ambiguous characters. Threshold changes require
held-out accuracy evidence; OCR confidence is not a calibrated exact-code probability.
The pipeline and policy have a single owner thread. UI commands must be marshalled to it.

Use real offline OCR for integration checks, and injected recognizer/clipboard interfaces
for deterministic unit tests. Unit tests must not require a display or mutate the OS
clipboard. Label fixtures, mock timings, replay timings, and captured-frame measurements
accurately. Never claim DXcam, clipboard, GPU, accuracy, or <100 ms success without evidence.

The capture phase must deliver owned BGR frames through a capacity-one/latest handoff.
Do not queue OCR jobs or count reused DXcam frames as independent confirmations. Keep one
warmed OCR instance per worker; no model initialization or downloads in the hot path.
Measure before adding caches, GPU code, alternate models, tracking, or concurrency.
Keep experimental profiles opt-in until recall matches or exceeds the default on held-out
inputs. Never bypass the O/0 abstention or source-resolution guard with a fallback model.
Synthetic font templates are diagnostics, not proof that arbitrary broadcast text is correct.

Run `./scripts/check.ps1` after changes; run `./scripts/check.ps1 -Ocr` for OCR/policy/fixture
changes. Log commands, failures, fixes, environment, and unresolved gates in validation docs.
Do not relax assertions to conceal recognition errors. Offline replay's generous timing
budget is for accuracy testing only and must never become a live default.

Defer extensive GUI work until real capture -> OCR -> policy -> real clipboard passes
the Windows gate. Then use PySide6 with ROI selection, arm/disarm, status, and stop controls.
Keep interfaces small; no speculative plugin frameworks. Do not create subagents unless
the user explicitly requests delegation.
