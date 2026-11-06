"""Capacity-one handoff for the next capture phase; no FIFO backlog."""

from threading import Condition

from .domain import Frame


class LatestFrame:
    """Ownership transfers on publish; producer must never mutate a published image."""

    def __init__(self) -> None:
        self._lock = Condition()
        self._frame: Frame | None = None
        self._last_sequence = -1
        self.dropped = 0

    def publish(self, frame: Frame) -> None:
        with self._lock:
            if frame.sequence <= self._last_sequence:
                raise ValueError("Capture sequence must strictly increase")
            if self._frame is not None:
                self.dropped += 1
            self._frame = frame
            self._last_sequence = frame.sequence
            self._lock.notify()

    def take(self) -> Frame | None:
        with self._lock:
            frame, self._frame = self._frame, None
            return frame

    def wait(self, timeout: float = 0.02) -> Frame | None:
        """Wake on publication, with a bounded timeout for controls/health checks."""
        with self._lock:
            self._lock.wait_for(lambda: self._frame is not None, timeout=timeout)
            frame, self._frame = self._frame, None
            return frame
