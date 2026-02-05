"""Helper functions for the CatLink integration."""

from datetime import timedelta
import re
from typing import TYPE_CHECKING

import phonenumbers
from phonenumbers import NumberParseException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    API_SERVERS,
    CONF_API_BASE,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_PHONE_IAC,
    DOMAIN,
)

if TYPE_CHECKING:
    from .modules.devices_coordinator import DevicesCoordinator


async def async_setup_domain_platform(
    hass: HomeAssistant,
    domain: str,
    async_add_entities,
    extra_setup=None,
) -> None:
    """Set up a domain platform (sensor, switch, select, etc.) via discovery.

    Used when loading via async_load_platform; for config entries use
    async_setup_entry_for instead.
    """
    hass.data[DOMAIN]["add_entities"].setdefault("discovery", {})[domain] = (
        async_add_entities
    )
    await Helper.async_setup_accounts(hass, domain)
    if extra_setup is not None:
        await extra_setup()


def parse_phone_number(phone: str) -> tuple[str, str]:
    """Parse a full phone number into country code and national number.

    Accepts formats like +447911123456, 447911123456, or 07911123456.
    Returns (phone_iac, phone_number) for CatLink API.
    """
    cleaned = re.sub(r"[\s\-\.\(\)]", "", str(phone).strip())
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned.lstrip("0")
    try:
        parsed = phonenumbers.parse(cleaned, None)
        return (
            str(parsed.country_code),
            str(parsed.national_number),
        )
    except NumberParseException:
        pass
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) >= 10:
        for length in (3, 2, 1):
            if len(digits) > length:
                return (digits[:length], digits[length:])
    return ("86", digits or "0")


async def discover_region(
    hass: HomeAssistant, phone_iac: str, phone_number: str, password: str
) -> str | None:
    """Try each API region until login succeeds. Returns region key or None."""
    from .modules.account import Account

    for region in ("global", "china", "usa", "singapore"):
        api_base = API_SERVERS.get(region)
        if not api_base:
            continue
        config = {
            CONF_API_BASE: api_base,
            CONF_PHONE: phone_number,
            CONF_PHONE_IAC: phone_iac,
            CONF_PASSWORD: password,
        }
        account = Account(hass, config)
        if await account.async_login():
            return region
    return None


def format_api_error(rdt: dict) -> str:
    """Build a user-friendly error message from CatLink API response.

    Extracts the 'msg' field when present; otherwise returns a string
    representation of the full response for debugging.
    """
    msg = rdt.get("msg") or rdt.get("message")
    code = rdt.get("returnCode")
    if msg:
        return f"{msg} (returnCode: {code})" if code else str(msg)
    return str(rdt)


class Helper:
    """Helper class for the CatLink integration."""

    @classmethod
    def calculate_update_interval(
        cls, update_interval: str | timedelta | int | float | None
    ) -> timedelta:
        """Calculate the update interval as a timedelta object.

        Args:
            update_interval: A timedelta, seconds (int/float), or "HH:MM:SS" string.

        Returns:
            timedelta: The update interval as a timedelta object.
        """
        if isinstance(update_interval, timedelta):
            return update_interval
        if isinstance(update_interval, (int, float)) and update_interval > 0:
            return timedelta(seconds=int(update_interval))
        if isinstance(update_interval, str) and re.match(
            r"^\d{2}:\d{2}:\d{2}$", update_interval
        ):
            return timedelta(
                hours=int(update_interval[:2]),
                minutes=int(update_interval[3:5]),
                seconds=int(update_interval[6:8]),
            )
        return timedelta(minutes=1)

    @classmethod
    async def async_setup_accounts(cls, hass: HomeAssistant, domain: str) -> None:
        """Set up entities for all coordinators (discovery path only)."""
        coordinators: list[DevicesCoordinator] = list(
            hass.data[DOMAIN]["coordinators"].values()
        )
        for coordinator in coordinators:
            for sta in coordinator.data.values():
                await coordinator.update_hass_entities(domain, sta)

    @staticmethod
    def async_setup_entry_for(domain: str):
        """Return async_setup_entry bound to the given platform domain."""

        async def _async_setup_entry(
            hass: HomeAssistant,
            config_entry: ConfigEntry,
            async_add_entities,
        ) -> None:
            """Set up the Catlink platform for a config entry."""
            hass.data[DOMAIN].setdefault("add_entities", {})
            hass.data[DOMAIN]["add_entities"].setdefault(config_entry.entry_id, {})[
                domain
            ] = async_add_entities

            coordinator = hass.data[DOMAIN]["entry_coordinators"].get(
                config_entry.entry_id
            )
            if coordinator is not None:
                for sta in coordinator.data.values():
                    await coordinator.update_hass_entities(domain, sta)

        return _async_setup_entry
