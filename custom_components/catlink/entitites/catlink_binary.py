"""The component."""

from homeassistant.const import STATE_OFF, STATE_ON

from ..modules.device import Device
from .catlink import CatlinkEntity


class CatlinkBinaryEntity(CatlinkEntity): # pragma: no cover
    """CatlinkBinaryEntity."""

    def __init__(self, name, device: Device, option=None) -> None:
        """Initialize the entity."""
        super().__init__(name, device, option)
        self._attr_is_on = False

    def update(self) -> None:
        """Update the entity."""
        super().update()
        if hasattr(self._device, self._name):
            self._attr_is_on = bool(getattr(self._device, self._name))
        else:
            self._attr_is_on = False

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return STATE_ON if self._attr_is_on else STATE_OFF
