"""Support for button."""

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN, ButtonEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entitites import CatlinkEntity
from .helpers import Helper


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Catlink buttons from a config entry."""
    cfg = {**config_entry.data, **config_entry.options}
    await async_setup_platform(hass, cfg, async_add_entities)


async def async_setup_platform(
        hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Catlink switch platform."""
    hass.data[DOMAIN]["add_entities"][ENTITY_DOMAIN] = async_add_entities
    await Helper.async_setup_accounts(hass, ENTITY_DOMAIN)


class CatlinkButtonEntity(CatlinkEntity, ButtonEntity):

    async def async_press(self):
        """Press the button."""
        ret = False
        fun = self._option.get('async_press')
        if callable(fun):
            ret = await fun()
        return ret
