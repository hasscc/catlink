"""Helper functions for the CatLink integration."""

from datetime import timedelta
import re
from typing import TYPE_CHECKING, Union

from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .modules.devices_coordinator import DevicesCoordinator


class Helper:
    """Helper class for the CatLink integration."""

    @classmethod
    def calculate_update_interval(cls, update_interval: Union[str, timedelta]) -> timedelta:
        """Calculate the update interval as a timedelta object.

        Args:
            update_interval: The update interval as a string ("HH:MM:SS") or timedelta.
                When configured via YAML, Home Assistant's cv.time_period validator
                converts the string to a timedelta object.

        Returns:
            timedelta: The update interval as a timedelta object.

        """
        # If already a timedelta (from cv.time_period validation), return directly
        if isinstance(update_interval, timedelta):
            return update_interval

        # Handle string format "HH:MM:SS"
        return (
            timedelta(minutes=10)
            if not update_interval
            or not re.match(r"^\d{2}:\d{2}:\d{2}$", update_interval)
            else timedelta(
                hours=int(update_interval[:2]),
                minutes=int(update_interval[3:5]),
                seconds=int(update_interval[6:8]),
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
