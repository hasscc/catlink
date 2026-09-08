"""CATLINK visual C07 litter box support."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import LitterDeviceInfo
from ..models.api.logs import LogEntry
from ..models.api.parse import parse_response
from .base import Device
from .mixins.logs import LogsMixin

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class VisualC07Device(LogsMixin, Device):
    """Visual C07 device with the currently verified read-only surface."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        super().__init__(dat, coordinator, additional_config)
        self.sand_info: dict[str, Any] = {}
        self._media_events: list[dict[str, Any]] = []

    async def async_init(self) -> None:
        """Initialize detail and timeline coordinators."""
        await super().async_init()
        await self._async_init_logs()

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
    def auto_refill_installed(self) -> bool:
        """Return whether the auto-refill module is installed."""
        return self.sand_info.get("install") is True

    @property
    def auto_refill_mode(self) -> str:
        """Return the auto-refill mode without exposing an unverified control."""
        mode = self.sand_info.get("workModel")
        if mode == 0:
            return "automatic"
        if mode == 1:
            return "manual"
        return "unknown"

    @property
    def auto_refill_level(self) -> int | str:
        """Return the configured refill sensitivity/level."""
        value = self.sand_info.get("level")
        return value if isinstance(value, int) else "unknown"

    @property
    def hass_sensor(self) -> dict:
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
            "auto_refill_mode": {
                "icon": "mdi:auto-fix",
            },
            "auto_refill_level": {
                "icon": "mdi:signal",
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        return {
            "auto_refill_installed": {
                "icon": "mdi:tray-full",
            }
        }

    @property
    def hass_select(self) -> dict:
        # Visual C07 does not use the legacy device/changeMode and
        # device/actionCmd surface. Do not expose non-functional controls.
        return {}

    async def update_sand_info(self) -> dict[str, Any]:
        """Read the C07 auto-refill module state."""
        response = await self.account.request(
            "token/cameraLitterbox/sandSysInfo", {"deviceId": self.id}
        )
        data = response.get("data", {})
        info = data.get("info", {}) if isinstance(data, dict) else {}
        if not isinstance(info, dict):
            return {}
        return {
            key: info.get(key)
            for key in ("workModel", "level", "install")
            if key in info
        }

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
        try:
            self.sand_info = await self.update_sand_info()
        except (TypeError, ValueError) as exc:
            self.sand_info = {}
            _LOGGER.error("Got Visual C07 sand info for %s failed: %s", self.name, exc)
        self.detail = detail
        self._action_error = None
        self._handle_listeners()
        return detail

    async def update_logs(self) -> list[dict[str, Any]]:
        """Read timeline logs while keeping media locators out of HA state."""
        api = "token/litterbox/stats/log/timeline/v2"
        today = datetime.date.today().isoformat()
        params = {
            "deviceId": self.id,
            "date": today,
            "pageNumber": 1,
            "pageSize": 10,
            "type": 0,
            "subType": 0,
        }
        response = None
        try:
            response = await self.account.request(api, params)
            data = response.get("data", {})
            parsed = parse_response(data, "records", LogEntry, [])
            if isinstance(parsed, list) and parsed and hasattr(parsed[0], "model_dump"):
                raw_logs = [item.model_dump() for item in parsed]
            elif isinstance(parsed, list):
                raw_logs = parsed
            else:
                raw_logs = data.get("records") or []
        except (TypeError, ValueError) as exc:
            raw_logs = []
            _LOGGER.error("Got Visual C07 logs for %s failed: %s", self.name, exc)
        if not raw_logs:
            _LOGGER.warning("Got Visual C07 logs for %s failed", self.name)
        self._media_events = [log for log in raw_logs if isinstance(log, dict)]
        safe_keys = ("time", "event", "firstSection", "secondSection", "errkey")
        self.logs = [
            {
                **{key: log.get(key) for key in safe_keys if key in log},
                "has_video": bool(
                    log.get("moveDetectId")
                    or log.get("video1Url")
                    or log.get("video2Url")
                ),
            }
            for log in self._media_events
        ]
        self._handle_listeners()
        return self.logs
