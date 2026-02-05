"""Tests for CatLink device classes."""

from unittest.mock import MagicMock

import pytest

from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.feeder import FeederDevice
from custom_components.catlink.devices.litterbox import LitterBox
from custom_components.catlink.devices.registry import create_device
from custom_components.catlink.devices.scooper import ScooperDevice
from custom_components.catlink.models.additional_cfg import AdditionalDeviceConfig


@pytest.fixture
def mock_coordinator():
    """Create a mock DevicesCoordinator."""
    coordinator = MagicMock()
    coordinator.account = MagicMock()
    coordinator.account.uid = "86-13812345678"
    return coordinator


@pytest.fixture
def sample_device_data():
    """Sample device data from API."""
    return {
        "id": "dev123",
        "mac": "AA:BB:CC:DD:EE:FF",
        "model": "LB599",
        "deviceName": "Living Room Litter",
        "deviceType": "LITTER_BOX_599",
    }


@pytest.fixture
def sample_feeder_data():
    """Sample feeder device data."""
    return {
        "id": "feeder1",
        "mac": "11:22:33:44:55:66",
        "model": "Feeder Pro",
        "deviceName": "Kitchen Feeder",
        "deviceType": "FEEDER",
    }


@pytest.fixture
def sample_scooper_data():
    """Sample scooper device data."""
    return {
        "id": "scooper1",
        "mac": "FF:EE:DD:CC:BB:AA",
        "model": "Scooper C1",
        "deviceName": "Basement Scooper",
        "deviceType": "SCOOPER",
    }


