"""Tests for CatLink config flow."""

from unittest.mock import AsyncMock, patch

from custom_components.catlink.config_flow import _device_label
from custom_components.catlink.const import (
    CONF_DEVICE_IDS,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ERROR_INVALID_AUTH,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant


class TestDeviceLabel:
    """Tests for _device_label helper."""

    def test_device_label_with_name_and_model(self) -> None:
        """Test label when device has name and model."""
        dat = {
            "deviceName": "Living Room",
            "model": "LB599",
            "deviceType": "LITTER_BOX_599",
        }
        assert _device_label(dat, True) == "Living Room (LB599) - Supported"
        assert _device_label(dat, False) == "Living Room (LB599) - Limited support"

    def test_device_label_name_equals_model(self) -> None:
        """Test label when name equals model uses deviceType."""
        dat = {
            "deviceName": "LB599",
            "model": "LB599",
            "deviceType": "LITTER_BOX_599",
        }
        assert _device_label(dat, True) == "LB599 (LITTER_BOX_599) - Supported"

    def test_device_label_fallback_to_model(self) -> None:
        """Test label falls back to model when deviceName missing."""
        dat = {"model": "LB599", "deviceType": "LITTER_BOX_599"}
        assert _device_label(dat, True) == "LB599 (LITTER_BOX_599) - Supported"

    def test_device_label_fallback_to_unknown(self) -> None:
        """Test label falls back to Unknown when name and model missing."""
        dat = {"deviceType": "UNKNOWN"}
        assert _device_label(dat, True) == "Unknown (UNKNOWN) - Supported"


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


async def test_discovery_step_form(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test discovery step shows device selection and update interval."""
    mock_account.return_value.get_devices = AsyncMock(
        return_value=[
            {
                "id": "dev1",
                "deviceName": "Litter Box",
                "model": "LB599",
                "deviceType": "LITTER_BOX_599",
            },
            {
                "id": "dev2",
                "deviceName": "Feeder",
                "model": "FD001",
                "deviceType": "FEEDER",
            },
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
    assert CONF_DEVICE_IDS in result["data_schema"].schema
    assert CONF_UPDATE_INTERVAL in result["data_schema"].schema


async def test_discovery_step_create_entry(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test discovery step creates entry with selected devices and interval."""
    mock_account.return_value.get_devices = AsyncMock(
        return_value=[
            {
                "id": "dev1",
                "deviceName": "Litter Box",
                "model": "LB599",
                "deviceType": "LITTER_BOX_599",
            },
        ]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"phone": "+8613812345678", "password": "testpass"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_IDS: ["dev1"], CONF_UPDATE_INTERVAL: 120},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "+8613812345678"
    assert result["options"][CONF_DEVICE_IDS] == ["dev1"]
    assert result["options"][CONF_UPDATE_INTERVAL] == 120


async def test_reauth_flow(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test reauth flow updates entry with new credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            "api_base": "https://app.catlinks.cn/api/",
            "password": "oldpass",
        },
        unique_id="86-13812345678",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"phone": "+8613812345678", "password": "newpass"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PHONE] == "13812345678"
    assert entry.data["password"] == "newpass"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Test reauth flow shows error when auth fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            "api_base": "https://app.catlinks.cn/api/",
            "password": "oldpass",
        },
        unique_id="86-13812345678",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.catlink.config_flow.discover_region",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"phone": "+8613812345678", "password": "wrongpass"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == ERROR_INVALID_AUTH


async def test_options_flow(
    hass: HomeAssistant, enable_custom_integrations, mock_account
) -> None:
    """Test options flow updates device selection and refresh interval."""
    mock_account.return_value.get_devices = AsyncMock(
        return_value=[
            {
                "id": "dev1",
                "deviceName": "Litter Box",
                "model": "LB599",
                "deviceType": "LITTER_BOX_599",
            },
            {
                "id": "dev2",
                "deviceName": "Feeder",
                "model": "FD001",
                "deviceType": "FEEDER",
            },
        ]
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            "api_base": "https://app.catlinks.cn/api/",
            "password": "testpass",
        },
        options={CONF_DEVICE_IDS: ["dev1"], CONF_UPDATE_INTERVAL: 60},
        unique_id="86-13812345678",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DEVICE_IDS: ["dev1", "dev2"], CONF_UPDATE_INTERVAL: 300},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_IDS] == ["dev1", "dev2"]
    assert result["data"][CONF_UPDATE_INTERVAL] == 300
