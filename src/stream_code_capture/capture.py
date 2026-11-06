"""DXcam producer with bounded handoff. All DXGI operations have one owner thread."""

import ctypes
import logging
import sys
from collections.abc import Callable
from threading import Event, Thread
from time import perf_counter, perf_counter_ns, sleep, thread_time_ns
from typing import Any, Protocol

import numpy as np

from .domain import Frame, Image, Rect
from .latest import LatestFrame
from .metrics import Metrics


class Source(Protocol):
    def grab(self) -> Image | None:
        """Return a new frame or None for an idle poll. Raise on capture failure."""
        ...

    def close(self) -> None: ...


class CaptureFault(logging.Handler):
    """Pinned DXcam logs recovery warnings before it can silently recover the source."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.message: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        self.message = record.getMessage()


class DxcamSource:
    def __init__(self, roi: Rect, device: int = 0, output: int = 0) -> None:
        if sys.platform != "win32":
            raise RuntimeError("DXcam capture requires Windows")
        # Physical-pixel coordinates. Failure can mean awareness was already configured.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        import dxcam

        self._camera: Any = dxcam.create(
            device_idx=device, output_idx=output, output_color="BGR", backend="dxgi"
        )
        try:
            roi.validate(self._camera.width, self._camera.height)
        except Exception:
            self._camera.release()
            raise
        self._roi = (roi.left, roi.top, roi.right, roi.bottom)
        self._shape = (roi.bottom - roi.top, roi.right - roi.left, 3)
        self._fault = CaptureFault()
        logging.getLogger("dxcam").addHandler(self._fault)

    def grab(self) -> Image | None:
        # Polling avoids DXcam's blocking get_latest_frame; there is no internal FIFO.
        # new_frame_only=True does not reuse cached frames. copy=True owns the pixels.
        pixels = self._camera.grab(region=self._roi, copy=True, new_frame_only=True)
        if self._fault.message:
            raise RuntimeError(f"Capture invalidated: {self._fault.message}")
        if pixels is None:
            return None
        if pixels.shape != self._shape or pixels.dtype != np.uint8:
            raise RuntimeError("Capture dimensions or pixel format changed")
        return np.asarray(pixels, dtype=np.uint8)

    def close(self) -> None:
        logging.getLogger("dxcam").removeHandler(self._fault)
        self._camera.release()


class CaptureWorker:
    def __init__(self, factory: Callable[[], Source], *, fps: int = 60) -> None:
        if not 1 <= fps <= 240:
            raise ValueError("Capture FPS must be in 1..240")
        self.factory, self.fps = factory, fps
        self.latest = LatestFrame()
        self.stop_requested = Event()
        self.started = Event()
        self.error: str | None = None
        self.last_capture_poll_ns = 0
        self.ready_ns = 0
        self.captured = 0
        self.duplicates = 0
        self.metrics = Metrics()
        self._thread = Thread(target=self._run, name="dxcam-producer", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        source: Source | None = None
        try:
            source = self.factory()
            self.ready_ns = perf_counter_ns()
            self.started.set()
            previous: Image | None = None
            while not self.stop_requested.is_set():
                start = perf_counter_ns()
                cpu = thread_time_ns()
                pixels = source.grab()
                delivered = perf_counter_ns()
                # A successful poll can have no new pixels. Keep liveness separate
                # from the timestamp and sequence of an actual OCR observation.
                self.last_capture_poll_ns = delivered
                if pixels is not None and previous is not None and np.array_equal(pixels, previous):
                    self.duplicates += 1
                    pixels = None
                if pixels is not None:
                    previous = pixels
                    self.captured += 1
                    self.latest.publish(
                        Frame(pixels, self.captured, start, (delivered - start) / 1e6, delivered)
                    )
                processed = perf_counter_ns()
                compute_cpu = (thread_time_ns() - cpu) / 1e6
                elapsed = (processed - start) / 1e9
                self._pace(max(0, 1 / self.fps - elapsed))
                self.metrics.add(
                    {
                        "capture_read": (delivered - start) / 1e6,
                        "capture_filter_publish": (processed - delivered) / 1e6,
                        "capture_thread_cpu": compute_cpu,
                        "capture_idle_wait": (perf_counter_ns() - processed) / 1e6,
                    }
                )
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            if source is not None:
                try:
                    source.close()
                except Exception as exc:
                    self.error = self.error or f"Capture cleanup failed: {exc}"
            self.started.set()

    def _pace(self, seconds: float) -> None:
        if sys.platform != "win32":
            self.stop_requested.wait(seconds)
            return
        # Python 3.12 sleep uses a high-resolution waitable timer on Windows.
        # Event.wait rounded a requested 10 ms to ~15.5 ms on the target PC.
        # Bound each sleep so even 1 FPS capture responds promptly to stop.
        deadline = perf_counter() + seconds
        while not self.stop_requested.is_set():
            remaining = deadline - perf_counter()
            if remaining <= 0:
                return
            sleep(min(remaining, 0.02))

    def stop(self) -> None:
        self.stop_requested.set()
        self._thread.join(timeout=3)
        if self._thread.is_alive():
            raise RuntimeError("Capture thread did not stop within 3 seconds")

    def wait_closed(self) -> None:
        """Wait for source release on a background owner after a stop request."""
        if self._thread.ident is not None:
            self._thread.join()
