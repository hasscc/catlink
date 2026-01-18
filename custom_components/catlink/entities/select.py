"""Select entity for CatLink integration."""

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .base import CatlinkEntity

if TYPE_CHECKING:
    from ..devices.base import Device


class CatlinkSelectEntity(CatlinkEntity, SelectEntity):
    """Select entity for CatLink."""

    def __init__(self, name, device: "Device", option=None) -> None:
        """Initialize the entity."""
        super().__init__(name, device, option)
        self._attr_current_option = None
        self._attr_options = self._option.get("options")

    def update(self) -> None:
        """Update the entity."""
        super().update()
        self._attr_current_option = self._attr_state

    async def async_select_option(self, option: str):
        """Change the selected option."""
        ret = False
        fun = self._option.get("async_select")
        if callable(fun):
            kws = {"entity": self}
            ret = await fun(option, **kws)
        if ret:
            self._attr_current_option = option
        await self._async_after_action(bool(ret), self._option.get("delay_update"))
        return ret
