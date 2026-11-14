"""Scooper Pro Ultra device module for CatLink integration."""

from __future__ import annotations

import asyncio
import datetime
from functools import partial
import json
import re
import time
from typing import TYPE_CHECKING

from aiohttp import ClientError

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from ..const import _LOGGER
from ..helpers import format_api_error
from ..models.additional_cfg import AdditionalDeviceConfig
from ..models.api.device import LitterDeviceInfo
from ..models.api.logs import LogEntry
from ..models.api.parse import parse_response
from ..modules.aliyun_push import redact
from ..modules.linkvisual import LinkVisualError
from ..modules.talkback import LiveTalkSession, async_play_alaw
from .litter_device import LitterDevice

if TYPE_CHECKING:
    from ..modules.devices_coordinator import DevicesCoordinator

# Value meanings come from the CatLink app.
# RunStatus is "runStatus=<n>&biz=<n>"; biz is the job, runStatus its state.
RUN_JOBS = {"1": "cleaning", "2": "emptying", "3": "leveling"}
RUN_STATES = {"0": "idle", "2": "cancelling", "3": "paused", "4": "paused"}
# GarbageBoxStatus is "installed=<0|1>&status=<n>".
WASTE_BIN_LEVELS = {"0": "empty", "1": "half_full", "2": "full"}
# AbnormalState codes; 2 is not a fault, it is set while a cat is inside.
FAULTS = {
    "0": "none",
    "1": "anti_pinch",
    "2": "cat_inside",
    "6": "motor_blocked",
    "7": "weight_protection",
}
MODES = {0: "auto", 1: "manual", 2: "scheduled"}
# On/off settings written as 0/1 thing properties: key -> property.
SWITCHES = {
    "key_beep": "PromptSoundSwitch",
    "child_lock": "ChildLock",
    "continuous_clean": "ContinuousClean",
    "soft_stool_mode": "SoftStoolMode",
    "voice_announcements": "BroadcastSwitch",
    "microphone": "MicSwitch",
    "video_watermark": "Watermark",
    "camera_sleep": "SleepMode",
}
# The app refuses to change these while a job is running.
IDLE_ONLY_PROPERTIES = {"ContinuousClean", "SoftStoolMode"}
# RunStatus commands, as the app sends them.
RUN_START = "1"  # also resumes a paused job
RUN_CANCEL = "2"
RUN_PAUSE = "3"
JOB_BIZ = {"clean": "1", "empty_litter": "2", "level_litter": "3"}
# Faults for which the app refuses to move the device.
BLOCKING_FAULTS = {"anti_pinch", "motor_blocked", "weight_protection"}
# Clean delay (DelayTimeOfClean, minutes): the app offers 1-30 and refuses
# less than 10 while soft-stool mode is on.
CLEAN_DELAY_MIN = 1
CLEAN_DELAY_MAX = 30
CLEAN_DELAY_MIN_SOFT_STOOL = 10
# Litter leveling level (CatLitterFlatTime, seconds of leveling): levels 1-4
# are written as (level - 1) * 2 + 9, i.e. 9/11/13/15 s.
LEVELING_LEVELS = 4
# Bin-full detection sensitivity (LimitWhenFull): levels 1-4 are written as
# (level - 1) * 5. A higher level allows more cleans before a full bin.
BIN_FULL_LEVELS = 4
# Do not disturb (visualScooper/quietMode; briefInfo quietEnable and
# quietTimes "HH:MM-HH:MM"). Windows run from 10 min to 8 h in 10-minute
# steps, defaulting to 23:00-07:00 when none is set.
QUIET_DEFAULT_TIMES = (datetime.time(23, 0), datetime.time(7, 0))
QUIET_STEP_MINUTES = 10
QUIET_MAX_MINUTES = 8 * 60
QUIET_TIMES_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
# Camera fill light (DayNightMode): 1 always on, 3 on when dark, 2 on while a
# cat uses the box, 0 off. The thing model also allows 4, which the app has
# no label for.
FILL_LIGHT_MODES = {1: "on", 3: "when_dark", 2: "cat_visit", 0: "off"}
# Live video quality (StreamVideoQuality): 2 1080p, 1 720p in the app.
VIDEO_QUALITIES = {2: "1080p", 1: "720p"}
# Camera recording period (CameraOpenDuration, JSON {"type": "<n>",
# "timings": [{"start", "end", "repeat"}]}). Night is 20:00-08:00; custom
# uses the timings. A missing type reads as all day.
CAMERA_SCHEDULES = {"0": "all_day", "1": "off", "2": "daytime", "3": "night", "4": "custom"}
CAMERA_SCHEDULE_CUSTOM = "4"
# Visits in the activity timeline (litterbox/stats/log/timeline/v2): type 99
# records carry the matched cat (petId), weight ("4.8kg") in firstSection,
# time in the box ("68s") in secondSection and the result ("Pee") in
# thirdSection; eventEnd is the epoch second.
VISIT_LOG_TYPE = 99
LB_IN_KG = 0.45359237
# ExtInfo catSatus: 2 a cat on the scale (weihtvalue = its weight then; stays
# 2 after a cat leaves without using the box), 1 inside, 0 visit finished
# (weihtvalue = cat weight, usetime = seconds inside).
CAT_INSIDE = "1"
CAT_VISIT_DONE = "0"
CAT_AT_BOX = "2"
# Scale weight (g) above which a cat is on it; litter residue reads a few
# hundred grams, a cat stepping in at least a kilo.
CAT_ON_SCALE_MIN = 1000
# The box sometimes drops off Aliyun for about a second and comes straight
# back; only report it offline when it stays away.
OFFLINE_DELAY = 60
# After a visit ends, CatLink adds it to the timeline within a short while.
VISIT_LOG_REFRESH_DELAYS = (10, 60)
PUSH_EVENT = "catlink_event"
PICTURE_TIMEOUT = 20
# IntelligentAlarm AlarmType codes. 11003 with bizType 1 is the box's record
# of a visit, sent ~15 s after it ends (HA already fired "visit" from
# ExtInfo); bizType 0 is a cat appearing without a visit. 11007 repeats every
# ~20 s while something moves at the box, startFlag 0 marking the first.
ALARM_VISIT = 11003
ALARM_MOTION = 11007
ALARM_TYPES = {
    11003: "visit_recorded",
    11007: "motion",
    11008: "cleaning",
    11009: "leveling",
}
# Data.action in IntelligentAlarm: 0 start, 2 end.
ALARM_ACTIONS = {0: "started", 2: "finished"}
# Consumable counter resets (CatLink REST, form POST with deviceId).
RESETS = {
    "reset_litter": "token/visualScooper/litter/reset",
    "reset_deodorant": "token/visualScooper/deodorant/reset",
}

