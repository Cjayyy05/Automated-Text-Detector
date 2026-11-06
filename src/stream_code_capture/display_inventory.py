"""Read-only Windows display/session inventory; no capture, clipboard, or settings writes.

ABI reference: Microsoft's win32metadata WinSDK/um/wingdi.h. DPI awareness changes only
this diagnostic process's coordinate interpretation, never the Windows display settings.
"""

import ctypes as C
import platform
from datetime import UTC, datetime
from typing import Any

U = C.c_uint32


class Luid(C.Structure):
    _fields_ = [("low", U), ("high", C.c_int32)]


class Source(C.Structure):
    _fields_ = [("adapter", Luid), ("id", U), ("mode", U), ("flags", U)]


class Target(C.Structure):
    _fields_ = [("adapter", Luid)] + [
        (name, U)
        for name in (
            "id",
            "mode",
            "technology",
            "rotation",
            "scaling",
            "refresh_numerator",
            "refresh_denominator",
            "scanline",
            "available",
            "flags",
        )
    ]


class DisplayPath(C.Structure):
    _fields_ = [("source", Source), ("target", Target), ("flags", U)]


class Header(C.Structure):
    _fields_ = [("type", U), ("size", U), ("adapter", Luid), ("id", U)]


class SourceName(C.Structure):
    _fields_ = [("header", Header), ("name", C.c_wchar * 32)]


class ColorInfo2(C.Structure):
    _fields_ = [("header", Header)] + [
        (name, U) for name in ("flags", "encoding", "bits_per_channel", "active_mode")
    ]


def query_paths(user: Any, flags: int) -> list[Any]:
    for _ in range(3):
        n, m = U(), U()
        status = user.GetDisplayConfigBufferSizes(flags, C.byref(n), C.byref(m))
        if status:
            raise OSError(status, "GetDisplayConfigBufferSizes")
        paths = (DisplayPath * n.value)()
        # DISPLAYCONFIG_MODE_INFO: 16-byte header + 48-byte aligned union, not interpreted.
        modes = (C.c_uint64 * (8 * m.value))()
        status = user.QueryDisplayConfig(flags, C.byref(n), paths, C.byref(m), modes, None)
        if status == 122:  # Topology changed between buffer-size and query calls.
            continue
        if status:
            raise OSError(status, "QueryDisplayConfig")
        return list(paths[: n.value])
    raise RuntimeError("Display topology changed repeatedly; retry inventory")


def inventory() -> dict[str, Any]:
    import win32api  # type: ignore[import-untyped]
    import win32con
    import win32ts  # type: ignore[import-untyped]

    user = C.WinDLL("user32", use_last_error=True)
    user.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
    dpi_set = bool(user.SetProcessDpiAwarenessContext(C.c_void_p(-4)))
    user.GetDisplayConfigBufferSizes.argtypes = [U, C.POINTER(U), C.POINTER(U)]
    user.QueryDisplayConfig.argtypes = [
        U,
        C.POINTER(U),
        C.POINTER(DisplayPath),
        C.POINTER(U),
        C.c_void_p,
        C.c_void_p,
    ]
    user.DisplayConfigGetDeviceInfo.argtypes = [C.c_void_p]
    scale = C.WinDLL("shcore").GetScaleFactorForMonitor
    scale.argtypes, scale.restype = [C.c_void_p, C.POINTER(C.c_int)], C.c_long
    result: dict[str, Any] = {
        "recorded_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "process_dpi_awareness_set": dpi_set,
        "scope": "Read-only configuration inventory, not capture or manual usability qualification",
        "errors": [],
        "monitors": [],
    }
    for monitor, _, _ in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(monitor)
        mode = win32api.EnumDisplaySettings(info["Device"], win32con.ENUM_CURRENT_SETTINGS)
        factor = C.c_int()
        status = scale(int(monitor), C.byref(factor))
        result["monitors"].append(
            {
                "device_name": info["Device"],
                "primary": bool(info["Flags"] & 1),
                "physical_desktop_rect": info["Monitor"] if dpi_set else None,
                "resolution": [mode.PelsWidth, mode.PelsHeight],
                "position": [mode.Position_x, mode.Position_y],
                "refresh_hz": mode.DisplayFrequency,
                "orientation": mode.DisplayOrientation,
                "scale_percent": factor.value if status == 0 else None,
                "scale_status": status,
                "hdr": None,
            }
        )
    result["active_desktop_monitor_count"] = len(result["monitors"])
    try:
        result["wts_client_protocol"] = win32ts.WTSQuerySessionInformation(
            win32ts.WTS_CURRENT_SERVER_HANDLE,
            win32ts.WTS_CURRENT_SESSION,
            win32ts.WTSClientProtocolType,
        )
    except Exception as exc:
        result["wts_client_protocol"] = None
        result["errors"].append(f"WTS protocol: {exc}")
    result["sm_remote_session"] = bool(win32api.GetSystemMetrics(0x1000))
    result["sm_remote_control"] = bool(win32api.GetSystemMetrics(0x2001))
    try:
        paths = query_paths(user, 2)  # QDC_ONLY_ACTIVE_PATHS
        for path in paths:
            name = SourceName()
            name.header = Header(1, C.sizeof(name), path.source.adapter, path.source.id)
            status = user.DisplayConfigGetDeviceInfo(C.byref(name))
            if status:
                result["errors"].append(f"Display source name: {status}")
                continue
            color = ColorInfo2()
            color.header = Header(15, C.sizeof(color), path.target.adapter, path.target.id)
            status = user.DisplayConfigGetDeviceInfo(C.byref(color))
            for monitor in result["monitors"]:
                if monitor["device_name"] == name.name:
                    monitor["hdr"] = {
                        "query_status": status,
                        "supported": bool(color.flags & 16) if status == 0 else None,
                        "user_enabled": bool(color.flags & 32) if status == 0 else None,
                        "active": color.active_mode == 2 if status == 0 else None,
                        "active_color_mode": color.active_mode if status == 0 else None,
                        "bits_per_channel": color.bits_per_channel if status == 0 else None,
                    }
        all_paths = query_paths(user, 1)  # QDC_ALL_PATHS; available targets deduplicated.
        result["available_display_target_count"] = len(
            {
                (p.target.adapter.low, p.target.adapter.high, p.target.id)
                for p in all_paths
                if p.target.available
            }
        )
    except Exception as exc:
        result["errors"].append(f"Display configuration: {exc}")
    try:
        import dxcam

        # Read-only metadata from the installed, pinned DXcam 0.3.0 factory; no camera created.
        result["dxcam_outputs"] = [
            {"device": d, "output": o, "device_name": item.devicename}
            for d, outputs in enumerate(dxcam.__factory.outputs)
            for o, item in enumerate(outputs)
        ]
    except Exception as exc:
        result["errors"].append(f"DXcam output mapping: {exc}")
    return result
