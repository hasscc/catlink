"""Tests for the CatLink speaker (media player entity)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.catlink.devices.scooper_pro_ultra import ScooperProUltraDevice
from custom_components.catlink.entities.media_player import CatlinkMediaPlayerEntity
import pytest

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

PRO_ULTRA = {
    "id": "ultra1",
    "mac": "44:72:AC:0D:89:37",
    "model": "MODEL_00",
    "deviceName": "Ultra",
    "deviceType": "VISUAL_PRO_ULTRA",
    "iotId": "iot-1",
}


@pytest.fixture
def device():
    """A Scooper Pro Ultra that is online with live properties."""
    device = ScooperProUltraDevice(PRO_ULTRA, MagicMock())
    device.iot_online = True
    device.properties = {"RunStatus": "runStatus=0&biz=1"}
    return device


def _speaker(device, played: list | None = None) -> CatlinkMediaPlayerEntity:
    """Build the speaker entity, with the device's playback replaced."""
    option = dict(device.hass_media_player["speaker"])
    if played is not None:

        async def _play(frames, on_started=None) -> None:
            if on_started is not None:
                on_started()
            async for frame in frames:
                played.append(frame)

        option["async_play_stream"] = _play
    entity = CatlinkMediaPlayerEntity("speaker", device, option)
    entity.hass = MagicMock()
    entity.hass.async_create_task = lambda coro, *a, **kw: asyncio.ensure_future(coro)
    entity.async_write_ha_state = MagicMock()
    return entity


def _ffmpeg(audio: bytes):
    """Patch the A-law source so no ffmpeg is needed."""

    class _Source:
        def __init__(self, hass, media_id) -> None:
            self.media_id = media_id
            _Source.last = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None:
            return None

        async def async_frames(self):
            yield audio

    return patch(
        "custom_components.catlink.entities.media_player.FfmpegAlawSource", _Source
    ), _Source


class TestEntity:
    """What the entity looks like in Home Assistant."""

    def test_only_the_pro_ultra_gets_a_speaker(self, device) -> None:
        """The platform is opt-in: the device exposes hass_media_player."""
        from custom_components.catlink.devices.litterbox import LitterBox  # noqa: PLC0415

        assert list(device.hass_media_player) == ["speaker"]
        assert not hasattr(LitterBox({"id": "1"}, MagicMock()), "hass_media_player")

    def test_shape(self, device) -> None:
        """A speaker that plays, stops and browses, idle to start with."""
        entity = _speaker(device)

        assert entity.device_class == MediaPlayerDeviceClass.SPEAKER
        assert entity.supported_features == (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        )
        assert entity.state == MediaPlayerState.IDLE
        assert entity.translation_key == "speaker"

    def test_unavailable_when_the_box_is_not_live(self, device) -> None:
        """Without live properties the speaker cannot be used."""
        entity = _speaker(device)
        entity.coordinator.last_update_success = True
        assert entity.available is True

        device.iot_online = False

        assert entity.available is False

    async def test_browse_media_is_audio_only(self, device) -> None:
        """Browsing goes to the media sources, filtered to audio."""
        entity = _speaker(device)
        with patch(
            "custom_components.catlink.entities.media_player.media_source"
        ) as source:
            source.async_browse_media = AsyncMock(return_value="tree")

            assert await entity.async_browse_media(None, "media-source://") == "tree"

        kwargs = source.async_browse_media.await_args.kwargs
        item = MagicMock()
        item.media_content_type = "audio/mpeg"
        assert kwargs["content_filter"](item) is True
        item.media_content_type = "video/mp4"
        assert kwargs["content_filter"](item) is False


