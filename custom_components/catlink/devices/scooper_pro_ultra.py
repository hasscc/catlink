"""Scooper Pro Ultra device module for CatLink integration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import LitterDeviceInfo
from ..models.api.logs import LogEntry
from ..models.api.parse import parse_response
from .litter_device import LitterDevice

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class ScooperProUltraDevice(LitterDevice):
    """Scooper Pro Ultra device class (limited support)."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(dat, coordinator, additional_config)

    @property
    def name(self) -> str:
        """Return the device name with limited support suffix."""
        base_name = super().name or ""
        suffix = " (Limited Support)"
        if base_name.endswith(suffix):
            return base_name
        return f"{base_name}{suffix}".strip()

    @property
    def litter_remaining_days(self) -> int:
        """Return the litter remaining days."""
        try:
            return int(self.detail.get("litterCountdown", 0))
        except Exception as exc:
            _LOGGER.error("Got litter remaining days failed: %s", exc)
            return 0

    @property
    def total_clean_time(self) -> int:
        """Return total clean time from briefInfo when available."""
        try:
            return int(self.detail.get("totalCleanTimes", 0))
        except Exception as exc:
            _LOGGER.error("Get total clean time failed: %s", exc)
            return 0

    @property
    def hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
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

    async def update_device_detail(self) -> dict:
        """Update device detail from visualScooper briefInfo."""
        api = "token/visualScooper/briefInfo"
        pms = {"deviceId": self.id}
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            data = rsp.get("data", {})
            parsed = parse_response(data, "deviceInfo", LitterDeviceInfo, {})
            rdt = (
                parsed.model_dump(by_alias=True)
                if hasattr(parsed, "model_dump")
                else (parsed or {})
            )
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device detail for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device detail for %s failed: %s", self.name, rsp)
        self.detail = rdt
        self._action_error = None
        self._handle_listeners()
        return rdt

    async def update_logs(self) -> list:
        """Update device logs using timeline/v2 endpoint."""
        api = "token/litterbox/stats/log/timeline/v2"
        today = datetime.date.today().isoformat()
        pms = {
            "deviceId": self.id,
            "date": today,
            "pageNumber": 1,
            "pageSize": 10,
            "type": 0,
            "subType": 0,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            data = rsp.get("data", {})
            parsed = parse_response(data, "records", LogEntry, [])
            if isinstance(parsed, list) and parsed and hasattr(parsed[0], "model_dump"):
                rdt = [p.model_dump() for p in parsed]
            elif isinstance(parsed, list):
                rdt = parsed
            else:
                rdt = data.get("records") or []
        except (TypeError, ValueError) as exc:
            rdt = []
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt
