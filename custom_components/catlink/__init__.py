"""The component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity_component import EntityComponent

from .const import _LOGGER, CONF_ACCOUNTS, DOMAIN, SCAN_INTERVAL, SUPPORTED_DOMAINS
from .modules.account import Account
from .modules.devices_coordinator import DevicesCoordinator


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    """Set up the CatLink component."""

    hass.data.setdefault(DOMAIN, {})
    config = hass_config.get(DOMAIN) or {}
    hass.data[DOMAIN]["config"] = config
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("entries", {})

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    hass.data[DOMAIN]["component"] = component
    await component.async_setup(config)

    als = config.get(CONF_ACCOUNTS) or []
    if CONF_PASSWORD in config:
        acc = {**config}
        acc.pop(CONF_ACCOUNTS, None)
        als.append(acc)
    for cfg in als:
        if not cfg.get(CONF_PASSWORD) and not cfg.get(CONF_TOKEN):
            continue
        acc = Account(hass, cfg)
        coordinator = DevicesCoordinator(acc)
        await acc.async_check_auth()
        await coordinator.async_refresh()
        hass.data[DOMAIN][CONF_ACCOUNTS][acc.uid] = acc
        hass.data[DOMAIN]["coordinators"][coordinator.name] = coordinator

    for platform in SUPPORTED_DOMAINS:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    if config and not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.async_init(DOMAIN, context={"source": "import"}, data=config)
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CatLink from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("entries", {})

    cfg = {**entry.data, **entry.options}
    if not cfg.get(CONF_PASSWORD) and not cfg.get(CONF_TOKEN):
        return False

    acc = Account(hass, cfg)
    coordinator = DevicesCoordinator(acc)
    await acc.async_check_auth()
    await coordinator.async_refresh()

    hass.data[DOMAIN][CONF_ACCOUNTS][acc.uid] = acc
    hass.data[DOMAIN]["coordinators"][coordinator.name] = coordinator
    hass.data[DOMAIN]["entries"][entry.entry_id] = acc.uid

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_DOMAINS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, SUPPORTED_DOMAINS
    )
    if not unload_ok:
        return False

    uid = hass.data[DOMAIN].get("entries", {}).pop(entry.entry_id, None)
    if uid:
        hass.data[DOMAIN][CONF_ACCOUNTS].pop(uid, None)
        coordinator_name = f"{DOMAIN}-{uid}-{CONF_DEVICES}"
        hass.data[DOMAIN]["coordinators"].pop(coordinator_name, None)
    return True
