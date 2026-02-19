"""PurePro device module for CatLink integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..helpers import format_api_error
from ..models.additional_cfg import AdditionalDeviceConfig
from .base import Device
from .mixins.logs import LogsMixin

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator

API_PUREPRO_DETAIL = "token/device/purepro/detail"
API_PUREPRO_RUN_MODE = "token/device/purepro/runMode"
API_PUREPRO_STATS_CATS = "token/device/purepro/stats/log/top5"


class PureProDevice(LogsMixin, Device):
    """PurePro device class for CatLink integration."""

    def __init__(
        self,
        dat: dict,
        coordinator: DevicesCoordinator,
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(dat, coordinator, additional_config)

    async def async_init(self) -> None:
        """Initialize the device."""
        await super().async_init()
        await self._async_init_logs()

    @property
    def modes(self) -> dict:
        """Return the modes of the device."""
        return {
            "CONTINUOUS_SPRING": "Flowing mode",
            "INTERMITTENT_SPRING": "Eco-mode",
            "INDUCTION_SPRING": "Smart mode",
        }

    @property
    def online(self) -> bool:
        """Return the online status."""
        return (
            self.detail.get("online")
            or self.data.get("online")
            or self.detail.get("onlineStatus") == "ONLINE"
            or self.data.get("onlineStatus") == "ONLINE"
            or False
        )

    @property
    def water_level(self) -> int | None:
        """Return the water level of the fountain."""
        return self.detail.get("waterLevelNum")

    @property
    def filter_life(self) -> int | None:
        """Return the filter life percentage."""
        return self.detail.get("filterElementTimeCountdown")

    @property
    def temperature(self) -> float | None:
        """Return the water temperature."""
        return self.detail.get("waterTemperature")

    @property
    def state(self) -> str:
        """Return the state of the device."""
        mode = self.detail.get("runMode")
        if mode in self.modes:
            return self.modes[mode]
        return self.detail.get("workStatus", "unknown")

    def state_attrs(self) -> dict:
        """Return the state attributes of the device."""
        return {
            **self.detail,
            "work_status": self.detail.get("workStatus"),
            "run_mode": self.detail.get("runMode"),
            "water_level": self.water_level,
            "filter_life": self.filter_life,
            "temperature": self.temperature,
            "uv_active": self.detail.get("ultravioletRaysSwitch") == "OPEN",
            "heating": self.detail.get("waterHeatSwitch") == "OPEN",
            "light_active": self.detail.get("pureLightStatus") == "OPEN",
            "hair_cleaning": self.detail.get("fluffyHairStatus") != "STOP",
        }

    @property
    def last_log(self) -> str | None:
        """Return the last log entry formatted for the fountain."""
        log = self._last_log
        if not log:
            return "No activity recorded"
        # The event field usually contains "Cat drank water, X seconds"
        res = f"{log.get('time')} {log.get('event')}".strip()
        _LOGGER.debug("PurePro %s last_log: %s", self.name, res)
        return res

    @property
    def hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
            "online": {
                "icon": "mdi:cloud",
                "state": "Online" if self.online else "Offline",
            },
            "water_level": {
                "icon": "mdi:water-percent",
                "unit": "%",
            },
            "filter_life": {
                "icon": "mdi:filter-outline",
                "unit": "%",
            },
            "temperature": {
                "icon": "mdi:thermometer",
                "unit": "°C",
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the device binary sensors."""
        return {
            "uv_active": {
                "icon": "mdi:lightbulb-cfl-spiral",
                "name": "UV_active",
                "state": self.detail.get("ultravioletRaysSwitch") == "OPEN",
            },
            "heating": {
                "icon": "mdi:water-boiler",
                "state": self.detail.get("waterHeatSwitch") == "OPEN",
            },
            "light_active": {
                "icon": "mdi:palette",
                "state": self.detail.get("pureLightStatus") == "OPEN",
            },
            "hair_cleaning": {
                "icon": "mdi:spray",
                "state": self.detail.get("fluffyHairStatus") != "STOP",
            },
        }

    @property
    def hass_select(self) -> dict:
        """Return the device selects."""
        return {
            "mode": {
                "icon": "mdi:menu",
                "options": list(self.modes.values()),
                "state_attrs": self.mode_attrs,
                "async_select": self.select_mode,
            },
        }

    async def update_device_detail(self) -> dict:
        """Update device detail."""
        pms = {"deviceId": self.id}
        rsp = None
        try:
            rsp = await self.account.request(API_PUREPRO_DETAIL, pms)
            data = rsp.get("data") or {}
            
            # PurePro API might return the detail directly in 'data' 
            # or wrapped in 'deviceInfo' like generic endpoints.
            rdt = data.get("deviceInfo") or data
            
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device detail for %s failed: %s", self.name, exc)
        
        if not rdt:
            _LOGGER.warning("Got device detail for %s failed: %s", self.name, rsp)
        else:
            _LOGGER.debug("Got device detail for %s: %s", self.name, rdt)
            
        self.detail = rdt
        self._action_error = None
        self._handle_listeners()
        return rdt

    async def select_mode(self, mode, **kwargs) -> bool:
        """Select the device mode."""
        mod = None
        for k, v in self.modes.items():
            if v == mode:
                mod = k
                break
        if mod is None:
            _LOGGER.warning("Select mode failed for %s in %s", mode, self.modes)
            return False
        
        pms = {
            "runMode": mod,
            "deviceId": self.id,
        }
        rdt = await self.account.request(API_PUREPRO_RUN_MODE, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            err_msg = format_api_error(rdt)
            _LOGGER.error("Select mode failed: %s", err_msg)
            self._set_action_error(err_msg)
            return False
            
        await self.update_device_detail()
        _LOGGER.info("Select mode: %s", [rdt, pms])
        return True

    async def update_logs(self) -> list:
        """Update device logs."""
        return await self._fetch_logs(API_PUREPRO_STATS_CATS, "pureLogTop5")