class TestDevice:
    """Tests for base Device class."""

    def test_device_properties(self, mock_coordinator, sample_device_data) -> None:
        """Test Device basic properties from data."""
        device = Device(sample_device_data, mock_coordinator)
        assert device.id == "dev123"
        assert device.mac == "AA:BB:CC:DD:EE:FF"
        assert device.model == "LB599"
        assert device.name == "Living Room Litter"
        assert device.type == "LITTER_BOX_599"

    def test_device_error_from_detail(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test Device error property from detail."""
        device = Device(sample_device_data, mock_coordinator)
        device.detail = {"currentMessage": "Device offline"}
        assert device.error == "Device offline"

    def test_device_error_action_error_takes_precedence(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _action_error overrides detail error."""
        device = Device(sample_device_data, mock_coordinator)
        device.detail = {"currentMessage": "Old error"}
        device._set_action_error("Protection is temporarily paused.")
        assert device.error == "Protection is temporarily paused."

    def test_device_update_data(self, mock_coordinator, sample_device_data) -> None:
        """Test update_data updates device data."""
        device = Device(sample_device_data, mock_coordinator)
        new_data = {**sample_device_data, "deviceName": "Updated Name"}
        device.update_data(new_data)
        assert device.data == new_data
        assert device.name == "Updated Name"


class TestDeviceRegistry:
    """Tests for device registry create_device."""

    def test_create_litterbox(self, mock_coordinator, sample_device_data) -> None:
        """Test create_device returns LitterBox for LITTER_BOX_599."""
        device = create_device(sample_device_data, mock_coordinator)
        assert isinstance(device, LitterBox)
        assert device.id == "dev123"

    def test_create_feeder(self, mock_coordinator, sample_feeder_data) -> None:
        """Test create_device returns FeederDevice for FEEDER."""
        device = create_device(sample_feeder_data, mock_coordinator)
        assert isinstance(device, FeederDevice)
        assert device.name == "Kitchen Feeder"

    def test_create_scooper(self, mock_coordinator, sample_scooper_data) -> None:
        """Test create_device returns ScooperDevice for SCOOPER."""
        device = create_device(sample_scooper_data, mock_coordinator)
        assert isinstance(device, ScooperDevice)
        assert device.name == "Basement Scooper"

    def test_create_unknown_type_falls_back_to_base(self, mock_coordinator) -> None:
        """Test unknown device type uses base Device class."""
        data = {
            "id": "unknown1",
            "deviceType": "UNKNOWN_TYPE",
            "deviceName": "Unknown",
        }
        device = create_device(data, mock_coordinator)
        assert isinstance(device, Device)
        assert not isinstance(device, LitterBox)
        assert device.type == "UNKNOWN_TYPE"

    def test_create_with_additional_config(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test create_device with AdditionalDeviceConfig."""
        config = AdditionalDeviceConfig(
            mac="AA:BB:CC:DD:EE:FF",
            empty_weight=1.5,
            max_samples_litter=12,
        )
        device = create_device(
            sample_device_data, mock_coordinator, additional_config=config
        )
        assert device.additional_config.mac == "AA:BB:CC:DD:EE:FF"
        assert device.additional_config.empty_weight == 1.5


class TestLitterBox:
    """Tests for LitterBox device."""

    def test_modes_property(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox modes."""
        device = LitterBox(sample_device_data, mock_coordinator)
        modes = device.modes
        assert modes["00"] == "auto"
        assert modes["01"] == "manual"
        assert modes["02"] == "time"

    def test_actions_property(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox actions."""
        device = LitterBox(sample_device_data, mock_coordinator)
        actions = device.actions
        assert "01" in actions
        assert "00" in actions
        assert "Cleaning" in actions.values()
        assert "Pause" in actions.values()

    def test_box_full_levels(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox box full sensitivity levels."""
        device = LitterBox(sample_device_data, mock_coordinator)
        levels = device.box_full_levels
        assert "LEVEL_01" in levels
        assert levels["LEVEL_01"] == "Level 1"

    def test_error_default_normal_operation(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox error defaults to Normal Operation."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {}
        assert device.error == "Normal Operation"

    def test_error_from_detail(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox error from detail."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"currentError": "Litter full"}
        assert device.error == "Litter full"

    def test_litter_remaining_days(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox litter_remaining_days."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"litterCountdown": 5}
        assert device.litter_remaining_days == 5

    def test_knob_status_cleaning_mode(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox knob_status when no knob error."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deviceErrorList": []}
        assert device.knob_status == "Cleaning Mode"

    def test_knob_status_empty_mode(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox knob_status when left_knob_abnormal."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deviceErrorList": [{"errkey": "left_knob_abnormal"}]}
        assert device.knob_status == "Empty Mode"

    def test_garbage_actions(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox garbage_actions property."""
        device = LitterBox(sample_device_data, mock_coordinator)
        actions = device.garbage_actions
        assert actions["00"] == "Change Bag"
        assert actions["01"] == "Reset"

    def test_last_sync_with_timestamp(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox last_sync formats timestamp."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"lastHeartBeatTimestamp": 1700000000000}
        result = device.last_sync
        assert result is not None
        assert "2023" in result or "2024" in result

    def test_last_sync_no_timestamp(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox last_sync returns None when no timestamp."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {}
        assert device.last_sync is None

    def test_garbage_tobe_status_normal(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox garbage_tobe_status when no full error."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deviceErrorList": []}
        assert device.garbage_tobe_status == "Normal"

    def test_garbage_tobe_status_full(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox garbage_tobe_status when garbage full."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deviceErrorList": [{"errkey": "garbage_tobe_full_abnormal"}]}
        assert device.garbage_tobe_status == "Full"

    def test_garbage_attrs(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox garbage_attrs maps garbageStatus."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"garbageStatus": "00"}
        assert device.garbage_attrs()["status"] == "Normal"

        device.detail = {"garbageStatus": "02"}
        assert device.garbage_attrs()["status"] == "Movement Started"

        device.detail = {"garbageStatus": "03"}
        assert device.garbage_attrs()["status"] == "Moving"

    def test_error_attrs(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox error_attrs returns deviceErrorList."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deviceErrorList": [{"errkey": "test"}]}
        attrs = device.error_attrs()
        assert "errors" in attrs
        assert attrs["errors"] == [{"errkey": "test"}]

    def test_box_full_sensitivity_mapped(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox box_full_sensitivity maps level to label."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"boxFullSensitivity": "LEVEL_01"}
        assert device.box_full_sensitivity == "Level 1"

    def test_box_full_sensitivity_attrs(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test LitterBox box_full_sensitivity_attrs."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"boxFullSensitivity": "LEVEL_02"}
        attrs = device.box_full_sensitivity_attrs()
        assert attrs["raw_level"] == "LEVEL_02"

    def test_hass_sensor_structure(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox hass_sensor contains expected keys."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"currentError": "Normal"}
        device.logs = []
        sensor = device.hass_sensor
        assert "state" in sensor
        assert "error" in sensor
        assert "last_log" in sensor
        assert "garbage_tobe_status" in sensor
        assert "litter_weight" in sensor
        assert "litter_remaining_days" in sensor

    def test_hass_select_structure(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox hass_select contains expected keys."""
        device = LitterBox(sample_device_data, mock_coordinator)
        select = device.hass_select
        assert "mode" in select
        assert "action" in select
        assert "garbage" in select
        assert "box_full_sensitivity" in select
        assert select["mode"]["options"] == ["auto", "manual", "time"]


class TestFeederDevice:
    """Tests for FeederDevice."""

    def test_feeder_properties(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice basic properties."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        assert device.id == "feeder1"
        assert device.name == "Kitchen Feeder"
        assert device.type == "FEEDER"

    def test_feeder_weight(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice weight property."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.detail = {"weight": 250}
        assert device.weight == 250

    def test_feeder_error(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice error from detail."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.detail = {"error": "Low food level"}
        assert device.error == "Low food level"

    def test_feeder_error_attrs(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice error_attrs."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.detail = {
            "currentErrorMessage": "Check sensor",
            "currentErrorType": "sensor",
        }
        attrs = device.error_attrs()
        assert attrs["currentErrorMessage"] == "Check sensor"
        assert attrs["currentErrorType"] == "sensor"

    def test_feeder_state(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice state from foodOutStatus."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.detail = {"foodOutStatus": "idle"}
        assert device.state == "idle"

    def test_feeder_state_attrs(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice state_attrs."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.detail = {
            "foodOutStatus": "feeding",
            "autoFillStatus": "ok",
            "keyLockStatus": "unlocked",
        }
        attrs = device.state_attrs()
        assert attrs["work_status"] == "feeding"
        assert attrs["auto_fill_status"] == "ok"
        assert attrs["key_lock_status"] == "unlocked"

    def test_feeder_hass_sensor(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice hass_sensor structure."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.logs = []
        sensor = device.hass_sensor
        assert "state" in sensor
        assert "weight" in sensor
        assert "error" in sensor
        assert "last_log" in sensor

    def test_feeder_hass_button(self, mock_coordinator, sample_feeder_data) -> None:
        """Test FeederDevice hass_button has feed action."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        button = device.hass_button
        assert "feed" in button
        assert button["feed"]["async_press"] == device.food_out


class TestScooperDevice:
    """Tests for ScooperDevice."""

    def test_scooper_properties(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice basic properties."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        assert device.id == "scooper1"
        assert device.name == "Basement Scooper"
        assert device.type == "SCOOPER"

    def test_scooper_modes(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice modes include empty mode."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        modes = device.modes
        assert modes["00"] == "auto"
        assert modes["01"] == "manual"
        assert modes["02"] == "time"
        assert modes["03"] == "empty"

    def test_scooper_actions(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice actions."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        actions = device.actions
        assert actions["00"] == "pause"
        assert actions["01"] == "start"

    def test_scooper_temperature(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice temperature."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {"temperature": "25"}
        assert device.temperature == "25"

    def test_scooper_temperature_default(
        self, mock_coordinator, sample_scooper_data
    ) -> None:
        """Test ScooperDevice temperature defaults to -."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {}
        assert device.temperature == "-"

    def test_scooper_humidity(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice humidity."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {"humidity": "45"}
        assert device.humidity == "45"

    def test_scooper_error_from_current_message(
        self, mock_coordinator, sample_scooper_data
    ) -> None:
        """Test ScooperDevice error from currentMessage."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {"currentMessage": "Sensor fault"}
        assert device.error == "Sensor fault"

    def test_scooper_error_from_data(
        self, mock_coordinator, sample_scooper_data
    ) -> None:
        """Test ScooperDevice error from data currentErrorMessage."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {}
        device.data = {"currentErrorMessage": "Connection lost"}
        assert device.error == "Connection lost"

    def test_scooper_error_action_takes_precedence(
        self, mock_coordinator, sample_scooper_data
    ) -> None:
        """Test ScooperDevice _action_error overrides."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device.detail = {"currentMessage": "Old"}
        device._set_action_error("New error")
        assert device.error == "New error"

    def test_scooper_error_attrs(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice error_attrs contains error_logs."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        attrs = device.error_attrs()
        assert "error_logs" in attrs
        assert isinstance(attrs["error_logs"], list)

    def test_scooper_hass_sensor(self, mock_coordinator, sample_scooper_data) -> None:
        """Test ScooperDevice hass_sensor structure."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        sensor = device.hass_sensor
        assert "state" in sensor
        assert "litter_weight" in sensor
        assert "temperature" in sensor
        assert "humidity" in sensor
        assert "error" in sensor
