"""Tests for the CatLink camera entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.catlink.devices.scooper_pro_ultra import ScooperProUltraDevice
from custom_components.catlink.entities import camera as camera_module
from custom_components.catlink.entities.camera import CatlinkCameraEntity
from custom_components.catlink.modules.linkvisual import LinkVisualError
import pytest

from homeassistant.components.camera import Camera, CameraState
from homeassistant.core import HomeAssistant


@pytest.fixture
def device():
    """A Scooper Pro Ultra with an iotId."""
    coordinator = MagicMock()
    return ScooperProUltraDevice(
        {
            "id": "ultra1",
            "mac": "44:72:AC:0D:89:37",
            "model": "MODEL_00",
            "deviceName": "Ultra",
            "deviceType": "VISUAL_PRO_ULTRA",
            "iotId": "iot-1",
        },
        coordinator,
    )


def _camera(device, stream_source) -> CatlinkCameraEntity:
    return CatlinkCameraEntity("camera", device, {"stream_source": stream_source})


def _hass(*components: str) -> MagicMock:
    hass = MagicMock()
    hass.config.components = set(components)
    return hass


async def test_stream_source_returns_fresh_url(device) -> None:
    """Without go2rtc, stream_source returns the URL the device issues."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = _hass()

    assert await entity.stream_source() == "rtmp://relay/1"


async def test_stream_source_wraps_url_for_go2rtc(device) -> None:
    """With go2rtc, the URL is handed to its ffmpeg source."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = _hass("go2rtc")

    assert await entity.stream_source() == "ffmpeg:rtmp://relay/1"


async def test_ha_stream_gets_plain_url_with_go2rtc(device) -> None:
    """Home Assistant's own stream component always gets the plain URL."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = _hass("go2rtc")
    entity.hass.async_create_background_task.side_effect = lambda coro, name: coro.close()
    seen = []

    async def _create_stream(self):
        seen.append(await self.stream_source())
        return MagicMock()

    with patch.object(Camera, "async_create_stream", _create_stream):
        await entity.async_create_stream()

    assert seen == ["rtmp://relay/1"]
    assert await entity.stream_source() == "ffmpeg:rtmp://relay/1"


async def test_stream_source_handles_errors(device) -> None:
    """A LinkVisual failure yields no stream instead of raising."""
    entity = _camera(device, AsyncMock(side_effect=LinkVisualError("offline")))

    assert await entity.stream_source() is None


def test_state_is_camera_state(device) -> None:
    """The camera reports Camera's state, not CatlinkEntity's."""
    entity = _camera(device, AsyncMock())

    assert entity.state == CameraState.IDLE


def _bg_hass() -> MagicMock:
    """hass stub whose background tasks are recorded and not run."""
    hass = MagicMock()
    hass.async_create_background_task.side_effect = lambda coro, name: coro.close()
    return hass


async def test_snapshot_never_opens_the_stream(device) -> None:
    """With nothing at hand the snapshot is empty; the stream isn't touched."""
    source = AsyncMock(return_value="rtmp://relay/1")
    entity = _camera(device, source)
    entity.hass = MagicMock()

    with patch.object(camera_module, "async_get_image", AsyncMock()) as get_image:
        assert await entity.async_camera_image() is None

    source.assert_not_awaited()
    get_image.assert_not_awaited()


async def test_snapshot_is_newest_of_picture_and_frame(device) -> None:
    """The newer of the device's event picture and the kept live frame wins."""
    still = MagicMock(return_value=(b"event", 200.0))
    entity = CatlinkCameraEntity(
        "camera", device, {"stream_source": AsyncMock(), "still_image": still}
    )
    entity._frame, entity._frame_time = b"frame", 100.0

    assert await entity.async_camera_image(width=320) == b"event"

    entity._frame_time = 300.0
    assert await entity.async_camera_image() == b"frame"

    still.return_value = (None, 0.0)
    assert await entity.async_camera_image() == b"frame"


async def test_webrtc_session_keeps_frames(device, monkeypatch) -> None:
    """A WebRTC session (it sends candidates) starts frame keeping until it closes."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = MagicMock()
    entity.entity_id = "camera.ultra"
    started = []
    monkeypatch.setattr(entity, "_start_keeping_frames", lambda: started.append(1))
    monkeypatch.setattr(Camera, "async_on_webrtc_candidate", AsyncMock())
    monkeypatch.setattr(Camera, "close_webrtc_session", MagicMock())

    await entity.async_on_webrtc_candidate("s1", MagicMock())
    assert entity._viewing() is True and started

    entity.close_webrtc_session("s1")
    assert entity._viewing() is False


async def test_keep_frames_loop(device, monkeypatch) -> None:
    """While viewing, a frame is grabbed every interval; it stops when the view closes."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = MagicMock()
    entity._webrtc_sessions = {"s1"}
    sleeps = []

    async def _sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            entity._webrtc_sessions.clear()  # viewer leaves

    monkeypatch.setattr(camera_module.asyncio, "sleep", _sleep)
    with patch.object(
        camera_module, "async_get_image", AsyncMock(side_effect=[b"f1", b"f2"])
    ):
        await entity._async_keep_frames()

    assert sleeps == [camera_module.FRAME_FIRST_DELAY, camera_module.FRAME_INTERVAL, camera_module.FRAME_INTERVAL]
    assert entity._frame == b"f2" and entity._frame_time > 0


async def test_provider_check_does_not_keep_frames(device) -> None:
    """HA asking for the source (provider check) is not a live view."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/1"))
    entity.hass = _hass("go2rtc")

    await entity.stream_source()

    entity.hass.async_create_background_task.assert_not_called()
    assert entity._viewing() is False


async def test_idle_stream_gets_fresh_url_on_restart(device) -> None:
    """Reopening an idle stream swaps its expired URL for a new one."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/new"))
    entity.hass = _bg_hass()
    stream = MagicMock(source="rtmp://relay/old")
    stream.outputs.return_value = {}
    entity.stream = stream

    with patch.object(Camera, "async_create_stream", AsyncMock(return_value=stream)):
        assert await entity.async_create_stream() is stream

    assert stream.source == "rtmp://relay/new"
    stream.set_update_callback.assert_called_once_with(entity._async_stream_state_changed)


async def test_active_stream_keeps_its_url(device) -> None:
    """A stream that is being watched is left alone."""
    source = AsyncMock(return_value="rtmp://relay/new")
    entity = _camera(device, source)
    entity.hass = _bg_hass()
    stream = MagicMock(source="rtmp://relay/old")
    stream.outputs.return_value = {"hls": MagicMock()}
    entity.stream = stream

    with patch.object(Camera, "async_create_stream", AsyncMock(return_value=stream)):
        await entity.async_create_stream()

    assert stream.source == "rtmp://relay/old"
    source.assert_not_awaited()


async def test_failing_stream_gets_fresh_url(hass: HomeAssistant, device) -> None:
    """When the stream worker fails, the next retry uses a new URL."""
    entity = _camera(device, AsyncMock(return_value="rtmp://relay/new"))
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()
    entity.stream = MagicMock(source="rtmp://relay/old", available=False)

    entity._async_stream_state_changed()
    await hass.async_block_till_done()

    assert entity.stream.source == "rtmp://relay/new"
    assert entity._refreshing_source is False
