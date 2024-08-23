"Scooper device module for CatLink integration."

import datetime

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import _LOGGER, DOMAIN
from .device import Device


class ScooperDevice(Device):
    """Scooper device class for CatLink integration."""

    logs: list
    coordinator_logs = None

    async def async_init(self) -> None:
        """Initialize the device."""
        await super().async_init()
        self.logs = []
        self.coordinator_logs = DataUpdateCoordinator(
            self.account.hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.id}-logs",
            update_method=self.update_logs,
            update_interval=datetime.timedelta(minutes=1),
        )
        await self.coordinator_logs.async_config_entry_first_refresh()

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
    def _last_log(self):
        log = {}
        if self.logs:
            log = self.logs[0] or {}
        return log

    @property
    def last_log(self) -> str:
        """Return the last log of the device."""
        log = self._last_log
        if not log:
            return None
        return f"{log.get('time')} {log.get('event')}"

    def last_log_attrs(self) -> dict:
        """Return the last log attributes of the device."""
        log = self._last_log
        return {
            **log,
            "logs": self.logs,
        }

    async def update_logs(self) -> list:
        """Update device logs."""
        api = "token/device/scooper/stats/log/top5"
        pms = {
            "deviceId": self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get("data", {}).get("scooperLogTop5") or []
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt

    @property
    def hass_sensor(self) -> dict:
        """Return the hass sensor of the device."""
        return {
            **super().hass_sensor,
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
        }
