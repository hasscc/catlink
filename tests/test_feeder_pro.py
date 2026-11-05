"""Tests for read-only Feeder Pro support."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.catlink.devices.feeder import FeederDevice
from custom_components.catlink.devices.feeder_pro import FeederProDevice
from custom_components.catlink.devices.registry import create_device
from custom_components.catlink.entities.binary import CatlinkBinarySensorEntity
from custom_components.catlink.entities.sensor import CatlinkSensorEntity


@pytest.fixture
def feeder_pro():
    """Create a Feeder Pro with an offline account stub."""
    coordinator = MagicMock()
    coordinator.account.request = AsyncMock()
    device = create_device(
        {
            "id": "feeder-pro-test",
            "mac": "00:00:00:00:00:01",
            "deviceName": "Test Feeder Pro",
            "deviceType": "FEEDER_PRO",
            "model": "Feeder Pro",
        },
        coordinator,
    )
    device.logs = []
    return device


def test_registry_uses_separate_device_class(feeder_pro):
    """Pro devices must not inherit the regular feeder's controls."""
    assert isinstance(feeder_pro, FeederProDevice)
    assert not isinstance(feeder_pro, FeederDevice)
    assert feeder_pro.hass_button == {}
    assert feeder_pro.hass_switch == {}
    assert feeder_pro.hass_select == {}
    assert not getattr(feeder_pro, "hass_number", {})


@pytest.mark.parametrize("wrapped", [False, True])
async def test_detail_response(feeder_pro, wrapped):
    """Accept both direct details and the deviceInfo wrapper."""
    detail = {
        "foodOutStatus": "IDLE",
        "weight": 42.5,
        "online": True,
        "currentErrorMessage": "",
        "keyLockStatus": True,
    }
    feeder_pro.account.request.return_value = {
        "returnCode": 0,
        "data": {"deviceInfo": detail} if wrapped else detail,
    }
    listener = MagicMock()
    feeder_pro.listeners["test"] = listener

    assert await feeder_pro.update_device_detail() == detail
    feeder_pro.account.request.assert_awaited_once_with(
        "token/device/feederpro/detail", {"deviceId": "feeder-pro-test"}
    )
    listener.assert_called_once_with()
    assert feeder_pro.state == "IDLE"
    assert feeder_pro.weight == 42.5
    assert feeder_pro.online is True
    assert feeder_pro.state_attrs()["key_lock_status"] is True


@pytest.mark.parametrize("data", [None, [], "invalid", {"deviceInfo": None}])
async def test_missing_or_malformed_details(feeder_pro, data):
    """Missing details leave numeric values unknown without raising."""
    feeder_pro.account.request.return_value = {"returnCode": 0, "data": data}
    assert await feeder_pro.update_device_detail() == {}
    assert feeder_pro.state is None
    assert feeder_pro.weight is None
    assert feeder_pro.error is None


async def test_failed_detail_does_not_publish_error_payload(feeder_pro):
    """Business errors are not interpreted as device details."""
    feeder_pro.account.request.return_value = {
        "returnCode": 1002,
        "data": {"weight": 12},
    }
    assert await feeder_pro.update_device_detail() == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0.0), ("2.5", 2.5), (None, None), ("", None), (True, None), ("NaN", None)],
)
def test_weight_values(feeder_pro, value, expected):
    """Keep zero weight and reject values unsuitable for a numeric sensor."""
    feeder_pro.detail = {"weight": value}
    assert feeder_pro.weight == expected


@pytest.mark.parametrize(
    ("detail", "listed", "expected"),
    [
        ({"online": False}, {"onlineStatus": True}, False),
        ({"online": True}, {}, True),
        ({}, {"onlineStatus": True}, True),
        ({}, {"onlineStatus": False}, False),
        ({}, {"online": True}, True),
        ({"online": None}, {"onlineStatus": "ONLINE"}, True),
        ({"onlineStatus": "OFFLINE"}, {"online": True}, False),
        ({}, {}, False),
    ],
)
def test_online_status(feeder_pro, detail, listed, expected):
    """A definite detail status takes precedence over list fallbacks."""
    feeder_pro.detail = detail
    feeder_pro.data.update(listed)
    assert feeder_pro.online is expected


async def test_feeding_records(feeder_pro):
    """Read only the Pro log endpoint and preserve event attributes."""
    record = {"time": "10:00", "event": "Fed", "firstSection": "1 portion"}
    feeder_pro.account.request.return_value = {
        "returnCode": 0,
        "data": {"feederLogTop5": [record, None, "invalid"]},
    }
    assert await feeder_pro.update_logs() == [record]
    feeder_pro.account.request.assert_awaited_once_with(
        "token/device/feederpro/stats/log/top5", {"deviceId": "feeder-pro-test"}
    )
    assert feeder_pro.last_log == "10:00 Fed 1 portion"
    assert feeder_pro.last_log_attrs()["logs"] == [record]


@pytest.mark.parametrize("data", [None, {}, {"feederLogTop5": None}, {"feederLogTop5": {}}])
async def test_empty_or_malformed_records(feeder_pro, data):
    """No records is a normal result and does not crash the log coordinator."""
    feeder_pro.account.request.return_value = {"returnCode": 0, "data": data}
    assert await feeder_pro.update_logs() == []
    assert feeder_pro.last_log is None


async def test_failed_logs_do_not_publish_error_payload(feeder_pro):
    """Ignore log-shaped data in an unsuccessful response."""
    feeder_pro.account.request.return_value = {
        "returnCode": 1002,
        "data": {"feederLogTop5": [{"event": "Ignored"}]},
    }
    assert await feeder_pro.update_logs() == []


def test_entities_read_updated_values(feeder_pro):
    """Use the existing entity classes and keep values current across polls."""
    weight = CatlinkSensorEntity("weight", feeder_pro, feeder_pro.hass_sensor["weight"])
    online = CatlinkBinarySensorEntity(
        "online", feeder_pro, feeder_pro.hass_binary_sensor["online"]
    )
    feeder_pro.detail = {"weight": 35, "online": True}
    weight.update()
    online.update()
    assert weight.state == 35
    assert online.is_on is True
    feeder_pro.detail = {"weight": 0, "online": False}
    weight.update()
    online.update()
    assert weight.state == 0
    assert online.is_on is False


async def test_initialization_starts_read_only_polling(feeder_pro):
    """Initialize details and the existing log coordinator without controls."""
    feeder_pro.account.request.return_value = {"returnCode": 0, "data": {}}
    feeder_pro._async_init_logs = AsyncMock()
    await feeder_pro.async_init()
    feeder_pro._async_init_logs.assert_awaited_once_with()
    feeder_pro.account.request.assert_awaited_once_with(
        "token/device/feederpro/detail", {"deviceId": "feeder-pro-test"}
    )
