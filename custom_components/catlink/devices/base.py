"""Device base class for CatLink integration."""

from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..helpers import format_api_error
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import DeviceInfoBase
from ..models.api.parse import parse_response

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class Device:
    """Device class for CatLink integration."""

    data: dict

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig = None,
    ) -> None:
        """Initialize the device."""
        self.additional_config = additional_config or AdditionalDeviceConfig()
        self.coordinator = coordinator
        self.account = coordinator.account
        self.listeners = {}
        self._action_error: str | None = None
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

    def _handle_listeners(self) -> None:
        """Notify all registered listeners to refresh their state."""
        for fun in self.listeners.values():
            fun()

    def _set_action_error(self, error_msg: str) -> None:
        """Store API error and refresh entities so the error sensor updates."""
        self._action_error = error_msg
        self._handle_listeners()

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
            return self.data.get("deviceType")
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
        if self._action_error:
            return self._action_error
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
    def hass_button(self):
        """Return the device buttons."""
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
            err_msg = format_api_error(rdt)
            _LOGGER.error("Select mode failed: %s", err_msg)
            self._set_action_error(err_msg)
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
            err_msg = format_api_error(rdt)
            _LOGGER.error("Select action failed: %s", err_msg)
            self._set_action_error(err_msg)
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
            data = rsp.get("data", {})
            raw = data.get("deviceInfo")
            parsed = parse_response(data, "deviceInfo", DeviceInfoBase)
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
            _LOGGER.warning("Got device detail for %s failed: %s", self.name, rsp)
        self.detail = rdt
        self._action_error = None
        self._handle_listeners()
        return rdt
