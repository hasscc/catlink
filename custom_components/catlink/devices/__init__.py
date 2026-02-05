"""Device classes for CatLink integration."""

from .base import Device
from .feeder import FeederDevice
from .litterbox import LitterBox
from .scooper import ScooperDevice

__all__ = [
    "Device",
    "FeederDevice",
    "LitterBox",
    "ScooperDevice",
]
