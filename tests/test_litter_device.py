"""Tests for CatLink LitterDevice base class."""

from unittest.mock import MagicMock

import pytest

from custom_components.catlink.devices.litterbox import LitterBox


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


class TestLitterDeviceState:
    """Tests for LitterDevice state property."""

    def test_state_idle(self, mock_coordinator, sample_device_data) -> None:
        """Test state maps workStatus 00 to idle."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"workStatus": "00"}
        assert device.state == "idle"

    def test_state_running(self, mock_coordinator, sample_device_data) -> None:
        """Test state maps workStatus 01 to running."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"workStatus": "01"}
        assert device.state == "running"

    def test_state_need_reset(self, mock_coordinator, sample_device_data) -> None:
        """Test state maps workStatus 02 to need_reset."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"workStatus": "02"}
        assert device.state == "need_reset"

    def test_state_unknown_fallback(self, mock_coordinator, sample_device_data) -> None:
        """Test state returns raw value for unknown workStatus."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"workStatus": "99"}
        assert device.state == "99"


class TestLitterDeviceLitterWeight:
    """Tests for LitterDevice litter_weight property."""

    def test_litter_weight_calculated(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test litter_weight subtracts empty weight from catLitterWeight."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.empty_litter_box_weight = 1.0
        device.detail = {"catLitterWeight": 3.5}
        assert device.litter_weight == 2.5

    def test_litter_weight_default_empty(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test litter_weight when catLitterWeight missing uses empty_weight."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.empty_litter_box_weight = 1.0
        device.detail = {}
        assert device.litter_weight == 0.0


class TestLitterDeviceCleanTimes:
    """Tests for LitterDevice total_clean_time and manual_clean_time."""

    def test_total_clean_time(self, mock_coordinator, sample_device_data) -> None:
        """Test total_clean_time sums induction and manual times."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"inductionTimes": 10, "manualTimes": 5}
        assert device.total_clean_time == 15

    def test_manual_clean_time(self, mock_coordinator, sample_device_data) -> None:
        """Test manual_clean_time from manualTimes."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"manualTimes": 7}
        assert device.manual_clean_time == 7

    def test_deodorant_countdown(self, mock_coordinator, sample_device_data) -> None:
        """Test deodorant_countdown from detail."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"deodorantCountdown": 30}
        assert device.deodorant_countdown == 30


class TestLitterDeviceOccupied:
    """Tests for LitterDevice occupied property."""

    def test_occupied_true_when_weight_increases(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test occupied True when litter weight increases during day."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._litter_weight_during_day.clear()
        device._litter_weight_during_day.extend([1.0, 1.5, 2.0])
        assert device.occupied is True

    def test_occupied_false_when_weight_decreases(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test occupied False when litter weight only decreases."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._litter_weight_during_day.clear()
        device._litter_weight_during_day.extend([3.0, 2.5, 2.0])
        assert device.occupied is False

    def test_occupied_false_when_empty(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test occupied False when deque has fewer than 2 entries."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._litter_weight_during_day.clear()
        device._litter_weight_during_day.append(1.0)
        assert device.occupied is False


class TestLitterDeviceOnline:
    """Tests for LitterDevice online property."""

    def test_online_true(self, mock_coordinator, sample_device_data) -> None:
        """Test online returns True when detail has online."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"online": True}
        assert device.online is True

    def test_online_false(self, mock_coordinator, sample_device_data) -> None:
        """Test online returns False when detail has online False."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {"online": False}
        assert device.online is False


class TestLitterDeviceBaseStateAttrs:
    """Tests for LitterDevice _base_state_attrs."""

    def test_base_state_attrs(self, mock_coordinator, sample_device_data) -> None:
        """Test _base_state_attrs returns expected keys."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.detail = {
            "workStatus": "00",
            "alarmStatus": "ok",
            "weight": 2500,
            "catLitterWeight": 3.5,
            "inductionTimes": 10,
            "manualTimes": 5,
            "keyLock": "0",
            "safeTime": 30,
            "catLitterPaveSecond": 60,
            "deodorantCountdown": 30,
            "litterCountdown": 5,
        }
        attrs = device._base_state_attrs()
        assert attrs["mac"] == "AA:BB:CC:DD:EE:FF"
        assert attrs["work_status"] == "00"
        assert attrs["alarm_status"] == "ok"
        assert attrs["weight"] == 2500
        assert attrs["litter_weight_kg"] == 3.5
        assert attrs["total_clean_times"] == 15
        assert attrs["manual_clean_times"] == 5
        assert attrs["deodorant_countdown"] == 30
        assert attrs["litter_countdown"] == 5
