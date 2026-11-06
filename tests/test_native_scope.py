from copy import deepcopy

import pytest

from stream_code_capture import native_scope


@pytest.fixture
def display():
    return {
        "errors": [],
        "wts_client_protocol": 0,
        "sm_remote_session": False,
        "sm_remote_control": False,
        "available_display_target_count": 3,
        "dxcam_outputs": [{"device": 0, "output": 0, "device_name": "center"}],
        "monitors": [
            {
                "device_name": "center",
                "primary": True,
                "resolution": [1920, 1080],
                "position": [0, 0],
                "scale_percent": 100,
                "scale_status": 0,
                "orientation": 0,
                "hdr": {
                    "query_status": 0,
                    "active": False,
                    "user_enabled": False,
                    "active_color_mode": 0,
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("resolution", [1280, 720]),
        ("scale_percent", 125),
        ("primary", False),
        ("orientation", 1),
        ("hdr", None),
        ("hdr", {"query_status": 0, "active": True, "user_enabled": True, "active_color_mode": 2}),
    ],
)
def test_unsupported_selected_display_is_rejected(display, field, value):
    native_scope.validate_scope(display, 0, 0, "center")
    display["monitors"][0][field] = value
    with pytest.raises(RuntimeError):
        native_scope.validate_scope(display, 0, 0, "center")


@pytest.mark.parametrize(
    "field,value",
    [
        ("errors", ["query failed"]),
        ("wts_client_protocol", None),
        ("wts_client_protocol", 2),
        ("sm_remote_session", True),
        ("sm_remote_control", True),
        ("dxcam_outputs", []),
    ],
)
def test_remote_or_unknown_configuration_fails_closed(display, field, value):
    display[field] = value
    with pytest.raises(RuntimeError):
        native_scope.validate_scope(display, 0, 0, "center")


def test_secondary_and_topology_change_rejected(display, monkeypatch):
    with pytest.raises(RuntimeError):
        native_scope.validate_scope(display, 0, 1, "center")
    monkeypatch.setattr(native_scope, "inventory", lambda: deepcopy(display))
    scope = native_scope.NativeScope(0, 0, "center")
    scope.check()
    display["monitors"][0]["physical_desktop_rect"] = None
    scope.check()
    display["monitors"].append({"device_name": "new display"})
    with pytest.raises(RuntimeError, match="topology"):
        scope.check()
