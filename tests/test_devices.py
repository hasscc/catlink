"""Tests for CatLink device classes."""

import asyncio
import datetime
import json

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.cat import CatDevice
from custom_components.catlink.devices.c08 import C08Device
from custom_components.catlink.devices.feeder import FeederDevice
from custom_components.catlink.devices.litterbox import LitterBox
from custom_components.catlink.devices.registry import create_device
from custom_components.catlink.devices.scooper import ScooperDevice
from custom_components.catlink.devices.scooper_pro_ultra import ScooperProUltraDevice
from custom_components.catlink.modules.linkvisual import LinkVisualError
from custom_components.catlink.devices.purepro import PureProDevice
from custom_components.catlink.models.additional_cfg import AdditionalDeviceConfig
import pytest


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


@pytest.fixture
def sample_c08_data():
    """Sample C08 device data."""
    return {
        "id": "c08-1",
        "mac": "01:23:45:67:89:AB",
        "model": "Open-X",
        "deviceName": "Bedroom C08",
        "deviceType": "C08",
    }


@pytest.fixture
def sample_pro_ultra_data():
    """Sample Scooper Pro Ultra device data."""
    return {
        "id": "ultra1",
        "mac": "44:72:AC:0D:89:37",
        "model": "ScooperPROUltra",
        "deviceName": "ScooperPROUltra",
        "deviceType": "VISUAL_PRO_ULTRA",
    }


@pytest.fixture
def sample_purepro_data():
    """Sample PurePro device data."""
    return {
        "id": "purepro1",
        "mac": "22:33:44:55:66:77",
        "model": "Pure Pro",
        "deviceName": "Cat Fountain",
        "deviceType": "PUREPRO",
    }


@pytest.fixture
def sample_cat_data():
    """Sample cat device data."""
    return {
        "id": "cat-169004",
        "pet_id": "169004",
        "petName": "Zulu",
        "deviceName": "Zulu",
        "deviceType": "CAT",
        "mac": "cat-169004",
        "model": "STREET CAT",
        "gender": 3,
        "weight": 4.7,
        "summary_simple": {
            "statusDescription": "Data collection in progress",
            "toilet": {"times": 2, "weightAvg": 4.7, "peed": 1, "pood": 1},
            "drink": {"times": 1},
            "diet": {"times": 0, "intakes": "0"},
            "sport": {"activeDuration": 12},
        },
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
        device._set_action_error("Protection is temporarily paused.")  # noqa: SLF001
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

    def test_create_c08(self, mock_coordinator, sample_c08_data) -> None:
        """Test create_device returns C08Device for C08."""
        device = create_device(sample_c08_data, mock_coordinator)
        assert isinstance(device, C08Device)
        assert device.name == "Bedroom C08"

    def test_create_scooper_pro_ultra(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Test create_device returns ScooperProUltraDevice for VISUAL_PRO_ULTRA."""
        device = create_device(sample_pro_ultra_data, mock_coordinator)
        assert isinstance(device, ScooperProUltraDevice)

    def test_create_cat_device(
        self, mock_coordinator, sample_cat_data
    ) -> None:
        """Test create_device returns CatDevice for CAT."""
        device = create_device(sample_cat_data, mock_coordinator)
        assert isinstance(device, CatDevice)
        assert device.name == "Zulu"

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

    def test_last_sync_no_timestamp(self, mock_coordinator, sample_device_data) -> None:
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


class TestLitterBoxAsyncMethods:
    """Tests for LitterBox async methods."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_mode succeeds and updates device detail."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {}
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 0, "data": {}}
        )
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_mode("auto")

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/litterbox/changeMode"
        assert call_args[0][1]["workModel"] == "00"
        assert call_args[0][1]["deviceId"] == "dev123"
        device.update_device_detail.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_invalid_returns_false(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_mode returns False for invalid mode."""
        device = LitterBox(sample_device_data, mock_coordinator)
        result = await device.select_mode("invalid_mode")
        assert result is False

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_api_error_sets_action_error(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_mode sets action error on API failure."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 4007, "msg": "Device busy"}
        )

        result = await device.select_mode("auto")

        assert result is False
        assert "Device busy" in device.error

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_action_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_action succeeds for Cleaning."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_action("Cleaning")

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        assert mock_coordinator.account.request.call_args[0][1]["cmd"] == "01"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_action_garbage_bag_calls_change_bag(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_action with Garbage Bag delegates to changeBag."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.changeBag = AsyncMock(return_value=True)

        result = await device.select_action("Change Garbage Bag")

        assert result is True
        device.changeBag.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_change_bag_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test changeBag succeeds with Change Bag mode."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.changeBag("Change Bag")

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        assert mock_coordinator.account.request.call_args[0][1]["enable"] == "1"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_box_full_sensitivity_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_box_full_sensitivity succeeds."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_box_full_sensitivity("Level 1")

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        assert mock_coordinator.account.request.call_args[0][1]["level"] == "LEVEL_01"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_box_full_sensitivity_invalid_returns_false(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test select_box_full_sensitivity returns False for invalid level."""
        device = LitterBox(sample_device_data, mock_coordinator)
        result = await device.select_box_full_sensitivity("Invalid Level")
        assert result is False

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_reset_litter_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test async_reset_litter calls consumableReset with CAT_LITTER."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.async_reset_litter()

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/device/union/consumableReset"
        assert call_args[0][1]["consumablesType"] == "CAT_LITTER"
        assert call_args[0][1]["deviceId"] == "dev123"
        assert call_args[0][1]["deviceType"] == "LITTER_BOX_599"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_reset_deodorant_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test async_reset_deodorant calls consumableReset with DEODORIZER_02."""
        device = LitterBox(sample_device_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.async_reset_deodorant()

        assert result is not False
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][1]["consumablesType"] == "DEODORIZER_02"

    def test_hass_button_structure(self, mock_coordinator, sample_device_data) -> None:
        """Test LitterBox hass_button contains reset_litter and reset_deodorant."""
        device = LitterBox(sample_device_data, mock_coordinator)
        buttons = device.hass_button
        assert "reset_litter" in buttons
        assert "reset_deodorant" in buttons
        assert buttons["reset_litter"]["name"] == "Reset litter"
        assert buttons["reset_deodorant"]["name"] == "Reset deodorant"


class TestC08Device:
    """Tests for C08Device."""

    def test_modes_property(self, mock_coordinator, sample_c08_data) -> None:
        """Test C08Device modes."""
        device = C08Device(sample_c08_data, mock_coordinator)
        modes = device.modes
        assert modes["00"] == "auto"
        assert modes["01"] == "manual"
        assert modes["02"] == "scheduled"

    def test_litter_type(self, mock_coordinator, sample_c08_data) -> None:
        """Test C08Device litter type mapping."""
        device = C08Device(sample_c08_data, mock_coordinator)
        device.detail = {"litterType": "00"}
        assert device.litter_type == "Bentonite"

    def test_safe_time(self, mock_coordinator, sample_c08_data) -> None:
        """Test C08Device safe time mapping."""
        device = C08Device(sample_c08_data, mock_coordinator)
        device.detail = {"safeTime": "5"}
        assert device.safe_time == "5 min"

    def test_notice_switch_mapping(self, mock_coordinator, sample_c08_data) -> None:
        """Test notice switches map to notice configs."""
        device = C08Device(sample_c08_data, mock_coordinator)
        device.set_notice_configs(
            [{"noticeItem": "LITTERBOX_599_CAT_CAME", "noticeSwitch": True}]
        )
        assert device.notice_cat_came is True
        assert device.notice_box_full is False

    def test_hass_switch_contains_notice(self, mock_coordinator, sample_c08_data) -> None:
        """Test C08Device hass_switch includes notice entries."""
        device = C08Device(sample_c08_data, mock_coordinator)
        switches = device.hass_switch
        assert "notice_cat_came" in switches
        assert switches["notice_cat_came"]["name"] == "Notice: Cat came"

    def test_hass_select_structure(self, mock_coordinator, sample_c08_data) -> None:
        """Test C08Device hass_select contains expected keys."""
        device = C08Device(sample_c08_data, mock_coordinator)
        selects = device.hass_select
        assert "mode" in selects
        assert "action" in selects
        assert "litter_type" in selects
        assert "safe_time" in selects


class TestC08DeviceAsyncMethods:
    """Tests for C08Device async methods."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_c08_endpoint(
        self, mock_coordinator, sample_c08_data
    ) -> None:
        """Test update_device_detail uses C08 info endpoint."""
        device = C08Device(sample_c08_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={"data": {"deviceInfo": {"workStatus": "00"}}}
        )
        device.async_refresh_c08_extras = AsyncMock()

        result = await device.update_device_detail()

        assert result["workStatus"] == "00"
        mock_coordinator.account.request.assert_called_once_with(
            "token/litterbox/info/c08", {"deviceId": "c08-1"}
        )
        device.async_refresh_c08_extras.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_action_v3(
        self, mock_coordinator, sample_c08_data
    ) -> None:
        """Test select_action uses v3 command payload."""
        device = C08Device(sample_c08_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_action("Clean: start")

        assert result is True
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/litterbox/actionCmd/v3"
        assert call_args[0][1]["action"] == "RUN"
        assert call_args[0][1]["behavior"] == "CLEAN"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_litter_type(
        self, mock_coordinator, sample_c08_data
    ) -> None:
        """Test select_litter_type sends litterType setting."""
        device = C08Device(sample_c08_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_litter_type("Bentonite")

        assert result is True
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/litterbox/catLitterSetting"
        assert call_args[0][1]["litterType"] == "00"


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


class TestFeederDeviceAsyncMethods:
    """Tests for FeederDevice async methods."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_food_out_success(self, mock_coordinator, sample_feeder_data) -> None:
        """Test food_out succeeds and updates device detail."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.food_out()

        assert result is not False
        mock_coordinator.account.request.assert_called_once()
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/device/feeder/foodOut"
        assert call_args[0][1]["footOutNum"] == 1
        assert call_args[0][1]["deviceId"] == "feeder1"
        device.update_device_detail.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_food_out_custom_portions(self, mock_coordinator, sample_feeder_data) -> None:
        """Test food_out uses custom portion value."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device.portions = 3
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        await device.food_out()

        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][1]["footOutNum"] == 3

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_food_out_api_error_sets_action_error(
        self, mock_coordinator, sample_feeder_data
    ) -> None:
        """Test food_out sets action error on API failure."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 500, "msg": "Device busy"}
        )

        result = await device.food_out()

        assert result is False
        assert "Device busy" in (device._action_error or "")  # noqa: SLF001

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_success(
        self, mock_coordinator, sample_feeder_data
    ) -> None:
        """Test FeederDevice update_device_detail parses response."""
        device = FeederDevice(sample_feeder_data, mock_coordinator)
        device._handle_listeners = MagicMock()  # noqa: SLF001
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "deviceInfo": {
                        "foodOutStatus": "idle",
                        "weight": 250,
                    }
                }
            }
        )

        result = await device.update_device_detail()

        assert result["foodOutStatus"] == "idle"
        assert result["weight"] == 250
        assert device.detail == result
        device._handle_listeners.assert_called_once()  # noqa: SLF001


