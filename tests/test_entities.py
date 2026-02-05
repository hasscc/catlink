"""Tests for CatLink entity classes."""

from unittest.mock import MagicMock

import pytest

from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.litterbox import LitterBox
from custom_components.catlink.entities.base import CatlinkEntity
from custom_components.catlink.entities.sensor import CatlinkSensorEntity


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
