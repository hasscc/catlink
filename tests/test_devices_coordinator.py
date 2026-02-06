"""Tests for CatLink DevicesCoordinator module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.catlink.const import DOMAIN
from custom_components.catlink.modules.devices_coordinator import DevicesCoordinator
from custom_components.catlink.modules.account import Account


@pytest.fixture
def coordinator_hass_data(hass):
    """Set up hass.data structure required by DevicesCoordinator."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config"] = {"devices": []}
    hass.data[DOMAIN]["devices"] = {}
    hass.data[DOMAIN]["add_entities"] = {}
    return hass.data[DOMAIN]


@pytest.fixture
def mock_account(hass, coordinator_hass_data):
    """Create mock Account for coordinator."""
    account = MagicMock(spec=Account)
    account.hass = hass
    account.uid = "86-13812345678"
    account.update_interval = __import__("datetime").timedelta(minutes=1)
    return account


@pytest.fixture
def coordinator(mock_account, coordinator_hass_data):
    """Create DevicesCoordinator instance."""
    return DevicesCoordinator(
        mock_account,
        config_entry_id="test-entry-123",
        device_ids=None,
    )


class TestDevicesCoordinatorInit:
    """Tests for DevicesCoordinator initialization."""

    def test_init_sets_account(self, coordinator, mock_account) -> None:
        """Test coordinator stores account reference."""
        assert coordinator.account == mock_account

    def test_init_sets_config_entry_id(self, coordinator) -> None:
        """Test coordinator stores config entry id."""
        assert coordinator.config_entry_id == "test-entry-123"

    def test_init_sets_name(self, coordinator, mock_account) -> None:
        """Test coordinator name includes domain and uid."""
        assert coordinator.name == f"{DOMAIN}-{mock_account.uid}-devices"

    def test_init_parses_additional_config(
        self, mock_account, coordinator_hass_data
    ) -> None:
        """Test coordinator parses additional device config."""
        coordinator_hass_data["config"]["devices"] = [
            {"mac": "AA:BB:CC:DD:EE:FF", "empty_weight": 1.5},
        ]
        coord = DevicesCoordinator(mock_account, "entry-1")
        assert len(coord.additional_config) == 1
        assert coord.additional_config[0].mac == "AA:BB:CC:DD:EE:FF"
        assert coord.additional_config[0].empty_weight == 1.5


