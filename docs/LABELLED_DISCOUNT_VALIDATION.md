# Labelled Discount annotation validation

The operator reported that a TradingView ROI containing the blue annotation below
remained armed without confirming. The code was absent during setup and added after Arm.
The reported processing duration was approximately 150 ms. The Windows retest result
is recorded below.

```text
LIMITED TIME OFFER
CODE: Q8M4Z7P2VK
```

No source screenshot or OCR trace of the failing TradingView frame was supplied.
Real local RapidOCR on a recreated 440 × 135 blue-text fixture read both lines
exactly with confidence 0.99771 and 0.97709. OCR wall time was 173.8 ms. The old
Discount parser returned no candidates. It required a bare token, plus a qualifying
promotion phrase below it. The exact reported OCR strings would fail both checks
regardless of speed. This establishes a reproducible policy failure, while the exact
transcription and timing of the operator's original pixels remain unverified.

The smallest format extension recognizes an anchored `CODE:` label and an exact
alphanumeric token. It requires a confident, closely spaced, left-aligned
`LIMITED TIME OFFER` heading above. Bare-code and Game layouts retain their existing
paths. The existing quality checks apply to the labelled line, including the original
image pitch floor calculated over all its characters. The O/0 check applies to the
extracted token so the O in the literal label is not treated as code evidence. A
recognized labelled token in setup is suppressed just like a bare token.

One changed capture containing a valid new code remains insufficient. The capture
worker discards identical ROI pixels. A deterministic live-session test starts armed
after an empty baseline, adds the annotation, and confirms that the single changed
frame stays at `confirming` without a write. A second changed frame containing the
same token within the existing window produces one memory copy and disarms. Capture
and OCR frame-age checks, the confirmation window, clipboard deadlines and native
consent are unchanged. No evidence establishes that the original frame was stale or
baseline-suppressed. The regression proves neither is necessary to reproduce the failure.

**Show last OCR results** exposes the last decision, raw text snippets, confidence,
OCR quality rejection and whether a parsed code was eligible, baseline-suppressed or
already copied. The panel retains static observations and displays the single-frame
confirmation state. It is optional and limits display to eight lines. A context/quality
message means the code did not enter the candidate set. There is no new persisted
GUI OCR log.

## Automated checks

On Windows with Python 3.12.14, `./scripts/check.ps1` and
`./scripts/check.ps1 -Ocr` both exited 0. Dependency checks, Ruff lint and formatting,
and strict mypy over 20 source files passed. Default pytest reported 186 passed and
16 OCR tests skipped in 42.97 seconds. The run with real offline OCR enabled reported
199 passed and 3 expected failures in 62.06 seconds. The expected failures still cover
the original tiny, compressed O/0 recall challenges. `git diff --check` exited 0.

The 2026-11-09 MYT develop commit review reran both commands on Windows 11 build
26200 with Python 3.12.14, RapidOCR 3.10.0, ONNX Runtime 1.31.1 and PySide6 6.12.0.
Both exited 0 with passing dependency, Ruff and strict mypy checks. The standard run
reported 186 passed and 16 opt-in skips in 44.73 seconds. The offline OCR run reported
199 passed and the same three strict challenge xfails in 69.61 seconds. Logs are in
`artifacts/develop-20261109-check.txt` and `artifacts/develop-20261109-check-ocr.txt`.

## Windows retest

**PASS (operator-reported, 2026-11-09 MYT).** On Windows in TradingView, the operator
confirmed that Stream Code Capture detected the exact new Discount code `Q8M4Z7P2VK`
after they clicked **Arm**. This records one successful post-arm detection. The report
did not include clipboard mode, paste verification, automatic disarming or timings.

Retest procedure:

1. Launch `./.venv/Scripts/python.exe -m stream_code_capture.gui` on develop.
2. Use Discount in dry-run. Enable Show last OCR results. Select a region containing
   both annotation lines and a small changing part of the chart. Keep the code absent
   until Start, Ready and Arm.
3. Add the exact annotation. Keep both text lines clear and ensure pixels in the ROI
   continue changing so OCR can independently observe the code twice inside its
   existing confirmation window. Expect the exact code and automatic disarming.
4. If the region becomes entirely static after its first changed frame, expect
   `confirming` without a copy. If detection still fails with motion, report the raw
   OCR lines, confidence and decision from the panel. This can identify transcription,
   context/quality, suppression or freshness issues in the actual chart.

Coverage applies to this labelled layout. Other headings, split label/token OCR boxes,
and OCR transcription errors can still abstain. The tests use a generated fixture and
injected capture for the static confirmation case. Neither is representative TradingView
or livestream qualification.
