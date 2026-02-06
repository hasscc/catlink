"""Scooper device module for CatLink integration."""

from collections import deque
import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import LitterDeviceInfo
from ..models.api.parse import parse_response
from .litter_device import LitterDevice

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class ScooperDevice(LitterDevice):
    """Scooper device class for CatLink integration."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(dat, coordinator, additional_config)
        self._error_logs = deque(maxlen=20)

    @property
    def modes(self) -> dict:
        """Return the modes of the device."""
        return {
            "00": "auto",
            "01": "manual",
            "02": "time",
            "03": "empty",
        }

    @property
    def actions(self) -> dict:
        """Return the actions of the device."""
        return {
            "00": "pause",
            "01": "start",
        }

    @property
    def temperature(self) -> str:
        """Return the temperature."""
        return self.detail.get("temperature", "-")

    @property
    def humidity(self) -> str:
        """Return the humidity."""
        return self.detail.get("humidity", "-")

    @property
    def error(self) -> str:
        """Return the device error."""
        if self._action_error:
            return self._action_error
        try:
            error = self.detail.get("currentMessage") or self.data.get(
                "currentErrorMessage", ""
            )
            if error and error.lower() != "device online":
                self._error_logs.append(
                    {
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "error": error,
                    }
                )
            return error
        except Exception as exc:
            _LOGGER.error("Get device error failed: %s", exc)
            return "unknown"

    @property
    def hass_sensor(self) -> dict:
        """Return the hass sensor of the device."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
            "litter_weight": {
                "icon": "mdi:weight",
            },
            "litter_remaining_days": {
                "icon": "mdi:calendar",
            },
            "total_clean_time": {
                "icon": "mdi:timer",
            },
            "manual_clean_time": {
                "icon": "mdi:timer",
            },
            "deodorant_countdown": {
                "icon": "mdi:timer",
            },
            "occupied": {
                "icon": "mdi:cat",
            },
            "online": {
                "icon": "mdi:cloud",
            },
            "temperature": {
                "icon": "mdi:temperature-celsius",
                "state": self.temperature,
                "class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "humidity": {
                "icon": "mdi:water-percent",
                "state": self.humidity,
                "class": SensorDeviceClass.HUMIDITY,
                "unit": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "error": {
                "icon": "mdi:alert-circle",
                "state_attrs": self.error_attrs,
            },
        }

    def state_attrs(self) -> dict:
        """Return the state attributes."""
        return self._base_state_attrs()

    def error_attrs(self) -> dict:
        """Return the error attributes."""
        return {
            "error_logs": list(self._error_logs),
        }

    async def update_device_detail(self) -> dict:
        """Update device detail. Uses LitterDeviceInfo for Scooper response parsing."""
        api = "token/device/info"
        pms = {"deviceId": self.id}
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            data = rsp.get("data", {})
            raw = data.get("deviceInfo")
            parsed = parse_response(data, "deviceInfo", LitterDeviceInfo)
            rdt = (
                parsed.model_dump(by_alias=True)
                if hasattr(parsed, "model_dump")
                else (parsed or {})
            )
            if not rdt and raw:
                rdt = raw
                _LOGGER.debug(
                    "Using raw deviceInfo for %s because model parsing failed",
                    self.name,
                )
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device detail for %s failed: %s", self.name, exc)
        if not rdt:
            data_keys = list(rsp.get("data", {}).keys()) if rsp else []
            _LOGGER.warning(
                "Got device detail for %s failed (empty parse); response data keys: %s",
                self.name,
                data_keys,
            )
        self.detail = rdt
        self._action_error = None
        self._handle_listeners()
        return rdt

    async def update_logs(self) -> list:
        """Update device logs."""
        return await self._fetch_logs(
            "token/device/scooper/stats/log/top5", "scooperLogTop5"
        )
