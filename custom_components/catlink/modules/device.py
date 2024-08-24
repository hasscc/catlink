"""Device module for CatLink integration."""

from typing import TYPE_CHECKING

from ..const import _LOGGER

if TYPE_CHECKING:
    from .devices_coordinator import DevicesCoordinator


class Device:
    """Device class for CatLink integration."""

    data: dict

    def __init__(self, dat: dict, coordinator: "DevicesCoordinator") -> None:
        """Initialize the device."""
        self.coordinator = coordinator
        self.account = coordinator.account
        self.listeners = {}
        self.update_data(dat)
        self.detail = {}

    async def async_init(self) -> None:
        """Initialize the device."""
        await self.update_device_detail()

    def update_data(self, dat: dict) -> None:
        """Update device data."""
        self.data = dat
        self._handle_listeners()
        _LOGGER.info("Update device data: %s", dat)

    def _handle_listeners(self):
        for fun in self.listeners.values():
            fun()

    @property
    def id(self) -> str:
        """Return the device id."""
        try:
            return self.data.get("id")
        except (TypeError, ValueError):
            return None

    @property
    def mac(self) -> str:
        """Return the device mac."""
        try:
            return self.data.get("mac")
        except (TypeError, ValueError):
            return None

    @property
    def model(self) -> str:
        """Return the device model."""
        try:
            return self.data.get("model")
        except (TypeError, ValueError):
            return None

    @property
    def type(self) -> str:
        """Return the device type."""
        try:
            return self.data.get("type")
        except (TypeError, ValueError):
            return None

    @property
    def name(self) -> str:
        """Return the device name."""
        try:
            return self.data.get("deviceName", "")
        except (TypeError, ValueError):
            return None

    @property
    def error(self) -> str:
        """Return the device error."""
        try:
            return self.detail.get("currentMessage") or self.data.get(
                "currentErrorMessage", ""
            )
        except (TypeError, ValueError):
            return None

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
    def mode(self) -> str:
        """Return the device mode."""
        return self.modes.get(self.detail.get("workModel", ""))

    @property
    def modes(self) -> dict:
        """Return the device modes."""
        return {}

    @property
    def action(self) -> str:
        """Return the device action."""
        return None

    @property
    def actions(self) -> dict:
        """Return the device actions."""
        return {}

    @property
    def hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the device binary sensors."""
        return {}

    @property
    def hass_switch(self) -> dict:
        """Return the device switches."""
        return {}

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
            "action": {
                "icon": "mdi:play-box",
                "options": list(self.actions.values()),
                "async_select": self.select_action,
                "delay_update": 5,
            },
        }

    def state_attrs(self) -> dict:
        """Return the device state attributes."""
        return {
            "work_status": self.detail.get("workStatus"),
            "alarm_status": self.detail.get("alarmStatus"),
            "atmosphere_status": self.detail.get("atmosphereStatus"),
            "temperature": self.detail.get("temperature"),
            "humidity": self.detail.get("humidity"),
            "weight": self.detail.get("weight"),
            "key_lock": self.detail.get("keyLock"),
            "safe_time": self.detail.get("safeTime"),
            "pave_second": self.detail.get("catLitterPaveSecond"),
        }

    def mode_attrs(self) -> dict:
        """Return the device mode attributes."""
        return {
            "work_mode": self.detail.get("workModel"),
        }

    async def select_mode(self, mode, **kwargs) -> bool:
        """Select the device mode."""
        api = "token/device/changeMode"
        mod = None
        for k, v in self.modes.items():
            if v == mode:
                mod = k
                break
        if mod is None:
            _LOGGER.warning("Select mode failed for %s in %s", mode, self.modes)
            return False
        pms = {
            "workModel": mod,
            "deviceId": self.id,
        }
        rdt = await self.account.request(api, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            _LOGGER.error("Select mode failed: %s", [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info("Select mode: %s", [rdt, pms])
        return rdt

    async def select_action(self, action, **kwargs) -> bool:
        """Select the device action."""
        api = "token/device/actionCmd"
        val = None
        for k, v in self.actions.items():
            if v == action:
                val = k
                break
        if val is None:
            _LOGGER.warning("Select action failed for %s in %s", action, self.actions)
            return False
        pms = {
            "cmd": val,
            "deviceId": self.id,
        }
        rdt = await self.account.request(api, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            _LOGGER.error("Select action failed: %s", [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info("Select action: %s", [rdt, pms])
        return rdt

    async def update_device_detail(self) -> dict:
        """Update the device detail."""
        api = "token/device/info"
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
        self.detail = rdt
        self._handle_listeners()
        return rdt
