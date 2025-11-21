"""Visual Pro Ultra device module for CatLink integration."""

from collections import deque
import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import Device

if TYPE_CHECKING:
    from .devices_coordinator import DevicesCoordinator
from ..const import _LOGGER, DOMAIN
from ..models.additional_cfg import AdditionalDeviceConfig


class VisualProUltraDevice(Device):
    """Visual Pro Ultra device class for CatLink integration."""

    logs: list
    coordinator_logs = None

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig = None,
    ) -> None:
        super().__init__(dat, coordinator, additional_config)
        self._litter_weight_during_day = deque(
            maxlen=self.additional_config.max_samples_litter or 24
        )
        self._error_logs = deque(maxlen=20)
        self.empty_litter_box_weight = self.additional_config.empty_weight or 0.0

    async def async_init(self) -> None:
        """Initialize the device."""
        await super().async_init()
        self.logs = []
        # TODO: Set up coordinator for logs once we know the API endpoint
        # self.coordinator_logs = DataUpdateCoordinator(
        #     self.account.hass,
        #     _LOGGER,
        #     name=f"{DOMAIN}-{self.id}-logs",
        #     update_method=self.update_logs,
        #     update_interval=datetime.timedelta(minutes=1),
        # )
        # await self.coordinator_logs.async_refresh()

    @property
    def modes(self) -> dict:
        """Return the modes of the device."""
        # TODO: Update with actual modes from API
        return {
            "00": "auto",
            "01": "manual",
            "02": "time",
            "03": "empty",
        }

    @property
    def actions(self) -> dict:
        """Return the actions of the device."""
        # TODO: Update with actual actions from API
        return {
            "00": "pause",
            "01": "start",
        }

    @property
    def state(self) -> str:
        """Return the device state."""
        try:
            sta = self.detail.get("workStatus", "")
            dic = {
                "00": "idle",
                "01": "running",
                "02": "need_reset",
            }
            return dic.get(f"{sta}".strip(), sta)
        except Exception as exc:
            _LOGGER.error("Get device state failed: %s", exc)
            return "unknown"

    @property
    def online(self) -> bool:
        """Return the online status."""
        try:
            return self.detail.get("online", False)
        except Exception as exc:
            _LOGGER.error("Get online status failed: %s", exc)
            return False

    @property
    def error(self) -> str:
        """Return the device error."""
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
        # TODO: Add more sensors based on device capabilities
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "error": {
                "icon": "mdi:alert-circle",
                "state_attrs": self.error_attrs,
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the device binary sensors."""
        return {
            "online": {
                "icon": "mdi:cloud",
                "state": self.online,
            },
        }

    def state_attrs(self) -> dict:
        """Return the state attributes."""
        return {
            "mac": self.mac,
            "model": self.model,
            "device_type": self.type,
            "real_model": self.data.get("realModel"),
            "timezone_id": self.data.get("timezoneId"),
            # TODO: Add more attributes from detail once we know the structure
        }

    def error_attrs(self) -> dict:
        """Return the error attributes."""
        return {
            "error_logs": list(self._error_logs),
        }

    async def update_logs(self) -> list:
        """Update device logs."""
        # TODO: Implement once we know the API endpoint for Visual Pro Ultra logs
        _LOGGER.debug("Visual Pro Ultra logs update not yet implemented")
        return []

    async def update_device_detail(self) -> dict:
        """Update the device detail."""
        # TODO: Check if Visual Pro Ultra uses a different API endpoint
        # For now, use the default implementation
        return await super().update_device_detail()
