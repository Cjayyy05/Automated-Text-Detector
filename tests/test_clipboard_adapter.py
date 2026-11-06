import sys
from types import SimpleNamespace

import pytest

from stream_code_capture.clipboard import WindowsClipboard


def test_unicode_clipboard_transaction_closes_on_success_and_failure(monkeypatch):
    calls = []

    def set_text(text, kind):
        calls.append((text, kind))

    api = SimpleNamespace(
        OpenClipboard=lambda: calls.append("open"),
        EmptyClipboard=lambda: calls.append("empty"),
        SetClipboardText=set_text,
        CloseClipboard=lambda: calls.append("close"),
    )
    monkeypatch.setitem(sys.modules, "win32clipboard", api)
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(CF_UNICODETEXT=13))
    adapter = object.__new__(WindowsClipboard)  # No OS calls, portable adapter contract test.
    adapter.write("AB23CD45EF")
    assert calls == ["open", "empty", ("AB23CD45EF", 13), "close"]
    calls.clear()

    def fail(text, kind):
        raise RuntimeError("set failed")

    api.SetClipboardText = fail
    with pytest.raises(RuntimeError, match="set failed"):
        adapter.write("AB23CD45EF")
    assert calls == ["open", "empty", "close"]


def test_busy_native_clipboard_does_not_empty_or_retry(monkeypatch):
    calls = []

    def busy():
        calls.append("open")
        raise RuntimeError("busy")

    monkeypatch.setitem(sys.modules, "win32clipboard", SimpleNamespace(OpenClipboard=busy))
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(CF_UNICODETEXT=13))
    with pytest.raises(RuntimeError, match="busy"):
        object.__new__(WindowsClipboard).write("AB23CD45EF")
    assert calls == ["open"]
