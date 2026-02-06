"""Switch entity for CatLink integration."""

from homeassistant.components.switch import SwitchEntity

from .binary import CatlinkBinaryEntity


class CatlinkSwitchEntity(CatlinkBinaryEntity, SwitchEntity):
    """Switch entity for CatLink."""

    async def async_turn_switch(self, on=True, **kwargs):
        """Turn the entity on/off."""
        ret = False
        fun = self._option.get("async_turn_on" if on else "async_turn_off")
        if callable(fun):
            kwargs["entity"] = self
            ret = await fun(**kwargs)
        if ret:
            self._attr_is_on = bool(on)
        await self._async_after_action(bool(ret), self._option.get("delay_update"))
        return ret

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        return await self.async_turn_switch(True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        return await self.async_turn_switch(False)