class TestScooperDeviceAsyncMethods:
    """Tests for ScooperDevice async methods."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_logs_fetches_from_api(
        self, mock_coordinator, sample_scooper_data
    ) -> None:
        """Test ScooperDevice update_logs calls correct API."""
        device = ScooperDevice(sample_scooper_data, mock_coordinator)
        device._handle_listeners = MagicMock()  # noqa: SLF001
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "scooperLogTop5": [
                        {"time": "10:00", "event": "Cleaning"},
                    ]
                }
            }
        )

        result = await device.update_logs()

        assert len(result) == 1
        mock_coordinator.account.request.assert_called_once_with(
            "token/device/scooper/stats/log/top5", {"deviceId": "scooper1"}
        )


class TestScooperProUltraDevice:
    """Tests for ScooperProUltraDevice."""

    def test_name_is_plain(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The device name is the user's name, without a support suffix."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        assert device.name == "ScooperPROUltra"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_brief_info(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Test update_device_detail uses visualScooper briefInfo."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "deviceInfo": {
                        "litterCountdown": 14,
                        "deodorantCountdown": 0,
                        "totalCleanTimes": "3",
                    }
                }
            }
        )

        result = await device.update_device_detail()

        assert result["litterCountdown"] == 14
        assert result["totalCleanTimes"] == "3"
        apis = [c.args[0] for c in mock_coordinator.account.request.call_args_list]
        assert apis == [
            "token/visualScooper/briefInfo",
            "token/litterbox/stats/toiletDataNow",
        ]

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_logs_timeline_v2(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Test update_logs uses timeline/v2 endpoint."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "records": [
                        {"time": "11:05", "event": "Auto-clean"},
                    ]
                }
            }
        )

        result = await device.update_logs()

        assert result[0]["event"] == "Auto-clean"
        assert (
            mock_coordinator.account.request.call_args[0][0]
            == "token/litterbox/stats/log/timeline/v2"
        )


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
        device._set_action_error("New error")  # noqa: SLF001
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


class TestPureProDevice:
    """Tests for PureProDevice."""

    def test_purepro_properties(self, mock_coordinator, sample_purepro_data) -> None:
        """Test PureProDevice basic properties."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        assert device.id == "purepro1"
        assert device.name == "Cat Fountain"
        assert device.type == "PUREPRO"

    def test_purepro_modes(self, mock_coordinator, sample_purepro_data) -> None:
        """Test PureProDevice modes."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        modes = device.modes
        assert modes["CONTINUOUS_SPRING"] == "Flowing mode"
        assert modes["INTERMITTENT_SPRING"] == "Eco-mode"
        assert modes["INDUCTION_SPRING"] == "Smart mode"

    def test_purepro_hass_sensor(self, mock_coordinator, sample_purepro_data) -> None:
        """Test PureProDevice hass_sensor structure."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        sensor = device.hass_sensor
        assert "state" in sensor
        assert "last_log" in sensor
        assert "online" in sensor