class TestPlayback:
    """Playing audio through the box."""

    async def test_plays_a_plain_url(self, device) -> None:
        """A URL is decoded and handed to the device as A-law frames."""
        played: list[bytes] = []
        entity = _speaker(device, played)
        patcher, source = _ffmpeg(b"\xd5" * 320)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            await entity.async_play_media("music", "http://host/song.mp3")

        assert source.last.media_id == "http://host/song.mp3"
        assert played == [b"\xd5" * 320]
        assert entity.state == MediaPlayerState.IDLE

    async def test_plays_a_media_source_id(self, device) -> None:
        """A media-source id (what tts.speak sends) is resolved first."""
        played: list[bytes] = []
        entity = _speaker(device, played)
        patcher, source = _ffmpeg(b"\x55" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player.media_source"
        ) as media, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: f"http://ha{url}",
        ):
            media.is_media_source_id.return_value = True
            media.async_resolve_media = AsyncMock(
                return_value=MagicMock(url="/api/tts_proxy/x.mp3")
            )

            await entity.async_play_media("provider", "media-source://tts/cloud?message=hi")

        media.async_resolve_media.assert_awaited_once()
        assert source.last.media_id == "http://ha/api/tts_proxy/x.mp3"
        assert played == [b"\x55" * 160]

    async def test_playing_state_and_stop(self, device) -> None:
        """While audio plays the state is playing; stop ends it."""
        entity = _speaker(device)
        started = asyncio.Event()

        async def _play(frames, on_started=None) -> None:
            if on_started is not None:
                on_started()
            started.set()
            await asyncio.sleep(10)

        entity._option["async_play_stream"] = _play
        patcher, _ = _ffmpeg(b"\xd5" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            # play_media returns as soon as the box is playing, so there is
            # no need to run it in the background any more.
            await entity.async_play_media("music", "http://host/song.mp3")
            await started.wait()
            assert entity.state == MediaPlayerState.PLAYING

            await entity.async_media_stop()

        assert entity.state == MediaPlayerState.IDLE

    async def test_a_new_playback_stops_the_one_before(self, device) -> None:
        """Playing again interrupts whatever is playing."""
        entity = _speaker(device)
        first_started = asyncio.Event()
        calls: list[str] = []

        async def _play(frames, on_started=None) -> None:
            calls.append("start")
            if on_started is not None:
                on_started()
            first_started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                calls.append("cancelled")
                raise

        entity._option["async_play_stream"] = _play
        patcher, _ = _ffmpeg(b"\xd5" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            await entity.async_play_media("music", "http://host/1.mp3")
            await first_started.wait()
            entity._option["async_play_stream"] = AsyncMock()
            await entity.async_play_media("music", "http://host/2.mp3")
            await asyncio.sleep(0)

        assert calls == ["start", "cancelled"]
        assert entity.state == MediaPlayerState.IDLE

    async def test_play_media_returns_once_the_box_is_playing(self, device) -> None:
        """A long message does not hold the service call open."""
        entity = _speaker(device)
        finished = asyncio.Event()

        async def _play(frames, on_started=None) -> None:
            on_started()
            await asyncio.sleep(10)
            finished.set()

        entity._option["async_play_stream"] = _play
        patcher, _ = _ffmpeg(b"\xd5" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            await asyncio.wait_for(
                entity.async_play_media("music", "http://host/long.mp3"), 2
            )

            assert entity.state == MediaPlayerState.PLAYING
            assert not finished.is_set()
            await entity.async_media_stop()

        assert entity.state == MediaPlayerState.IDLE

    async def test_a_failure_after_the_start_is_only_logged(self, device, caplog) -> None:
        """Once the box plays, a later error warns instead of raising."""
        entity = _speaker(device)

        async def _play(frames, on_started=None) -> None:
            on_started()
            await asyncio.sleep(0)
            raise RuntimeError("the relay hung up")

        entity._option["async_play_stream"] = _play
        patcher, _ = _ffmpeg(b"\xd5" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            await entity.async_play_media("music", "http://host/song.mp3")
            for _ in range(20):
                if entity.state == MediaPlayerState.IDLE:
                    break
                await asyncio.sleep(0.01)

        assert "the relay hung up" in caplog.text
        assert entity.state == MediaPlayerState.IDLE

    async def test_playback_errors_reach_the_caller(self, device) -> None:
        """A failed talk session is raised from the service call."""
        entity = _speaker(device)
        entity._option["async_play_stream"] = AsyncMock(
            side_effect=RuntimeError("box is busy")
        )
        patcher, _ = _ffmpeg(b"\xd5" * 160)
        with patcher, patch(
            "custom_components.catlink.entities.media_player"
            ".async_process_play_media_url",
            lambda hass, url: url,
        ):
            with pytest.raises(RuntimeError, match="box is busy"):
                await entity.async_play_media("music", "http://host/song.mp3")

        assert entity.state == MediaPlayerState.IDLE
