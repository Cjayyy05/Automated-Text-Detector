# Discount layout and O/0 validation

This comparison used the earlier O/0 abstention and two-observation policy.
[v0.2.0 validation](DETECTION_POLICY_VALIDATION.md)

The [recognition follow-up](DISCOUNT_ACCURACY_VALIDATION.md) audits all 11 misses and
adds split-label validation. The table below preserves the earlier comparison.

## Reproduction and decision

The operator reported exact OCR of `680J6BN7JX`, `LudiFlex Eval 50k` and `100% off`,
followed by `unresolved_O0_glyph`. The original TradingView pixels were unavailable.
Real offline baseline OCR on a recreated blue annotation read the exact token with
confidence 0.99996 and marked it `unresolved_O0_glyph`. The English PP-OCRv4 recognizer
read the same token from the padded source crop at 0.94764. The adapter's conservative
glyph guard explains this rejection. The existing layout already allowed a percentage
offer below the code, with space for an intervening product name.

The layout change requires a whole code-shaped OCR line, optionally with an anchored
code label, and separate spatially associated evidence. It accepts qualifying offers
above, below or to either side. Bare `promo` or `promotion` in unrelated prose no longer
qualifies. A standalone code heading or percentage-off phrase can support a bare token.
A limited-time heading alone needs an explicitly labelled token. Numbers, timestamps,
prices, `@` handles and metadata prefixes are ineligible under the exact format. The
recognizer's source-pitch and confidence thresholds remain in place. The policy also
rejects O/0 in injected recognizer output, even without an adapter rejection flag. No
spelling repair, merchant dictionary, model change or new live inference call is used.

Only the unchanged token is eligible for copying. Existing baseline learning, two
distinct changed-frame observations, expiry, one-shot arm and duplicate suppression
still apply. Capture, native consent and clipboard verification were outside the change.

## Matched offline benchmark

Both runs used Windows, Python 3.12.14, RapidOCR 3.10.0 and ONNX Runtime 1.31.1 on CPU.
`scripts/benchmark_discount_layouts.py` fed two changed source images per event through
the existing pipeline after an empty baseline, with default freshness and a memory
clipboard. The seed was 41361. Generated images cover three fonts/colors, JPEG in one
style, six layouts and eight negative types. Historical smoke and challenge manifests
were included. The timing sample has 114 processed images per run. There was no capture,
native clipboard write, or real broadcast video in this benchmark.

| Measure | Before (`1f0342d`) | After |
|---|---:|---:|
| Clear layout exact copies | 6/18 | 17/18 |
| Clear layout abstentions | 12 | 1 |
| Original smoke exact copies | 3/3 | 3/3 |
| Generated O/0, recreated annotation and original challenges | 0/10 | 0/10 |
| All exact copies | 9/31 | 20/31 |
| Positive abstentions | 22 | 11 |
| Incorrect copies from 26 negative events | 3 | 0 |
| Incorrect copies from 31 positive events | 0 | 0 |
| Per-frame processing p50 / p95 / worst, ms | 173.813 / 536.222 / 692.363 | 192.665 / 585.102 / 982.483 |
| OCR p50 / p95 / worst, ms | 173.233 / 534.753 / 690.958 | 191.731 / 583.638 / 980.844 |
| Candidate validation p50 / p95 / worst, ms | 0.010 / 0.027 / 0.755 | 0.015 / 0.037 / 0.074 |

The old policy copied `TRADER2345` on all three generated `chat about a promo` cases.
The remaining clear-layout miss occurred when OCR merged a code and `25% off` into
one line. Unlabelled substring extraction from such lines is outside the accepted
format. Processing was slower in the after run. The OCR settings were identical and
almost all of that elapsed difference was inside OCR, so the sequential wall times do
not isolate a policy-induced slowdown. Candidate validation stayed below 0.04 ms at p95.

### Why the O/0 guard remains

The diagnostic re-read used a separately trained local PP-OCRv4 English recognizer on
a padded crop selected by the baseline detector. The second model's output was never
passed to policy. Of ten probes, baseline read four exactly, and PP-OCRv4 read five
exactly. They agreed on the same wrong token four times. For example, the printed
`YPOWX64975` became `YP0WX64975` with scores 0.98853 and 0.91624. The small sample
does not validate a confidence-based exception. The historical template and crop
results also show font dependence and correlated errors. See
[Phase 3 validation](PHASE3_VALIDATION.md). The diagnostic cost was 48.718 / 58.415 /
61.505 ms p50 / p95 / worst for ten crops. The live path does not incur that cost.

The three original strict challenge xfails remain. O/0 still costs exact recall, and
the user's token will continue to abstain. A code-shaped identifier near genuine
offer text can remain indistinguishable from a code. Keep chat and other identifiers
out of the ROI. These fixtures do not qualify arbitrary layouts, text languages or
real livestreams. A release decision needs an independently labelled broadcast
holdout with matched O/0 pairs, fonts, sizes, slant and compression, and an evaluation
of wrong writes as well as recall.

## Commands

The same benchmark command ran before and after the policy change, with `--report`
set to `artifacts/discount-layouts-before.json` and `artifacts/discount-layouts-final.json`
respectively. The alternate model was already present locally.

```powershell
./.venv/Scripts/python.exe scripts/benchmark_discount_layouts.py --manifest samples/smoke/manifest.json --manifest samples/challenge/manifest.json --alternate v4 --report artifacts/discount-layouts-final.json
./.venv/Scripts/python.exe -m pytest -q tests/test_policy.py tests/test_labelled_discount.py tests/test_discount_layouts.py tests/test_pipeline.py --run-ocr
./scripts/check.ps1
./scripts/check.ps1 -Ocr
git diff --check
```

The targeted run passed all 56 tests in 5.41 seconds. `./scripts/check.ps1` exited 0
with 203 passed and 17 OCR skips in 43.08 seconds. `./scripts/check.ps1 -Ocr` exited
0 with 217 passed and the same three strict challenge xfails in 66.78 seconds.
Both runs passed dependency checks, Ruff lint and formatting, and strict mypy over
20 source files. `git diff --check` passed. Logs are in
`artifacts/discount-layouts-check.txt` and `artifacts/discount-layouts-check-ocr.txt`.

## Windows TradingView retest

1. From the `develop` worktree, run `./.venv/Scripts/python.exe -m stream_code_capture.gui`.
   Select **Discount**, keep **Dry Run**, and turn on **Show last OCR results**.
2. With the annotation absent, choose an ROI covering where the annotation will appear
   and a small moving part of the chart. Click **Start**, wait for **Ready**, then click
   **Arm**.
3. Add the reported three lines. If the OCR text matches, expect `unresolved_O0_glyph`,
   no simulated copy, and continued arming. Keep the raw OCR text if it differs.
4. Replace the code with a fresh uppercase test token of 8–16 letters and digits
   containing neither `O` nor `0`. Move the percentage offer above or beside the code.
   When both lines stay legible over two changed frames inside the confirmation window,
   expect the exact token in **Last confirmed code** and automatic disarming. If OCR
   merges the lines, increase spacing and keep both boxes in the ROI.

This TradingView retest is pending. No native clipboard opt-in is needed.
