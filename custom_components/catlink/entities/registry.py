"""Entity registry for CatLink integration."""

from .binary import CatlinkBinarySensorEntity
from .button import CatlinkButtonEntity
from .camera import CatlinkCameraEntity
from .number import CatlinkNumberEntity
from .select import CatlinkSelectEntity
from .sensor import CatlinkSensorEntity
from .switch import CatlinkSwitchEntity

DOMAIN_ENTITY_CLASSES: dict[str, type] = {
    "sensor": CatlinkSensorEntity,
    "binary_sensor": CatlinkBinarySensorEntity,
    "switch": CatlinkSwitchEntity,
    "select": CatlinkSelectEntity,
    "button": CatlinkButtonEntity,
    "camera": CatlinkCameraEntity,
    "number": CatlinkNumberEntity,
}
