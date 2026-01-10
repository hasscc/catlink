"""API models for CatLink integration."""

from .base import ApiResponse
from .device import DeviceInfoBase, DeviceListItem, FeederDeviceInfo, LitterDeviceInfo
from .logs import LogEntry

__all__ = [
    "ApiResponse",
    "DeviceInfoBase",
    "DeviceListItem",
    "FeederDeviceInfo",
    "LitterDeviceInfo",
    "LogEntry",
]
