"""CATLINK visual C07 litter box support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import LitterDeviceInfo
from ..models.api.parse import parse_response
from .base import Device

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class VisualC07Device(Device):
    """Visual C07 device with the currently verified read-only surface."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        super().__init__(dat, coordinator, additional_config)

    @property
    def litter_remaining_days(self) -> int | str:
        return self.detail.get("litterCountdown", "unknown")

    @property
    def deodorant_countdown(self) -> int | str:
        return self.detail.get("deodorantCountdown", "unknown")

    @property
    def total_clean_time(self) -> int | str:
        value = self.detail.get("totalCleanTimes")
        try:
            return int(value)
        except (TypeError, ValueError):
            return "unknown"

    @property
    def hass_sensor(self) -> dict:
        return {
            "litter_remaining_days": {
                "icon": "mdi:calendar",
                "unit": "days",
            },
            "deodorant_countdown": {
                "icon": "mdi:timer",
                "unit": "days",
            },
            "total_clean_time": {
                "icon": "mdi:history",
                "unit": "times",
            },
        }

    @property
    def hass_select(self) -> dict:
        # Visual C07 does not use the legacy device/changeMode and
        # device/actionCmd surface. Do not expose non-functional controls.
        return {}

    async def update_device_detail(self) -> dict:
        api = "token/visualScooper/briefInfo"
        params = {"deviceId": self.id}
        response = None
        try:
            response = await self.account.request(api, params)
            data = response.get("data", {})
            parsed = parse_response(data, "deviceInfo", LitterDeviceInfo, {})
            detail = (
                parsed.model_dump(by_alias=True)
                if hasattr(parsed, "model_dump")
                else (parsed or {})
            )
        except (TypeError, ValueError) as exc:
            detail = {}
            _LOGGER.error("Got Visual C07 detail for %s failed: %s", self.name, exc)
        if not detail:
            _LOGGER.warning("Got Visual C07 detail for %s failed", self.name)
        self.detail = detail
        self._action_error = None
        self._handle_listeners()
        return detail
