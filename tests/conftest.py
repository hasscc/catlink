"""Fixtures for testing."""

import pytest
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant

from custom_components.catlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntries
from unittest.mock import patch
from collections.abc import Generator

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def hass_config() -> ConfigType:
    return {
        DOMAIN: {
                    "phone": "xxxxxxxxx",
                    "phone_iac": "+1",
                    "password": "xxxxxxxx",
                    "scan_interval": "00:00:10"
        }
    }

@pytest.fixture
def mock_hass_config(hass: HomeAssistant, hass_config: ConfigType) -> Generator[None]:
    """Fixture to mock the content of main configuration.

    Patches homeassistant.config.load_yaml_config_file and hass.config_entries
    with `hass_config` as parameterized.
    """
    if hass_config:
        hass.config_entries = ConfigEntries(hass, hass_config)
    with patch("homeassistant.config.load_yaml_config_file", return_value=hass_config):
        yield
