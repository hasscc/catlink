"""Device API models."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class DeviceListItem(BaseModel):
    """Device list item from API."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    mac: str = ""
    model: str = ""
    deviceType: str = ""
    deviceName: str = ""
    currentErrorMessage: str = ""


class DeviceInfoBase(BaseModel):
    """Common device detail fields."""

    model_config = ConfigDict(extra="allow")

    workStatus: str = ""
    alarmStatus: str = ""
    workModel: str = ""
    temperature: str = ""
    humidity: str = ""
    weight: Any = None
    keyLock: str = ""
    safeTime: str = ""
    catLitterPaveSecond: str = ""
    catLitterWeight: float = 0.0
    inductionTimes: Any = 0
    manualTimes: Any = 0
    deodorantCountdown: int = 0
    litterCountdown: Any = None
    online: bool = False
    firmwareVersion: str = ""
    lastHeartBeatTimestamp: Any = None


class LitterDeviceInfo(DeviceInfoBase):
    """Litter device (LitterBox, Scooper) specific fields."""

    model_config = ConfigDict(extra="allow")

    deviceErrorList: list[dict[str, Any]] = []
    boxFullSensitivity: Any = ""
    quietTimes: str = ""
    garbageStatus: str = ""
    currentError: str = ""
    currentMessage: str = ""


class C08DeviceInfo(LitterDeviceInfo):
    """C08 device specific fields."""

    model_config = ConfigDict(extra="allow")

    autoUpdatePetWeight: bool | None = None
    indicatorLight: str = ""
    paneltone: str = ""
    autoBurial: bool | None = None
    continuousCleaning: bool | None = None
    litterType: int | str | None = None
    kittenModel: bool | None = None


class FeederDeviceInfo(DeviceInfoBase):
    """Feeder device specific fields."""

    model_config = ConfigDict(extra="allow")

    foodOutStatus: str = ""
    autoFillStatus: str = ""
    indicatorLightStatus: str = ""
    breathLightStatus: str = ""
    powerSupplyStatus: str = ""
    keyLockStatus: str = ""
    currentErrorMessage: str = ""
    currentErrorType: str = ""
    error: str = ""