class TestDevicesCoordinatorAsyncUpdateData:
    """Tests for DevicesCoordinator _async_update_data."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_data_creates_devices(
        self, coordinator, mock_account, coordinator_hass_data
    ) -> None:
        """Test _async_update_data creates devices from API response."""
        mock_account.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "model": "LB599",
                    "deviceName": "Litter Box",
                    "deviceType": "LITTER_BOX_599",
                },
            ]
        )

        with patch(
            "custom_components.catlink.modules.devices_coordinator.create_device"
        ) as mock_create:
            mock_device = MagicMock()
            mock_device.id = "dev1"
            mock_device.name = "Litter Box"
            mock_device.update_data = MagicMock()
            mock_device.async_init = AsyncMock()
            mock_create.return_value = mock_device

            result = await coordinator._async_update_data()

            assert "dev1" in result
            assert result["dev1"] == mock_device
            mock_create.assert_called_once()
            mock_device.async_init.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_data_updates_existing_device(
        self, coordinator, mock_account, coordinator_hass_data
    ) -> None:
        """Test _async_update_data updates existing device instead of creating new."""
        mock_account.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "deviceName": "Updated Name",
                    "deviceType": "LITTER_BOX_599",
                },
            ]
        )

        existing_device = MagicMock()
        existing_device.id = "dev1"
        existing_device.name = "Old Name"
        existing_device.update_data = MagicMock()
        existing_device.async_init = AsyncMock()
        coordinator_hass_data["devices"]["dev1"] = existing_device

        with patch(
            "custom_components.catlink.modules.devices_coordinator.create_device"
        ) as mock_create:
            result = await coordinator._async_update_data()

            assert result["dev1"] == existing_device
            existing_device.update_data.assert_called_once()
            mock_create.assert_not_called()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_data_filters_by_device_ids(
        self, mock_account, coordinator_hass_data
    ) -> None:
        """Test _async_update_data filters devices when device_ids is set."""
        coordinator = DevicesCoordinator(
            mock_account,
            config_entry_id="entry-1",
            device_ids=["dev2"],
        )

        mock_account.get_devices = AsyncMock(
            return_value=[
                {"id": "dev1", "deviceType": "LITTER_BOX_599"},
                {"id": "dev2", "deviceType": "LITTER_BOX_599"},
            ]
        )

        with patch(
            "custom_components.catlink.modules.devices_coordinator.create_device"
        ) as mock_create:
            mock_device = MagicMock()
            mock_device.id = "dev2"
            mock_device.async_init = AsyncMock()
            mock_create.return_value = mock_device

            result = await coordinator._async_update_data()

            assert "dev1" not in result
            assert "dev2" in result
            assert mock_create.call_count == 1

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_data_skips_device_without_id(
        self, coordinator, mock_account, coordinator_hass_data
    ) -> None:
        """Test _async_update_data skips devices without id."""
        mock_account.get_devices = AsyncMock(
            return_value=[
                {"id": "", "deviceType": "LITTER_BOX_599"},
                {"deviceType": "LITTER_BOX_599"},
            ]
        )

        with patch(
            "custom_components.catlink.modules.devices_coordinator.create_device"
        ) as mock_create:
            result = await coordinator._async_update_data()

            assert len(result) == 0
            mock_create.assert_not_called()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_data_creates_cat_devices(
        self, coordinator, mock_account, coordinator_hass_data
    ) -> None:
        """Test _async_update_data creates cat devices from API response."""
        mock_account.get_devices = AsyncMock(return_value=[])
        mock_account.get_cats = AsyncMock(
            return_value=[{"id": "169004", "petName": "Zulu", "breedName": "Cat"}]
        )
        mock_account.get_cat_summary_simple = AsyncMock(
            return_value={"statusDescription": "Data collection in progress"}
        )

        with patch(
            "custom_components.catlink.modules.devices_coordinator.create_device"
        ) as mock_create:
            mock_device = MagicMock()
            mock_device.id = "cat-169004"
            mock_device.name = "Zulu"
            mock_device.update_data = MagicMock()
            mock_device.async_init = AsyncMock()
            mock_create.return_value = mock_device

            result = await coordinator._async_update_data()

            assert "cat-169004" in result
            mock_create.assert_called_once()
            mock_account.get_cat_summary_simple.assert_called_once()


class TestDevicesCoordinatorUpdateHassEntities:
    """Tests for DevicesCoordinator update_hass_entities."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_hass_entities_adds_entities(
        self, coordinator, coordinator_hass_data
    ) -> None:
        """Test update_hass_entities adds entities when add_entities is set."""
        add_sensor = MagicMock()
        coordinator_hass_data["add_entities"]["test-entry-123"] = {
            "sensor": add_sensor,
        }

        mock_device = MagicMock()
        mock_device.id = "dev1"
        mock_device.name = "Litter Box"
        mock_device.coordinator = coordinator
        mock_device.mac = "AA:BB:CC:DD:EE:FF"
        mock_device.type = "LITTER_BOX_599"
        mock_device.model = "LB599"
        mock_device.detail = {}
        mock_device.hass_sensor = {
            "state": {"icon": "mdi:info", "state_attrs": lambda: {}},
            "error": {"icon": "mdi:alert", "state_attrs": lambda: {}},
        }

        await coordinator.update_hass_entities("sensor", mock_device)

        assert add_sensor.call_count >= 1
        added = add_sensor.call_args[0][0]
        assert len(added) >= 1

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_hass_entities_skips_when_no_add(
        self, coordinator, coordinator_hass_data
    ) -> None:
        """Test update_hass_entities does nothing when add_entities not set."""
        coordinator_hass_data["add_entities"] = {}

        mock_device = MagicMock()
        mock_device.id = "dev1"
        mock_device.hass_sensor = {"state": {}}

        await coordinator.update_hass_entities("sensor", mock_device)

        assert "dev1" not in coordinator._subs or not coordinator._subs

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_hass_entities_skips_when_device_has_no_domain_attr(
        self, coordinator, coordinator_hass_data
    ) -> None:
        """Test update_hass_entities skips when device has no hass_X attribute."""
        add_sensor = MagicMock()
        coordinator_hass_data["add_entities"]["test-entry-123"] = {
            "sensor": add_sensor,
        }

        mock_device = MagicMock()
        mock_device.id = "dev1"
        del mock_device.hass_sensor

        await coordinator.update_hass_entities("sensor", mock_device)

        add_sensor.assert_not_called()
