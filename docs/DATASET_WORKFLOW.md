# Local recording and screenshot qualification

This workflow does not capture the screen, open a simulated window, access a website,
or write the Windows clipboard. It prepares local files and scores offline recognition.
It accepts a user-selected chart ROI and never uses target text or labelled code boxes
to guide the normal OCR/policy replay. Real-video qualification remains blocked until
representative media and independently checked labels are supplied.

## Prepare original pixels

Keep the original permitted recording unchanged. Use a new output directory per import.
Use the **same session ID** for every clip/screenshot from the same recording session,
including re-encoded copies. Do not invent a new session ID for each appearance.
The tools hash sources and extracted pixels, but cannot detect renamed/re-encoded sessions
or prove that a declared recording is authentic broadcast footage.

```powershell
# Decode frames 0..899 sequentially, retain every frame. No real-time playback.
./.venv/Scripts/python.exe scripts/dataset.py prepare 'C:\Media\session-A.mp4' --kind recording --session session-A --start 0 --stop 900 --stride 1 --output datasets/session-A

# Source-image order is exactly the command's order. Screenshots have no video timestamp.
./.venv/Scripts/python.exe scripts/dataset.py prepare 'C:\Media\before.png' 'C:\Media\code.png' --kind screenshot --session session-B --output datasets/session-B

# Existing generated PNG/JPEG inputs may also be imported; label their origin honestly.
./.venv/Scripts/python.exe scripts/dataset.py prepare samples/smoke/case_000_1.png --kind synthetic --session synthetic-smoke-7 --output datasets/synthetic-image
```

The placeholders above are **not existing user files**. Supported video containers:
MP4/MKV/MOV/AVI/WebM/M4V; installed OpenCV decoder support is still required. Local playlists,
URLs and camera identifiers are refused. Images: PNG/JPEG/BMP/TIFF/WebP. Decode failures or
EOF are reported together as `decoder_end_or_failure`; verify extracted counts against
the intended segment, rather than assuming every premature decoder stop is genuine EOF.
The default bound is 3000 retained frames; `--max-frames` changes it explicitly.
Use `--stride 1` around brief appearances: subsampling can remove the entire target.

`dataset.json` records source SHA256, session ID, origin, decoder/FPS where available,
source indices, extraction limits, image dimensions, PNG hash and decoded-pixel hash.
Lossless PNGs preserve **decoded** pixels; they do not undo source compression.
`timestamp_ms` is OpenCV `CAP_PROP_POS_MSEC`, which can be unavailable/inaccurate for some
backends and variable-frame-rate sources. It is not a verified presentation timestamp,
Windows acquisition time, or evidence of capture-to-copy latency. No FPS-derived fake
timestamps are supplied for screenshots. Failed imports leave their incomplete output for
inspection and never overwrite existing datasets.

## Review and label

Copy `labels.csv` to `reviewed.csv` and edit with a text/CSV editor. Open the original
extracted PNGs yourself, for example in Paint, to read source-pixel coordinates. No label
GUI or window automation is included. Do not rescale/recompress originals during labelling.

Every row must retain its unique `frame_id`. Fill these columns:

| Column | Meaning |
|---|---|
| `event_id` | One appearance or negative interval; group its baseline and following frames |
| `state` | `baseline`, `visible`, `partial`, `negative`, or `unknown` |
| `code` | Exact independently verified target, preserving case, zeros and separators; never an OCR guess |
| `box` | Target code only, full-source `left top right bottom`; right/bottom exclusive |
| `roi` | User-selected chart/search area, same coordinate convention, fixed within an event |
| `tags` | Semicolon-separated conditions, e.g. `small;italic;O0;compression;moving_background` |
| `reviewer` | Reviewer identities or provenance; synthetic generator labels must say synthetic |

A fully visible example row has the shape:

```csv
frame_id,event_id,state,code,box,roi,tags,reviewer
1,appearance-01,visible,aB-23Cd,105 190 245 216,70 160 610 325,small;slanted,reviewer-A/reviewer-B
```

Those coordinates/text illustrate the schema only; choose values from the actual image.
Labels allow printable ASCII without whitespace, including short codes, lowercase and
separators. This does **not** expand the runtime acceptance policy: it still requires
8–16 uppercase alphanumerics, both letters and digits, context, quality and confirmation.
Unsupported formats remain in the accuracy denominator and must be reported as misses.

- `baseline`: first event frame before target appearance; leave `code` and `box` empty.
  Permanent promotions should already be visible so the existing policy can suppress them.
- `visible`: full target visible; requires exact code and box inside ROI.
- `partial`: some characters occluded/clipped. Supply full identity only if independently
  verified elsewhere; otherwise leave it empty. Partial-frame writes are counted as unsafe.
- `negative`: no transient target, even if banner/chat/permanent codes exist. Empty target.
- `unknown`: undecidable annotation, not a convenient negative. Evaluation refuses unresolved
  unknowns instead of silently excluding them. Retain an audit trail when resolving labels.

