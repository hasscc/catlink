"""Button entity for CatLink integration."""

from homeassistant.components.button import ENTITY_ID_FORMAT, ButtonEntity

from .base import CatlinkEntity


class CatlinkButtonEntity(CatlinkEntity, ButtonEntity):
    """Button entity for CatLink."""

    _entity_id_format = ENTITY_ID_FORMAT

    async def async_press(self):
        """Press the button."""
        ret = False
        fun = self._option.get("async_press")
        if callable(fun):
            ret = await fun()
        return ret
