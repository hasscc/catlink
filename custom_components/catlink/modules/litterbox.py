"""Litter box class for CatLink."""

from collections import deque
import datetime
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import _LOGGER, DOMAIN
from ..models.additional_cfg import AdditionalDeviceConfig
from .device import Device

if TYPE_CHECKING:
    from .devices_coordinator import DevicesCoordinator


class LitterBox(Device):
    """Litter box class for CatLink."""

    logs: list
    coordinator_logs = None

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig = None,
    ) -> None:
        """Initialize the litter box."""
        super().__init__(dat, coordinator, additional_config)
        self.logs = []
        self._litter_weight_during_day = deque(
            maxlen=self.additional_config.max_samples_litter or 24
        )
        self.empty_litter_box_weight = self.additional_config.empty_weight or 0.0

    async def async_init(self) -> None:
        """Initialize the litter box."""
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

    @property
    def modes(self) -> dict:
        """Return the modes."""
        return {
            "00": "auto",
            "01": "manual",
            "02": "time",
        }

    @property
    def actions(self) -> dict:
        """Return the actions."""
        return {
            "01": "Cleaning",
            "00": "Pause",
        }

    @property
    def garbage_actions(self) -> dict:
        """Return the garbage actions."""
        return {
            "00": "Change Bag",
            "01": "Reset",
        }

    @property
    def box_full_levels(self) -> dict:
        """Return the box full sensitivity levels."""
        return {
            "LEVEL_01": "Level 1",
            "LEVEL_02": "Level 2",
            "LEVEL_03": "Level 3",
            "LEVEL_04": "Level 4",
        }

    @property
    def _last_log(self) -> dict:
        """Return the last log."""
        log = {}
        if self.logs:
            log = self.logs[0] or {}
        return log

    @property
    def last_log(self) -> str:
        """Return the last log."""
        log = self._last_log
        if not log:
            return None
        return f"{log.get('time')} {log.get('event')}"

    @property
    def error(self) -> str:
        """Return the error."""
        try:
            return self.detail.get("currentError") or "Normal Operation"
        except Exception as exc:
            _LOGGER.error("Got error failed: %s", exc)
            return "Unknown"

    @property
    def litter_weight(self) -> float:
        """Return the litter weight."""
        litter_weight = 0
        try:
            catLitterWeight = self.detail.get(
                "catLitterWeight", self.empty_litter_box_weight
            )
            litter_weight = catLitterWeight - self.empty_litter_box_weight
            self._litter_weight_during_day.append(litter_weight)

        except Exception as exc:
            _LOGGER.error("Got litter weight failed: %s", exc)

        return litter_weight

    @property
    def litter_remaining_days(self) -> str:
        """Return the litter remaining days."""
        try:
            return int(self.detail.get("litterCountdown", 0))
        except Exception as exc:
            _LOGGER.error("Got litter remaining days failed: %s", exc)
            return 0

    @property
    def total_clean_time(self) -> int:
        """Return the total clean time."""
        try:
            return int(self.detail.get("inductionTimes", 0)) + int(
                self.detail.get("manualTimes", 0)
            )
        except Exception as exc:
            _LOGGER.error("Got total clean time failed: %s", exc)
            return 0

    @property
    def manual_clean_time(self) -> int:
        """Return the manual clean time."""
        try:
            return int(self.detail.get("manualTimes", 0))
        except Exception as exc:
            _LOGGER.error("Got manual clean time failed: %s", exc)
            return 0

    @property
    def deodorant_countdown(self) -> int:
        """Return the deodorant countdown."""
        try:
            return int(self.detail.get("deodorantCountdown", 0))
        except Exception as exc:
            _LOGGER.error("Got deodorant countdown failed: %s", exc)
            return 0

    @property
    def knob_status(self) -> bool:
        """Return the knob status."""
        try:
            knob_flab = (
                any(
                    "left_knob_abnormal" in e.get("errkey")
                    for e in self.detail.get("deviceErrorList", [])
                )
                if self.detail
                else False
            )
            return "Empty Mode" if knob_flab else "Cleaning Mode"
        except Exception as exc:
            _LOGGER.error("Got knob status failed: %s", exc)
            return "Unknown"

    @property
    def occupied(self) -> bool:
        """Return the occupied status."""
        # based on _litter_weight_during_day to determine if the litter box is occupied
        # check whether value is increasing at any point in the day
        # Now we can check which cat is using the litter box :)
        try:
            return any(
                self._litter_weight_during_day[i]
                < self._litter_weight_during_day[i + 1]
                for i in range(len(self._litter_weight_during_day) - 1)
            )
        except Exception as exc:
            _LOGGER.error("Got occupied status failed: %s", exc)
            return False

    @property
    def online(self) -> bool:
        """Return the online status."""
        try:
            return self.detail.get("online")
        except Exception as exc:
            _LOGGER.error("Got online status failed: %s", exc)
            return False

    @property
    def last_sync(self) -> str:
        """Return the last sync time."""
        return (
            datetime.datetime.fromtimestamp(
                int(self.detail.get("lastHeartBeatTimestamp")) / 1000.0
            ).strftime("%Y-%m-%d %H:%M:%S")
            if self.detail.get("lastHeartBeatTimestamp")
            else None
        )

    @property
    def garbage_tobe_status(self) -> str:
        """Return the garbage to be status."""
        try:
            full_flag = (
                any(
                    "garbage_tobe_full_abnormal" in e.get("errkey")
                    for e in self.detail.get("deviceErrorList", [])
                )
                if self.detail
                else False
            )
            return "Full" if full_flag else "Normal"
        except Exception as exc:
            _LOGGER.error("Got garbage to be status failed: %s", exc)
            return "Unknown"

    @property
    def hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "state": {
                "icon": "mdi:information",
                "state_attrs": self.state_attrs,
            },
            "error": {
                "icon": "mdi:alert-circle",
                "state_attrs": self.error_attrs,
            },
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
            "garbage_tobe_status": {
                "icon": "mdi:delete"
                if self.garbage_tobe_status == "Full"
                else "mdi:delete-empty",
            },
            "litter_weight": {
                "icon": "mdi:weight",
                "unit": "kg",
            },
            "litter_remaining_days": {
                "icon": "mdi:calendar",
                "unit": "days",
            },
            "total_clean_time": {
                "icon": "mdi:history",
                "unit": "times",
            },
            "manual_clean_time": {
                "icon": "mdi:history",
                "unit": "times",
            },
            "deodorant_countdown": {
                "icon": "mdi:timer",
                "unit": "days",
            },
            "knob_status": {
                "icon": "mdi:knob"
                if self.knob_status.lower() == "empty mode"
                else "mdi:circle",
            },
            "occupied": {
                "icon": "mdi:cat",
            },
            "online": {
                "icon": "mdi:wifi",
            },
            "last_sync": {
                "icon": "mdi:clock",
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
            "action": {
                "icon": "mdi:play-box",
                "options": list(self.actions.values()),
                "async_select": self.select_action,
                "delay_update": 5,
            },
            "garbage": {
                "icon": "mdi:trash-can",
                "options": list(self.garbage_actions.values()),
                "async_select": self.changeBag,
                "delay_update": 5,
            },
            "box_full_sensitivity": {
                "icon": "mdi:tune",
                "options": list(self.box_full_levels.values()),
                "state_attrs": self.box_full_sensitivity_attrs,
                "async_select": self.select_box_full_sensitivity,
            },
        }

    # Additional Attributes
    def state_attrs(self) -> dict:
        """Return the state attributes."""
        return {
            "mac": self.mac,
            "work_status": self.detail.get("workStatus"),
            "alarm_status": self.detail.get("alarmStatus"),
            "weight": self.detail.get("weight"),
            "litter_weight_kg": self.detail.get("catLitterWeight"),
            "total_clean_times": int(self.detail.get("inductionTimes", 0))
            + int(self.detail.get("manualTimes", 0)),
            "manual_clean_times": self.detail.get("manualTimes"),
            "key_lock": self.detail.get("keyLock"),
            "safe_time": self.detail.get("safeTime"),
            "pave_second": self.detail.get("catLitterPaveSecond"),
            "deodorant_countdown": self.detail.get("deodorantCountdown"),
            "litter_countdown": self.detail.get("litterCountdown"),
            "last_sync_time": datetime.datetime.fromtimestamp(
                int(self.detail.get("lastHeartBeatTimestamp")) / 1000.0
            ).strftime("%Y-%m-%d %H:%M:%S")
            if self.detail.get("lastHeartBeatTimestamp")
            else None,
            "box_full_sensitivity": self.detail.get("boxFullSensitivity"),
            "quiet_times": self.detail.get("quietTimes"),
        }

    def last_log_attrs(self) -> dict:
        """Return the last log attributes."""
        log = self._last_log
        return {
            **log,
            "logs": self.logs,
        }

    def garbage_attrs(self) -> dict:
        """Return the garbage attributes."""
        status = "Unknown"
        match self.garbageStatus:
            case "00":
                status = "Normal"
            case "02":
                status = "Movement Started"
            case "03":
                status = "Moving"
            case _:
                status = "Unknown"
        return {
            "status": status,
        }

    def error_attrs(self) -> list:
        """Return the error attributes."""
        try:
            return {
                "errors": self.detail.get("deviceErrorList"),
            }
        except Exception as exc:
            _LOGGER.error("Got error attributes failed: %s", exc)
            return []

    @property
    def box_full_sensitivity(self) -> str:
        """Return the box full sensitivity."""
        sensitivity = self.detail.get("boxFullSensitivity", "")
        # Try direct mapping first
        mapped_value = self.box_full_levels.get(sensitivity)
        if mapped_value:
            _LOGGER.debug(
                "Box full sensitivity mapped: %s -> %s", sensitivity, mapped_value
            )
            return mapped_value
        # Try converting numeric format (e.g., "01" -> "LEVEL_01")
        if sensitivity and isinstance(sensitivity, (str, int)):
            try:
                # If it's a number or numeric string, convert to LEVEL_XX format
                if isinstance(sensitivity, str) and sensitivity.isdigit():
                    level_key = f"LEVEL_{sensitivity.zfill(2)}"
                elif isinstance(sensitivity, int):
                    level_key = f"LEVEL_{str(sensitivity).zfill(2)}"
                else:
                    level_key = None
                if level_key:
                    mapped_value = self.box_full_levels.get(level_key)
                    if mapped_value:
                        _LOGGER.debug(
                            "Box full sensitivity mapped (converted): %s -> %s -> %s",
                            sensitivity,
                            level_key,
                            mapped_value,
                        )
                        return mapped_value
            except (ValueError, AttributeError):
                pass
        _LOGGER.warning(
            "Box full sensitivity not found in mapping: %s (type: %s, available: %s)",
            sensitivity,
            type(sensitivity).__name__,
            list(self.box_full_levels.keys()),
        )
        return None

    def box_full_sensitivity_attrs(self) -> dict:
        """Return the box full sensitivity attributes."""
        return {
            "raw_level": self.detail.get("boxFullSensitivity"),
        }

    # Actions
    async def update_logs(self) -> list:
        """Update the logs."""
        api = "token/litterbox/stats/log/top5"
        pms = {
            "deviceId": self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            dat = rsp.get("data", {}) or {}
            rdt = (
                dat.get("litterboxLogTop5")
                or dat.get("litterBoxLogTop5")
                or dat.get("scooperLogTop5")
                or []
            )
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt

    async def select_mode(self, mode, **kwargs) -> bool:
        """Select the device mode."""
        api = "token/litterbox/changeMode"
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

    async def select_box_full_sensitivity(self, level, **kwargs) -> bool:
        """Select the box full sensitivity level."""
        api = "token/litterbox/boxFullSetting"
        lvl = None
        for k, v in self.box_full_levels.items():
            if v == level:
                lvl = k
                break
        if lvl is None:
            _LOGGER.warning(
                "Select box full sensitivity failed for %s in %s", level, self.box_full_levels
            )
            return False
        pms = {
            "deviceId": self.id,
            "level": lvl,
        }
        rdt = await self.account.request(api, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            _LOGGER.error("Select box full sensitivity failed: %s", [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info("Select box full sensitivity: %s", [rdt, pms])
        return rdt

    async def update_device_detail(self) -> dict:
        """Update the device detail."""
        api = "token/litterbox/info"
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

    async def select_action(self, action, **kwargs) -> bool:
        """Select the device action."""
        if "Garbage Bag" in action:
            return await self.changeBag()
        api = "token/litterbox/actionCmd"
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

    async def changeBag(self, mode, **kwargs) -> bool:
        """Change the garbage bag."""
        api = "token/litterbox/replaceGarbageBagCmd"
        pms = {
            "enable": "1" if mode == "Change Bag" else "0",
            "deviceId": self.id,
        }
        rdt = await self.account.request(api, pms, "POST")
        eno = rdt.get("returnCode", 0)
        if eno:
            _LOGGER.error("Change bag failed: %s", [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info("Change bag: %s", [rdt, pms])
        return rdt
