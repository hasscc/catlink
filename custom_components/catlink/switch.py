"""Support for switch."""

import asyncio

from homeassistant.components.switch import DOMAIN as ENTITY_DOMAIN, SwitchEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entitites import CatlinkBinaryEntity
from .helpers import Helper


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Catlink switches from a config entry."""
    cfg = {**config_entry.data, **config_entry.options}
    await async_setup_platform(hass, cfg, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Catlink switch platform."""
    hass.data[DOMAIN]["add_entities"][ENTITY_DOMAIN] = async_add_entities
    await Helper.async_setup_accounts(hass, ENTITY_DOMAIN)


class CatlinkSwitchEntity(CatlinkBinaryEntity, SwitchEntity):
    """SwitchEntity."""

    async def async_turn_switch(self, on=True, **kwargs):
        """Turn the entity on/off."""
        ret = False
        fun = self._option.get("async_turn_on" if on else "async_turn_off")
        if callable(fun):
            kwargs["entity"] = self
            ret = await fun(**kwargs)
        if ret:
            self._attr_is_on = bool(on)
            self.async_write_ha_state()
            if dly := self._option.get("delay_update"):
                await asyncio.sleep(dly)
                self._handle_coordinator_update()
        return ret

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        return await self.async_turn_switch(True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        return await self.async_turn_switch(False)
