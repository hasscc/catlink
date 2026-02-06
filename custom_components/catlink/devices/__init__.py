"""Device classes for CatLink integration."""

from .base import Device
from .cat import CatDevice
from .feeder import FeederDevice
from .litterbox import LitterBox
from .scooper import ScooperDevice
from .scooper_pro_ultra import ScooperProUltraDevice

__all__ = [
    "CatDevice",
    "Device",
    "FeederDevice",
    "LitterBox",
    "ScooperDevice",
    "ScooperProUltraDevice",
]
