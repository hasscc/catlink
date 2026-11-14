"""Tests for CatLink integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.catlink import async_setup
from custom_components.catlink.const import (
    CONF_ACCOUNTS,
    CONF_PHONE,
    CONF_PHONE_IAC,
    DOMAIN,
    SUPPORTED_DOMAINS,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant


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
        options={},
        entry_id="test-entry-id",
    )


@pytest.fixture
def mock_account():
    """Mock Account class."""
    with patch("custom_components.catlink.Account") as mock:
        instance = mock.return_value
        instance.uid = "86-13812345678"
        instance.async_check_auth = AsyncMock()
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


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup initializes hass.data structure."""
    result = await async_setup(hass, {})

    assert result is True
    assert DOMAIN in hass.data
    assert CONF_ACCOUNTS in hass.data[DOMAIN]
    assert CONF_DEVICES in hass.data[DOMAIN]
    assert "coordinators" in hass.data[DOMAIN]
    assert "add_entities" in hass.data[DOMAIN]
    assert "config" in hass.data[DOMAIN]
    assert "entry_coordinators" in hass.data[DOMAIN]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_account,
    mock_coordinator,
) -> None:
    """Test async_setup_entry loads config entry and forwards platforms."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_account.return_value.async_check_auth.assert_called_once()
    mock_coordinator.return_value.async_refresh.assert_called_once()
    assert mock_account.return_value.uid in hass.data[DOMAIN][CONF_ACCOUNTS]
    assert mock_config_entry.entry_id in hass.data[DOMAIN]["entry_coordinators"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_account,
    mock_coordinator,
) -> None:
    """Test async_unload_entry cleans up hass.data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert "86-13812345678" not in hass.data[DOMAIN][CONF_ACCOUNTS]
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]["entry_coordinators"]
    mock_account.return_value.close.assert_called_once_with()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_unload_entry_drops_its_devices(
    hass: HomeAssistant,
    mock_config_entry,
    mock_account,
    mock_coordinator,
) -> None:
    """Unload removes the entry's devices so a reload binds new ones to the new coordinator."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    own = MagicMock(coordinator=mock_coordinator.return_value)
    other = MagicMock(coordinator=MagicMock())
    hass.data[DOMAIN][CONF_DEVICES].update({"own": own, "other": other})

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.data[DOMAIN][CONF_DEVICES] == {"other": other}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup_entry_retries_when_first_update_fails(
    hass: HomeAssistant,
    mock_config_entry,
    mock_account,
    mock_coordinator,
) -> None:
    """A failed first update leaves the entry in setup-retry instead of dead."""
    mock_coordinator.return_value.last_update_success = False
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN].setdefault("add_entities", {})
    hass.data[DOMAIN].setdefault("config", {})
    hass.data[DOMAIN].setdefault("entry_coordinators", {})

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_account.return_value.close.assert_called_once_with()
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]["entry_coordinators"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup_entry_forwards_all_platforms(
    hass: HomeAssistant,
    mock_config_entry,
    mock_account,
    mock_coordinator,
) -> None:
    """Test async_setup_entry forwards all supported domains."""
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as mock_forward:
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
        hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
        hass.data[DOMAIN].setdefault("coordinators", {})
        hass.data[DOMAIN].setdefault("add_entities", {})
        hass.data[DOMAIN].setdefault("config", {})
        hass.data[DOMAIN].setdefault("entry_coordinators", {})

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_forward.assert_called_once()
        call_args = mock_forward.call_args
        assert call_args[0][1] == SUPPORTED_DOMAINS
