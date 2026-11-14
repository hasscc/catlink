"""Number entities for CatLink integration."""

from homeassistant.components.number import NumberEntity, NumberMode

from ..devices.base import Device
from .base import CatlinkEntity


class CatlinkNumberEntity(CatlinkEntity, NumberEntity):
    """Number entity for CatLink."""

    def __init__(self, name, device: Device, option=None) -> None:
        """Initialize the entity."""
        super().__init__(name, device, option)
        self._attr_native_min_value = self._option.get("min", 0)
        self._attr_native_max_value = self._option.get("max", 100)
        self._attr_native_step = self._option.get("step", 1)
        self._attr_mode = self._option.get("mode", NumberMode.AUTO)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value.

        With an "async_set_value" option the value is sent through it (like
        "async_select" on selects); otherwise it's only stored on the device.
        """
        fun = self._option.get("async_set_value")
        if callable(fun):
            ret = await fun(value, entity=self)
            await self._async_after_action(bool(ret), self._option.get("delay_update"))
            return
        if hasattr(self._device, self._name):
            setattr(self._device, self._name, int(value))
            self.async_write_ha_state()
