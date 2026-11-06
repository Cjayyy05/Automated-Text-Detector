"""Fail-closed enforcement of the approved personal-use native GUI display scope."""

from typing import Any

from .display_inventory import inventory


def validate_scope(data: dict[str, Any], device: int, output: int, name: str) -> None:
    selected = next((m for m in data["monitors"] if m["device_name"] == name), None)
    mapping = {"device": device, "output": output, "device_name": name}
    if (
        data["errors"]
        or data["wts_client_protocol"] != 0
        or data["sm_remote_session"]
        or data["sm_remote_control"]
        or (device, output) != (0, 0)
        or mapping not in data["dxcam_outputs"]
        or selected is None
        or not selected["primary"]
        or selected["resolution"] != [1920, 1080]
        or selected["scale_percent"] != 100
        or selected["scale_status"] != 0
        or selected["orientation"] != 0
        or not selected["hdr"]
        or selected["hdr"]["query_status"] != 0
        or selected["hdr"]["active"] is not False
        or selected["hdr"]["user_enabled"] is not False
        or selected["hdr"]["active_color_mode"] != 0
    ):
        raise RuntimeError(
            "Native copying requires the center primary output 0 at 1920 × 1080, "
            "100%, SDR, local Windows. Stop and restore the approved configuration."
        )


class NativeScope:
    def __init__(self, device: int, output: int, name: str) -> None:
        self.device, self.output, self.name = device, output, name
        self.initial = self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        data = inventory()
        validate_scope(data, self.device, self.output, self.name)
        # The diagnostic's desktop rect is omitted after process DPI awareness is
        # already set. DEVMODE position/resolution remain stable physical coordinates.
        data["monitors"] = [
            {key: value for key, value in monitor.items() if key != "physical_desktop_rect"}
            for monitor in data["monitors"]
        ]
        return {
            key: data[key]
            for key in ("monitors", "dxcam_outputs", "available_display_target_count")
        }

    def check(self) -> None:
        if self.snapshot() != self.initial:
            raise RuntimeError("Display topology/configuration changed. Start a fresh session.")
