"""Litter device base class for LitterBox and ScooperDevice."""

from collections import deque
from typing import TYPE_CHECKING

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from .base import Device
from .mixins.logs import LogsMixin

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator


class LitterDevice(LogsMixin, Device):
    """Base class for litter-related devices (LitterBox, ScooperDevice)."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the litter device."""
        super().__init__(dat, coordinator, additional_config)
        self._litter_weight_during_day = deque(
            maxlen=self.additional_config.max_samples_litter or 24
        )
        self.empty_litter_box_weight = self.additional_config.empty_weight or 0.0

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
    def litter_weight(self) -> float:
        """Return the litter weight."""
        litter_weight = 0.0
        try:
            cat_litter_weight = self.detail.get("catLitterWeight")
            if cat_litter_weight is None:
                # The API sends the key with a null value on some models, so the
                # dict.get() default never fires - guard explicitly.
                cat_litter_weight = self.empty_litter_box_weight
            litter_weight = cat_litter_weight - self.empty_litter_box_weight
            self._litter_weight_during_day.append(litter_weight)
            if litter_weight == 0.0:
                _LOGGER.debug(
                    "litter_weight is 0: catLitterWeight=%r, empty_litter_box_weight=%r (detail keys: %s)",
                    cat_litter_weight,
                    self.empty_litter_box_weight,
                    list(self.detail.keys()) if self.detail else "none",
                )
        except Exception as exc:
            _LOGGER.error("Got litter weight failed: %s", exc)
        return litter_weight

    @property
    def litter_remaining_days(self) -> str | int:
        """Return the litter remaining days."""
        try:
            return self.detail.get("litterCountdown", "unknown")
        except Exception as exc:
            _LOGGER.error("Get litter remaining days failed: %s", exc)
            return "unknown"

    @property
    def total_clean_time(self) -> int:
        """Return the total clean time."""
        try:
            auto = self.detail.get("inductionTimes")
            man = self.detail.get("manualTimes")
            # API can return these present-but-null; int(None) would raise.
            return int(auto or 0) + int(man or 0)
        except Exception as exc:
            _LOGGER.error("Get total clean time failed: %s", exc)
            return 0

    @property
    def manual_clean_time(self) -> int:
        """Return the manual clean time."""
        try:
            raw = self.detail.get("manualTimes")
            result = int(raw) if raw is not None else 0
            if result == 0:
                _LOGGER.debug(
                    "manual_clean_time is 0: manualTimes=%r (detail keys: %s)",
                    raw,
                    list(self.detail.keys()) if self.detail else "none",
                )
            return result
        except Exception as exc:
            _LOGGER.error("Get manual clean time failed: %s", exc)
            return 0

    @property
    def deodorant_countdown(self) -> int:
        """Return the deodorant countdown."""
        try:
            raw = self.detail.get("deodorantCountdown")
            # Same here: the key is present but null, so the default is skipped.
            return int(raw) if raw is not None else 0
        except Exception as exc:
            _LOGGER.error("Get deodorant countdown failed: %s", exc)
            return 0

    @property
    def occupied(self) -> bool:
        """Return the occupied status based on litter weight changes during the day."""
        try:
            return any(
                self._litter_weight_during_day[i]
                < self._litter_weight_during_day[i + 1]
                for i in range(len(self._litter_weight_during_day) - 1)
            )
        except IndexError:
            return False

    @property
    def online(self) -> bool:
        """Return the online status."""
        try:
            return self.detail.get("online")
        except Exception as exc:
            _LOGGER.error("Get online status failed: %s", exc)
            return False

    async def async_init(self) -> None:
        """Initialize the device."""
        await super().async_init()
        await self._async_init_logs()

    def _base_state_attrs(self) -> dict:
        """Return base state attributes shared by LitterBox and ScooperDevice."""
        return {
            "mac": self.mac,
            "work_status": self.detail.get("workStatus"),
            "alarm_status": self.detail.get("alarmStatus"),
            "weight": self.detail.get("weight"),
            "litter_weight_kg": self.detail.get("catLitterWeight"),
            "total_clean_times": self.total_clean_time,
            "manual_clean_times": self.detail.get("manualTimes"),
            "key_lock": self.detail.get("keyLock"),
            "safe_time": self.detail.get("safeTime"),
            "pave_second": self.detail.get("catLitterPaveSecond"),
            "deodorant_countdown": self.detail.get("deodorantCountdown"),
            "litter_countdown": self.detail.get("litterCountdown"),
        }
