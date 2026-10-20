"""Tests for CatLink LogsMixin."""

from unittest.mock import AsyncMock, MagicMock

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


class TestLogsMixinLastLog:
    """Tests for LogsMixin _last_log and last_log properties."""

    def test_last_log_empty_when_no_logs(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _last_log and last_log when logs is empty."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.logs = []
        assert device._last_log == {}
        assert device.last_log is None

    def test_last_log_returns_first_entry(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _last_log returns first log entry."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.logs = [
            {"time": "2024-01-15 10:00", "event": "Cleaning"},
            {"time": "2024-01-15 09:00", "event": "Idle"},
        ]
        assert device._last_log == {"time": "2024-01-15 10:00", "event": "Cleaning"}

    def test_last_log_formatted_string(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test last_log returns formatted string."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.logs = [{"time": "2024-01-15 10:00", "event": "Cleaning"}]
        assert device.last_log == "2024-01-15 10:00 Cleaning"

    def test_last_log_handles_none_first_entry(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _last_log when first entry is None."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.logs = [None, {"time": "2024-01-15", "event": "Clean"}]
        assert device._last_log == {}


class TestLogsMixinLastLogAttrs:
    """Tests for LogsMixin last_log_attrs."""

    def test_last_log_attrs_includes_logs(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test last_log_attrs includes log data and full logs list."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device.logs = [{"time": "10:00", "event": "Clean", "extra": "val"}]
        attrs = device.last_log_attrs()
        assert attrs["time"] == "10:00"
        assert attrs["event"] == "Clean"
        assert attrs["extra"] == "val"
        assert attrs["logs"] == device.logs


class TestLogsMixinFetchLogs:
    """Tests for LogsMixin _fetch_logs."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_fetch_logs_success(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _fetch_logs parses API response and updates logs."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._handle_listeners = MagicMock()
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "data": {
                    "scooperLogTop5": [
                        {"time": "10:00", "event": "Cleaning"},
                    ]
                }
            }
        )

        result = await device._fetch_logs(
            "token/litterbox/stats/log/top5", "scooperLogTop5"
        )

        assert len(result) == 1
        assert result[0]["time"] == "10:00"
        assert result[0]["event"] == "Cleaning"
        assert device.logs == result
        mock_coordinator.account.request.assert_called_once_with(
            "token/litterbox/stats/log/top5", {"deviceId": "dev123"}
        )
        device._handle_listeners.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_fetch_logs_empty_response(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _fetch_logs handles empty API response."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._handle_listeners = MagicMock()
        mock_coordinator.account.request = AsyncMock(return_value={"data": {}})

        result = await device._fetch_logs("token/litterbox/log", "scooperLogTop5")

        assert result == []
        assert device.logs == []

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_fetch_logs_api_error_sets_empty(
        self, mock_coordinator, sample_device_data
    ) -> None:
        """Test _fetch_logs sets empty list on parse error."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._handle_listeners = MagicMock()
        mock_coordinator.account.request = AsyncMock(
            return_value={"data": {"scooperLogTop5": "invalid"}}
        )

        result = await device._fetch_logs("token/litterbox/log", "scooperLogTop5")

        assert result == []
        assert device.logs == []

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_fetch_logs_successful_empty_list_does_not_warn(
        self, mock_coordinator, sample_device_data, caplog
    ) -> None:
        """Test a successful response with no entries is not logged as a failure."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._handle_listeners = MagicMock()
        mock_coordinator.account.request = AsyncMock(
            return_value={
                "returnCode": 0,
                "msg": None,
                "data": {"scooperLogTop5": []},
                "success": True,
            }
        )

        result = await device._fetch_logs(
            "token/litterbox/stats/log/top5", "scooperLogTop5"
        )

        assert result == []
        assert "failed" not in caplog.text

    @pytest.mark.usefixtures("enable_custom_integrations")
    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"returnCode": 1, "msg": "error", "data": {}, "success": False},
        ],
        ids=["request_failed", "error_return_code"],
    )
    async def test_fetch_logs_failed_request_warns(
        self, mock_coordinator, sample_device_data, caplog, response
    ) -> None:
        """Test a failed request or an error return code is still a warning."""
        device = LitterBox(sample_device_data, mock_coordinator)
        device._handle_listeners = MagicMock()
        mock_coordinator.account.request = AsyncMock(return_value=response)

        result = await device._fetch_logs(
            "token/litterbox/stats/log/top5", "scooperLogTop5"
        )

        assert result == []
        assert "Got device logs for Living Room Litter failed" in caplog.text
