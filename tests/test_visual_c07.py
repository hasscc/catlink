"""Regression tests for VISUAL_C07 support."""
from unittest.mock import AsyncMock, MagicMock
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
        "litter_remaining_days",
        "deodorant_countdown",
        "total_clean_time",
    }
    assert device.hass_select == {}
    assert device.total_clean_time == 7
    assert device.deodorant_countdown == 11
    assert device.litter_remaining_days == 3


@pytest.mark.asyncio
async def test_visual_c07_uses_visual_brief_info(coordinator, visual_c07_data):
    coordinator.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {
                "deviceInfo": {
                    "totalCleanTimes": "7",
                    "deodorantCountdown": 11,
                    "litterCountdown": 3,
                }
            },
        }
    )
    device = VisualC07Device(visual_c07_data, coordinator)

    detail = await device.update_device_detail()

    coordinator.account.request.assert_awaited_once_with(
        "token/visualScooper/briefInfo", {"deviceId": "visual-c07-1"}
    )
    assert detail["totalCleanTimes"] == "7"
