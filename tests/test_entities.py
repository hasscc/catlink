"""Tests for CatLink entity classes."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.litterbox import LitterBox
from custom_components.catlink.entities.base import CatlinkEntity
from custom_components.catlink.entities.binary import CatlinkBinarySensorEntity
from custom_components.catlink.entities.button import CatlinkButtonEntity
from custom_components.catlink.entities.select import CatlinkSelectEntity
from custom_components.catlink.entities.sensor import CatlinkSensorEntity
from custom_components.catlink.entities.switch import CatlinkSwitchEntity
import pytest

from homeassistant.const import STATE_OFF, STATE_ON


@pytest.fixture
def mock_device():
    """Create a mock device with required attributes."""
    device = MagicMock(spec=Device)
    device.id = "dev123"
    device.mac = "AABBCCDDEEFF"
    device.type = "LITTER_BOX_599"
    device.name = "Test Litter Box"
    device.model = "LB599"
    device.detail = {"firmwareVersion": "1.0.0"}
    device.listeners = {}
    return device


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.account = MagicMock()
    return coordinator


@pytest.fixture
def real_device(mock_coordinator):
    """Create a real LitterBox device for entity tests."""
    data = {
        "id": "dev123",
        "mac": "AA:BB:CC:DD:EE:FF",
        "model": "LB599",
        "deviceName": "Test Litter Box",
        "deviceType": "LITTER_BOX_599",
    }
    device = LitterBox(data, mock_coordinator)
    device.detail = {"firmwareVersion": "1.0.0", "currentError": "Normal"}
    device.coordinator = mock_coordinator
    return device


class TestCatlinkEntity:
    """Tests for CatlinkEntity base class."""

    def test_entity_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkEntity initializes with correct attributes."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkEntity("error", mock_device, {"icon": "mdi:alert"})
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._name == "error"
        assert entity._device == mock_device
        assert entity._attr_icon == "mdi:alert"
        assert "Test Litter Box" in entity._attr_name
        assert "error" in entity._attr_name
        assert entity._attr_device_id == "LITTER_BOX_599_AABBCCDDEEFF"
        assert entity._attr_unique_id == "LITTER_BOX_599_AABBCCDDEEFF-error"

    def test_entity_device_info(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkEntity device_info."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkEntity("state", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        info = entity._attr_device_info
        assert info["identifiers"] == {
            ("catlink", "LITTER_BOX_599_AABBCCDDEEFF")
        }
        assert info["name"] == "Test Litter Box"
        assert info["model"] == "LB599"
        assert info["manufacturer"] == "CatLink"
        assert info["sw_version"] == "1.0.0"

    def test_entity_update_from_device(
        self, hass, real_device, mock_coordinator
    ) -> None:
        """Test entity update reads state from device."""
        real_device.coordinator = mock_coordinator
        entity = CatlinkSensorEntity("error", real_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_state == "Normal"

    def test_entity_unique_id_format(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test entity unique_id format."""
        mock_device.coordinator = mock_coordinator
        mock_device.mac = "1122"
        mock_device.id = "dev456"
        entity = CatlinkEntity("litter_weight", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_unique_id.endswith("-litter_weight")
        assert "LITTER_BOX_599" in entity._attr_unique_id


class TestCatlinkBinarySensorEntity:
    """Tests for CatlinkBinarySensorEntity."""

    def test_binary_sensor_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkBinarySensorEntity initializes with is_on False."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_is_on is False

    def test_binary_sensor_update_from_device(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test binary sensor update sets is_on from device attribute."""
        mock_device.coordinator = mock_coordinator
        mock_device.occupied = True
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_is_on is True
        assert entity.state == STATE_ON

    def test_binary_sensor_update_off(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test binary sensor state is OFF when device attribute is falsy."""
        mock_device.coordinator = mock_coordinator
        mock_device.occupied = False
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_is_on is False
        assert entity.state == STATE_OFF


class TestCatlinkButtonEntity:
    """Tests for CatlinkButtonEntity."""

    async def test_button_press_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_press calls option's async_press when callable."""
        mock_device.coordinator = mock_coordinator
        mock_press = AsyncMock(return_value=True)
        entity = CatlinkButtonEntity(
            "action",
            mock_device,
            {"async_press": mock_press},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_press()
        assert result is True
        mock_press.assert_called_once()

    async def test_button_press_no_option_returns_false(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_press returns False when option has no async_press."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkButtonEntity("action", mock_device, {})
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_press()
        assert result is False


class TestCatlinkSelectEntity:
    """Tests for CatlinkSelectEntity."""

    def test_select_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkSelectEntity initializes with options from config."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"]},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_options == ["auto", "manual"]
        assert entity._attr_current_option is None

    def test_select_update_sets_current_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test select update sets current_option from state."""
        mock_device.coordinator = mock_coordinator
        mock_device.mode = "auto"
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"]},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_current_option == "auto"

    async def test_select_option_calls_async_select(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_select_option calls option's async_select."""
        mock_device.coordinator = mock_coordinator
        mock_device.mode = "manual"
        mock_select = AsyncMock(return_value=True)
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"], "async_select": mock_select},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_select_option("manual")
        assert result is True
        mock_select.assert_called_once_with("manual", entity=entity)
        assert entity._attr_current_option == "manual"


class TestCatlinkSwitchEntity:
    """Tests for CatlinkSwitchEntity."""

    def test_switch_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkSwitchEntity initializes."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": None, "async_turn_off": None},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_is_on is False

    async def test_switch_turn_on_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_turn_on calls option's async_turn_on."""
        mock_device.coordinator = mock_coordinator
        mock_device.key_lock = True
        mock_turn_on = AsyncMock(return_value=True)
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": mock_turn_on, "async_turn_off": MagicMock()},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        await entity.async_turn_on()
        assert entity._attr_is_on is True
        mock_turn_on.assert_called_once()

    async def test_switch_turn_off_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_turn_off calls option's async_turn_off."""
        mock_device.coordinator = mock_coordinator
        mock_turn_off = AsyncMock(return_value=True)
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": MagicMock(), "async_turn_off": mock_turn_off},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass
        entity._attr_is_on = True

        await entity.async_turn_off()
        assert entity._attr_is_on is False
        mock_turn_off.assert_called_once()
