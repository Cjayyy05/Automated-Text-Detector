"""Test-only clipboard measurement. Construction alone never changes the clipboard."""

from time import perf_counter_ns, sleep

from stream_code_capture.clipboard import WindowsClipboard


class MeasuredWindowsClipboard:
    def __init__(self):
        self.target = WindowsClipboard()
        self.last_write = None

    def write(self, text):
        start = perf_counter_ns()
        self.target.write(text)
        self.last_write = {"start_ns": start, "end_ns": perf_counter_ns()}


def readback():
    import pywintypes
    import win32clipboard
    import win32con

    start = perf_counter_ns()
    error, value = None, None
    for attempt in range(20):
        try:
            win32clipboard.OpenClipboard()
        except pywintypes.error as exc:
            error = str(exc)
            if attempt < 19:
                sleep(0.05)  # Read retry only; application writes never retry.
        else:
            try:
                value = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                error = None
            except pywintypes.error as exc:
                error = str(exc)
            finally:
                win32clipboard.CloseClipboard()
            break
    return {"value": value, "error": error, "start_ns": start, "end_ns": perf_counter_ns()}
