"""The component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    _LOGGER,
    CONF_ACCOUNTS,
    CONF_DEVICE_IDS,
    DOMAIN,
    SUPPORTED_DOMAINS,
)
from .modules.account import Account
from .modules.devices_coordinator import DevicesCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    """Set up the CatLink component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CatLink from a config entry."""
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN]["config"].setdefault(CONF_DEVICES, [])

    config = {**entry.data, **(entry.options or {})}
    acc = Account(hass, config)
    device_ids = entry.options.get(CONF_DEVICE_IDS) if entry.options else None
    coordinator = DevicesCoordinator(acc, entry.entry_id, device_ids=device_ids)

    await acc.async_check_auth()
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        # Entities are created by the first successful update; without one
        # nothing would ever poll again. Let HA retry the setup later.
        acc.close()
        raise ConfigEntryNotReady("Could not fetch CatLink devices")

    hass.data[DOMAIN][CONF_ACCOUNTS][acc.uid] = acc
    hass.data[DOMAIN]["coordinators"][coordinator.name] = coordinator
    hass.data[DOMAIN]["entry_coordinators"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_DOMAINS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, SUPPORTED_DOMAINS)

    # Drop this entry's devices: a reload must build new ones bound to the new
    # coordinator, or its entities would listen to the old, shut-down one.
    coordinator = hass.data[DOMAIN]["entry_coordinators"].get(entry.entry_id)
    if coordinator is not None:
        devices = hass.data[DOMAIN][CONF_DEVICES]
        for did in [d for d, dvc in devices.items() if dvc.coordinator is coordinator]:
            del devices[did]

    uid = f"{entry.data.get('phone_iac', '86')}-{entry.data.get('phone', '')}"
    acc = hass.data[DOMAIN][CONF_ACCOUNTS].pop(uid, None)
    if acc is not None:
        acc.close()
    coordinator_name = f"{DOMAIN}-{uid}-{CONF_DEVICES}"
    if coordinator_name in hass.data[DOMAIN]["coordinators"]:
        del hass.data[DOMAIN]["coordinators"][coordinator_name]
    if entry.entry_id in hass.data[DOMAIN]["entry_coordinators"]:
        del hass.data[DOMAIN]["entry_coordinators"][entry.entry_id]
    if entry.entry_id in hass.data[DOMAIN].get("add_entities", {}):
        del hass.data[DOMAIN]["add_entities"][entry.entry_id]

    return True
