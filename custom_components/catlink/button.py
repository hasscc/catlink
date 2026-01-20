"""Support for button."""

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entities import CatlinkButtonEntity
from .helpers import Helper, async_setup_domain_platform

async_setup_entry = Helper.async_setup_entry_for(ENTITY_DOMAIN)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Catlink button platform."""
    await async_setup_domain_platform(hass, ENTITY_DOMAIN, async_add_entities)
