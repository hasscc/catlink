"""CATLINK visual C07 litter box support."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from aiohttp import ClientError

from ..const import _LOGGER
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.logs import LogEntry
from ..models.api.parse import parse_response
from .base import Device
from .mixins.logs import LogsMixin

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator

_DETAIL_FIELDS = (
    "online",
    "workStatus",
    "runStatus",
    "finalStatus",
    "cleanStatus",
    "emptyStatus",
    "alarmStatus",
    "currentMessage",
    "currentMessageType",
    "autoSwitch",
    "keyLock",
    "kittenModel",
    "deodorantEnable",
    "timerSwitch",
    "continuousCleaning",
    "quietEnable",
    "watermark",
    "autoUpdatePetWeight",
    "cameraSwitch",
    "fillLight",
    "safeTime",
    "offScreenDuration",
    "paneltone",
    "sandBoxInstall",
    "sandPaveLevel",
    "sandboxBalance",
    "catLitterBalance",
    "garbageStatus",
    "litterType",
    "catLitterPaveSecond",
    "boxFullSensitivity",
    "totalCleanTimes",
    "litterCountdown",
    "deodorantCountdown",
    "firmwareVersion",
)
_BALANCE_STATES = {0: "full", 1: "low", 2: "half"}
_GARBAGE_STATES = {"00": "low", "01": "half", "02": "full"}
_MAX_EVENT_IMAGE_BYTES = 5 * 1024 * 1024


class VisualC07Device(LogsMixin, Device):
    """Visual C07 device with the currently verified read-only surface."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        super().__init__(dat, coordinator, additional_config)
        self.sand_info: dict[str, Any] = {}
        self._media_events: list[dict[str, Any]] = []
        self._iot_id: str | None = None

    async def async_init(self) -> None:
        """Initialize detail and timeline coordinators."""
        await super().async_init()
        await self._async_init_logs()

    @property
    def state(self) -> str:
        """Return the observed device work state."""
        value = self.detail.get("workStatus")
        if value == "00":
            return "idle"
        if value == "01":
            return "running"
        if value == "02":
            return "need_reset"
        return value if isinstance(value, str) and value else "unknown"

    def state_attrs(self) -> dict[str, Any]:
        """Return recorder-safe operational attributes."""
        errors = self.detail.get("deviceErrorList")
        return {
            "run_status": self.detail.get("runStatus"),
            "final_status": self.detail.get("finalStatus"),
            "clean_status": self.detail.get("cleanStatus"),
            "error_keys": [
                item.get("errkey")
                for item in errors
                if isinstance(item, dict) and isinstance(item.get("errkey"), str)
            ]
            if isinstance(errors, list)
            else [],
        }

    @property
    def online(self) -> bool:
        return self.detail.get("online") is True

    @property
    def litter_remaining_days(self) -> int | str:
        return self.detail.get("litterCountdown", "unknown")

    @property
    def deodorant_countdown(self) -> int | str:
        return self.detail.get("deodorantCountdown", "unknown")

    @property
    def total_clean_time(self) -> int | str:
        value = self.detail.get("totalCleanTimes")
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return "unknown"

    @property
    def auto_refill_installed(self) -> bool:
        """Return whether the auto-refill module is installed."""
        return (
            self.sand_info.get("install") is True
            or self.detail.get("sandBoxInstall") is True
        )

    @property
    def auto_refill_mode(self) -> str:
        """Return the auto-refill mode without exposing an unverified control."""
        mode = self.sand_info.get("workModel")
        if mode == 0:
            return "automatic"
        if mode == 1:
            return "manual"
        return "unknown"

    @property
    def auto_refill_level(self) -> int | str:
        """Return the configured refill sensitivity/level."""
        value = self.sand_info.get("level")
        return value if isinstance(value, int) else "unknown"

    @property
    def sand_box_balance(self) -> str:
        value = self.detail.get("sandboxBalance")
        return (
            _BALANCE_STATES.get(value, "unknown")
            if isinstance(value, int)
            else "unknown"
        )

    @property
    def litter_balance(self) -> str:
        value = self.detail.get("catLitterBalance")
        return (
            _BALANCE_STATES.get(value, "unknown")
            if isinstance(value, int)
            else "unknown"
        )

    @property
    def garbage_status(self) -> str:
        value = self.detail.get("garbageStatus")
        return (
            _GARBAGE_STATES.get(value, "unknown")
            if isinstance(value, str)
            else "unknown"
        )

    @property
    def auto_clean(self) -> bool:
        return self.detail.get("autoSwitch") is True

    @property
    def child_lock(self) -> bool:
        return self.detail.get("keyLock") in (True, 1, "1", "01")

    @property
    def kitten_mode(self) -> bool:
        return self.detail.get("kittenModel") is True

    @property
    def deodorant_enabled(self) -> bool:
        return self.detail.get("deodorantEnable") is True

    @property
    def timer_clean_enabled(self) -> bool:
        return self.detail.get("timerSwitch") is True

    @property
    def continuous_cleaning(self) -> bool:
        return self.detail.get("continuousCleaning") is True

    @property
    def quiet_mode(self) -> bool:
        return self.detail.get("quietEnable") is True

    @property
    def watermark_enabled(self) -> bool:
        return self.detail.get("watermark") is True

    @property
    def auto_update_pet_weight(self) -> bool:
        return self.detail.get("autoUpdatePetWeight") is True

    @property
    def hass_sensor(self) -> dict:
        return {
            "state": {"icon": "mdi:information", "state_attrs": self.state_attrs},
            "last_log": {
                "icon": "mdi:message",
                "state_attrs": self.last_log_attrs,
            },
            "litter_remaining_days": {"icon": "mdi:calendar", "unit": "days"},
            "deodorant_countdown": {"icon": "mdi:timer", "unit": "days"},
            "total_clean_time": {"icon": "mdi:history", "unit": "times"},
            "auto_refill_mode": {"icon": "mdi:auto-fix"},
            "auto_refill_level": {"icon": "mdi:signal"},
            "sand_box_balance": {"icon": "mdi:tray-full"},
            "litter_balance": {"icon": "mdi:chart-donut"},
            "garbage_status": {"icon": "mdi:delete"},
        }

    @property
    def hass_binary_sensor(self) -> dict:
        return {
            "online": {"icon": "mdi:cloud-check"},
            "auto_refill_installed": {"icon": "mdi:tray-full"},
            "auto_clean": {"icon": "mdi:auto-fix"},
            "child_lock": {"icon": "mdi:lock"},
            "kitten_mode": {"icon": "mdi:cat"},
            "deodorant_enabled": {"icon": "mdi:air-filter"},
            "timer_clean_enabled": {"icon": "mdi:timer-cog"},
            "continuous_cleaning": {"icon": "mdi:autorenew"},
            "quiet_mode": {"icon": "mdi:volume-off"},
            "watermark_enabled": {"icon": "mdi:watermark"},
            "auto_update_pet_weight": {"icon": "mdi:scale"},
        }

    @property
    def hass_camera(self) -> dict:
        return {
            "latest_event_picture": {
                "name": "Latest Event Picture",
                "async_image": self.async_get_latest_event_image,
            }
        }

    @property
    def hass_select(self) -> dict:
        # Visual C07 does not use the legacy device/changeMode and
        # device/actionCmd surface. Do not expose non-functional controls.
        return {}

    async def async_get_latest_event_image(self) -> bytes | None:
        """Fetch the newest event JPEG without exposing its signed URL."""
        picture_id = None
        for event in self._media_events:
            picture_id = next(
                (
                    event.get(key)
                    for key in (
                        "picIdOfPre",
                        "picIdOfNext",
                        "picIdOfCapture",
                        "picIdOfBehind",
                    )
                    if isinstance(event.get(key), str) and event.get(key)
                ),
                None,
            )
            if picture_id:
                break
        if not picture_id:
            return None
        try:
            response = await self.account.request(
                "token/cameraLitterbox/getPicUrl",
                {"deviceId": self.id, "picId": picture_id},
            )
            if response.get("returnCode") not in (None, 0):
                return None
            data = response.get("data", {})
            url = data.get("picUrl") if isinstance(data, dict) else None
            if not isinstance(url, str):
                return None
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or not host
                or not (host == "aliyuncs.com" or host.endswith(".aliyuncs.com"))
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443)
            ):
                return None
            async with self.account.http.get(
                url, allow_redirects=False, timeout=10
            ) as image_response:
                if image_response.status not in (200, 206):
                    return None
                content_type = image_response.headers.get("Content-Type", "")
                if content_type.split(";", 1)[0].strip().lower() != "image/jpeg":
                    return None
                content_length = image_response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > _MAX_EVENT_IMAGE_BYTES:
                            return None
                    except ValueError:
                        return None
                chunks = []
                total = 0
                async for chunk in image_response.content.iter_chunked(64 * 1024):
                    total += len(chunk)
                    if total > _MAX_EVENT_IMAGE_BYTES:
                        return None
                    chunks.append(chunk)
                image = b"".join(chunks)
                return image if image.startswith(b"\xff\xd8\xff") else None
        except (ClientError, TimeoutError, TypeError, ValueError) as exc:
            _LOGGER.warning(
                "Got Visual C07 event picture for %s failed: %s",
                self.name,
                type(exc).__name__,
            )
            return None

    async def update_sand_info(self) -> dict[str, Any]:
        """Read the C07 auto-refill module state."""
        response = await self.account.request(
            "token/cameraLitterbox/sandSysInfo", {"deviceId": self.id}
        )
        data = response.get("data", {})
        info = data.get("info", {}) if isinstance(data, dict) else {}
        if not isinstance(info, dict):
            return {}
        return {
            key: info.get(key)
            for key in ("workModel", "level", "install")
            if key in info
        }

    @staticmethod
    def _safe_detail(raw: object) -> dict[str, Any]:
        """Keep identifiers, media grants, URLs and sharing data out of HA state."""
        if not isinstance(raw, dict):
            return {}
        detail = {key: raw.get(key) for key in _DETAIL_FIELDS if key in raw}
        errors = raw.get("deviceErrorList")
        if isinstance(errors, list):
            detail["deviceErrorList"] = [
                {"errkey": item.get("errkey")}
                for item in errors
                if isinstance(item, dict) and isinstance(item.get("errkey"), str)
            ]
        return detail

    async def update_device_detail(self) -> dict:
        api = "token/cameraLitterbox/info"
        params = {"deviceId": self.id}
        try:
            response = await self.account.request(api, params)
            data = response.get("data", {})
            raw = data.get("deviceInfo", {}) if isinstance(data, dict) else {}
            self._iot_id = (
                raw.get("iotId")
                if isinstance(raw, dict) and isinstance(raw.get("iotId"), str)
                else None
            )
            detail = self._safe_detail(raw)
        except (TypeError, ValueError) as exc:
            detail = {}
            self._iot_id = None
            _LOGGER.error("Got Visual C07 detail for %s failed: %s", self.name, exc)
        if not detail:
            _LOGGER.warning("Got Visual C07 detail for %s failed", self.name)
        try:
            self.sand_info = await self.update_sand_info()
        except (TypeError, ValueError) as exc:
            self.sand_info = {}
            _LOGGER.error("Got Visual C07 sand info for %s failed: %s", self.name, exc)
        self.detail = detail
        self._action_error = None
        self._handle_listeners()
        return detail

    async def update_logs(self) -> list[dict[str, Any]]:
        """Read timeline logs while keeping media locators out of HA state."""
        api = "token/litterbox/stats/log/timeline/v2"
        today = datetime.date.today().isoformat()
        params = {
            "deviceId": self.id,
            "date": today,
            "pageNumber": 1,
            "pageSize": 10,
            "type": 0,
            "subType": 0,
        }
        try:
            response = await self.account.request(api, params)
            data = response.get("data", {})
            parsed = parse_response(data, "records", LogEntry, [])
            if isinstance(parsed, list) and parsed and hasattr(parsed[0], "model_dump"):
                raw_logs = [item.model_dump() for item in parsed]
            elif isinstance(parsed, list):
                raw_logs = parsed
            else:
                raw_logs = data.get("records") or []
        except (TypeError, ValueError) as exc:
            raw_logs = []
            _LOGGER.error("Got Visual C07 logs for %s failed: %s", self.name, exc)
        if not raw_logs:
            _LOGGER.warning("Got Visual C07 logs for %s failed", self.name)
        self._media_events = [log for log in raw_logs if isinstance(log, dict)]
        safe_keys = ("time", "event", "firstSection", "secondSection", "errkey")
        self.logs = [
            {
                **{key: log.get(key) for key in safe_keys if key in log},
                "has_video": bool(
                    log.get("moveDetectId")
                    or log.get("video1Url")
                    or log.get("video2Url")
                ),
            }
            for log in self._media_events
        ]
        self._handle_listeners()
        return self.logs
