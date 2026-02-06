"""Button entity for CatLink integration."""

from homeassistant.components.button import ButtonEntity

from .base import CatlinkEntity


class CatlinkButtonEntity(CatlinkEntity, ButtonEntity):
    """Button entity for CatLink."""

    async def async_press(self):
        """Press the button."""
        ret = False
        fun = self._option.get("async_press")
        if callable(fun):
            ret = await fun()
        return ret
