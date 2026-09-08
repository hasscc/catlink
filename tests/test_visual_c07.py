"""Regression tests for VISUAL_C07 support."""
import datetime
from unittest.mock import AsyncMock, MagicMock, call
import pytest

from custom_components.catlink.devices.registry import create_device
from custom_components.catlink.devices.visual_c07 import VisualC07Device


@pytest.fixture
def coordinator():
    value = MagicMock()
    value.account = MagicMock()
    value.account.uid = "86-13812345678"
    return value


@pytest.fixture
def visual_c07_data():
    return {
        "id": "visual-c07-1",
        "mac": "00:11:22:33:44:55",
        "model": "MODEL_00",
        "deviceName": "C07",
        "deviceType": "VISUAL_C07",
    }


def test_registry_maps_visual_c07(coordinator, visual_c07_data):
    device = create_device(visual_c07_data, coordinator)
    assert isinstance(device, VisualC07Device)


def test_visual_c07_only_exposes_verified_read_entities(coordinator, visual_c07_data):
    device = VisualC07Device(visual_c07_data, coordinator)
    device.detail = {
        "totalCleanTimes": "7",
        "deodorantCountdown": 11,
        "litterCountdown": 3,
    }

    assert set(device.hass_sensor) == {
        "last_log",
        "litter_remaining_days",
        "deodorant_countdown",
        "total_clean_time",
        "auto_refill_mode",
        "auto_refill_level",
    }
    assert set(device.hass_binary_sensor) == {"auto_refill_installed"}
    assert device.hass_select == {}
    assert device.total_clean_time == 7
    assert device.deodorant_countdown == 11
    assert device.litter_remaining_days == 3
    assert device.auto_refill_mode == "unknown"
    assert device.auto_refill_level == "unknown"
    assert device.auto_refill_installed is False


@pytest.mark.asyncio
async def test_visual_c07_uses_visual_brief_info(coordinator, visual_c07_data):
    coordinator.account.request = AsyncMock(
        side_effect=[{
            "returnCode": 0,
            "data": {
                "deviceInfo": {
                    "totalCleanTimes": "7",
                    "deodorantCountdown": 11,
                    "litterCountdown": 3,
                }
            },
        }, {
            "returnCode": 0,
            "data": {
                "info": {"workModel": 0, "level": 2, "install": True}
            },
        }]
    )
    device = VisualC07Device(visual_c07_data, coordinator)

    detail = await device.update_device_detail()

    assert coordinator.account.request.await_args_list == [
        call("token/visualScooper/briefInfo", {"deviceId": "visual-c07-1"}),
        call("token/cameraLitterbox/sandSysInfo", {"deviceId": "visual-c07-1"}),
    ]
    assert detail["totalCleanTimes"] == "7"
    assert device.auto_refill_mode == "automatic"
    assert device.auto_refill_level == 2
    assert device.auto_refill_installed is True


@pytest.mark.asyncio
async def test_visual_c07_uses_timeline_v2_logs(coordinator, visual_c07_data):
    coordinator.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {
                "records": [
                    {"time": "10:20", "event": "clean", "moveDetectId": "redacted"}
                ]
            },
        }
    )
    device = VisualC07Device(visual_c07_data, coordinator)

    logs = await device.update_logs()

    coordinator.account.request.assert_awaited_once_with(
        "token/litterbox/stats/log/timeline/v2",
        {
            "deviceId": "visual-c07-1",
            "date": datetime.date.today().isoformat(),
            "pageNumber": 1,
            "pageSize": 10,
            "type": 0,
            "subType": 0,
        },
    )
    assert logs[0]["event"] == "clean"
    assert logs[0]["has_video"] is True
    assert "moveDetectId" not in logs[0]
    assert device.last_log == "10:20 clean"