Use different events for different targets and keep source indices increasing. This first
tooling version labels at most one target per frame and uses axis-aligned code boxes;
simultaneous target codes require explicit dataset/schema work, not arbitrary selection.
Each replay event is a fresh policy session with one explicit arm; cross-event process-lifetime
deduplication remains covered by the existing policy/live tests, not this replay score.
An event without a baseline is a **snapshot diagnostic**: recognition is measured while
disarmed, and no clipboard event recall or invented second confirmation is reported.

```powershell
./.venv/Scripts/python.exe scripts/dataset.py label datasets/session-A/dataset.json --labels datasets/session-A/reviewed.csv --output datasets/session-A/labelled.json
./.venv/Scripts/python.exe scripts/dataset.py audit datasets/session-A/labelled.json
```

Every frame needs exactly one row, a reviewer and ROI. Bounds, label consistency, frame
hashes, ordering and immutable output paths are checked. Labelled manifests stay beside
their relative image paths. Paths escaping the dataset directory are refused.

## Freeze partitions before choosing methods

```powershell
./.venv/Scripts/python.exe scripts/dataset.py split datasets/session-A/labelled.json datasets/session-B/labelled.json --seed qualification-v1 --holdout-fraction 0.25 --output artifacts/qualification-split.json
```

Whole sessions are joined transitively whenever they share a session ID, target identity,
source hash, or exact decoded pixels. Connected groups cannot cross tuning/holdout. A single
connected group fails instead of leaking frames across partitions. Large groups can prevent
the requested fraction; the resulting assignments and group count are explicit. Common
distractor banner text is not a target identity. Exact hashes cannot detect near-duplicate
re-encodes, and annotations cannot detect missing identity labels: reviewer discipline matters.

The split records absolute manifest paths and content hashes. Evaluation rechecks hashes,
pixels and cross-partition leakage, including manually edited assignments. Moved datasets
need a new split manifest. Once holdout results influence changes, call that data a regression
corpus and obtain a fresh untouched qualification set. A synthetic held-out session is not
a representative real-video holdout.

## Run local comparisons

```powershell
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/qualification-split.json --partition tuning --no-spinning --profile-inference --report artifacts/tuning-baseline.jsonl
./.venv/Scripts/python.exe scripts/evaluate_dataset.py artifacts/qualification-split.json --partition holdout --model-profile tiny --scale 1 --det-limit 640 --threads 4 --cpu-arena --no-spinning --fallback-baseline --profile-inference --report artifacts/holdout-cascade.jsonl
./.venv/Scripts/python.exe scripts/benchmark_labelled_crops.py artifacts/qualification-split.json --partition tuning --report artifacts/tuning-crop-diagnostics.json
```

Optional models must already be provisioned with the existing explicit setup command.
The evaluator has **no native clipboard option**. Models are warmed once and reused.
Baseline, candidate extraction, exact agreement, abstention, one-shot and dedup behavior
come from the existing pipeline. Consecutive identical ROI pixels cannot confirm twice.
Replay deliberately uses the documented 10000 ms offline age/agreement budget, never a
live setting. Source-file decoding, setup and baseline are excluded from hot-path stage
percentiles; the process CPU/wall totals include the evaluation loop. Percentiles retain
at most the last 10000 samples per stage/dataset. Raw observations retain every outcome.

Reports separate frame-level raw exact text occurrences, eligible candidates, event exact
copies, incorrect writes, abstentions, partial violations and unsuited snapshot events.
Geometry overlap with annotated boxes is **diagnostic evidence**, not confidence or a
policy threshold. Memory writes on a partial/negative frame count as incorrect even if the
string matches a later visible label. Unsupported formats and safety abstentions are not
removed from recall. A completed diagnostic command exits zero even when accuracy is poor;
read the counts. It is not a release-pass command.

The crop benchmark deliberately uses labelled code boxes to isolate recognition, reporting
tight/padded/grayscale/Otsu crops and lightweight connected-component glyph templates.
These are **oracle localization** results; the recognizer sees pixels, never truth or
expected code length. Glyph templates cover generic A–Z/0–9 Hershey Simplex symbols and
return pixel MSE, not invented OCR confidence. No diagnostic method can write a clipboard.
Its apparent accuracy/speed excludes detection, context, confirmation and policy and must
not be substituted for application results.

## Media still required

The user confirms a real screenshot exists elsewhere, but it has not been added locally
and its code has not been independently verified. It cannot currently support a result.
Provide the original-resolution screenshot and independent transcription for an initial
recognition check; a single phone screenshot cannot qualify Windows capture or event latency.

For the next engineering experiment, supply several permitted recording sessions from
different overlays/backgrounds, with at least 30–50 labelled appearances to diagnose errors.
Keep a separate unseen session/code group. Include original video metadata, before/during/
after frames, first/last visible frame indices, chart ROI and code boxes, two independent
transcriptions, ambiguous O/0/I/1/B/8 cases, italic/small/colored text, compression/blur,
different positions/formats, partial occlusion, and long negative banner/chat intervals.
Do not infer truth from this OCR model. These initial samples are for diagnosis, not release.

Phase 3 aims for >=90% exact event recall and zero observed incorrect writes on a genuinely
unseen representative dataset; the project's stricter G3 release gate remains unchanged:
>=1000 appearances, >=10000 negative frames, >=99% recall under declared conditions, and
the specified live p95/p99 latency gates. No such representative dataset is available yet.
