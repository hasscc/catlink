"""Tests for CatLink config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from custom_components.catlink.const import DOMAIN, ERROR_INVALID_AUTH


@pytest.fixture(autouse=True)
def mock_discover_region():
    """Mock discover_region to avoid real API calls."""
    with patch(
        "custom_components.catlink.config_flow.discover_region",
        new_callable=AsyncMock,
        return_value="global",
    ):
        yield


@pytest.fixture
def mock_account():
    """Mock Account class."""
    with patch("custom_components.catlink.config_flow.Account") as mock:
        instance = mock.return_value
        instance.uid = "86-13812345678"
        instance.async_check_auth = AsyncMock()
        instance.get_devices = AsyncMock(return_value=[])
        yield mock


async def test_user_step_form(hass: HomeAssistant, enable_custom_integrations) -> None:
    """Test the initial user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "phone" in result["data_schema"].schema
    assert "password" in result["data_schema"].schema


async def test_user_step_success_no_devices(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test successful flow with no devices."""
    mock_account.return_value.get_devices = AsyncMock(return_value=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"phone": "+8613812345678", "password": "testpass"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "+8613812345678"
    assert result["data"]["phone_iac"] == "86"
    assert result["data"]["phone"] == "13812345678"
    assert result["data"]["api_base"] == "https://app.catlinks.cn/api/"


async def test_user_step_success_with_devices(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test successful flow with devices proceeds to discovery."""
    mock_account.return_value.get_devices = AsyncMock(
        return_value=[
            {
                "id": "dev1",
                "deviceName": "Litter Box",
                "model": "LB599",
                "deviceType": "LITTER_BOX_599",
            }
        ]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"phone": "+8613812345678", "password": "testpass"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "discovery"


async def test_user_step_invalid_auth(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Test flow shows error when auth fails."""
    with patch(
        "custom_components.catlink.config_flow.discover_region",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"phone": "+8613812345678", "password": "wrongpass"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == ERROR_INVALID_AUTH
