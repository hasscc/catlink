"""Button entity for CatLink integration."""

from homeassistant.components.button import ButtonEntity

from .base import CatlinkEntity


class CatlinkButtonEntity(CatlinkEntity, ButtonEntity):
    """Button entity for CatLink."""

    _entity_id_domain = "button"

    async def async_press(self):
        """Press the button."""
        ret = False
        fun = self._option.get("async_press")
        if callable(fun):
            ret = await fun()
        return ret
