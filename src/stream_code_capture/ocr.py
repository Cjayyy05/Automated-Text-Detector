"""Pinned RapidOCR adapter: local models, one warmed engine, ROI text localization."""

import math
from collections.abc import Callable
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from time import perf_counter, perf_counter_ns, process_time_ns
from typing import Any

import cv2
import numpy as np

from .domain import Image, Recognition, RecognitionBatchTiming, RecognitionProfile, Rect, TextLine
from .policy import MIN_CODE_PITCH, PolicyConfig, candidates, code_text, extract_code

PROVIDERS = {
    "cpu": "CPUExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "directml": "DmlExecutionProvider",
}
LARGE_ROI_PIXELS = 750_000
RECOGNITION_REUSE_BYTES = 8 * 1024 * 1024

BatchKey = tuple[tuple[tuple[int, ...], bytes], ...]
BatchReadings = tuple[tuple[str, float], ...]


class RecognitionBatchReuse:
    """Reuse only exact, complete RapidOCR batches without code-shaped readings."""

    def __init__(self, recognize: Callable[[list[Image]], Any], batch_size: int) -> None:
        from rapidocr.ch_ppocr_rec import TextRecOutput

        self.recognize = recognize
        self.output: Any = TextRecOutput
        self.batch_size = batch_size
        self.enabled = False
        self.previous: dict[BatchKey, BatchReadings] = {}
        self.profile: RecognitionProfile | None = None

    def __call__(self, images: list[Image]) -> Any:
        if not self.enabled:
            self.previous.clear()
            return self.recognize(images)
        crop_bytes = sum(image.nbytes for image in images)
        profile = self.profile
        if profile is not None:
            profile.crop_bytes = crop_bytes
            profile.cache_state = "active"
        if crop_bytes > RECOGNITION_REUSE_BYTES:
            if profile is not None:
                profile.cache_state = "over byte budget"
            self.previous.clear()
            return self.recognize(images)

        started = perf_counter()
        # Match the pinned recognizer's aspect sort and padding groups. Keeping the
        # complete group in the key preserves the model input width of every crop.
        order = np.argsort([image.shape[1] / float(image.shape[0]) for image in images]).tolist()
        groups = [order[i : i + self.batch_size] for i in range(0, len(order), self.batch_size)]
        keys = [tuple((images[i].shape, images[i].tobytes()) for i in group) for group in groups]
        cached = [self.previous.get(key) for key in keys]
        if profile is not None:
            previous_crops = {crop for group in self.previous for crop in group}
            for key, hit in zip(keys, cached, strict=True):
                if hit is not None:
                    profile.cache_hits += 1
                    continue
                matched = sum(crop in previous_crops for crop in key)
                profile.cache_misses += 1
                profile.matched_crops_in_misses += matched
                profile.grouping_misses += int(matched == len(key))
        current: dict[BatchKey, BatchReadings] = {}
        if all(readings is None for readings in cached):
            result = self.recognize(images)
            for group, key in zip(groups, keys, strict=True):
                rows_read = tuple((result.txts[i], result.scores[i]) for i in group)
                if self.can_reuse(rows_read):
                    current[key] = rows_read
        else:
            rows = [("", 0.0)] * len(images)
            for group, key, readings in zip(groups, keys, cached, strict=True):
                if readings is None:
                    batch = self.recognize([images[i] for i in group])
                    readings = tuple(zip(batch.txts, batch.scores, strict=True))
                if self.can_reuse(readings):
                    current[key] = readings
                for i, row in zip(group, readings, strict=True):
                    rows[i] = row
            texts, scores = zip(*rows, strict=True)
            result = self.output(
                imgs=images, txts=texts, scores=list(scores), word_results=(None,) * len(images)
            )
        self.previous = current
        if profile is not None:
            profile.code_batches_excluded = len(groups) - sum(key in current for key in keys)
        result.elapse = perf_counter() - started
        return result

    @staticmethod
    def can_reuse(readings: BatchReadings) -> bool:
        # Even a rejected or context-free token must get fresh recognition. A code
        # can qualify on a later frame after its surrounding text changes.
        return not any(extract_code(text, "game") for text, _ in readings)


