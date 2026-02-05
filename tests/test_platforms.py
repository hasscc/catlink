"""Tests for CatLink platform setup (sensor, switch, binary_sensor, select, button)."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.catlink import binary_sensor, button, select, sensor, switch
from custom_components.catlink.const import (
    CONF_ACCOUNTS,
    CONF_DEVICE_IDS,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SUPPORTED_DOMAINS,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_account():
    """Mock Account to avoid real API calls."""
    with patch("custom_components.catlink.Account") as mock:
        instance = mock.return_value
        instance.uid = "86-13812345678"
        instance.hass = None
        instance.async_check_auth = AsyncMock()
        instance.get_devices = AsyncMock(return_value=[])
        instance.update_interval = __import__("datetime").timedelta(minutes=1)
        instance.get_config = MagicMock(return_value=None)
        yield mock


@pytest.fixture
def mock_coordinator():
    """Mock DevicesCoordinator class."""
    with patch("custom_components.catlink.DevicesCoordinator") as mock:
        instance = mock.return_value
        instance.name = f"{DOMAIN}-86-13812345678-devices"
        instance.async_refresh = AsyncMock()
        instance.data = {}
        yield mock


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            "api_base": "https://app.catlinks.cn/api/",
            "password": "testpass",
        },
        options={CONF_DEVICE_IDS: [], CONF_UPDATE_INTERVAL: 60},
        unique_id="86-13812345678",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_account,
    mock_coordinator,
) -> MockConfigEntry:
    """Set up the CatLink integration for platform tests."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {CONF_DEVICES: []})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_account.return_value.hass = hass

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_platforms_loaded(init_integration: MockConfigEntry) -> None:
    """Test all supported platforms are loaded."""
    assert init_integration.state is ConfigEntryState.LOADED
    for domain in SUPPORTED_DOMAINS:
        assert domain in ["sensor", "binary_sensor", "switch", "select", "button"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_entities_registered(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test add_entities callbacks are registered for each platform."""
    add_entities = hass.data[DOMAIN].get("add_entities", {})
    entry_add = add_entities.get(init_integration.entry_id, {})
    for domain in SUPPORTED_DOMAINS:
        assert domain in entry_add
        assert callable(entry_add[domain])


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_sensor_platform_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test sensor platform async_setup_entry registers callback and updates entities."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_add_entities = MagicMock()
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PHONE_IAC: "86", CONF_PHONE: "13812345678"},
        entry_id="test-sensor-entry",
    )
    mock_config_entry.add_to_hass(hass)

    await sensor.async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert mock_config_entry.entry_id in hass.data[DOMAIN]["add_entities"]
    assert "sensor" in hass.data[DOMAIN]["add_entities"][mock_config_entry.entry_id]
    assert (
        hass.data[DOMAIN]["add_entities"][mock_config_entry.entry_id]["sensor"]
        is mock_add_entities
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_switch_platform_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test switch platform async_setup_entry registers callback."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_add_entities = MagicMock()
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PHONE_IAC: "86", CONF_PHONE: "13812345678"},
        entry_id="test-switch-entry",
    )
    mock_config_entry.add_to_hass(hass)

    await switch.async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert "switch" in hass.data[DOMAIN]["add_entities"][mock_config_entry.entry_id]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_all_platforms_have_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test all supported domains have async_setup_entry."""
    for _domain, module in [
        ("sensor", sensor),
        ("switch", switch),
        ("binary_sensor", binary_sensor),
        ("select", select),
        ("button", button),
    ]:
        assert hasattr(module, "async_setup_entry")
        assert callable(module.async_setup_entry)
