"""Support for button."""

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN, ButtonEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entitites import CatlinkEntity
from .helpers import Helper

async_setup_entry = Helper.async_setup_entry


async def async_setup_platform(
        hass: HomeAssistant, config, async_add_entities, discovery_info=None
): # pragma: no cover
    """Set up the Catlink switch platform."""
    hass.data[DOMAIN]["add_entities"][ENTITY_DOMAIN] = async_add_entities
    await Helper.async_setup_accounts(hass, ENTITY_DOMAIN)


class CatlinkButtonEntity(CatlinkEntity, ButtonEntity):

    async def async_press(self): # pragma: no cover
        """Press the button."""
        ret = False
        fun = self._option.get('async_press')
        if callable(fun):
            ret = await fun()
        return ret
