"""Read-only support for Feeder Pro devices."""

from math import isfinite

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfMass

from .base import Device
from .mixins.logs import LogsMixin


class FeederProDevice(LogsMixin, Device):
    """Feeder Pro status and recent feeding records."""

    async def async_init(self) -> None:
        """Initialize device details and logs."""
        await super().async_init()
        await self._async_init_logs()

    async def update_device_detail(self) -> dict:
        """Read details from the Feeder Pro endpoint."""
        response = await self.account.request(
            "token/device/feederpro/detail", {"deviceId": self.id}
        )
        data = response.get("data") if response.get("returnCode", 0) == 0 else None
        if isinstance(data, dict):
            detail = data.get("deviceInfo", data)
        else:
            detail = None
        self.detail = detail if isinstance(detail, dict) else {}
        self._handle_listeners()
        return self.detail

    async def update_logs(self) -> list:
        """Read the five most recent feeding records."""
        response = await self.account.request(
            "token/device/feederpro/stats/log/top5", {"deviceId": self.id}
        )
        data = response.get("data") if response.get("returnCode", 0) == 0 else None
        logs = data.get("feederLogTop5") if isinstance(data, dict) else None
        self.logs = (
            [log for log in logs if isinstance(log, dict)]
            if isinstance(logs, list)
            else []
        )
        self._handle_listeners()
        return self.logs

    @property
    def state(self) -> str | None:
        """Return the food dispensing status."""
        return self.detail.get("foodOutStatus")

    @property
    def weight(self) -> float | None:
        """Return the food tray weight in grams, when supplied."""
        value = self.detail.get("weight")
        if value is None or isinstance(value, bool):
            return None
        try:
            weight = float(value)
        except (TypeError, ValueError):
            return None
        return weight if isfinite(weight) else None

    @property
    def online(self) -> bool:
        """Return connectivity, accepting both list and detail formats."""
        for source in (self.detail, self.data):
            for key in ("online", "onlineStatus"):
                value = source.get(key)
                if isinstance(value, bool):
                    return value
                if value in ("ONLINE", "OFFLINE"):
                    return value == "ONLINE"
        return False

    @property
    def error(self) -> str | None:
        """Return the current device error message."""
        return (
            self.detail.get("currentErrorMessage")
            or self.detail.get("error")
            or self.data.get("currentErrorMessage")
        )

    @property
    def last_log(self) -> str | None:
        """Format the latest feeding record without missing-field placeholders."""
        log = self._last_log
        return " ".join(
            str(log[key])
            for key in ("time", "event", "firstSection", "secondSection")
            if log.get(key) is not None and log[key] != ""
        ) or None

    def state_attrs(self) -> dict:
        """Return additional read-only device status."""
        return {
            "auto_fill_status": self.detail.get("autoFillStatus"),
            "power_supply_status": self.detail.get("powerSupplyStatus"),
            "key_lock_status": self.detail.get("keyLockStatus"),
            "current_error_type": self.detail.get("currentErrorType"),
        }

    @property
    def hass_sensor(self) -> dict:
        """Return status, food tray weight, errors and recent feeding records."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "weight": {
                "name": "Food tray weight",
                "icon": "mdi:weight-gram",
                "class": SensorDeviceClass.WEIGHT,
                "unit": UnitOfMass.GRAMS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "error": {"icon": "mdi:alert-circle"},
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the connectivity sensor."""
        return {"online": {"class": BinarySensorDeviceClass.CONNECTIVITY}}

    @property
    def hass_select(self) -> dict:
        """Feeder Pro controls are not exposed."""
        return {}
