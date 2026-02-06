"""Device classes for CatLink integration."""

from .base import Device
from .c08 import C08Device
from .feeder import FeederDevice
from .litterbox import LitterBox
from .scooper import ScooperDevice
from .scooper_pro_ultra import ScooperProUltraDevice

__all__ = [
    "Device",
    "C08Device",
    "FeederDevice",
    "LitterBox",
    "ScooperDevice",
    "ScooperProUltraDevice",
]
