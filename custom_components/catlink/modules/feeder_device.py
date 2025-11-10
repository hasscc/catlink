"""Feeder device class for CatLink integration."""

import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfMass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import _LOGGER, DOMAIN
from ..models.additional_cfg import AdditionalDeviceConfig
from .device import Device

if TYPE_CHECKING:
    from .devices_coordinator import DevicesCoordinator


class FeederDevice(Device):
    """Feeder device class for CatLink integration."""

    logs: list
    coordinator_logs = None

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(dat, coordinator, additional_config)

    @property
    def weight(self) -> int:
        """Return the weight of the device."""
        return self.detail.get("weight")

    @property
    def error(self) -> str:
        """Return the error of the device."""
        return self.detail.get("error")

    def error_attrs(self) -> dict:
        """Return the error attributes of the device."""
        return {
            "currentErrorMessage": self.detail.get("currentErrorMessage"),
            "currentErrorType": self.detail.get("currentErrorType"),
        }

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
        await self.coordinator_logs.async_refresh()

    async def update_device_detail(self) -> dict:
        api = "token/device/feeder/detail"
        pms = {
            "deviceId": self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get("data", {}).get("deviceInfo") or {}
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device detail for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device detail for %s failed: %s", self.name, rsp)
        _LOGGER.debug("Update device detail: %s", rsp)
        self.detail = rdt
        self._handle_listeners()
        return rdt

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self.detail.get("foodOutStatus")

    def state_attrs(self) -> dict:
        """Return the state attributes of the device."""
        return {
            "work_status": self.detail.get("foodOutStatus"),
            "auto_fill_status": self.detail.get("autoFillStatus"),
            "indicator_light_status": self.detail.get("indicatorLightStatus"),
            "breath_light_status": self.detail.get("breathLightStatus"),
            "power_supply_status": self.detail.get("powerSupplyStatus"),
            "key_lock_status": self.detail.get("keyLockStatus"),
        }

    @property
    def _last_log(self) -> dict:
        """Return the last log of the device."""
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
        return f"{log.get('time')} {log.get('event')} {log.get('firstSection')} {log.get('secondSection')}".strip()

    def last_log_attrs(self) -> dict:
        """Return the last log attributes of the device."""
        log = self._last_log
        return {
            **log,
            "logs": self.logs,
        }

    async def update_logs(self) -> list:
        """Update the logs of the device."""
        api = "token/device/feeder/stats/log/top5"
        pms = {
            "deviceId": self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get("data", {}).get("feederLogTop5") or []
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.debug("Got device logs for %s failed: %s", self.name, rsp)
        _LOGGER.debug("Update device logs: %s", rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt

    async def food_out(self) -> dict:
        """Food out of the device."""
        api = "token/device/feeder/foodOut"
        pms = {
            "footOutNum": 5,
            "deviceId": self.id,
        }
        rdt = await self.account.request(api, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            _LOGGER.error("Food out failed: %s", [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info("Food out: %s", [rdt, pms])
        return rdt

    @property
    def hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "weight": {
                "icon": "mdi:weight-gram",
                "state": self.weight,
                "class": SensorDeviceClass.WEIGHT,
                "unit": UnitOfMass.GRAMS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "error": {
                "icon": "mdi:alert-circle",
                "state": self.error,
                "state_attrs": self.error_attrs,
            },
            "last_log": {
                "icon": "mdi:message",
                "state": self.last_log,
                "state_attrs": self.last_log_attrs,
            },
        }

    @property
    def hass_button(self) -> dict:
        """Return the device buttons."""
        return {
            "feed": {
                "icon": "mdi:food",
                "async_press": self.food_out,
            }
        }

    @property
    def hass_select(self) -> dict:
        """Return the device selects."""
        return {}
