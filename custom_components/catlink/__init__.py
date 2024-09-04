"""The component."""

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
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][CONF_ACCOUNTS][acc.uid] = acc
        hass.data[DOMAIN]["coordinators"][coordinator.name] = coordinator

    for platform in SUPPORTED_DOMAINS:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    return True
