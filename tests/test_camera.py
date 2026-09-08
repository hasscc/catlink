"""Tests for the privacy-safe C07 latest-event camera."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.catlink.devices.visual_c07 import VisualC07Device
from custom_components.catlink.entities.camera import CatlinkCameraEntity

JPEG = b"\xff\xd8\xff\xe0" + b"safe-test-image"


class _Chunks:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def _iterate(self):
        yield self.payload

    def iter_chunked(self, _size: int):
        return self._iterate()


class _Response:
    def __init__(
        self, payload: bytes, *, status: int = 200, content_type: str = "image/jpeg"
    ):
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(payload)),
        }
        self.content = _Chunks(payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.fixture
def device():
    coordinator = MagicMock()
    coordinator.account = MagicMock()
    coordinator.account.uid = "86-13812345678"
    value = VisualC07Device(
        {
            "id": "visual-c07-1",
            "mac": "00:11:22:33:44:55",
            "model": "MODEL_00",
            "deviceName": "C07",
            "deviceType": "VISUAL_C07",
        },
        coordinator,
    )
    value._media_events = [{"picIdOfPre": "private-picture-id"}]
    return value


@pytest.mark.asyncio
async def test_latest_event_picture_fetches_bounded_jpeg(device):
    device.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {
                "picUrl": "https://bucket.oss-cn-hangzhou.aliyuncs.com/private?signed=yes"
            },
        }
    )
    device.account.http.get = MagicMock(return_value=_Response(JPEG))

    image = await device.async_get_latest_event_image()

    assert image == JPEG
    device.account.request.assert_awaited_once_with(
        "token/cameraLitterbox/getPicUrl",
        {"deviceId": "visual-c07-1", "picId": "private-picture-id"},
    )
    device.account.http.get.assert_called_once()
    _, kwargs = device.account.http.get.call_args
    assert kwargs == {"allow_redirects": False, "timeout": 10}


@pytest.mark.asyncio
async def test_latest_event_picture_rejects_non_aliyun_url(device):
    device.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {"picUrl": "https://127.0.0.1/private"},
        }
    )
    device.account.http.get = MagicMock()

    assert await device.async_get_latest_event_image() is None
    device.account.http.get.assert_not_called()


@pytest.mark.asyncio
async def test_latest_event_picture_rejects_non_image(device):
    device.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {"picUrl": "https://bucket.aliyuncs.com/private"},
        }
    )
    device.account.http.get = MagicMock(
        return_value=_Response(b"not-an-image", content_type="text/plain")
    )

    assert await device.async_get_latest_event_image() is None


@pytest.mark.asyncio
async def test_camera_entity_returns_event_picture(device):
    device.async_get_latest_event_image = AsyncMock(return_value=JPEG)
    entity = CatlinkCameraEntity(
        "latest_event_picture",
        device,
        {
            "name": "Latest Event Picture",
            "async_image": device.async_get_latest_event_image,
        },
    )

    assert await entity.async_camera_image() == JPEG
    assert entity.name.endswith("Latest Event Picture")