class RapidRecognizer:
    def __init__(
        self,
        *,
        scale: float = 2,
        provider: str = "cpu",
        threads: int = 2,
        min_code_pitch: float = MIN_CODE_PITCH,
        model_profile: str = "baseline",
        model_dir: Path | None = None,
        det_limit: int = 960,
        preprocessing: str = "none",
        cpu_arena: bool = False,
        profile_inference: bool = False,
        fallback_baseline: bool = False,
        allow_spinning: bool = True,
        reuse_static_batches: bool = True,
    ) -> None:
        import onnxruntime as ort
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

        if not math.isfinite(scale) or not 1 <= scale <= 4:
            raise ValueError("scale must be between 1 and 4")
        if threads < 1:
            raise ValueError("threads must be positive")
        if not math.isfinite(min_code_pitch) or min_code_pitch < 0:
            raise ValueError("min_code_pitch must be finite and nonnegative")
        self.min_code_pitch = min_code_pitch
        if model_profile not in {"baseline", "tiny", "v4"}:
            raise ValueError("Unknown local model profile")
        if fallback_baseline and model_profile != "tiny":
            raise ValueError("Baseline fallback is available only for the tiny fast path")
        if not 128 <= det_limit <= 2048:
            raise ValueError("det_limit must be between 128 and 2048")
        if preprocessing not in {"none", "gray", "clahe"}:
            raise ValueError("Unknown preprocessing strategy")
        self.preprocessing = preprocessing
        self.profile_inference = profile_inference
        self._inference_ms: dict[str, float] = {}
        self._profile: RecognitionProfile | None = None
        self._meter_installed = False
        self._resize_buffer: Image | None = None
        self.model_profile = model_profile
        self._reuse_static_batches = (
            reuse_static_batches and provider == "cpu" and model_profile == "baseline"
        )
        self._batch_reuse: RecognitionBatchReuse | None = None
        self._clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8))
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider")
        self.provider = PROVIDERS[provider]
        if self.provider not in ort.get_available_providers():
            raise RuntimeError(f"Requested provider {self.provider} is not installed")
        spec = find_spec("rapidocr")
        if spec is None or spec.origin is None:
            raise RuntimeError("RapidOCR installation is missing")
        bundled = Path(spec.origin).parent / "models"
        external = model_dir or Path(__file__).resolve().parents[2] / "models"
        if model_profile == "baseline":
            detector = bundled / "PP-OCRv6_det_small.onnx"
            recognizer = bundled / "PP-OCRv6_rec_small.onnx"
        elif model_profile == "tiny":
            detector = external / "PP-OCRv6_det_tiny.onnx"
            recognizer = external / "PP-OCRv6_rec_tiny.onnx"
        else:
            detector = external / "ch_PP-OCRv4_det_mobile.onnx"
            recognizer = external / "en_PP-OCRv4_rec_mobile.onnx"
        for model in (detector, recognizer):
            if not model.is_file():
                raise FileNotFoundError(
                    f"Offline model missing: {model}; provision models explicitly before use"
                )
        # Validate embedded dictionary before RapidOCR can attempt a dictionary download.
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = cpu_arena
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.log_severity_level = 4
        options.add_session_config_entry(
            "session.intra_op.allow_spinning", str(int(allow_spinning))
        )
        options.add_session_config_entry(
            "session.inter_op.allow_spinning", str(int(allow_spinning))
        )
        if provider == "directml":
            options.enable_mem_pattern = False
        metadata_session = ort.InferenceSession(
            str(recognizer), sess_options=options, providers=[self.provider]
        )
        if "character" not in metadata_session.get_modelmeta().custom_metadata_map:
            raise RuntimeError("Recognizer has no embedded dictionary; offline startup refused")
        self.scale = scale
        self.model_paths = [detector, recognizer]
        # Keep third-party dynamic objects confined to this adapter.
        params: dict[str, Any] = {
            "Global.use_cls": False,
            "Global.log_level": "error",
            "Global.text_score": 0.5,
            "Global.max_side_len": 4096,
            "Det.model_path": str(detector),
            "Rec.model_path": str(recognizer),
            "Det.limit_side_len": det_limit,
            "Det.limit_type": "max",
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "EngineConfig.onnxruntime.use_cuda": provider == "cuda",
            "EngineConfig.onnxruntime.use_dml": provider == "directml",
            "EngineConfig.onnxruntime.enable_cpu_mem_arena": cpu_arena,
        }
        if model_profile == "tiny":
            params.update({"Det.model_type": ModelType.TINY, "Rec.model_type": ModelType.TINY})
        elif model_profile == "v4":
            params.update(
                {
                    "Det.model_type": ModelType.MOBILE,
                    "Rec.model_type": ModelType.MOBILE,
                    "Det.ocr_version": OCRVersion.PPOCRV4,
                    "Rec.ocr_version": OCRVersion.PPOCRV4,
                    "Rec.lang_type": LangRec.EN,
                    "Det.mean": [0.485, 0.456, 0.406],
                    "Det.std": [0.229, 0.224, 0.225],
                }
            )
        self._engine: Any = RapidOCR(params=params)
        # RapidOCR 3.10's OrtInferSession supports supplied ORT sessions. Reuse the
        # already validated recognition session, including its embedded dictionary.
        detector_session = ort.InferenceSession(
            str(detector), sess_options=options, providers=[self.provider]
        )
        for section, session in (("Det", detector_session), ("Rec", metadata_session)):
            config = getattr(self._engine.cfg, section)
            config._set_flag("allow_objects", True)
            config.session = session
        self.warmed = False
        self._fallback = (
            RapidRecognizer(
                provider=provider,
                min_code_pitch=min_code_pitch,
                profile_inference=profile_inference,
                allow_spinning=allow_spinning,
                reuse_static_batches=False,
            )
            if fallback_baseline
            else None
        )

    def warmup(self) -> None:
        # Blank images can skip the lazy recognizer; text exercises both models.
        image = np.full((96, 400, 3), 255, dtype=np.uint8)
        cv2.putText(
            image, "WARMUP 234567", (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA
        )
        self.recognize(image)
        for name in ("text_det", "text_rec"):
            model = getattr(self._engine, name)
            if model is None:
                raise RuntimeError(f"Warmup did not initialize {name}")
            actual = model.session.session.get_providers()
            if not actual or actual[0] != self.provider:
                raise RuntimeError(f"Requested {self.provider}, actual session providers: {actual}")
            if self.profile_inference and not self._meter_installed:
                # Pinned ORT Python run API: measures inference separately from RapidOCR
                # preprocessing, crop sorting and CTC decoding. No GPU synchronization claim.
                session = model.session.session
                original = session.run

                def measured(
                    *args: Any, _name: str = name, _original: Any = original, **kwargs: Any
                ) -> Any:
                    started = perf_counter_ns()
                    result = _original(*args, **kwargs)
                    elapsed = (perf_counter_ns() - started) / 1e6
                    key = f"{_name}_inference"
                    self._inference_ms[key] = self._inference_ms.get(key, 0) + elapsed
                    if _name == "text_rec" and self._profile is not None:
                        feed = args[1] if len(args) > 1 else kwargs["input_feed"]
                        shape = next(iter(feed.values())).shape
                        self._profile.batches.append(
                            RecognitionBatchTiming(shape[0], shape[-1], elapsed)
                        )
                    return result

                session.run = measured
        install_crop_meter = self.profile_inference and not self._meter_installed
        self._meter_installed = True
        if self._reuse_static_batches and self._batch_reuse is None:
            self._batch_reuse = RecognitionBatchReuse(
                self._engine.recognize_txt, self._engine.text_rec.rec_batch_num
            )
            self._engine.recognize_txt = self._batch_reuse
        if install_crop_meter:
            recognize = self._engine.recognize_txt

            def measure_crops(images: list[Image]) -> Any:
                if self._profile is not None:
                    self._profile.detected_lines = len(images)
                return recognize(images)

            self._engine.recognize_txt = measure_crops
        if self._fallback is not None:
            self._fallback.warmup()
        self.warmed = True

    def recognize(self, image: Image) -> list[TextLine]:
        return self.recognize_timed(image).lines

    def recognize_timed(self, image: Image) -> Recognition:
        started = perf_counter_ns()
        result = self._recognize_once(image)
        if self._fallback is None:
            return result
        eligible = candidates(result.lines, PolicyConfig())
        if len(eligible) == 1:
            verification_start, cpu = perf_counter_ns(), process_time_ns()
            verified_lines = []
            for line in result.lines:
                if code_text(line) == eligible[0] and line.rejection is None:
                    text, confidence = self._fallback.verify_line(image, line.box)
                    agreed = (
                        text == line.text.strip()
                        and confidence is not None
                        and PolicyConfig().min_confidence <= confidence <= 1
                    )
                    line = replace(
                        line,
                        rejection=None if agreed else "verification_disagreement",
                        verification_text=text,
                        verification_confidence=confidence,
                    )
                elif code_text(line) and line.rejection is None:
                    line = replace(line, rejection="unverified_fast_candidate")
                verified_lines.append(line)
            elapsed = (perf_counter_ns() - verification_start) / 1e6
            timings = dict(result.timings_ms)
            timings["verification"] = elapsed
            timings["ocr"] += elapsed
            timings["ocr_process_cpu"] += (process_time_ns() - cpu) / 1e6
            for key, value in self._fallback._inference_ms.items():
                timings[key] = timings.get(key, 0) + value
            return Recognition(verified_lines, timings, result.profile)
        if eligible or not needs_fallback(result.lines):
            # Baseline/duplicate filtering happens downstream, so it could turn
            # several fast candidates into one. Only verified fast lines may copy.
            return replace(
                result,
                lines=[
                    replace(line, rejection="unverified_fast_candidate")
                    if code_text(line) and line.rejection is None
                    else line
                    for line in result.lines
                ],
            )
        fallback_started = perf_counter_ns()
        fallback = self._fallback.recognize_timed(image)
        completed = perf_counter_ns()
        # Quality rejection cannot be bypassed by trying another model. Fallback
        # runs only on localized but unusable text, not every empty moving chart.
        timings = dict(result.timings_ms)
        for key, value in fallback.timings_ms.items():
            timings[key] = timings.get(key, 0) + value
        timings.update(
            {
                "fast_path": (fallback_started - started) / 1e6,
                "fallback": (completed - fallback_started) / 1e6,
            }
        )
        return Recognition(fallback.lines, timings)

    def verify_line(self, image: Image, box: Rect) -> tuple[str, float | None]:
        """Independent rec-only reading of a wider source crop; never repairs a string."""
        from rapidocr.ch_ppocr_rec import TextRecInput

        if not self.warmed:
            raise RuntimeError("Verification requires a warmed model")
        height, width = image.shape[:2]
        padding = max(2, box.bottom - box.top)
        region = Rect(
            max(0, box.left - padding),
            max(0, box.top - 2),
            min(width, box.right + padding),
            min(height, box.bottom + 2),
        )
        self._inference_ms.clear()
        result = self._engine.text_rec(TextRecInput(img=region.crop(image, copy=False)))
        if not result.txts or not result.scores:
            return "", None
        return str(result.txts[0]).strip(), float(result.scores[0])

    def _recognize_once(self, image: Image) -> Recognition:
        start = perf_counter_ns()
        cpu_start = process_time_ns()
        self._inference_ms.clear()
        self._profile = RecognitionProfile() if self.profile_inference else None
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or image.size == 0:
            raise ValueError("Expected a nonempty uint8 BGR image")
        if self._batch_reuse is not None:
            self._batch_reuse.enabled = image.shape[0] * image.shape[1] >= LARGE_ROI_PIXELS
            self._batch_reuse.profile = self._profile
        if self.preprocessing != "none":
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if self.preprocessing == "clahe":
                gray = self._clahe.apply(gray)
            image = np.asarray(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), dtype=np.uint8)
        if self.scale == 1:
            enlarged = image
        else:
            shape = (round(image.shape[0] * self.scale), round(image.shape[1] * self.scale), 3)
            if self._resize_buffer is None or self._resize_buffer.shape != shape:
                self._resize_buffer = np.empty(shape, dtype=np.uint8)
            enlarged = np.asarray(
                cv2.resize(
                    image,
                    (shape[1], shape[0]),
                    dst=self._resize_buffer,
                    interpolation=cv2.INTER_CUBIC,
                ),
                dtype=np.uint8,
            )
        prepared = perf_counter_ns()
        profile = self._profile
        try:
            result = self._engine(enlarged)
        finally:
            # Rec-only verification must not append to a prior frame's profile.
            self._profile = None
            if self._batch_reuse is not None:
                self._batch_reuse.profile = None
        recognized = perf_counter_ns()
        timings = {
            "preprocess": (prepared - start) / 1e6,
            "ocr": (recognized - prepared) / 1e6,
            "ocr_process_cpu": (process_time_ns() - cpu_start) / 1e6,
            **self._inference_ms,
        }
        for name, seconds in zip(
            ("detection", "classification", "text_recognition"),
            result.elapse_list or (),
            strict=False,
        ):
            if seconds is not None:
                timings[name] = float(seconds) * 1000
        if result.boxes is None or result.txts is None or result.scores is None:
            return Recognition([], timings, profile)
        lines = []
        for box, text, confidence in zip(result.boxes, result.txts, result.scores, strict=True):
            points = np.asarray(box, dtype=np.float64) / self.scale
            left, top = np.floor(points.min(axis=0)).astype(int)
            right, bottom = np.ceil(points.max(axis=0)).astype(int)
            # Upsampling cannot restore lost source pixels. This is a conservative
            # quality floor, not evidence that larger text is necessarily correct.
            text = str(text)
            token = extract_code(text, "game")
            pitch = float(np.linalg.norm(points[1] - points[0])) / max(1, len(text.strip()))
            rejection = (
                "insufficient_source_resolution"
                if token is not None and pitch < self.min_code_pitch
                else None
            )
            lines.append(
                TextLine(
                    text,
                    float(confidence),
                    Rect(int(left), int(top), int(right), int(bottom)),
                    rejection,
                )
            )
        return Recognition(lines, timings, profile)


def needs_fallback(lines: list[TextLine]) -> bool:
    return (
        bool(lines)
        and not candidates(lines, PolicyConfig())
        and not any(code_text(line, "game") and line.rejection for line in lines)
    )