class TestPureProDeviceAsyncMethods:
    """Tests for PureProDevice async methods."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_purepro(
        self, mock_coordinator, sample_purepro_data
    ) -> None:
        """Test update_device_detail uses PurePro detail endpoint."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={"data": {"workStatus": "00"}}
        )

        result = await device.update_device_detail()

        assert result["workStatus"] == "00"
        mock_coordinator.account.request.assert_called_once_with(
            "token/device/purepro/detail", {"deviceId": "purepro1"}
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_purepro(
        self, mock_coordinator, sample_purepro_data
    ) -> None:
        """Test select_mode uses PurePro runMode endpoint."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        device.update_device_detail = AsyncMock(return_value={})

        result = await device.select_mode("Flowing mode")

        assert result is True
        call_args = mock_coordinator.account.request.call_args
        assert call_args[0][0] == "token/device/purepro/runMode"
        assert call_args[0][1]["runMode"] == "CONTINUOUS_SPRING"
        assert call_args[0][1]["deviceId"] == "purepro1"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_logs_purepro(
        self, mock_coordinator, sample_purepro_data
    ) -> None:
        """Test update_logs uses PurePro stats/log/top5 endpoint."""
        device = PureProDevice(sample_purepro_data, mock_coordinator)
        mock_coordinator.account.request = AsyncMock(
            return_value={"data": {"pureLogTop5": [{"event": "Cat drank water"}]}}
        )

        result = await device.update_logs()

        assert len(result) == 1
        assert result[0]["event"] == "Cat drank water"
        mock_coordinator.account.request.assert_called_once_with(
            "token/device/purepro/stats/log/top5", {"deviceId": "purepro1"}
        )


class TestScooperProUltraBriefInfo:
    """Tests for parsing the Scooper Pro Ultra's briefInfo."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_null_string_fields_fall_back_to_raw(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Null currentMessage/quietTimes don't wipe the detail (real API response)."""
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "deviceInfo": {
                        "currentMessage": None,
                        "quietTimes": None,
                        "litterCountdown": 14,
                        "deodorantCountdown": 3,
                        "totalCleanTimes": "7",
                    }
                }
            }
        )
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        await device.update_device_detail()

        assert device.litter_remaining_days == 14
        assert device.deodorant_countdown == 3
        assert device.total_clean_time == 7


class TestScooperProUltraProperties:
    """Tests for the Scooper Pro Ultra's Aliyun thing properties."""

    BRIEF_INFO = {"data": {"deviceInfo": {"litterCountdown": 14}}}

    def _device(self, mock_coordinator, sample_pro_ultra_data):
        mock_coordinator.account.request = AsyncMock(return_value=self.BRIEF_INFO)
        if not isinstance(mock_coordinator.account.linkvisual.async_is_online, AsyncMock):
            mock_coordinator.account.linkvisual.async_is_online = AsyncMock(
                return_value=True
            )
        return ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_reads_properties(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A detail update also reads the thing properties."""
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(
            return_value={"CatLitterBalance": 75}
        )
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        await device.update_device_detail()

        assert device.detail["litterCountdown"] == 14
        assert device.properties == {"CatLitterBalance": 75}
        mock_coordinator.account.linkvisual.async_get_properties.assert_awaited_once_with(
            "iot-1"
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_property_failure_keeps_last_values(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """If Aliyun fails, briefInfo still updates and the last properties are kept."""
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(
            side_effect=[{"CatLitterBalance": 75}, LinkVisualError("down")]
        )
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        await device.update_device_detail()

        await device.update_device_detail()

        assert device.detail["litterCountdown"] == 14
        assert device.properties == {"CatLitterBalance": 75}

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_no_iot_id_skips_properties(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A device without an iotId never calls Aliyun."""
        mock_coordinator.account.request = AsyncMock(return_value=self.BRIEF_INFO)
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock()
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        await device.update_device_detail()

        assert device.properties == {}
        mock_coordinator.account.linkvisual.async_get_properties.assert_not_awaited()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_update_device_detail_reads_online(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A detail update also checks whether the device is connected."""
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(
            return_value={}
        )
        mock_coordinator.account.linkvisual.async_is_online = AsyncMock(
            return_value=False
        )
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        await device.update_device_detail()

        assert device.online is False
        mock_coordinator.account.linkvisual.async_is_online.assert_awaited_once_with(
            "iot-1"
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_online_failure_keeps_last_value(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """If the status query fails, the last known value is kept."""
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(
            return_value={}
        )
        mock_coordinator.account.linkvisual.async_is_online = AsyncMock(
            side_effect=[True, LinkVisualError("down")]
        )
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        await device.update_device_detail()

        await device.update_device_detail()

        assert device.online is True

    def test_online_binary_sensor(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A device with an iotId exposes a diagnostic connectivity sensor."""
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )

        sensors = device.hass_binary_sensor

        assert "online" in sensors
        assert "available" not in sensors["online"]
        assert sensors["online"]["class"] == BinarySensorDeviceClass.CONNECTIVITY
        assert sensors["online"]["entity_category"] == EntityCategory.DIAGNOSTIC

    def test_no_online_sensor_without_iot_id(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Without an iotId there is nothing to check."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        assert device.hass_binary_sensor == {}

    def test_no_selects(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The inherited mode/action selects (with no options) are not exposed."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        assert device.hass_select == {}


# Values as the real device reports them.
LIVE_PROPERTIES = {
    "RunStatus": "runStatus=0&biz=1",
    "CatLitterBalance": 75,
    "GarbageBoxStatus": "installed=1&status=0",
    "AbnormalState": "0",
    "CurrentModel": 0,
    "WifiSignal": 78,
    "WiFiRSSI": -54,
    "Band": "5G",
    "FirmwareVersion": "9.00.26_01.01.52",
    "DeviceWeihgt": 5664,
    "ExtInfo": "catSatus=1&weihtvalue=5364&usetime=100&biz=2",
    "DelayTimeOfClean": 2,
    "CatLitterFlatTime": 15,
    "LimitWhenFull": 10,
    "ContinuousClean": 0,
    "SoftStoolMode": 0,
    "ChildLock": 0,
    "PromptSoundSwitch": 1,
    "BroadcastSwitch": 1,
    "SleepMode": 0,
}


class TestScooperProUltraLiveSensors:
    """Tests for the sensors read from Aliyun thing properties."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        return device

    def test_values_from_real_device(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The real device's values map to readable states."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert device.state == "idle"
        assert device.litter_level == 75
        assert device.waste_bin_installed is True
        assert device.waste_bin == "empty"
        assert device.fault == "none"
        assert device.mode == "auto"
        assert device.wifi_signal == 78
        assert device.wifi_rssi == -54
        assert device.wifi_band == "5G"
        assert device.firmware_version == "9.00.26_01.01.52"
        assert device.scale_weight == 5664
        assert device.state_attrs()["ext_info"] == LIVE_PROPERTIES["ExtInfo"]
        assert device.clean_delay == 2
        assert device.leveling_level == 4
        assert device.bin_full_sensitivity == 3

    @pytest.mark.parametrize(
        ("run_status", "expected"),
        [
            ("runStatus=1&biz=1", "cleaning"),
            ("runStatus=1&biz=2", "emptying"),
            ("runStatus=1&biz=3", "leveling"),
            ("runStatus=1&biz=9", "running"),
            ("runStatus=2&biz=1", "cancelling"),
            ("runStatus=3&biz=1", "paused"),
            ("runStatus=4&biz=3", "paused"),
            ("runStatus=7&biz=1", "code_7"),
            ("", None),
        ],
    )
    def test_state(
        self, mock_coordinator, sample_pro_ultra_data, run_status, expected
    ) -> None:
        """RunStatus maps to the job while running, else to the run state."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus=run_status
        )

        assert device.state == expected

    @pytest.mark.parametrize(
        ("box", "installed", "level"),
        [
            ("installed=1&status=1", True, "half_full"),
            ("installed=1&status=2", True, "full"),
            ("installed=0&status=0", False, "empty"),
            (None, None, None),
        ],
    )
    def test_waste_bin(
        self, mock_coordinator, sample_pro_ultra_data, box, installed, level
    ) -> None:
        """GarbageBoxStatus gives bin presence and fill level."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, GarbageBoxStatus=box
        )

        assert device.waste_bin_installed is installed
        assert device.waste_bin == level

    @pytest.mark.parametrize(
        ("code", "expected"),
        [("1", "anti_pinch"), ("6", "motor_blocked"), ("7", "weight_protection"), ("2", "cat_inside"), ("3", "code_3")],
    )
    def test_fault(self, mock_coordinator, sample_pro_ultra_data, code, expected) -> None:
        """Known fault codes get names; unknown ones keep their code."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, AbnormalState=code)

        assert device.fault == expected

    @pytest.mark.parametrize(("model", "expected"), [(1, "manual"), (2, "scheduled"), (5, "code_5")])
    def test_mode(self, mock_coordinator, sample_pro_ultra_data, model, expected) -> None:
        """CurrentModel maps to auto/manual/scheduled."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, CurrentModel=model)

        assert device.mode == expected

    @pytest.mark.parametrize(
        ("online", "props", "expected"),
        [(True, True, True), (False, True, False), (None, True, False), (True, False, False)],
    )
    def test_live_available(
        self, mock_coordinator, sample_pro_ultra_data, online, props, expected
    ) -> None:
        """Live values only count while Aliyun sees the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        device.iot_online = online
        if not props:
            device.properties = {}

        assert device.live_available() is expected

    def test_live_entities_use_availability(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Every property-based entity is tied to live_available; history ones aren't."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        sensors = device.hass_sensor

        live = [
            "state", "litter_level", "waste_bin", "fault",
            "wifi_signal", "wifi_rssi", "wifi_band", "firmware_version", "scale_weight",
        ]
        for key in live:
            assert sensors[key]["available"] == device.live_available, key
        for key in [
            "last_log", "litter_remaining_days", "deodorant_countdown", "total_clean_time",
            "last_visit", "last_visit_weight", "last_visit_duration", "visits_today",
        ]:
            assert "available" not in sensors[key], key
        assert (
            device.hass_binary_sensor["waste_bin_installed"]["available"]
            == device.live_available
        )

    def test_no_live_sensors_without_iot_id(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Without an iotId only the CatLink sensors exist."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        assert list(device.hass_sensor) == [
            "last_log", "litter_remaining_days", "deodorant_countdown", "total_clean_time",
            "last_visit", "last_visit_weight", "last_visit_duration", "visits_today",
        ]


class TestScooperProUltraSwitches:
    """Tests for the switches written as Aliyun thing properties."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, "MicSwitch": 1, "Watermark": 1, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def test_switches_read_their_property(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Each switch reads its 0/1 property and needs the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        switches = device.hass_switch

        expected = {
            "key_beep": True,
            "child_lock": False,
            "continuous_clean": False,
            "soft_stool_mode": False,
            "voice_announcements": True,
            "microphone": True,
            "video_watermark": True,
            "camera_sleep": False,
            "do_not_disturb": None,  # from briefInfo, not loaded here
            "indicator_light": None,  # not in the recorded values
        }
        assert {key: sw["is_on"]() for key, sw in switches.items()} == expected
        for key, sw in switches.items():
            assert sw["available"] == device.live_available, key

    @pytest.mark.parametrize(
        ("key", "prop"),
        [
            ("key_beep", "PromptSoundSwitch"),
            ("child_lock", "ChildLock"),
            ("continuous_clean", "ContinuousClean"),
            ("soft_stool_mode", "SoftStoolMode"),
            ("voice_announcements", "BroadcastSwitch"),
            ("microphone", "MicSwitch"),
            ("video_watermark", "Watermark"),
            ("camera_sleep", "SleepMode"),
        ],
    )
    async def test_turn_on_and_off_write_property(
        self, mock_coordinator, sample_pro_ultra_data, key, prop
    ) -> None:
        """Turning a switch on/off writes 1/0 and updates the local copy."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        switch = device.hass_switch[key]
        set_properties = mock_coordinator.account.linkvisual.async_set_properties

        assert await switch["async_turn_on"]() is True
        assert switch["is_on"]() is True
        assert await switch["async_turn_off"]() is True
        assert switch["is_on"]() is False
        assert [c.args for c in set_properties.await_args_list] == [
            ("iot-1", {prop: 1}),
            ("iot-1", {prop: 0}),
        ]

    @pytest.mark.parametrize("key", ["continuous_clean", "soft_stool_mode"])
    async def test_idle_only_settings_refused_while_running(
        self, mock_coordinator, sample_pro_ultra_data, key
    ) -> None:
        """Like the app, these can't be changed while a job runs."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )

        with pytest.raises(HomeAssistantError, match="cleaning"):
            await device.hass_switch[key]["async_turn_on"]()
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

    async def test_other_settings_allowed_while_running(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Settings without that rule can be changed while a job runs."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )

        assert await device.hass_switch["child_lock"]["async_turn_on"]() is True

    async def test_failed_write_reports_error(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A rejected write returns False, keeps the old value and sets the error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_set_properties.side_effect = (
            LinkVisualError("Property update failed: 6205 not writable")
        )

        assert await device.hass_switch["key_beep"]["async_turn_off"]() is False

        assert device.hass_switch["key_beep"]["is_on"]() is True
        assert "6205" in device.error

    def test_no_switches_without_iot_id(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Without an iotId there is nothing to write to."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        assert device.hass_switch == {}


class TestScooperProUltraActions:
    """Tests for the action buttons and the mode select."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def _sent(self, mock_coordinator) -> list:
        return [
            c.args[1]
            for c in mock_coordinator.account.linkvisual.async_set_properties.await_args_list
        ]

    def test_buttons(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """All action buttons exist and need the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        buttons = device.hass_button

        assert list(buttons) == [
            "clean", "empty_litter", "level_litter", "pause", "resume", "cancel",
            "reset_litter", "reset_deodorant", "reboot",
        ]
        for key in ["clean", "empty_litter", "level_litter", "pause", "resume", "cancel"]:
            assert buttons[key]["available"] == device.live_available, key

    @pytest.mark.parametrize(
        ("key", "biz"), [("clean", "1"), ("empty_litter", "2"), ("level_litter", "3")]
    )
    async def test_start_job(
        self, mock_coordinator, sample_pro_ultra_data, key, biz
    ) -> None:
        """Starting a job sends runStatus=1 with its biz, as the app does."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_button[key]["async_press"]() is True

        assert self._sent(mock_coordinator) == [{"RunStatus": f"runStatus=1&biz={biz}"}]
        assert device.state in ("cleaning", "emptying", "leveling")

    @pytest.mark.parametrize(
        ("props", "match"),
        [
            ({"RunStatus": "runStatus=1&biz=3"}, "leveling, not idle"),
            ({"AbnormalState": "1"}, "anti_pinch"),
            ({"AbnormalState": "6"}, "motor_blocked"),
            ({"AbnormalState": "7"}, "weight_protection"),
            ({"GarbageBoxStatus": "installed=0&status=0"}, "not installed"),
            ({"GarbageBoxStatus": "installed=1&status=2"}, "full"),
        ],
    )
    async def test_start_job_refused(
        self, mock_coordinator, sample_pro_ultra_data, props, match
    ) -> None:
        """Jobs are refused where the app refuses or asks for confirmation."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, **props)

        with pytest.raises(HomeAssistantError, match=match):
            await device.hass_button["clean"]["async_press"]()
        assert self._sent(mock_coordinator) == []

    async def test_start_job_allowed_with_half_full_bin(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A half-full bin only gets a warning in the app, so it's allowed."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data,
            GarbageBoxStatus="installed=1&status=1",
        )

        assert await device.hass_button["clean"]["async_press"]() is True

    async def test_pause_resume_cancel(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Pause, resume and cancel keep the running job's biz."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=2"
        )
        buttons = device.hass_button

        await buttons["pause"]["async_press"]()
        assert device.state == "paused"
        await buttons["resume"]["async_press"]()
        assert device.state == "emptying"
        await buttons["cancel"]["async_press"]()
        assert device.state == "cancelling"
        assert self._sent(mock_coordinator) == [
            {"RunStatus": "runStatus=3&biz=2"},
            {"RunStatus": "runStatus=1&biz=2"},
            {"RunStatus": "runStatus=2&biz=2"},
        ]

    async def test_cancel_paused_job(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A paused job can be cancelled."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=4&biz=1"
        )

        await device.hass_button["cancel"]["async_press"]()

        assert self._sent(mock_coordinator) == [{"RunStatus": "runStatus=2&biz=1"}]

    @pytest.mark.parametrize("key", ["pause", "resume", "cancel"])
    async def test_nothing_to_control_when_idle(
        self, mock_coordinator, sample_pro_ultra_data, key
    ) -> None:
        """Pause, resume and cancel need a job."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match="idle"):
            await device.hass_button[key]["async_press"]()
        assert self._sent(mock_coordinator) == []

    async def test_resume_refused_on_fault(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Resuming moves the device, so the same checks as starting apply."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data,
            RunStatus="runStatus=3&biz=1", AbnormalState="6",
        )

        with pytest.raises(HomeAssistantError, match="motor_blocked"):
            await device.hass_button["resume"]["async_press"]()

    async def test_pause_allowed_on_fault(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Stopping is always allowed."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data,
            RunStatus="runStatus=1&biz=1", AbnormalState="6",
        )

        assert await device.hass_button["pause"]["async_press"]() is True

    def test_mode_select(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The mode select lists the three modes."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        select = device.hass_select["mode"]

        assert select["options"] == ["auto", "manual", "scheduled"]
        assert select["available"] == device.live_available
        assert "state_attrs" not in select
        assert device.mode == "auto"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_calls_change_mode(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Changing the mode posts visualScooper/changeMode with workModel 0/1/2."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})

        assert await device.async_select_mode("scheduled") is True

        mock_coordinator.account.request.assert_awaited_once_with(
            "token/visualScooper/changeMode",
            {"deviceId": "ultra1", "workModel": "2"},
            "POST",
        )
        assert device.mode == "scheduled"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_select_mode_api_error(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A CatLink error keeps the old mode and sets the device error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 1, "msg": "device busy"}
        )

        assert await device.async_select_mode("manual") is False

        assert device.mode == "auto"
        assert "device busy" in device.error

    async def test_select_mode_refused_while_running(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Like the app, the mode can't change while a job runs."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )
        mock_coordinator.account.request = AsyncMock()

        with pytest.raises(HomeAssistantError, match="cleaning"):
            await device.async_select_mode("manual")
        mock_coordinator.account.request.assert_not_awaited()


class TestScooperProUltraCleanDelay:
    """Tests for the clean delay number."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def test_number(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The number covers the app's 1-30 minute range and needs the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        number = device.hass_number["clean_delay"]

        assert (number["min"], number["max"], number["step"]) == (1, 30, 1)
        assert number["unit"] == "min"
        assert number["available"] == device.live_available
        assert device.clean_delay == 2

    def test_no_number_without_iot_id(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """No number without an Aliyun device."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        assert device.hass_number == {}

    async def test_set(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The value is written as whole minutes, as the app does."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_number["clean_delay"]["async_set_value"](5.0) is True

        mock_coordinator.account.linkvisual.async_set_properties.assert_awaited_once_with(
            "iot-1", {"DelayTimeOfClean": 5}
        )
        assert device.clean_delay == 5

    async def test_set_while_running(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """The app doesn't block this during a job, so neither do we."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )

        assert await device.async_set_clean_delay(4) is True

    @pytest.mark.parametrize("value", [0, 31])
    async def test_out_of_range(
        self, mock_coordinator, sample_pro_ultra_data, value
    ) -> None:
        """Values outside the app's picker are refused."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match="1-30"):
            await device.async_set_clean_delay(value)
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

    async def test_soft_stool_minimum(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """With soft-stool mode on, less than 10 minutes is refused; 10 is fine."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, SoftStoolMode=1)

        with pytest.raises(HomeAssistantError, match="at least 10"):
            await device.async_set_clean_delay(9)
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

        assert await device.async_set_clean_delay(10) is True

    async def test_set_failure(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A failed write keeps the old value and sets the device error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_set_properties.side_effect = (
            LinkVisualError("device offline")
        )

        assert await device.async_set_clean_delay(6) is False
        assert device.clean_delay == 2
        assert "device offline" in device.error


class TestScooperProUltraLevelingLevel:
    """Tests for the litter leveling level number (CatLitterFlatTime)."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def test_number(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Levels 1-4 like the app's picker; the raw seconds are an attribute."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        number = device.hass_number["leveling_level"]

        assert (number["min"], number["max"], number["step"]) == (1, 4, 1)
        assert number["available"] == device.live_available
        assert number["state_attrs"]() == {"leveling_time": 15}
        assert device.leveling_level == 4

    @pytest.mark.parametrize(
        ("seconds", "level"),
        [(0, 1), (9, 1), (10, 2), (11, 2), (12, 3), (13, 3), (14, 4), (15, 4), (30, 4), (None, None)],
    )
    def test_level_from_seconds(
        self, mock_coordinator, sample_pro_ultra_data, seconds, level
    ) -> None:
        """Seconds map to levels with the app's thresholds (<=9, <=11, <=13, else 4)."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, CatLitterFlatTime=seconds
        )
        assert device.leveling_level == level

    @pytest.mark.parametrize(("level", "seconds"), [(1, 9), (2, 11), (3, 13), (4, 15)])
    async def test_set(
        self, mock_coordinator, sample_pro_ultra_data, level, seconds
    ) -> None:
        """A level is written as the app writes it: (level - 1) * 2 + 9 seconds."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_number["leveling_level"]["async_set_value"](float(level)) is True

        mock_coordinator.account.linkvisual.async_set_properties.assert_awaited_once_with(
            "iot-1", {"CatLitterFlatTime": seconds}
        )
        assert device.leveling_level == level

    async def test_set_while_running(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """The app only checks that the device is online, so a job doesn't block it."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=3"
        )
        assert await device.async_set_leveling_level(2) is True

    @pytest.mark.parametrize("value", [0, 5])
    async def test_out_of_range(
        self, mock_coordinator, sample_pro_ultra_data, value
    ) -> None:
        """Levels outside 1-4 are refused."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match="1-4"):
            await device.async_set_leveling_level(value)
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

    async def test_set_failure(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A failed write keeps the old level and sets the device error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_set_properties.side_effect = (
            LinkVisualError("device offline")
        )

        assert await device.async_set_leveling_level(1) is False
        assert device.leveling_level == 4
        assert "device offline" in device.error


class TestScooperProUltraBinFullSensitivity:
    """Tests for the bin-full detection sensitivity number (LimitWhenFull)."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def test_number(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Levels 1-4 like the app's picker; the raw value is an attribute."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        number = device.hass_number["bin_full_sensitivity"]

        assert (number["min"], number["max"], number["step"]) == (1, 4, 1)
        assert number["available"] == device.live_available
        assert number["state_attrs"]() == {"limit_when_full": 10}
        assert device.bin_full_sensitivity == 3

    @pytest.mark.parametrize(
        ("value", "level"),
        [(0, 1), (4, 1), (5, 2), (10, 3), (15, 4), (20, 4), (-5, 1), (None, None)],
    )
    def test_level_from_value(
        self, mock_coordinator, sample_pro_ultra_data, value, level
    ) -> None:
        """The value reads as value / 5 + 1 like the app, kept within 1-4."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, LimitWhenFull=value)
        assert device.bin_full_sensitivity == level

    @pytest.mark.parametrize(("level", "value"), [(1, 0), (2, 5), (3, 10), (4, 15)])
    async def test_set(
        self, mock_coordinator, sample_pro_ultra_data, level, value
    ) -> None:
        """A level is written as the app writes it: (level - 1) * 5."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert (
            await device.hass_number["bin_full_sensitivity"]["async_set_value"](float(level))
            is True
        )

        mock_coordinator.account.linkvisual.async_set_properties.assert_awaited_once_with(
            "iot-1", {"LimitWhenFull": value}
        )
        assert device.bin_full_sensitivity == level

    async def test_set_while_running(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """The app only checks that the device is online, so a job doesn't block it."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )
        assert await device.async_set_bin_full_sensitivity(2) is True

    @pytest.mark.parametrize("value", [0, 5])
    async def test_out_of_range(
        self, mock_coordinator, sample_pro_ultra_data, value
    ) -> None:
        """Levels outside 1-4 are refused."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match="1-4"):
            await device.async_set_bin_full_sensitivity(value)
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

    async def test_set_failure(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A failed write keeps the old level and sets the device error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_set_properties.side_effect = (
            LinkVisualError("device offline")
        )

        assert await device.async_set_bin_full_sensitivity(1) is False
        assert device.bin_full_sensitivity == 3
        assert "device offline" in device.error


class TestScooperProUltraResets:
    """Tests for the litter and deodorant reset buttons."""

    def _device(self, mock_coordinator, sample_pro_ultra_data):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = dict(LIVE_PROPERTIES)
        device.iot_online = True
        device.update_device_detail = AsyncMock(return_value={})
        return device

    def test_buttons_always_available(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """The app resets without checking the device, so offline doesn't matter."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        device.iot_online = False

        for key in ("reset_litter", "reset_deodorant"):
            assert "available" not in device.hass_button[key]

    @pytest.mark.parametrize(
        ("key", "api"),
        [
            ("reset_litter", "token/visualScooper/litter/reset"),
            ("reset_deodorant", "token/visualScooper/deodorant/reset"),
        ],
    )
    async def test_reset(
        self, mock_coordinator, sample_pro_ultra_data, key, api
    ) -> None:
        """Each button posts its reset with the device id, then refreshes briefInfo."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 0, "data": None}
        )

        assert await device.hass_button[key]["async_press"]() is True

        mock_coordinator.account.request.assert_awaited_once_with(
            api, {"deviceId": "ultra1"}, "POST"
        )
        device.update_device_detail.assert_awaited_once()

    async def test_reset_error(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A CatLink error sets the device error and skips the refresh."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 1, "msg": "no permission"}
        )

        assert await device.async_reset_counter("reset_deodorant") is False

        assert "no permission" in device.error
        device.update_device_detail.assert_not_awaited()


class TestScooperProUltraVisitsToday:
    """Tests for today's visits (litterbox/stats/toiletDataNow)."""

    # Shape of the real response: totalCount is a number, the per-cat counts
    # are strings.
    TOILET_DATA = {
        "returnCode": 0,
        "msg": "success",
        "data": {
            "list": [
                {"petId": "4499", "petName": "Mia", "petAvatar": "", "totalCounts": "4", "datePoint": None},
                {"petId": "4500", "petName": "Leo", "petAvatar": "", "totalCounts": "5", "datePoint": None},
            ],
            "totalCount": 9.0,
        },
        "success": True,
    }

    def _device(self, mock_coordinator, sample_pro_ultra_data, response):
        mock_coordinator.account.request = AsyncMock(return_value=response)
        return ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

    def test_sensor(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A daily counter, kept as long-term statistics; needs no Aliyun device."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        sensor = device.hass_sensor["visits_today"]

        assert sensor["state_class"] == "total_increasing"
        assert sensor["unit"] == "visits"
        assert "available" not in sensor
        assert device.visits_today is None
        assert device.visits_today_attrs() == {"cats": []}

    async def test_update(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The total and the per-cat counts are read as the app reads them."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, self.TOILET_DATA)

        await device.update_toilet_today()

        mock_coordinator.account.request.assert_awaited_once_with(
            "token/litterbox/stats/toiletDataNow", {"deviceId": "ultra1"}
        )
        assert device.visits_today == 9
        assert device.visits_today_attrs() == {
            "cats": [
                {"pet_id": "4499", "name": "Mia", "visits": 4},
                {"pet_id": "4500", "name": "Leo", "visits": 5},
            ]
        }

    async def test_no_visits(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """No visits yet today: zero and an empty list."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data,
            {"returnCode": 0, "data": {"totalCount": "0", "list": []}},  # string too
        )

        await device.update_toilet_today()

        assert device.visits_today == 0
        assert device.visits_today_attrs() == {"cats": []}

    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"returnCode": 1, "msg": "server busy"},
            {"returnCode": 0, "data": None},
        ],
    )
    async def test_failure_keeps_last_values(
        self, mock_coordinator, sample_pro_ultra_data, response
    ) -> None:
        """A failed or empty answer keeps the last counts."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, self.TOILET_DATA)
        await device.update_toilet_today()
        mock_coordinator.account.request = AsyncMock(return_value=response)

        await device.update_toilet_today()

        assert device.visits_today == 9

    def test_bad_values(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Unparseable counts read as unknown instead of failing."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        device.toilet_today = {
            "totalCount": None,
            "list": [{"petId": "1", "petName": "X", "totalCounts": ""}, "junk"],
        }

        assert device.visits_today is None
        assert device.visits_today_attrs() == {
            "cats": [{"pet_id": "1", "name": "X", "visits": None}]
        }


class TestScooperProUltraIndicatorLight:
    """Tests for the indicator light switch (IndicatorLight)."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    @pytest.mark.parametrize(("value", "on"), [(0, False), (1, True), (2, True), (None, None)])
    def test_state(self, mock_coordinator, sample_pro_ultra_data, value, on) -> None:
        """Like the app, any non-zero value is on."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, IndicatorLight=value)
        switch = device.hass_switch["indicator_light"]

        assert switch["available"] == device.live_available
        assert switch["is_on"]() is on

    async def test_turn_on_off(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """On writes 1 and off writes 0, as the app does."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, IndicatorLight=0)
        switch = device.hass_switch["indicator_light"]

        assert await switch["async_turn_on"]() is True
        assert device.indicator_light_on() is True
        assert await switch["async_turn_off"]() is True

        sent = [
            c.args[1]
            for c in mock_coordinator.account.linkvisual.async_set_properties.await_args_list
        ]
        assert sent == [{"IndicatorLight": 1}, {"IndicatorLight": 0}]


class TestScooperProUltraDoNotDisturb:
    """Tests for do not disturb (REST visualScooper/quietMode)."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **detail):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = dict(LIVE_PROPERTIES)
        device.iot_online = True
        # The real briefInfo sends both as null until DND has been set.
        device.detail = {"quietEnable": None, "quietTimes": None, **detail}
        mock_coordinator.account.request = AsyncMock(return_value={"returnCode": 0})
        return device

    def _posted(self, mock_coordinator) -> list:
        return [c.args[1] for c in mock_coordinator.account.request.await_args_list]

    def test_entities(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A switch and two times, all needing the device online like the app."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, quietEnable=True, quietTimes="22:30-06:00"
        )

        switch = device.hass_switch["do_not_disturb"]
        assert switch["is_on"]() is True
        assert switch["state_attrs"]() == {"times": "22:30-06:00"}
        assert switch["available"] == device.live_available
        assert list(device.hass_time) == ["do_not_disturb_start", "do_not_disturb_end"]
        for option in device.hass_time.values():
            assert option["available"] == device.live_available
        assert device.do_not_disturb_start == datetime.time(22, 30)
        assert device.do_not_disturb_end == datetime.time(6, 0)

    def test_never_set(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Null values (never configured) read as unknown."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert device.do_not_disturb_on() is None
        assert device.do_not_disturb_start is None
        assert device.do_not_disturb_end is None

    def test_no_times_without_iot_id(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """No time entities without an Aliyun device."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        assert device.hass_time == {}

    async def test_turn_on_uses_app_defaults(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Turning on with no window set sends the app's default 23:00-07:00."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_switch["do_not_disturb"]["async_turn_on"]() is True

        mock_coordinator.account.request.assert_awaited_once_with(
            "token/visualScooper/quietMode",
            {"deviceId": "ultra1", "enable": "true", "times": "23:00-07:00"},
            "POST",
        )
        assert device.do_not_disturb_on() is True
        assert device.do_not_disturb_start == datetime.time(23, 0)

    async def test_turn_off_keeps_times(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Turning off sends the current window along."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, quietEnable=True, quietTimes="22:30-06:00"
        )

        assert await device.hass_switch["do_not_disturb"]["async_turn_off"]() is True

        assert self._posted(mock_coordinator) == [
            {"deviceId": "ultra1", "enable": "false", "times": "22:30-06:00"}
        ]
        assert device.do_not_disturb_on() is False

    async def test_set_start_keeps_end_and_switch(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Changing one end keeps the other end and the on/off state."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, quietEnable=False, quietTimes="22:30-06:00"
        )
        times = device.hass_time

        assert await times["do_not_disturb_start"]["async_set_value"](datetime.time(23, 0)) is True
        assert await times["do_not_disturb_end"]["async_set_value"](datetime.time(7, 0)) is True

        assert self._posted(mock_coordinator) == [
            {"deviceId": "ultra1", "enable": "false", "times": "23:00-06:00"},
            {"deviceId": "ultra1", "enable": "false", "times": "23:00-07:00"},
        ]
        assert device.do_not_disturb_end == datetime.time(7, 0)

    @pytest.mark.parametrize(
        ("start", "end", "match"),
        [
            (datetime.time(23, 5), datetime.time(7, 0), "10-minute steps"),
            (datetime.time(20, 0), datetime.time(7, 0), "10 minutes to 8 hours"),
            (datetime.time(7, 0), datetime.time(7, 0), "10 minutes to 8 hours"),
        ],
    )
    async def test_refused_like_the_app(
        self, mock_coordinator, sample_pro_ultra_data, start, end, match
    ) -> None:
        """Off-step times and windows outside 10 min-8 h are refused."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match=match):
            await device.async_set_quiet_mode(start=start, end=end)
        mock_coordinator.account.request.assert_not_awaited()

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (datetime.time(23, 0), datetime.time(7, 0)),  # exactly 8 h over midnight
            (datetime.time(12, 0), datetime.time(12, 10)),  # 10 min
        ],
    )
    async def test_window_limits_allowed(
        self, mock_coordinator, sample_pro_ultra_data, start, end
    ) -> None:
        """The limits themselves are allowed."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        assert await device.async_set_quiet_mode(start=start, end=end) is True

    async def test_api_error(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A CatLink error keeps the old values and sets the device error."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, quietEnable=False, quietTimes="22:30-06:00"
        )
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 1, "msg": "busy"}
        )

        assert await device.async_set_quiet_mode(enable=True) is False

        assert device.do_not_disturb_on() is False
        assert "busy" in device.error


class TestScooperProUltraCameraSchedule:
    """Tests for the camera recording period select (CameraOpenDuration)."""

    TIMINGS = [{"start": "08:00", "end": "12:00", "repeat": "1,2,3,4,5"}]

    def _device(self, mock_coordinator, sample_pro_ultra_data, value):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, "CameraOpenDuration": value}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def _sent(self, mock_coordinator) -> list:
        return [
            json.loads(c.args[1]["CameraOpenDuration"])
            for c in mock_coordinator.account.linkvisual.async_set_properties.await_args_list
        ]

    def test_select(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The app's five choices, needing the device online; periods as an attribute."""
        value = json.dumps({"type": "4", "timings": self.TIMINGS})
        device = self._device(mock_coordinator, sample_pro_ultra_data, value)
        select = device.hass_select["camera_schedule"]

        assert select["options"] == ["all_day", "off", "daytime", "night", "custom"]
        assert select["available"] == device.live_available
        assert select["state_attrs"]() == {"timings": self.TIMINGS}
        assert device.camera_schedule == "custom"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ('{"type":"0"}', "all_day"),
            ('{"type":"1","timings":[]}', "off"),
            ({"type": "2"}, "daytime"),
            ('{"type":3}', "night"),
            ('{"timings":[]}', "all_day"),
            ('{"type":"9"}', "code_9"),
            ("not json", None),
            (None, None),
        ],
    )
    def test_state(
        self, mock_coordinator, sample_pro_ultra_data, value, expected
    ) -> None:
        """JSON text or an object; a missing type is all day, like the app."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, value)
        assert device.camera_schedule == expected

    async def test_select_keeps_timings(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Choosing a period writes the type and keeps the custom periods."""
        value = json.dumps({"type": "4", "timings": self.TIMINGS})
        device = self._device(mock_coordinator, sample_pro_ultra_data, value)

        assert await device.async_select_camera_schedule("night") is True

        assert self._sent(mock_coordinator) == [{"timings": self.TIMINGS, "type": "3"}]
        assert device.camera_schedule == "night"

        assert await device.async_select_camera_schedule("custom") is True
        assert device.camera_schedule == "custom"

    async def test_custom_needs_periods(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Custom without periods is refused (the app keeps at least one)."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, '{"type":"0"}')

        with pytest.raises(HomeAssistantError, match="no custom recording periods"):
            await device.async_select_camera_schedule("custom")
        mock_coordinator.account.linkvisual.async_set_properties.assert_not_awaited()

    async def test_from_unknown_value(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """With no readable value, a fixed period is written with no periods."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, None)

        assert await device.async_select_camera_schedule("off") is True
        assert self._sent(mock_coordinator) == [{"timings": [], "type": "1"}]


class TestScooperProUltraReboot:
    """Tests for the reboot button (Reboot thing service; not in the app)."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_invoke_service = AsyncMock(
            return_value={"code": 200}
        )
        return device

    def test_button(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A diagnostic restart button, enabled, needing the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        button = device.hass_button["reboot"]

        assert button["class"] == "restart"
        assert button["entity_category"] == EntityCategory.DIAGNOSTIC
        assert button["available"] == device.live_available

    def test_no_deodorizer_strength(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The deodorizer is passive, so DeodorizationLevel gets no entity."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        assert "deodorizer_strength" not in device.hass_number

    async def test_reboot(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The button calls the Reboot thing service."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_button["reboot"]["async_press"]() is True

        mock_coordinator.account.linkvisual.async_invoke_service.assert_awaited_once_with(
            "iot-1", "Reboot"
        )

    async def test_reboot_refused_during_job(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """No reboot in the middle of a job."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, RunStatus="runStatus=1&biz=1"
        )

        with pytest.raises(HomeAssistantError, match="cleaning"):
            await device.async_reboot()
        mock_coordinator.account.linkvisual.async_invoke_service.assert_not_awaited()

    async def test_reboot_failure(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A failed call sets the device error."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_invoke_service.side_effect = (
            LinkVisualError("Service Reboot failed: 9201 device offline")
        )

        assert await device.async_reboot() is False
        assert "9201" in device.error

class TestScooperProUltraCameraSelects:
    """Tests for the fill light and video quality selects."""

    def _device(self, mock_coordinator, sample_pro_ultra_data, **props):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = {**LIVE_PROPERTIES, **props}
        device.iot_online = True
        mock_coordinator.account.linkvisual.async_set_properties = AsyncMock()
        return device

    def test_selects(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The app's choices, in its order, needing the device online."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)
        selects = device.hass_select

        assert selects["fill_light"]["options"] == ["on", "when_dark", "cat_visit", "off"]
        assert selects["video_quality"]["options"] == ["1080p", "720p"]
        for key in ("fill_light", "video_quality"):
            assert selects[key]["available"] == device.live_available

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0, "off"), (1, "on"), ("2", "cat_visit"), (3, "when_dark"), (4, "code_4"), (None, None)],
    )
    def test_fill_light_state(
        self, mock_coordinator, sample_pro_ultra_data, value, expected
    ) -> None:
        """DayNightMode maps like the app's live-view menu."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, DayNightMode=value)
        assert device.fill_light == expected

    @pytest.mark.parametrize(
        ("value", "expected"), [(2, "1080p"), (1, "720p"), (0, "code_0"), (None, None)]
    )
    def test_video_quality_state(
        self, mock_coordinator, sample_pro_ultra_data, value, expected
    ) -> None:
        """StreamVideoQuality 2 is 1080p and 1 is 720p."""
        device = self._device(
            mock_coordinator, sample_pro_ultra_data, StreamVideoQuality=value
        )
        assert device.video_quality == expected

    @pytest.mark.parametrize(
        ("key", "option", "sent"),
        [
            ("fill_light", "when_dark", {"DayNightMode": 3}),
            ("fill_light", "off", {"DayNightMode": 0}),
            ("video_quality", "720p", {"StreamVideoQuality": 1}),
            ("video_quality", "1080p", {"StreamVideoQuality": 2}),
        ],
    )
    async def test_select(
        self, mock_coordinator, sample_pro_ultra_data, key, option, sent
    ) -> None:
        """Each choice writes the app's value."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        assert await device.hass_select[key]["async_select"](option) is True

        mock_coordinator.account.linkvisual.async_set_properties.assert_awaited_once_with(
            "iot-1", sent
        )
        assert getattr(device, key) == option

    async def test_unknown_option(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """An option that isn't offered is refused."""
        device = self._device(mock_coordinator, sample_pro_ultra_data)

        with pytest.raises(HomeAssistantError, match="Unknown option"):
            await device.hass_select["fill_light"]["async_select"]("disco")


class TestScooperProUltraLastVisit:
    """Tests for the last-visit sensors (activity timeline type 99 records)."""

    # Records as timeline/v2 sends them, newest first.
    RECORDS = [
        {"id": "100003", "type": 0, "time": "21:27", "event": "Auto-clean",
         "unrecognized": False, "firstSection": "Once", "secondSection": "",
         "thirdSection": None, "petId": "0", "eventStart": "1793913730"},
        {"id": "100002", "type": 99, "time": "21:21", "event": "Milo visited",
         "unrecognized": False, "firstSection": "4.8kg", "secondSection": "68s",
         "thirdSection": "Pee", "petId": "1001", "eventStart": "1793913526",
         "eventEnd": "1793913706"},
        {"id": "100001", "type": 99, "time": "20:49", "event": "Luna visited",
         "unrecognized": False, "firstSection": "5.7kg", "secondSection": "51s",
         "thirdSection": None, "petId": "1002", "eventStart": "1793911740"},
    ]

    def _device(self, mock_coordinator, sample_pro_ultra_data, records):
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 0, "data": {"records": records}}
        )
        return ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

    def test_sensors(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Three history sensors: the cat, its weight (kg) and the time inside (s)."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        sensors = device.hass_sensor

        assert sensors["last_visit_weight"]["unit"] == "kg"
        assert sensors["last_visit_weight"]["class"] == "weight"
        assert sensors["last_visit_duration"]["unit"] == "s"
        assert sensors["last_visit_duration"]["class"] == "duration"
        for key in ("last_visit", "last_visit_weight", "last_visit_duration"):
            assert "available" not in sensors[key]
        assert device.last_visit is None
        assert device.last_visit_weight is None
        assert device.last_visit_duration is None

    async def test_latest_visit(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The newest visit record wins; cleans and other records are skipped."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, self.RECORDS)

        await device.update_logs()

        assert device.last_visit == "Milo"
        assert device.last_visit_weight == 4.8
        assert device.last_visit_duration == 68
        assert device.last_visit_attrs() == {
            "pet_id": "1001",
            "weight": 4.8,
            "duration": 68,
            "result": "Pee",
            "time": "2026-11-05T21:21:46+00:00",
            "event": "Milo visited",
        }

    async def test_name_from_today_list(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """The cat's name comes from today's per-cat list when it has the pet."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, self.RECORDS)
        device.toilet_today = {"list": [{"petId": "1001", "petName": "Milo Jr"}]}

        await device.update_logs()

        assert device.last_visit == "Milo Jr"

    async def test_unrecognized(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A visit CatLink couldn't match to a cat."""
        record = {**self.RECORDS[1], "unrecognized": True, "petId": "0", "event": "Cat visited"}
        device = self._device(mock_coordinator, sample_pro_ultra_data, [record])

        await device.update_logs()

        assert device.last_visit == "unrecognized"
        assert device.last_visit_weight == 4.8

    async def test_kept_without_new_visit(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A timeline without visits (e.g. after midnight) keeps the last one."""
        device = self._device(mock_coordinator, sample_pro_ultra_data, self.RECORDS)
        await device.update_logs()
        mock_coordinator.account.request = AsyncMock(
            return_value={"returnCode": 0, "data": {"records": [self.RECORDS[0]]}}
        )

        await device.update_logs()

        assert device.last_visit == "Milo"

    @pytest.mark.parametrize(
        ("first", "second", "weight", "duration"),
        [
            ("4.8kg", "68s", 4.8, 68),
            ("10.6lb", "1min8s", 4.81, 68),
            ("5.7 kg", "2m 5s", 5.7, 125),
            ("", "", None, None),
            ("heavy", "a while", None, None),
            (None, None, None, None),
        ],
    )
    def test_parsing(
        self, mock_coordinator, sample_pro_ultra_data, first, second, weight, duration
    ) -> None:
        """Weight in kg (lb converted) and duration in seconds; unknown text reads as unknown."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        device.last_visit_record = {
            **self.RECORDS[1], "firstSection": first, "secondSection": second,
        }

        assert device.last_visit_weight == weight
        assert device.last_visit_duration == duration


class TestScooperProUltraPush:
    """Tests for the Aliyun push hook."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_init_starts_push(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A device with an iotId starts the account's push connection for itself."""
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.update_device_detail = AsyncMock()
        device._async_init_logs = AsyncMock()

        await device.async_init()

        mock_coordinator.account.linkvisual.start_push.assert_called_once_with(
            mock_coordinator.account.hass, "iot-1", device._on_push
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_no_push_without_iot_id(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """No Aliyun device, no push connection."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)
        device.update_device_detail = AsyncMock()
        device._async_init_logs = AsyncMock()

        await device.async_init()

        mock_coordinator.account.linkvisual.start_push.assert_not_called()

    def _push_device(self, mock_coordinator, sample_pro_ultra_data):
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )
        device.properties = dict(LIVE_PROPERTIES)
        device.iot_online = True
        device.listeners["x"] = MagicMock()
        mock_coordinator.account.hass = MagicMock()
        mock_coordinator.account.hass.async_create_task.side_effect = lambda coro: coro.close()
        return device

    def test_properties_applied_at_once(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Pushed items update the properties and the entities right away."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)

        device._on_push(
            "/thing/properties",
            {"params": {"iotId": "iot-1", "items": {
                "RunStatus": {"time": 1, "value": "runStatus=1&biz=3"},
                "DeviceWeihgt": {"time": 1, "value": 170},
            }}},
        )

        assert device.state == "leveling"
        assert device.scale_weight == 170
        device.listeners["x"].assert_called()
        mock_coordinator.account.hass.async_create_task.assert_not_called()

    def test_visit_end_refreshes_timeline(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """A finished visit (catSatus=0, new values) schedules a timeline re-read."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        hass = mock_coordinator.account.hass
        done = {"params": {"iotId": "iot-1", "items": {
            "ExtInfo": {"value": "catSatus=0&weihtvalue=4764&usetime=131&biz=1"}}}}

        device._on_push("/thing/properties", done)
        device._on_push("/thing/properties", done)  # repeated value: no second refresh

        assert hass.async_create_task.call_count == 1

    async def test_refresh_after_visit(
        self, mock_coordinator, sample_pro_ultra_data, monkeypatch
    ) -> None:
        """The timeline is read again after 10 s and 60 s."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        device.update_logs = AsyncMock()
        sleeps = []

        async def _sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(
            "custom_components.catlink.devices.scooper_pro_ultra.asyncio.sleep", _sleep
        )
        await device._async_refresh_logs_after_visit()

        assert sleeps == [10, 50]
        assert device.update_logs.await_count == 2

    @pytest.fixture
    def timers(self, monkeypatch):
        """Capture async_call_later: list of [delay, callback, cancel mock]."""
        scheduled = []

        def _later(hass, delay, action):
            cancel = MagicMock()
            scheduled.append([delay, action, cancel])
            return cancel

        monkeypatch.setattr(
            "custom_components.catlink.devices.scooper_pro_ultra.async_call_later", _later
        )
        return scheduled

    def _status(self, device, value):
        device._on_push(
            "/thing/status",
            {"params": {"iotId": "iot-1", "status": {"time": 1, "value": value}}},
        )

    def test_offline_waits(self, mock_coordinator, sample_pro_ultra_data, timers) -> None:
        """An offline push only takes effect if the box stays away for 60 s."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)

        self._status(device, 3)
        assert device.online is True
        assert [t[0] for t in timers] == [60]

        timers[0][1](None)
        assert device.online is False

        self._status(device, "1")
        assert device.online is True

    def test_quick_reconnect_stays_online(
        self, mock_coordinator, sample_pro_ultra_data, timers
    ) -> None:
        """Offline then online a second later never shows offline."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)

        self._status(device, 3)
        self._status(device, 3)  # one timer only
        self._status(device, 1)

        assert device.online is True
        assert len(timers) == 1
        timers[0][2].assert_called_once()

    def test_offline_at_once_when_not_online(
        self, mock_coordinator, sample_pro_ultra_data, timers
    ) -> None:
        """Without a known online state there's nothing to wait for."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        device.iot_online = None

        self._status(device, "0")

        assert device.online is False
        assert timers == []

    async def test_poll_offline_waits(
        self, mock_coordinator, sample_pro_ultra_data, timers
    ) -> None:
        """The polled status goes through the same delay."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_is_online = AsyncMock(return_value=False)

        await device.update_online()

        assert device.online is True
        assert len(timers) == 1

    def _ext(self, device, status):
        device._on_push(
            "/thing/properties",
            {"params": {"iotId": "iot-1", "items": {
                "ExtInfo": {"value": f"catSatus={status}&weihtvalue=4764&usetime=9&biz=0"}}}},
        )

    def _replay(self, device, steps):
        """Push (key, value) steps; return the cat_inside value after each."""
        seen = []
        for key, value in steps:
            device._on_push(
                "/thing/properties",
                {"params": {"iotId": "iot-1", "items": {key: {"value": value}}}},
            )
            seen.append(device.cat_inside)
        return seen

    def _events(self, mock_coordinator) -> list:
        return [
            c.args[1] for c in mock_coordinator.account.hass.bus.async_fire.call_args_list
        ]

    def _idle_device(self, mock_coordinator, sample_pro_ultra_data):
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        device.properties.update(
            ExtInfo="catSatus=0&weihtvalue=4818&usetime=68&biz=1", DeviceWeihgt=0
        )
        device._cat_inside = False
        return device

    def test_visit_sequence(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Real pushes of the 13:05 visit: on at the first step, off when done."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        seen = self._replay(device, [
            ("ExtInfo", "catSatus=2&weihtvalue=2294&usetime=0&biz=0"),  # steps in
            ("DeviceWeihgt", 2294),
            ("ExtInfo", "catSatus=1&weihtvalue=4675&usetime=99&biz=2"),  # inside
            ("AbnormalState", "2"),
            ("DeviceWeihgt", 4507),
            ("ExtInfo", "catSatus=0&weihtvalue=4675&usetime=71&biz=1"),  # done
            ("DeviceWeihgt", 0),
        ])

        assert seen == [True, True, True, True, True, False, False]
        events = self._events(mock_coordinator)
        assert [e["type"] for e in events] == ["cat_entered", "cat_left", "visit"]
        assert events[0]["weight"] == 2.29
        assert events[2]["weight"] == 4.67 and events[2]["duration"] == 71

    def test_scale_empties_first(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """13:11: the scale drops 5 s before the visit is marked done; off at the drop."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        seen = self._replay(device, [
            ("ExtInfo", "catSatus=2&weihtvalue=5854&usetime=0&biz=0"),
            ("ExtInfo", "catSatus=1&weihtvalue=5886&usetime=99&biz=2"),
            ("DeviceWeihgt", 5806),
            ("DeviceWeihgt", 0),  # out
            ("ExtInfo", "catSatus=0&weihtvalue=5886&usetime=186&biz=1"),
        ])

        assert seen == [True, True, True, False, False]
        assert [e["type"] for e in self._events(mock_coordinator)] == [
            "cat_entered", "cat_left", "visit",
        ]

    def test_step_in_and_out(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """13:04: a cat steps in and out without a visit: on for those seconds, no visit."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        seen = self._replay(device, [
            ("ExtInfo", "catSatus=2&weihtvalue=5924&usetime=0&biz=0"),
            ("DeviceWeihgt", 5924),
            ("DeviceWeihgt", 0),
        ])

        assert seen == [True, True, False]
        assert [e["type"] for e in self._events(mock_coordinator)] == [
            "cat_entered", "cat_left",
        ]

    def test_shifting_mid_visit(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """catSatus 2 mid-visit with the cat's weight on the scale stays on."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        seen = self._replay(device, [
            ("ExtInfo", "catSatus=1&weihtvalue=4764&usetime=98&biz=2"),
            ("ExtInfo", "catSatus=2&weihtvalue=2229&usetime=152&biz=0"),
            ("ExtInfo", "catSatus=1&weihtvalue=4764&usetime=98&biz=2"),
        ])

        assert seen == [True, True, True]
        assert [e["type"] for e in self._events(mock_coordinator)] == ["cat_entered"]

    def test_light_step_ignored(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Under 1 kg on the scale (a paw, residue) isn't a cat inside."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        assert self._replay(device, [
            ("ExtInfo", "catSatus=2&weihtvalue=640&usetime=0&biz=0"),
            ("DeviceWeihgt", 290),
        ]) == [False, False]
        assert self._events(mock_coordinator) == []

    def test_off_while_running(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Weight readings during a clean or leveling never count as a cat."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        assert self._replay(device, [
            ("RunStatus", "runStatus=1&biz=3"),
            ("ExtInfo", "catSatus=2&weihtvalue=3881&usetime=0&biz=0"),
            ("DeviceWeihgt", 3881),
        ]) == [False, False, False]

    def test_startup_from_current_values(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Without history the current values decide, and no events fire."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        device.properties.update(
            ExtInfo="catSatus=1&weihtvalue=4764&usetime=98&biz=2", DeviceWeihgt=4700
        )

        assert device.cat_inside is True
        self._replay(device, [("DeviceWeihgt", 4710)])
        assert self._events(mock_coordinator) == []

    async def test_poll_sees_visit(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Without pushes, a poll that shows a finished visit still fires it."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(return_value={
            **device.properties, "ExtInfo": "catSatus=0&weihtvalue=5755&usetime=108&biz=1",
        })

        await device.update_properties()

        (event,) = self._events(mock_coordinator)
        assert event["type"] == "visit" and event["weight"] == 5.75

    def test_motion_started_only_first(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Motion events: startFlag 0 is started, the repeats are ongoing."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        events = [
            {"AlarmType": 11007, "Data": json.dumps({"action": 0, "startFlag": flag})}
            for flag in (0, 1, 1)
        ]

        device._on_push(
            "/thing/events",
            {"params": {"iotId": "iot-1", "identifier": "IntelligentAlarm",
                        "value": {"EventList": events}}},
        )

        assert [e["action"] for e in self._events(mock_coordinator)] == [
            "started", "ongoing", "ongoing",
        ]

    def test_fault_events(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Each anti-pinch push fires an event, then the clear."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)

        self._replay(device, [
            ("RunStatus", "runStatus=4&biz=1"),
            ("AbnormalState", "1"),
            ("AbnormalState", "1"),  # the box repeats the warning
            ("AbnormalState", "2"),  # a cat inside isn't a fault...
            ("AbnormalState", "0"),
        ])

        faults = [e for e in self._events(mock_coordinator) if e["type"] == "fault"]
        assert [(e["action"], e["fault"]) for e in faults] == [
            ("reported", "anti_pinch"),
            ("reported", "anti_pinch"),
            ("cleared", "anti_pinch"),  # ...but it ends the anti-pinch
        ]
        assert faults[0]["code"] == "1"

    async def test_fault_poll_only_on_change(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """Polls fire a fault once, when it appears."""
        device = self._idle_device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_get_properties = AsyncMock(
            return_value={**device.properties, "AbnormalState": "6"}
        )

        await device.update_properties()
        await device.update_properties()

        faults = [e for e in self._events(mock_coordinator) if e["type"] == "fault"]
        assert [(e["action"], e["fault"]) for e in faults] == [("reported", "motor_blocked")]

    def _picture_http(self, mock_coordinator, body=b"jpeg", status=200):
        rsp = MagicMock(status=status)
        rsp.read = AsyncMock(return_value=body)
        mock_coordinator.account.http.get = AsyncMock(return_value=rsp)
        mock_coordinator.account.linkvisual.async_query_pictures = AsyncMock(
            side_effect=lambda iot, ids: {
                i: {"pictureId": i, "pictureUrl": f"https://oss/{i}", "thumbUrl": "t"} for i in ids
            }
        )
        return rsp

    async def test_event_picture_kept(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """An event's picture is downloaded and becomes the camera's still."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        self._picture_http(mock_coordinator)

        await device._async_fetch_picture("3/x/osssts_ia_1", 1793924087746)

        assert device.latest_picture_info() == (b"jpeg", 1793924087.746)
        mock_coordinator.account.http.get.assert_awaited_once_with("https://oss/3/x/osssts_ia_1")

    async def test_older_picture_ignored(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A picture older than the one kept isn't even looked up."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        self._picture_http(mock_coordinator)
        device.latest_picture, device.latest_picture_time = b"new", 2e9

        await device._async_fetch_picture("p-old", 1793924087746)

        assert device.latest_picture == b"new"
        mock_coordinator.account.linkvisual.async_query_pictures.assert_not_awaited()

    @pytest.mark.parametrize("status", [403, 404])
    async def test_picture_download_failure(
        self, mock_coordinator, sample_pro_ultra_data, status
    ) -> None:
        """An expired or missing URL keeps the previous picture."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        self._picture_http(mock_coordinator, status=status)

        await device._async_fetch_picture("p1", 1793924087746)

        assert device.latest_picture is None

    async def test_picture_lookup_failure(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A failed lookup is ignored."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        mock_coordinator.account.linkvisual.async_query_pictures = AsyncMock(
            side_effect=LinkVisualError("460")
        )

        await device._async_fetch_picture("p1", None)

        assert device.latest_picture is None

    def test_event_schedules_picture(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """Pushed events with an AlarmPicID fetch their picture."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        event = {"AlarmType": 11007, "AlarmPicID": "3/x/p", "EventTime": "1793924087746",
                 "Data": json.dumps({"action": 0, "startFlag": 0})}

        device._on_push(
            "/thing/events",
            {"params": {"iotId": "iot-1", "identifier": "IntelligentAlarm",
                        "value": {"EventList": [event]}}},
        )

        assert mock_coordinator.account.hass.async_create_task.call_count == 1

    async def test_initial_picture_from_timeline(
        self, mock_coordinator, sample_pro_ultra_data
    ) -> None:
        """After a restart the newest timeline picture is fetched once."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        hass = mock_coordinator.account.hass
        records = [
            {"type": 0, "picIdOfPre": None, "picIdOfNext": None},
            {"type": 0, "picIdOfNext": "p-next", "eventEnd": "1793913910"},
        ]

        device._fetch_initial_picture(records)
        device._fetch_initial_picture(records)

        assert hass.async_create_task.call_count == 1

    def test_cat_appeared_event(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """11003 with bizType 0 (no weight, judgeCode) is cat_appeared, not a visit."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        data = {"bizID": "id1", "action": 2, "duration": 0, "weight": 0,
                "bizType": 0, "judgeCode": 1001}

        device._on_push(
            "/thing/events",
            {"params": {"iotId": "iot-1", "identifier": "IntelligentAlarm",
                        "value": {"EventList": [{"AlarmType": 11003, "Data": json.dumps(data)}]}}},
        )

        (name, payload), = [c.args for c in mock_coordinator.account.hass.bus.async_fire.call_args_list]
        assert payload["type"] == "cat_appeared"
        assert payload["judge_code"] == 1001
        assert "weight" not in payload

    def test_alarm_events_fired(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """IntelligentAlarm events become catlink_event bus events, decoded where known."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        events = [
            {"AlarmType": 11003, "EventTime": "1793924087746", "AlarmPicID": "x",
             "Data": json.dumps({"bizID": "id1", "action": 2, "duration": 131,
                                 "weight": 4764, "bizType": 1})},
            {"AlarmType": 11008, "Data": json.dumps({"action": 0, "type": 0, "remote": 1})},
            {"AlarmType": 12345, "Data": "not json"},
        ]

        device._on_push(
            "/thing/events",
            {"params": {"iotId": "iot-1", "identifier": "IntelligentAlarm",
                        "value": {"EventList": events}}},
        )

        fired = [c.args for c in mock_coordinator.account.hass.bus.async_fire.call_args_list]
        assert [name for name, _ in fired] == ["catlink_event"] * 3
        visit, clean, unknown = (data for _, data in fired)
        assert visit["type"] == "visit_recorded" and visit["action"] == "finished"
        assert visit["weight"] == 4.76 and visit["duration"] == 131
        assert visit["device_id"] == "ultra1"
        assert clean["type"] == "cleaning" and clean["action"] == "started"
        assert unknown["type"] == "alarm_12345" and unknown["data"] == {}

    def test_push_logged_redacted(self, mock_coordinator, sample_pro_ultra_data, caplog) -> None:
        """Pushes are logged at debug level with credential-looking fields masked."""
        device = self._push_device(mock_coordinator, sample_pro_ultra_data)
        with caplog.at_level("DEBUG"):
            device._on_push(
                "/thing/properties",
                {"params": {"iotId": "iot-1", "items": {
                    "ExtInfo": {"value": "catSatus=1"}, "iotToken": "t0ps3cret"}}},
            )

        assert "catSatus=1" in caplog.text
        assert "t0ps3cret" not in caplog.text


class TestScooperProUltraCamera:
    """Tests for the Scooper Pro Ultra camera."""

    def test_hass_camera_with_iot_id(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A device with an iotId exposes one camera."""
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )

        cameras = device.hass_camera

        assert list(cameras) == ["camera"]
        assert cameras["camera"]["stream_source"] == device.async_get_stream_url

    def test_hass_camera_without_iot_id(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """A device without an iotId exposes no camera."""
        device = ScooperProUltraDevice(sample_pro_ultra_data, mock_coordinator)

        assert device.hass_camera == {}

    async def test_async_get_stream_url(self, mock_coordinator, sample_pro_ultra_data) -> None:
        """The stream URL comes from the account's LinkVisual client."""
        mock_coordinator.account.linkvisual.async_get_live_url = AsyncMock(
            return_value="rtmp://relay/live"
        )
        device = ScooperProUltraDevice(
            {**sample_pro_ultra_data, "iotId": "iot-1"}, mock_coordinator
        )

        assert await device.async_get_stream_url() == "rtmp://relay/live"
        mock_coordinator.account.linkvisual.async_get_live_url.assert_awaited_once_with(
            "iot-1"
        )
