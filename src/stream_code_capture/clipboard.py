"""Clipboard adapters. The default CLI uses memory, never the OS clipboard."""

import sys
from dataclasses import dataclass, field


@dataclass
class MemoryClipboard:
    writes: list[str] = field(default_factory=list)

    def write(self, text: str) -> None:
        self.writes.append(text)


class WindowsClipboard:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows clipboard requires Windows")

    def write(self, text: str) -> None:
        import win32clipboard
        import win32con

        # A busy clipboard fails immediately; no unbounded hot-path retry loop.
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