def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _translated(entities: dict) -> dict:
    """Name entities through translations/ and take icons from icons.json.

    Each entity's translation key is its key; the "icon" option is dropped
    so icons.json (which can vary the icon with the state) applies.
    """
    return {
        key: {**{k: v for k, v in option.items() if k != "icon"}, "translation_key": key}
        for key, option in entities.items()
    }


def parse_kv(value) -> dict[str, str]:
    """Parse a "key=value&key=value" property string."""
    if not isinstance(value, str) or "=" not in value:
        return {}
    pairs = (item.split("=", 1) for item in value.split("&") if "=" in item)
    return {key.strip(): val.strip() for key, val in pairs}


class ScooperProUltraDevice(LitterDevice):
    """Scooper Pro Ultra device class."""

    def __init__(
        self,
        dat: dict,
        coordinator: "DevicesCoordinator",
        additional_config: AdditionalDeviceConfig | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(dat, coordinator, additional_config)
        self.properties: dict = {}
        self.iot_online: bool | None = None
        self._offline_timer = None
        self._cat_inside: bool | None = None
        # Newest picture the box uploaded (event or timeline), for the camera.
        self.latest_picture: bytes | None = None
        self.latest_picture_time = 0.0
        self._initial_picture_tried = False
        # Today's visits (litterbox/stats/toiletDataNow); None until read.
        self.toilet_today: dict | None = None
        # Latest visit from the activity timeline; kept until a newer one.
        self.last_visit_record: dict | None = None

    async def async_init(self) -> None:
        """Initialize the device and start listening for Aliyun pushes."""
        await super().async_init()
        if self.iot_id:
            self.account.linkvisual.start_push(self.account.hass, self.iot_id, self._on_push)

    @property
    def hass_sensor(self) -> dict:
        """Return the device's sensor entities (translated names and icons)."""
        return _translated(self._hass_sensor)

    @property
    def hass_binary_sensor(self) -> dict:
        """Return the device's binary sensor entities (translated names and icons)."""
        return _translated(self._hass_binary_sensor)

    @property
    def hass_switch(self) -> dict:
        """Return the device's switch entities (translated names and icons)."""
        return _translated(self._hass_switch)

    @property
    def hass_time(self) -> dict:
        """Return the device's time entities (translated names and icons)."""
        return _translated(self._hass_time)

    @property
    def hass_number(self) -> dict:
        """Return the device's number entities (translated names and icons)."""
        return _translated(self._hass_number)

    @property
    def hass_select(self) -> dict:
        """Return the device's select entities (translated names and icons)."""
        return _translated(self._hass_select)

    @property
    def hass_button(self) -> dict:
        """Return the device's button entities (translated names and icons)."""
        return _translated(self._hass_button)

    @property
    def hass_camera(self) -> dict:
        """Return the device's camera entities (translated names and icons)."""
        return _translated(self._hass_camera)

    @property
    def hass_media_player(self) -> dict:
        """Return the device's media players (translated names and icons)."""
        return _translated(self._hass_media_player)

    def _on_push(self, topic: str, payload: dict) -> None:
        """Apply an Aliyun push: properties, online status or a device event."""
        params = payload.get("params")
        if not isinstance(params, dict):
            return
        _LOGGER.debug(
            "Aliyun push for %s on %s: %s",
            self.name,
            topic,
            json.dumps(redact(params.get("items") or params.get("value") or params.get("status")),
                       ensure_ascii=False)[:1000],
        )
        if topic == "/thing/properties":
            self._apply_pushed_properties(params.get("items"))
        elif topic == "/thing/status":
            status = params.get("status")
            value = status.get("value") if isinstance(status, dict) else None
            if value is not None:
                self._set_online(str(value) == "1")
        elif topic == "/thing/events" and params.get("identifier") == "IntelligentAlarm":
            self._fire_alarm_events(params.get("value"))

    def _apply_pushed_properties(self, items) -> None:
        if not isinstance(items, dict) or not items:
            return
        old = dict(self.properties)
        for key, item in items.items():
            self.properties[key] = item.get("value") if isinstance(item, dict) else item
        # A push means the device is talking to Aliyun.
        self._set_online(True, notify=False)
        self._on_properties_changed(old, pushed=set(items))
        self._handle_listeners()

    def _on_properties_changed(self, old: dict, pushed: set | None = None) -> None:
        """React to new property values (from a push or a poll).

        pushed holds the keys of a push; the box repeats a fault warning by
        pushing the same AbnormalState again, so each push of a blocking
        fault fires an event, while polls only fire on a change.
        """
        self._update_cat_inside(old)
        self._fire_fault_event(old, pushed)
        old_ext = parse_kv(old.get("ExtInfo"))
        new_ext = parse_kv(self._prop("ExtInfo"))
        if new_ext.get("catSatus") == CAT_VISIT_DONE and new_ext != old_ext and old:
            weight = _to_int(new_ext.get("weihtvalue"))
            self._fire_event(
                "visit",
                weight=round(weight / 1000, 2) if weight else None,
                duration=_to_int(new_ext.get("usetime")),
            )
            self.account.hass.async_create_task(self._async_refresh_logs_after_visit())

    def _fire_fault_event(self, old: dict, pushed: set | None) -> None:
        if not old:
            return
        code = str(self._prop("AbnormalState")).strip()
        old_code = str(old.get("AbnormalState")).strip()
        fault = FAULTS.get(code, f"code_{code}")
        old_fault = FAULTS.get(old_code, f"code_{old_code}")
        repeated = pushed is not None and "AbnormalState" in pushed
        if fault in BLOCKING_FAULTS and (code != old_code or repeated):
            self._fire_event("fault", action="reported", fault=fault, code=code)
        elif old_fault in BLOCKING_FAULTS and code != old_code:
            self._fire_event("fault", action="cleared", fault=old_fault, code=old_code)

    def _fire_event(self, kind: str, **data) -> None:
        self.account.hass.bus.async_fire(
            PUSH_EVENT,
            {"device_id": self.id, "device_name": self.name, "type": kind, **data},
        )

    async def _async_refresh_logs_after_visit(self) -> None:
        """Re-read the timeline so the last-visit sensors catch up."""
        waited = 0
        for delay in VISIT_LOG_REFRESH_DELAYS:
            await asyncio.sleep(delay - waited)
            waited = delay
            await self.update_logs()

    def _fire_alarm_events(self, value) -> None:
        events = value.get("EventList") if isinstance(value, dict) else None
        for event in events or []:
            if not isinstance(event, dict):
                continue
            try:
                data = json.loads(event.get("Data") or "{}")
            except (TypeError, ValueError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            alarm = _to_int(event.get("AlarmType"))
            if event.get("AlarmPicID"):
                self.account.hass.async_create_task(
                    self._async_fetch_picture(
                        str(event["AlarmPicID"]), _to_int(event.get("EventTime"))
                    )
                )
            payload = {
                "device_id": self.id,
                "device_name": self.name,
                "type": ALARM_TYPES.get(alarm, f"alarm_{alarm}"),
                "alarm_type": alarm,
                "action": ALARM_ACTIONS.get(data.get("action"), data.get("action")),
                "data": data,
            }
            if alarm == ALARM_VISIT and _to_int(data.get("bizType")) == 1:
                weight = _to_int(data.get("weight"))
                payload["weight"] = round(weight / 1000, 2) if weight else None
                payload["duration"] = _to_int(data.get("duration"))
            elif alarm == ALARM_VISIT:
                payload["type"] = "cat_appeared"
                payload["judge_code"] = data.get("judgeCode")
            elif alarm == ALARM_MOTION:
                payload["action"] = "started" if data.get("startFlag") == 0 else "ongoing"
            self.account.hass.bus.async_fire(PUSH_EVENT, payload)

    async def _async_fetch_picture(self, pic_id: str, when_ms: int | None) -> None:
        """Keep the picture the box uploaded for an event, if it is the newest.

        The picture URL is signed and short-lived, so download it right away.
        This never wakes the camera.
        """
        when = when_ms / 1000 if when_ms else time.time()
        if when <= self.latest_picture_time:
            return
        try:
            pictures = await self.account.linkvisual.async_query_pictures(
                self.iot_id, [pic_id]
            )
        except LinkVisualError as exc:
            _LOGGER.debug("Picture lookup for %s failed: %s", self.name, exc)
            return
        picture = pictures.get(pic_id) or {}
        url = picture.get("pictureUrl") or picture.get("thumbUrl")
        if not url:
            return
        try:
            async with asyncio.timeout(PICTURE_TIMEOUT):
                rsp = await self.account.http.get(url)
                if rsp.status != 200:
                    rsp.release()
                    _LOGGER.debug("Picture download for %s: HTTP %s", self.name, rsp.status)
                    return
                image = await rsp.read()
        except (ClientError, TimeoutError) as exc:
            _LOGGER.debug("Picture download for %s failed: %s", self.name, exc)
            return
        if image and when > self.latest_picture_time:
            self.latest_picture = image
            self.latest_picture_time = when
            _LOGGER.debug(
                "Kept picture for %s from %s (%s bytes)",
                self.name,
                datetime.datetime.fromtimestamp(when).isoformat(timespec="seconds"),
                len(image),
            )

    def latest_picture_info(self) -> tuple[bytes | None, float]:
        """Return the newest event picture and when it was taken (epoch s)."""
        return self.latest_picture, self.latest_picture_time

    def _fetch_initial_picture(self, records: list) -> None:
        """After a restart, start from the newest timeline picture (no wake)."""
        if self.latest_picture is not None or self._initial_picture_tried or not self.iot_id:
            return
        for rec in records:
            if not isinstance(rec, dict):
                continue
            pic_id = rec.get("picIdOfNext") or rec.get("picIdOfPre")
            if pic_id:
                self._initial_picture_tried = True
                when = _to_int(rec.get("eventEnd") or rec.get("eventStart"))
                self.account.hass.async_create_task(
                    self._async_fetch_picture(str(pic_id), when * 1000 if when else None)
                )
                return

    @property
    def cat_inside(self) -> bool | None:
        """Return whether a cat is in the box right now.

        On as soon as a cat steps onto the scale (catSatus 2 with at least
        CAT_ON_SCALE_MIN g) or the box confirms it (1); off when the scale
        drops below that, the visit is done (0), or a job runs.
        """
        if self._cat_inside is not None:
            return self._cat_inside
        return self._cat_inside_now()

    def _cat_inside_now(self) -> bool | None:
        """Judge from the current values alone (startup, or no history)."""
        ext = parse_kv(self._prop("ExtInfo"))
        status = ext.get("catSatus")
        if status is None:
            return None
        if self.state not in (None, "idle"):
            return False
        if status == CAT_INSIDE:
            return True
        weight = self._prop_int("DeviceWeihgt")
        return status == CAT_AT_BOX and (weight or 0) >= CAT_ON_SCALE_MIN

    def _update_cat_inside(self, old: dict) -> None:
        """Follow cat_inside through property changes and fire enter/leave events."""
        prev = self._cat_inside
        ext = parse_kv(self._prop("ExtInfo"))
        status = ext.get("catSatus")
        weight = self._prop_int("DeviceWeihgt")
        if prev is None or not old:
            new = self._cat_inside_now()
        elif self.state not in (None, "idle"):
            new = False
        elif ext != parse_kv(old.get("ExtInfo")):
            if status == CAT_INSIDE:
                new = True
            elif status == CAT_VISIT_DONE:
                new = False
            elif status == CAT_AT_BOX:
                entry = _to_int(ext.get("weihtvalue"))
                new = (entry if entry is not None else weight or 0) >= CAT_ON_SCALE_MIN
            else:
                new = prev
        elif weight is not None and weight != _to_int(old.get("DeviceWeihgt")):
            new = prev and weight >= CAT_ON_SCALE_MIN
        else:
            new = prev
        self._cat_inside = new
        if prev is None or new is None or new == prev:
            return
        if new:
            entry = _to_int(ext.get("weihtvalue")) or weight
            self._fire_event("cat_entered", weight=round(entry / 1000, 2) if entry else None)
        else:
            self._fire_event("cat_left")

    def _set_online(self, online: bool, notify: bool = True) -> None:
        """Set the online state; going offline waits OFFLINE_DELAY seconds."""
        if online:
            if self._offline_timer is not None:
                self._offline_timer()
                self._offline_timer = None
            changed = self.iot_online is not True
            self.iot_online = True
        elif self.iot_online is True:
            if self._offline_timer is None:
                self._offline_timer = async_call_later(
                    self.account.hass, OFFLINE_DELAY, self._went_offline
                )
            changed = False
        else:
            changed = self.iot_online is not False
            self.iot_online = False
        if notify and changed:
            self._handle_listeners()

    def _went_offline(self, _now=None) -> None:
        self._offline_timer = None
        self.iot_online = False
        self._handle_listeners()

    @property
    def litter_remaining_days(self) -> int:
        """Return the litter remaining days."""
        try:
            return int(self.detail.get("litterCountdown", 0))
        except Exception as exc:
            _LOGGER.error("Got litter remaining days failed: %s", exc)
            return 0

    @property
    def total_clean_time(self) -> int:
        """Return total clean time from briefInfo when available."""
        try:
            return int(self.detail.get("totalCleanTimes", 0))
        except Exception as exc:
            _LOGGER.error("Get total clean time failed: %s", exc)
            return 0

    @property
    def _hass_sensor(self) -> dict:
        """Return the device sensors."""
        return {
            "last_log": {
                "state_attrs": self.last_log_attrs,
            },
            "litter_remaining_days": {
                "unit": "days",
            },
            "deodorant_countdown": {
                "unit": "days",
            },
            "total_clean_time": {
                "unit": "times",
            },
            "last_visit": {
                "state_attrs": self.last_visit_attrs,
            },
            "last_visit_weight": {
                "class": SensorDeviceClass.WEIGHT,
                "unit": UnitOfMass.KILOGRAMS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "last_visit_duration": {
                "class": SensorDeviceClass.DURATION,
                "unit": UnitOfTime.SECONDS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "visits_today": {
                "unit": "visits",
                "state_class": SensorStateClass.TOTAL_INCREASING,
                "state_attrs": self.visits_today_attrs,
            },
            **self._live_sensors(),
        }

    def _live_sensors(self) -> dict:
        """Return the sensors read from the device's Aliyun properties."""
        if not self.iot_id:
            return {}
        live = {"available": self.live_available}
        diagnostic = {**live, "entity_category": EntityCategory.DIAGNOSTIC}
        return {
            "state": {
                **live,
                "state_attrs": self.state_attrs,
            },
            "litter_level": {
                **live,
                "unit": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "waste_bin": {
                **live,
            },
            "fault": {
                **live,
                "state_attrs": self.fault_attrs,
            },
            "wifi_signal": {
                **diagnostic,
                "unit": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "wifi_rssi": {
                **diagnostic,
                "class": SensorDeviceClass.SIGNAL_STRENGTH,
                "unit": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "wifi_band": {
                **diagnostic,
            },
            "firmware_version": {
                **diagnostic,
            },
            "scale_weight": {
                **diagnostic,
                "class": SensorDeviceClass.WEIGHT,
                "unit": UnitOfMass.GRAMS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        }

    def live_available(self) -> bool:
        """Return whether the property values are current.

        Aliyun keeps serving the last reported values while a device is
        offline, so the entities must hide them.
        """
        return self.iot_online is True and bool(self.properties)

    def _prop(self, key: str):
        return self.properties.get(key)

    def _prop_int(self, key: str) -> int | None:
        try:
            return int(self.properties.get(key))
        except (TypeError, ValueError):
            return None

    @property
    def state(self) -> str | None:
        """Return what the device is doing (from RunStatus)."""
        run = parse_kv(self._prop("RunStatus"))
        status = run.get("runStatus")
        if status is None:
            return None
        if status == "1":
            return RUN_JOBS.get(run.get("biz"), "running")
        return RUN_STATES.get(status, f"code_{status}")

    def state_attrs(self) -> dict:
        """Return the raw run status and ExtInfo."""
        run = parse_kv(self._prop("RunStatus"))
        return {
            "run_status": run.get("runStatus"),
            "job": RUN_JOBS.get(run.get("biz")),
            "ext_info": self._prop("ExtInfo"),
        }

    @property
    def litter_level(self) -> int | None:
        """Return the litter remaining, in percent."""
        return self._prop_int("CatLitterBalance")

    @property
    def waste_bin_installed(self) -> bool | None:
        """Return whether the waste bin is in place."""
        installed = parse_kv(self._prop("GarbageBoxStatus")).get("installed")
        return None if installed is None else installed == "1"

    @property
    def waste_bin(self) -> str | None:
        """Return how full the waste bin is."""
        level = parse_kv(self._prop("GarbageBoxStatus")).get("status")
        if level is None:
            return None
        return WASTE_BIN_LEVELS.get(level, f"code_{level}")

    @property
    def fault(self) -> str | None:
        """Return the device fault (AbnormalState)."""
        code = self._prop("AbnormalState")
        if code is None:
            return None
        code = str(code).strip()
        return FAULTS.get(code, f"code_{code}")

    def fault_attrs(self) -> dict:
        """Return the raw fault code."""
        return {"code": self._prop("AbnormalState")}

    @property
    def mode(self) -> str | None:
        """Return the cleaning mode (CurrentModel)."""
        model = self._prop_int("CurrentModel")
        if model is None:
            return None
        return MODES.get(model, f"code_{model}")

    @property
    def leveling_level(self) -> int | None:
        """Return the litter leveling level (1-4), read the way the app does."""
        seconds = self._prop_int("CatLitterFlatTime")
        if seconds is None:
            return None
        for level, limit in enumerate((9, 11, 13), start=1):
            if seconds <= limit:
                return level
        return LEVELING_LEVELS

    def leveling_attrs(self) -> dict:
        """Return the raw leveling time."""
        return {"leveling_time": self._prop_int("CatLitterFlatTime")}

    @property
    def bin_full_sensitivity(self) -> int | None:
        """Return the bin-full detection sensitivity (1-4), read like the app."""
        value = self._prop_int("LimitWhenFull")
        if value is None:
            return None
        return min(max(value // 5 + 1, 1), BIN_FULL_LEVELS)

    def bin_full_attrs(self) -> dict:
        """Return the raw LimitWhenFull value."""
        return {"limit_when_full": self._prop_int("LimitWhenFull")}

    @property
    def clean_delay(self) -> int | None:
        """Return the minutes the device waits after a visit before cleaning."""
        return self._prop_int("DelayTimeOfClean")

    @property
    def wifi_signal(self) -> int | None:
        """Return the Wi-Fi signal, in percent."""
        return self._prop_int("WifiSignal")

    @property
    def wifi_rssi(self) -> int | None:
        """Return the Wi-Fi RSSI, in dBm."""
        return self._prop_int("WiFiRSSI")

    @property
    def wifi_band(self) -> str | None:
        """Return the Wi-Fi band (2.4G/5G)."""
        return self._prop("Band")

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version."""
        return self._prop("FirmwareVersion")

    @property
    def scale_weight(self) -> int | None:
        """Return the weight on the scale, in g (DeviceWeihgt, sic)."""
        return self._prop_int("DeviceWeihgt")

    @property
    def visits_today(self) -> int | None:
        """Return today's visits to the box, as the app's "today's data" shows them.

        Counts every visit, including ones not matched to a cat.
        """
        if self.toilet_today is None:
            return None
        try:
            return int(float(self.toilet_today.get("totalCount")))
        except (TypeError, ValueError):
            return None

    def visits_today_attrs(self) -> dict:
        """Return today's visits per recognised cat."""
        cats = []
        for item in (self.toilet_today or {}).get("list") or []:
            if not isinstance(item, dict):
                continue
            try:
                visits = int(float(item.get("totalCounts")))
            except (TypeError, ValueError):
                visits = None
            cats.append(
                {"pet_id": item.get("petId"), "name": item.get("petName"), "visits": visits}
            )
        return {"cats": cats}

    def _pet_name(self, pet_id) -> str | None:
        for item in (self.toilet_today or {}).get("list") or []:
            if isinstance(item, dict) and str(item.get("petId")) == str(pet_id):
                return item.get("petName")
        return None

    @property
    def last_visit(self) -> str | None:
        """Return which cat visited last ("unrecognized" if CatLink couldn't tell)."""
        rec = self.last_visit_record
        if not rec:
            return None
        pet_id = str(rec.get("petId") or "0")
        if rec.get("unrecognized") or pet_id == "0":
            return "unrecognized"
        name = self._pet_name(pet_id)
        if name:
            return name
        event = str(rec.get("event") or "")
        return event.removesuffix(" visited").strip() or pet_id

    @property
    def last_visit_weight(self) -> float | None:
        """Return the weight of the cat at its last visit, in kg."""
        rec = self.last_visit_record or {}
        match = re.match(r"^\s*([\d.]+)\s*(kg|lbs?)?\s*$", str(rec.get("firstSection") or ""), re.I)
        if not match:
            return None
        try:
            weight = float(match.group(1))
        except ValueError:
            return None
        if (match.group(2) or "kg").lower().startswith("lb"):
            weight *= LB_IN_KG
        return round(weight, 2)

    @property
    def last_visit_duration(self) -> int | None:
        """Return how long the last visit lasted, in seconds."""
        text = str((self.last_visit_record or {}).get("secondSection") or "")
        parts = re.findall(r"(\d+)\s*(h|min|m|s)", text, re.I)
        if not parts or re.sub(r"[\d\s]|h|min|m|s", "", text, flags=re.I):
            return None
        factor = {"h": 3600, "min": 60, "m": 60, "s": 1}
        return sum(int(n) * factor[unit.lower()] for n, unit in parts)

    def last_visit_attrs(self) -> dict:
        """Return the details of the last visit."""
        rec = self.last_visit_record or {}
        # eventEnd matches the time the app shows; eventStart is earlier (the
        # camera clip's start).
        when = None
        try:
            when = datetime.datetime.fromtimestamp(
                int(rec.get("eventEnd") or rec.get("eventStart")), tz=datetime.UTC
            ).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            pass
        return {
            "pet_id": rec.get("petId"),
            "weight": self.last_visit_weight,
            "duration": self.last_visit_duration,
            "result": rec.get("thirdSection"),
            "time": when,
            "event": rec.get("event"),
        }

    def _update_last_visit(self, records: list) -> None:
        for rec in records:
            if not isinstance(rec, dict):
                continue
            if str(rec.get("type")) == str(VISIT_LOG_TYPE):
                self.last_visit_record = rec
                return

    @property
    def iot_id(self) -> str | None:
        """Return the Aliyun IoT id used for camera streaming."""
        return self.data.get("iotId") or self.detail.get("iotId")

    @property
    def online(self) -> bool | None:
        """Return whether the device is connected (Aliyun thing status)."""
        return self.iot_online

    @property
    def _hass_binary_sensor(self) -> dict:
        """Return the device binary sensors."""
        if not self.iot_id:
            return {}
        return {
            "online": {
                "class": BinarySensorDeviceClass.CONNECTIVITY,
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            "waste_bin_installed": {
                "available": self.live_available,
            },
            "cat_inside": {
                "class": BinarySensorDeviceClass.OCCUPANCY,
                "available": self.live_available,
            },
        }

    @property
    def _hass_switch(self) -> dict:
        """Return the device switches (written as Aliyun thing properties)."""
        if not self.iot_id:
            return {}
        switches = {
            key: {
                "available": self.live_available,
                "is_on": partial(self.property_flag, prop),
                "async_turn_on": partial(self.async_set_property, prop, 1),
                "async_turn_off": partial(self.async_set_property, prop, 0),
            }
            for key, prop in SWITCHES.items()
        }
        switches["do_not_disturb"] = {
            "available": self.live_available,
            "is_on": self.do_not_disturb_on,
            "async_turn_on": partial(self.async_set_quiet_mode, enable=True),
            "async_turn_off": partial(self.async_set_quiet_mode, enable=False),
            "state_attrs": self.do_not_disturb_attrs,
        }
        switches["indicator_light"] = {
            "available": self.live_available,
            "is_on": self.indicator_light_on,
            "async_turn_on": partial(self.async_set_property, "IndicatorLight", 1),
            "async_turn_off": partial(self.async_set_property, "IndicatorLight", 0),
        }
        return switches

    def do_not_disturb_on(self) -> bool | None:
        """Return whether do-not-disturb is enabled (briefInfo quietEnable)."""
        enabled = self.detail.get("quietEnable")
        return None if enabled is None else bool(enabled)

    def do_not_disturb_attrs(self) -> dict:
        """Return the raw do-not-disturb window."""
        return {"times": self.detail.get("quietTimes")}

    def _quiet_times(self) -> tuple[datetime.time, datetime.time] | None:
        match = QUIET_TIMES_RE.match(str(self.detail.get("quietTimes") or ""))
        if not match:
            return None
        try:
            h1, m1, h2, m2 = (int(g) for g in match.groups())
            return datetime.time(h1, m1), datetime.time(h2, m2)
        except ValueError:
            return None

    @property
    def do_not_disturb_start(self) -> datetime.time | None:
        """Return when do-not-disturb starts."""
        times = self._quiet_times()
        return times[0] if times else None

    @property
    def do_not_disturb_end(self) -> datetime.time | None:
        """Return when do-not-disturb ends."""
        times = self._quiet_times()
        return times[1] if times else None

    @property
    def _hass_time(self) -> dict:
        """Return the device times (do-not-disturb window)."""
        if not self.iot_id:
            return {}
        return {
            "do_not_disturb_start": {
                "available": self.live_available,
                "async_set_value": partial(self._async_set_quiet_time, "start"),
            },
            "do_not_disturb_end": {
                "available": self.live_available,
                "async_set_value": partial(self._async_set_quiet_time, "end"),
            },
        }

    async def _async_set_quiet_time(self, which: str, value: datetime.time, **kwargs) -> bool:
        return await self.async_set_quiet_mode(**{which: value})

    async def async_set_quiet_mode(
        self,
        enable: bool | None = None,
        start: datetime.time | None = None,
        end: datetime.time | None = None,
        **kwargs,
    ) -> bool:
        """Change do-not-disturb; what isn't given keeps its current value."""
        current = self._quiet_times() or QUIET_DEFAULT_TIMES
        start = start or current[0]
        end = end or current[1]
        if enable is None:
            enable = bool(self.detail.get("quietEnable"))
        for value in (start, end):
            if value.minute % QUIET_STEP_MINUTES or value.second:
                raise HomeAssistantError(
                    f"Do-not-disturb times must be in {QUIET_STEP_MINUTES}-minute steps"
                )
        window = (end.hour * 60 + end.minute - start.hour * 60 - start.minute) % (24 * 60)
        if not QUIET_STEP_MINUTES <= window <= QUIET_MAX_MINUTES:
            raise HomeAssistantError(
                f"Do-not-disturb can last {QUIET_STEP_MINUTES} minutes to "
                f"{QUIET_MAX_MINUTES // 60} hours ({start:%H:%M}-{end:%H:%M} is not); "
                "change the other end first"
            )
        times = f"{start:%H:%M}-{end:%H:%M}"
        rdt = await self.account.request(
            "token/visualScooper/quietMode",
            {"deviceId": self.id, "enable": "true" if enable else "false", "times": times},
            "POST",
        )
        _LOGGER.debug("Do not disturb on %s (%s, %s): %s", self.name, enable, times, rdt)
        if rdt.get("returnCode", 0):
            err = format_api_error(rdt)
            _LOGGER.error("Setting do not disturb on %s failed: %s", self.name, err)
            self._set_action_error(err)
            return False
        self.detail["quietEnable"] = enable
        self.detail["quietTimes"] = times
        self._action_error = None
        self._handle_listeners()
        return True

    def indicator_light_on(self) -> bool | None:
        """Return whether the panel's indicator light is on (any non-zero value)."""
        value = self._prop_int("IndicatorLight")
        return None if value is None else value != 0

    @property
    def _hass_number(self) -> dict:
        """Return the device numbers (written as Aliyun thing properties)."""
        if not self.iot_id:
            return {}
        return {
            "clean_delay": {
                "unit": UnitOfTime.MINUTES,
                "min": CLEAN_DELAY_MIN,
                "max": CLEAN_DELAY_MAX,
                "step": 1,
                "available": self.live_available,
                "async_set_value": self.async_set_clean_delay,
            },
            "leveling_level": {
                "min": 1,
                "max": LEVELING_LEVELS,
                "step": 1,
                "available": self.live_available,
                "state_attrs": self.leveling_attrs,
                "async_set_value": self.async_set_leveling_level,
            },
            "bin_full_sensitivity": {
                "min": 1,
                "max": BIN_FULL_LEVELS,
                "step": 1,
                "available": self.live_available,
                "state_attrs": self.bin_full_attrs,
                "async_set_value": self.async_set_bin_full_sensitivity,
            },
        }

    async def async_set_leveling_level(self, value: float, **kwargs) -> bool:
        """Set the litter leveling level; like the app, allowed while a job runs."""
        level = int(value)
        if not 1 <= level <= LEVELING_LEVELS:
            raise HomeAssistantError(f"Leveling level must be 1-{LEVELING_LEVELS}")
        return await self.async_set_property("CatLitterFlatTime", (level - 1) * 2 + 9)

    async def async_set_bin_full_sensitivity(self, value: float, **kwargs) -> bool:
        """Set the bin-full detection sensitivity; like the app, allowed while a job runs."""
        level = int(value)
        if not 1 <= level <= BIN_FULL_LEVELS:
            raise HomeAssistantError(f"Bin-full sensitivity must be 1-{BIN_FULL_LEVELS}")
        return await self.async_set_property("LimitWhenFull", (level - 1) * 5)

    async def async_set_clean_delay(self, value: float, **kwargs) -> bool:
        """Set the clean delay, with the same limits as the app."""
        minutes = int(value)
        if not CLEAN_DELAY_MIN <= minutes <= CLEAN_DELAY_MAX:
            raise HomeAssistantError(
                f"Clean delay must be {CLEAN_DELAY_MIN}-{CLEAN_DELAY_MAX} minutes"
            )
        if self.property_flag("SoftStoolMode") and minutes < CLEAN_DELAY_MIN_SOFT_STOOL:
            raise HomeAssistantError(
                f"{self.name}: with soft-stool mode on, the clean delay must be at "
                f"least {CLEAN_DELAY_MIN_SOFT_STOOL} minutes"
            )
        return await self.async_set_property("DelayTimeOfClean", minutes)

    def property_flag(self, key: str) -> bool | None:
        """Return a 0/1 thing property as a bool."""
        value = self._prop_int(key)
        return None if value is None else value == 1

    async def async_set_property(self, key: str, value, **kwargs) -> bool:
        """Write one thing property; the next poll confirms what the device applied."""
        if key in IDLE_ONLY_PROPERTIES and self.state not in (None, "idle"):
            raise HomeAssistantError(
                f"{self.name} is {self.state}; this setting can only be changed while idle"
            )
        try:
            await self.account.linkvisual.async_set_properties(self.iot_id, {key: value})
        except LinkVisualError as exc:
            _LOGGER.error("Setting %s on %s failed: %s", key, self.name, exc)
            self._set_action_error(str(exc))
            return False
        self.properties[key] = value
        self._action_error = None
        self._handle_listeners()
        return True

    @property
    def _hass_select(self) -> dict:
        """Return the device selects."""
        if not self.iot_id:
            return {}
        return {
            "mode": {
                "options": list(MODES.values()),
                "available": self.live_available,
                "async_select": self.async_select_mode,
            },
            "camera_schedule": {
                "options": list(CAMERA_SCHEDULES.values()),
                "available": self.live_available,
                "state_attrs": self.camera_schedule_attrs,
                "async_select": self.async_select_camera_schedule,
            },
            "fill_light": {
                "options": list(FILL_LIGHT_MODES.values()),
                "available": self.live_available,
                "async_select": partial(
                    self._async_select_prop, "DayNightMode", FILL_LIGHT_MODES
                ),
            },
            "video_quality": {
                "options": list(VIDEO_QUALITIES.values()),
                "available": self.live_available,
                "async_select": partial(
                    self._async_select_prop, "StreamVideoQuality", VIDEO_QUALITIES
                ),
            },
        }

    def _prop_choice(self, key: str, choices: dict) -> str | None:
        value = self._prop_int(key)
        if value is None:
            return None
        return choices.get(value, f"code_{value}")

    async def _async_select_prop(
        self, key: str, choices: dict, option: str, **kwargs
    ) -> bool:
        value = next((k for k, v in choices.items() if v == option), None)
        if value is None:
            raise HomeAssistantError(f"Unknown option: {option}")
        return await self.async_set_property(key, value)

    @property
    def fill_light(self) -> str | None:
        """Return when the camera's fill light comes on (DayNightMode)."""
        return self._prop_choice("DayNightMode", FILL_LIGHT_MODES)

    @property
    def video_quality(self) -> str | None:
        """Return the live video quality (StreamVideoQuality)."""
        return self._prop_choice("StreamVideoQuality", VIDEO_QUALITIES)

    def _camera_open_duration(self) -> dict | None:
        value = self._prop("CameraOpenDuration")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return None
        return value if isinstance(value, dict) else None

    @property
    def camera_schedule(self) -> str | None:
        """Return when the camera records (the app's recording period)."""
        duration = self._camera_open_duration()
        if duration is None:
            return None
        kind = duration.get("type")
        kind = "0" if kind in (None, "") else str(kind)
        return CAMERA_SCHEDULES.get(kind, f"code_{kind}")

    def camera_schedule_attrs(self) -> dict:
        """Return the custom recording periods."""
        return {"timings": (self._camera_open_duration() or {}).get("timings") or []}

    async def async_select_camera_schedule(self, option: str, **kwargs) -> bool:
        """Change the recording period, keeping the custom periods as the app does."""
        kind = next((k for k, v in CAMERA_SCHEDULES.items() if v == option), None)
        if kind is None:
            raise HomeAssistantError(f"Unknown camera schedule: {option}")
        timings = (self._camera_open_duration() or {}).get("timings") or []
        if kind == CAMERA_SCHEDULE_CUSTOM and not timings:
            raise HomeAssistantError(
                f"{self.name} has no custom recording periods; add them in the CatLink app"
            )
        # Written like the app's Gson output.
        value = json.dumps({"timings": timings, "type": kind}, separators=(",", ":"))
        return await self.async_set_property("CameraOpenDuration", value)

    @property
    def _hass_button(self) -> dict:
        """Return the device action buttons."""
        if not self.iot_id:
            return {}
        buttons = {
            key: {
                "available": self.live_available,
                "async_press": partial(self.async_start_job, key),
            }
            for key in JOB_BIZ
        }
        for key, fun in [
            ("pause", self.async_pause),
            ("resume", self.async_resume),
            ("cancel", self.async_cancel),
        ]:
            buttons[key] = {
                "available": self.live_available,
                "async_press": fun,
            }
        # Server-side counters, so they work while the box is offline.
        for key in RESETS:
            buttons[key] = {"async_press": partial(self.async_reset_counter, key)}
        buttons["reboot"] = {
            "class": ButtonDeviceClass.RESTART,
            "available": self.live_available,
            "entity_category": EntityCategory.DIAGNOSTIC,
            "async_press": self.async_reboot,
        }
        return buttons

    async def async_reboot(self, **kwargs) -> bool:
        """Restart the device (Aliyun thing service "Reboot"); refused during a job."""
        if self.state not in (None, "idle"):
            raise HomeAssistantError(f"{self.name} is {self.state}; reboot it while idle")
        try:
            await self.account.linkvisual.async_invoke_service(self.iot_id, "Reboot")
        except LinkVisualError as exc:
            _LOGGER.error("Rebooting %s failed: %s", self.name, exc)
            self._set_action_error(str(exc))
            return False
        self._action_error = None
        return True

    async def async_reset_counter(self, key: str, **kwargs) -> bool:
        """Reset the litter or deodorant countdown after replacing it."""
        api = RESETS[key]
        rdt = await self.account.request(api, {"deviceId": self.id}, "POST")
        _LOGGER.debug("%s on %s: %s", key, self.name, rdt)
        if rdt.get("returnCode", 0):
            err = format_api_error(rdt)
            _LOGGER.error("%s on %s failed: %s", key, self.name, err)
            self._set_action_error(err)
            return False
        # Like the app, read briefInfo again to show the new countdowns.
        await self.update_device_detail()
        return True

    def _check_can_move(self) -> None:
        """Refuse to move the device where the app refuses (or asks first)."""
        if self.fault in BLOCKING_FAULTS:
            raise HomeAssistantError(f"{self.name} reports a fault: {self.fault}")
        if self.waste_bin_installed is False:
            raise HomeAssistantError(f"{self.name}: the waste bin is not installed")
        if self.waste_bin == "full":
            raise HomeAssistantError(f"{self.name}: the waste bin is full")

    def _run_parts(self) -> tuple[str | None, str | None]:
        run = parse_kv(self._prop("RunStatus"))
        return run.get("runStatus"), run.get("biz")

    async def _async_send_run(self, status: str, biz: str) -> bool:
        return await self.async_set_property("RunStatus", f"runStatus={status}&biz={biz}")

    async def async_start_job(self, job: str, **kwargs) -> bool:
        """Start cleaning, emptying or leveling the litter."""
        if self.state != "idle":
            raise HomeAssistantError(f"{self.name} is {self.state}, not idle")
        self._check_can_move()
        return await self._async_send_run(RUN_START, JOB_BIZ[job])

    async def async_pause(self, **kwargs) -> bool:
        """Pause the running job."""
        status, biz = self._run_parts()
        if status != RUN_START:
            raise HomeAssistantError(f"{self.name} is {self.state}; nothing to pause")
        return await self._async_send_run(RUN_PAUSE, biz)

    async def async_resume(self, **kwargs) -> bool:
        """Resume a paused job."""
        _, biz = self._run_parts()
        if self.state != "paused":
            raise HomeAssistantError(f"{self.name} is {self.state}; nothing to resume")
        self._check_can_move()
        return await self._async_send_run(RUN_START, biz)

    async def async_cancel(self, **kwargs) -> bool:
        """Cancel the running or paused job."""
        status, biz = self._run_parts()
        if status != RUN_START and self.state != "paused":
            raise HomeAssistantError(f"{self.name} is {self.state}; nothing to cancel")
        self._check_can_move()
        return await self._async_send_run(RUN_CANCEL, biz)

    async def async_select_mode(self, mode: str, **kwargs) -> bool:
        """Switch between auto, manual and scheduled cleaning (CatLink REST)."""
        model = next((k for k, v in MODES.items() if v == mode), None)
        if model is None:
            raise HomeAssistantError(f"Unknown mode: {mode}")
        if self.state != "idle":
            raise HomeAssistantError(f"{self.name} is {self.state}; change the mode while idle")
        rdt = await self.account.request(
            "token/visualScooper/changeMode",
            {"deviceId": self.id, "workModel": str(model)},
            "POST",
        )
        _LOGGER.debug("Change mode of %s to %s: %s", self.name, mode, rdt)
        if rdt.get("returnCode", 0):
            err = format_api_error(rdt)
            _LOGGER.error("Changing mode of %s failed: %s", self.name, err)
            self._set_action_error(err)
            return False
        self.properties["CurrentModel"] = model
        self._action_error = None
        self._handle_listeners()
        return True

    @property
    def _hass_camera(self) -> dict:
        """Return the device cameras."""
        if not self.iot_id:
            return {}
        return {
            "camera": {
                "stream_source": self.async_get_stream_url,
                "still_image": self.latest_picture_info,
            },
        }

    @property
    def _hass_media_player(self) -> dict:
        """Return the box's speaker (the app's talk-back channel)."""
        if not self.iot_id:
            return {}
        return {
            "speaker": {
                "class": MediaPlayerDeviceClass.SPEAKER,
                "available": self.live_available,
                "async_play_stream": self.async_play_alaw_stream,
                "live_talk": self.live_talk_session,
            },
        }

    async def async_play_alaw_stream(self, frames, on_started=None) -> None:
        """Play G.711 A-law 8 kHz mono audio through the box's speaker.

        One talk session at a time: it opens here and ends when the playback
        does. `on_started` fires once the speaker is open.
        """
        await async_play_alaw(
            self.account.linkvisual,
            self.iot_id,
            frames,
            name=self.name,
            on_started=on_started,
        )

    def live_talk_session(self, **kwargs) -> LiveTalkSession:
        """Build a live talk session for this box (used by the websocket API)."""
        return LiveTalkSession(
            self.account.linkvisual, self.iot_id, name=self.name, **kwargs
        )

    async def async_get_stream_url(self) -> str:
        """Return a fresh live stream URL; it expires about a minute after issue."""
        return await self.account.linkvisual.async_get_live_url(self.iot_id)

    async def update_device_detail(self) -> dict:
        """Update device detail from visualScooper briefInfo."""
        api = "token/visualScooper/briefInfo"
        pms = {"deviceId": self.id}
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            data = rsp.get("data", {})
            raw = data.get("deviceInfo")
            parsed = parse_response(data, "deviceInfo", LitterDeviceInfo, {})
            rdt = (
                parsed.model_dump(by_alias=True)
                if hasattr(parsed, "model_dump")
                else (parsed or {})
            )
            if not rdt and raw:
                # briefInfo sends null for some string fields (currentMessage,
                # quietTimes), which fails model validation.
                rdt = raw
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error("Got device detail for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device detail for %s failed: %s", self.name, rsp)
        self.detail = rdt
        await self.update_online()
        await self.update_properties()
        await self.update_toilet_today()
        self._action_error = None
        self._handle_listeners()
        return rdt

    async def update_online(self) -> bool | None:
        """Update whether the device is connected.

        On failure the last known value is kept and a warning is logged.
        """
        if not self.iot_id:
            return self.iot_online
        try:
            self._set_online(
                await self.account.linkvisual.async_is_online(self.iot_id), notify=False
            )
        except LinkVisualError as exc:
            _LOGGER.warning("Got online status for %s failed: %s", self.name, exc)
        return self.iot_online

    async def update_properties(self) -> dict:
        """Update the Aliyun thing properties (live state and settings).

        On failure the last known values are kept and a warning is logged.
        """
        if not self.iot_id:
            return self.properties
        try:
            props = await self.account.linkvisual.async_get_properties(self.iot_id)
        except LinkVisualError as exc:
            _LOGGER.warning("Got properties for %s failed: %s", self.name, exc)
            return self.properties
        _LOGGER.debug("Properties for %s: %s", self.name, sorted(props))
        old = self.properties
        self.properties = props
        self._on_properties_changed(old)
        return props

    async def update_toilet_today(self) -> dict | None:
        """Update today's visit counts (CatLink REST, as the app's detail screen).

        On failure the last values are kept and a warning is logged.
        """
        rsp = await self.account.request(
            "token/litterbox/stats/toiletDataNow", {"deviceId": self.id}
        )
        data = rsp.get("data")
        if rsp.get("returnCode", 0) or not isinstance(data, dict):
            _LOGGER.warning("Got today's visits for %s failed: %s", self.name, rsp)
            return self.toilet_today
        self.toilet_today = data
        return data

    async def update_logs(self) -> list:
        """Update device logs using timeline/v2 endpoint."""
        api = "token/litterbox/stats/log/timeline/v2"
        today = datetime.date.today().isoformat()
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
            data = rsp.get("data", {})
            parsed = parse_response(data, "records", LogEntry, [])
            if isinstance(parsed, list) and parsed and hasattr(parsed[0], "model_dump"):
                rdt = [p.model_dump() for p in parsed]
            elif isinstance(parsed, list):
                rdt = parsed
            else:
                rdt = data.get("records") or []
        except (TypeError, ValueError) as exc:
            rdt = []
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        # Newest first; today's only, so the last visit is kept across midnight.
        self._update_last_visit(rdt)
        self._fetch_initial_picture(rdt)
        self._handle_listeners()
        return rdt
