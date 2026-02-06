"""Device registry for CatLink integration."""

from typing import TYPE_CHECKING

from .base import Device
from .cat import CatDevice
from .c08 import C08Device
from .feeder import FeederDevice
from .litterbox import LitterBox
from .scooper import ScooperDevice
from .scooper_pro_ultra import ScooperProUltraDevice

if TYPE_CHECKING:
    from ..models.additional_cfg import AdditionalDeviceConfig
    from ..modules.devices_coordinator import DevicesCoordinator

DEVICE_TYPES: dict[str, type[Device]] = {
    "CAT": CatDevice,
    "C08": C08Device,
    "SCOOPER": ScooperDevice,
    "LITTER_BOX_599": LitterBox,  # SCOOPER C1
    "VISUAL_PRO_ULTRA": ScooperProUltraDevice,
    "FEEDER": FeederDevice,
}


def create_device(
    dat: dict,
    coordinator: "DevicesCoordinator",
    additional_config: "AdditionalDeviceConfig | None" = None,
) -> Device:
    """Create a device instance from API data."""
    typ = dat.get("deviceType")
    device_cls = DEVICE_TYPES.get(typ, Device)
    return device_cls(dat, coordinator, additional_config)
