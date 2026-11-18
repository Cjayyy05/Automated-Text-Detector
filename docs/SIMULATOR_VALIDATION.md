# Livestream Code Simulator validation

The v0.2.0 policy comparison used real offline OCR on the simulator's reveal widget.
See [detection policy validation](DETECTION_POLICY_VALIDATION.md) for results and
[Windows verification](WINDOWS_VALIDATION.md#verify-v020-on-windows) for the current
static-reveal procedure.

2026-11-18 MYT on Windows 11 build 26200, Python 3.12.14, and PySide6 6.12.0.

| Command | Result |
|---|---|
| `./scripts/check.ps1` | 222 passed, 18 opt-in OCR tests skipped. Dependency, Ruff, and source mypy checks passed. |
| `./scripts/check.ps1 -Ocr` | 237 passed, including real offline OCR. All three strict challenge xfails reproduced. |
| `./.venv/Scripts/python.exe -m pytest -q tests/test_livestream_code_simulator.py --basetemp .tmp/simulator-final-tests` | Three tests passed on Qt's offscreen platform, including the final selection-clearing regression check. |
| `./.venv/Scripts/python.exe -m mypy scripts/livestream_code_simulator.py` | Passed. |
| `./.venv/Scripts/python.exe scripts/livestream_code_simulator.py -platform offscreen` | Entry point stayed in the Qt event loop for the two-second smoke-test interval. |
| `./.venv/Scripts/python.exe -m stream_code_capture image .tmp/simulator-visual-a0ced9e9001b471483eb831af3dfb8bc/display.png --roi 130 24 680 240` | Real offline OCR read all three rendered lines exactly. The expected code was the sole candidate and the detector stayed disarmed. |

Tests cover one multiline editor, literal text and whitespace, formatting, countdown,
Reset, Esc, a real Qt timer, timestamp records, and blocked copy and cut shortcuts.
The Windows offscreen backend supplied an empty font list on this host. The automated
test injects a selected font, and a separate Windows-backend render verified real
Consolas selection. The three rendered states were visually inspected. The final
reveal clears any editor selection and scrolls to the first line.

Qt APIs were checked against the installed version and the primary documentation for
the [timer](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html),
[text document](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTextDocument.html), and
[key events](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeyEvent.html).

The image probe used a Qt widget render saved to PNG. It exercises file-based OCR
only. The reveal timestamp records the Qt transition and needs separate correlation
with an actual captured frame for latency work. Live DXcam confirmation, native
clipboard delivery, and screen presentation timing remain unverified for this tool.
