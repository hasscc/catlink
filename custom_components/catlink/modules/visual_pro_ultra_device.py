"""Visual Pro Ultra device module for CatLink integration."""

from collections import deque
import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import _LOGGER, DOMAIN  # noqa: TID252
from ..models.additional_cfg import AdditionalDeviceConfig  # noqa: TID252
from .device import Device

if TYPE_CHECKING:
    from .devices_coordinator import DevicesCoordinator


class VisualProUltraDevice(Device):
    """Visual Pro Ultra device class for CatLink integration."""

    logs: list
    coordinator_logs = None

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the Visual Pro Ultra device."""
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
        """Return the modes of the device."""
        return {
            "00": "auto",
            "01": "manual",
            "02": "time",
        }

    @property
    def actions(self) -> dict:
        """Return the actions of the device."""
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
    def last_log(self) -> str | None:
        """Return the last log."""
        log = self._last_log
        if not log:
            return None
        return f"{log.get('time')} {log.get('event')}"

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
            result = dic.get(f"{sta}".strip(), sta)
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get device state failed: %s", exc)
            return "unknown"
        else:
            return result if result else "unknown"

    @property
    def litter_weight(self) -> float:
        """Return the litter weight."""
        litter_weight = 0.0
        try:
            catLitterWeight = self.detail.get(
                "catLitterWeight", self.empty_litter_box_weight
            )
            litter_weight = catLitterWeight - self.empty_litter_box_weight
            self._litter_weight_during_day.append(litter_weight)

        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Got litter weight failed: %s", exc)

        return litter_weight

    @property
    def litter_remaining_days(self) -> int:
        """Return the litter remaining days."""
        try:
            return int(self.detail.get("litterCountdown", 0))
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get litter remaining days failed: %s", exc)
            return 0

    @property
    def total_clean_time(self) -> int:
        """Return the total clean time."""
        try:
            return int(self.detail.get("inductionTimes", 0)) + int(
                self.detail.get("manualTimes", 0)
            )
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get total clean time failed: %s", exc)
            return 0

    @property
    def manual_clean_time(self) -> int:
        """Return the manual clean time."""
        try:
            return int(self.detail.get("manualTimes", 0))
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get manual clean time failed: %s", exc)
            return 0

    @property
    def deodorant_countdown(self) -> int:
        """Return the deodorant countdown."""
        try:
            return int(self.detail.get("deodorantCountdown", 0))
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get deodorant countdown failed: %s", exc)
            return 0

    @property
    def knob_status(self) -> str:
        """Return the knob status."""
        try:
            knob_flab = (
                any(
                    "left_knob_abnormal" in e.get("errkey", "")
                    for e in self.detail.get("deviceErrorList", [])
                )
                if self.detail
                else False
            )
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Got knob status failed: %s", exc)
            return "Unknown"
        else:
            return "Empty Mode" if knob_flab else "Cleaning Mode"

    @property
    def occupied(self) -> bool:
        """Return the occupied status."""
        # Visual Pro Ultra provides inUse status from visualCloudStorageRecordVo
        try:
            storage_info = self.detail.get("visualCloudStorageRecordVo", {})
            in_use = storage_info.get("inUse")

            # If inUse is available (not None), use it directly
            if in_use is not None:
                return bool(in_use)

            # Fallback: based on _litter_weight_during_day to determine if occupied
            # check whether value is increasing at any point in the day
            return any(
                self._litter_weight_during_day[i]
                < self._litter_weight_during_day[i + 1]
                for i in range(len(self._litter_weight_during_day) - 1)
            )
        except (IndexError, TypeError, ValueError) as exc:
            _LOGGER.debug("Get occupied status failed: %s", exc)
            return False

    @property
    def online(self) -> bool:
        """Return the online status."""
        try:
            return bool(self.detail)
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get online status failed: %s", exc)
            return False

    @property
    def last_sync(self) -> str | None:
        """Return the last sync time."""
        tz_info = self.detail["timezoneId"] if self.detail else None
        tz = ZoneInfo(tz_info) if tz_info else datetime.UTC
        # Current time in that timezone
        now_local = datetime.datetime.now(tz)

        return now_local.strftime("%Y-%m-%d %H:%M:%S %Z")

    @property
    def garbage_tobe_status(self) -> str:
        """Return the garbage to be status."""
        try:
            full_flag = (
                any(
                    "garbage_tobe_full_abnormal" in e.get("errkey", "")
                    for e in self.detail.get("deviceErrorList", [])
                )
                if self.detail
                else False
            )
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Got garbage to be status failed: %s", exc)
            return "Unknown"
        else:
            return "Full" if full_flag else "Normal"

    @property
    def error(self) -> str:
        """Return the device error."""
        try:
            error = (
                self.detail.get("currentMessage")
                or self.detail.get("currentError")
                or "Normal Operation"
            )
            if error and error.lower() not in ("device online", "normal operation"):
                self._error_logs.append(
                    {
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "error": error,
                    }
                )
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get device error failed: %s", exc)
            return "Unknown"
        else:
            return error

    @property
    def cloud_storage_status(self) -> str:
        """Return the cloud storage status."""
        try:
            storage_info = self.detail.get("visualCloudStorageRecordVo", {})
            if not storage_info:
                return "Not Available"
            status = storage_info.get("status", 0)
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get cloud storage status failed: %s", exc)
            return "Unknown"
        else:
            if status == 2:
                return "Active"
            if status == 1:
                return "Pending"
            return "Inactive"

    @property
    def cloud_storage_days_left(self) -> int:
        """Return cloud storage days left."""
        try:
            storage_info = self.detail.get("visualCloudStorageRecordVo", {})
            return int(storage_info.get("leftDays", 0))
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get cloud storage days left failed: %s", exc)
            return 0

    @property
    def total_clean_times(self) -> int:
        """Return the total clean times."""
        try:
            return int(self.detail.get("totalCleanTimes", 0))
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get total clean times failed: %s", exc)
            return 0

    @property
    def quiet_mode_enabled(self) -> bool:
        """Return if quiet mode is enabled."""
        try:
            return self.detail.get("quietEnable", False)
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get quiet mode status failed: %s", exc)
            return False

    @property
    def auto_update_pet_weight(self) -> bool:
        """Return if auto update pet weight is enabled."""
        try:
            return self.detail.get("autoUpdatePetWeight", False)
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Get auto update pet weight status failed: %s", exc)
            return False

    @property
    def hass_sensor(self) -> dict:
        """Return the hass sensor of the device."""
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
            "cloud_storage_status": {
                "icon": "mdi:cloud-check"
                if self.cloud_storage_status == "Active"
                else "mdi:cloud-off",
            },
            "cloud_storage_days_left": {
                "icon": "mdi:calendar-clock",
                "unit": "days",
            },
            "total_clean_times": {
                "icon": "mdi:counter",
                "unit": "times",
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the device binary sensors."""
        return {
            "occupied": {
                "icon": "mdi:cat",
                "state": self.occupied,
            },
            "online": {
                "icon": "mdi:wifi",
                "state": self.online,
            },
            "quiet_mode_enabled": {
                "icon": "mdi:volume-off"
                if self.quiet_mode_enabled
                else "mdi:volume-high",
                "state": self.quiet_mode_enabled,
            },
            "auto_update_pet_weight": {
                "icon": "mdi:scale" if self.auto_update_pet_weight else "mdi:scale-off",
                "state": self.auto_update_pet_weight,
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

    def state_attrs(self) -> dict:
        """Return the state attributes."""
        storage_info = self.detail.get("visualCloudStorageRecordVo", {})
        return {
            "mac": self.mac,
            "model": self.model,
            "device_type": self.type,
            "real_model": self.data.get("realModel"),
            "device_model": self.detail.get("deviceModel"),
            "timezone_id": self.data.get("timezoneId") or self.detail.get("timezoneId"),
            "gmt": self.detail.get("gmt"),
            "work_status": self.detail.get("workStatus"),
            "alarm_status": self.detail.get("alarmStatus"),
            "weight": self.detail.get("weight"),
            "litter_weight_kg": self.detail.get("catLitterWeight"),
            "total_clean_times": self.total_clean_times,
            "manual_clean_times": self.detail.get("manualTimes"),
            "key_lock": self.detail.get("keyLock"),
            "secret_lock": self.detail.get("secretLock"),
            "safe_time": self.detail.get("safeTime"),
            "pave_second": self.detail.get("catLitterPaveSecond"),
            "deodorant_countdown": self.detail.get("deodorantCountdown"),
            "litter_countdown": self.detail.get("litterCountdown"),
            "last_sync_time": self.last_sync,
            "box_full_sensitivity": self.detail.get("boxFullSensitivity"),
            "quiet_times": self.detail.get("quietTimes"),
            "quiet_enable": self.detail.get("quietEnable"),
            "auto_update_pet_weight": self.detail.get("autoUpdatePetWeight"),
            "all_timing_toggle": self.detail.get("allTimingToggle"),
            "cat_litter_type": self.detail.get("catLitterType"),
            "sn_enable": self.detail.get("snEnable"),
            "qc_flag": self.detail.get("qcFlag"),
            "master": self.detail.get("master"),
            "cloud_storage_status": self.cloud_storage_status,
            "cloud_storage_days_left": self.cloud_storage_days_left,
            "cloud_storage_product": storage_info.get("productName"),
            "cloud_storage_lifecycle": storage_info.get("lifecycle"),
            "cloud_storage_multicat": storage_info.get("muticatStatus") == 1,
        }

    def last_log_attrs(self) -> dict:
        """Return the last log attributes."""
        log = self._last_log
        return {
            **log,
            "logs": self.logs,
        }

    def error_attrs(self) -> dict:
        """Return the error attributes."""
        try:
            return {
                "errors": self.detail.get("deviceErrorList", []),
                "error_logs": list(self._error_logs),
            }
        except (TypeError, ValueError, KeyError) as exc:
            _LOGGER.error("Got error attributes failed: %s", exc)
            return {"error_logs": list(self._error_logs)}

    @property
    def box_full_sensitivity(self) -> str | None:
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

    async def update_logs(self) -> list:
        """Update device logs."""
        api = "token/litterbox/stats/log/timeline/v2"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        pms = {
            "deviceId": self.id,
            "date": today,
            "pageNumber": 1,
            "pageSize": 10,
            "type": 0,
            "subType": 0,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get("data", {}).get("records") or []
        except (TypeError, ValueError) as exc:
            rdt = []
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt

    async def update_device_detail(self) -> dict:
        """Update the device detail."""
        api = "token/visualScooper/briefInfo"
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

    async def select_mode(self, mode, **kwargs) -> bool:
        """Select the device mode."""
        api = "token/visualScooper/changeMode"
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
        return True

    async def select_action(self, action, **kwargs) -> bool:
        """Select the device action."""
        api = "token/visualScooper/actionCmd"
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
        return True

    async def select_box_full_sensitivity(self, level, **kwargs) -> bool:
        """Select the box full sensitivity level."""
        api = "token/visualScooper/boxFullSetting"
        lvl = None
        for k, v in self.box_full_levels.items():
            if v == level:
                lvl = k
                break
        if lvl is None:
            _LOGGER.warning(
                "Select box full sensitivity failed for %s in %s",
                level,
                self.box_full_levels,
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
        return True

    async def changeBag(self, mode, **kwargs) -> bool:
        """Change the garbage bag."""
        api = "token/visualScooper/replaceGarbageBagCmd"
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
        return True
