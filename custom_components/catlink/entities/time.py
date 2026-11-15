"""Time entities for CatLink integration."""

from datetime import time

from homeassistant.components.time import ENTITY_ID_FORMAT, TimeEntity

from ..devices.base import Device
from .base import CatlinkEntity


class CatlinkTimeEntity(CatlinkEntity, TimeEntity):
    """Time entity for CatLink.

    The value is the device attribute named like the entity (a
    datetime.time or None). Changes go through the "async_set_value"
    option, as on numbers; without it the entity is read-only.
    """

    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(self, name, device: Device, option=None) -> None:
        """Initialize the entity."""
        super().__init__(name, device, option)
        self._attr_native_value = None

    def update(self) -> None:
        """Update the entity."""
        super().update()
        value = getattr(self, "_attr_state", None)
        self._attr_native_value = value if isinstance(value, time) else None

    @property
    def state(self) -> str | None:
        """Return the time as HA formats it (HH:MM:SS)."""
        return TimeEntity.state.fget(self)

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        fun = self._option.get("async_set_value")
        if not callable(fun):
            raise NotImplementedError(f"{self.entity_id} is read-only")
        ret = await fun(value, entity=self)
        await self._async_after_action(bool(ret), self._option.get("delay_update"))
