"""Helper functions for the CatLink integration."""

from datetime import timedelta
import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .modules.devices_coordinator import DevicesCoordinator


class Helper:
    """Helper class for the CatLink integration."""

    @classmethod
    def calculate_update_interval(cls, update_interval_str: str) -> timedelta:
        """Calculate the update interval as a timedelta object based on the given update_interval_str.

        Args:
            update_interval_str (str): The update interval string in the format "HH:MM:SS".

        Returns:
            timedelta: The update interval as a timedelta object.

        """

        if isinstance(update_interval_str, timedelta):
            return update_interval_str

        return (
            timedelta(minutes=10)
            if not update_interval_str
            or not isinstance(update_interval_str, str)
            or not re.match(r"^\d{2}:\d{2}:\d{2}$", update_interval_str)
            else timedelta(
                hours=int(update_interval_str[:2]),
                minutes=int(update_interval_str[3:5]),
                seconds=int(update_interval_str[6:8]),
            )
        )

    @classmethod
    async def async_setup_accounts(cls, hass: HomeAssistant, domain) -> None:
        """Set up the accounts."""
        coordinators: list[DevicesCoordinator] = hass.data[DOMAIN][
            "coordinators"
        ].values()
        for coordinator in coordinators:
            for sta in coordinator.data.values():
                await coordinator.update_hass_entities(domain, sta)

    @classmethod
    async def async_setup_entry(
        cls, hass: HomeAssistant, config_entry, async_add_entities
    ) -> None:
        """Set up the Catlink platform."""
        cfg = {**config_entry.data, **config_entry.options}
        await cls.async_setup_platform(
            hass, cfg, cls.async_setup_platform, async_add_entities
        )
