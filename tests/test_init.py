"""Test component setup."""
from homeassistant.setup import async_setup_component

from custom_components.catlink.const import DOMAIN, CONF_ACCOUNTS, CONF_PASSWORD, CONF_PHONE, CONF_PHONE_IAC, SCAN_INTERVAL


async def test_async_setup(hass, mock_hass_config):
    """Test the component gets setup."""
    
    
    assert await async_setup_component(hass, DOMAIN, {}) is True