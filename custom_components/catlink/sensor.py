"""Support for sensor."""

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import DOMAIN
from .entities import CatlinkSensorEntity
from .helpers import Helper, async_setup_domain_platform

async_setup_entry = Helper.async_setup_entry_for(ENTITY_DOMAIN)
async_setup_accounts = Helper.async_setup_accounts


async def _register_sensor_services() -> None:
    """Register sensor-specific entity services."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "request_api",
        {
            vol.Required("api"): cv.string,
            vol.Optional("params", default={}): vol.Any(dict, None),
            vol.Optional("method", default="GET"): cv.string,
            vol.Optional("throw", default=True): cv.boolean,
        },
        "async_request_api",
    )


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Catlink sensor platform."""
    await async_setup_domain_platform(
        hass, ENTITY_DOMAIN, async_add_entities, _register_sensor_services
    )
