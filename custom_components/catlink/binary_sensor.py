"""Support for binary_sensor."""

from homeassistant.components.binary_sensor import (
    DOMAIN as ENTITY_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from . import DOMAIN
from .entitites import CatlinkBinaryEntity
from .helpers import Helper


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Catlink binary sensors from a config entry."""
    cfg = {**config_entry.data, **config_entry.options}
    await async_setup_platform(hass, cfg, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Catlink binary_sensor platform."""
    hass.data[DOMAIN]["add_entities"][ENTITY_DOMAIN] = async_add_entities
    await Helper.async_setup_accounts(hass, ENTITY_DOMAIN)


class CatlinkBinarySensorEntity(CatlinkBinaryEntity, BinarySensorEntity):
    """BinarySensorEntity."""
