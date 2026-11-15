"""Tests for the talk-back playback helper (modules/talkback.py)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.catlink.modules import talkback
from custom_components.catlink.modules.linkvisual import LinkVisualError
from custom_components.catlink.modules.talkback import (
    FfmpegAlawSource,
    async_open_session,
    async_play_alaw,
    mask_rtmp_output,
    rtmp_url_shape,
    session_masks,
)
import pytest

from homeassistant.exceptions import HomeAssistantError

from tests.test_rtmp_talk import FakeRtmpServer

URL_SECRETS = ("SECRETTOKENVALUE123", "SECRETSESSION99")
CRYPTO_KEY = {"key": "U0VDUkVUS0VZU0VDUkVUSw==", "iv": "U0VDUkVUSVZTRUNSRVRJVg=="}


def _url(base: str) -> str:
    return f"{base}/live?token={URL_SECRETS[0]}&session={URL_SECRETS[1]}"


def _linkvisual(url: str, crypto_key=CRYPTO_KEY, *, codes=(200,)) -> MagicMock:
    """A LinkVisual client answering `async_start_intercom` with these codes."""
    replies = [
        {"code": code, "data": {"url": url, "cryptoKey": crypto_key, "supportPrePlay": False}}
        if code == 200
        else {"code": code, "message": "voice intercom existed"}
        for code in codes
    ]
    client = MagicMock()
    client.async_start_intercom = AsyncMock(side_effect=replies)
    return client


async def _frames(data: bytes, chunk: int = 160):
    for index in range(0, len(data), chunk):
        yield data[index:index + chunk]


@pytest.fixture(autouse=True)
def fast_pacing(monkeypatch):
    """Keep the pacing shape but make a playback take milliseconds."""
    monkeypatch.setattr(talkback, "LEAD_IN_SECONDS", 0.04)
    monkeypatch.setattr(talkback, "HOLD_SECONDS", 0.01)
    monkeypatch.setattr(talkback, "TALK_READY_WAIT", 1.0)


class TestSession:
    """Opening the intercom session."""

    async def test_url_and_key_come_back(self) -> None:
        """A 200 hands over the URL and the cryptoKey."""
        client = _linkvisual("rtmp://host/live?token=T")

        url, key = await async_open_session(client, "iot-1")

        assert (url, key) == ("rtmp://host/live?token=T", CRYPTO_KEY)

    async def test_busy_is_retried_once_then_reported(self) -> None:
        """9543 means a session is already open: one retry, then a clear error."""
        client = _linkvisual("rtmp://host/live", codes=(9543, 9543))

        with patch.object(talkback, "INTERCOM_BUSY_RETRY", 0):
            with pytest.raises(HomeAssistantError, match="busy with another talk session"):
                await async_open_session(client, "iot-1")

        assert client.async_start_intercom.await_count == 2

    async def test_busy_then_free(self) -> None:
        """The retry is used when the other session has gone."""
        client = _linkvisual("rtmp://host/live", codes=(9543, 200))

        with patch.object(talkback, "INTERCOM_BUSY_RETRY", 0):
            url, _ = await async_open_session(client, "iot-1")

        assert url == "rtmp://host/live"

    async def test_other_failures_are_reported(self) -> None:
        """Any other answer (or a transport error) raises with its reason."""
        client = _linkvisual("rtmp://host/live", codes=(460,))
        with pytest.raises(HomeAssistantError, match="code 460"):
            await async_open_session(client, "iot-1")

        client.async_start_intercom = AsyncMock(side_effect=LinkVisualError("down"))
        with pytest.raises(HomeAssistantError, match="down"):
            await async_open_session(client, "iot-1")


@pytest.mark.usefixtures("socket_enabled")
class TestPlayback:
    """One playback against the fake relay."""

    async def test_plays_the_recipe_and_logs_no_secrets(self, caplog) -> None:
        """Request, play, TalkReady, lead-in then the audio, all encrypted."""
        server = FakeRtmpServer(needs_request=True)
        base = await server.start()
        client = _linkvisual(_url(base))
        try:
            with caplog.at_level("DEBUG"):
                await async_play_alaw(
                    client, "iot-1", _frames(bytes([0x55]) * 480), name="Box"
                )
        finally:
            await server.stop()

        assert server.connections == 1
        assert server.commands[:4] == ["connect", "onStatus", "createStream", "play"]
        assert server.statuses[0]["audio_type"] == "1"
        # sequence header + 40 ms lead-in + 60 ms of audio, all encrypted
        assert len(server.audio) == 1 + 2 + 3
        assert all(len(body) % 16 == 0 for _, _, body in server.audio)
        assert {csid for csid, _, _ in server.audio} == {4}
        assert "Talk session for Box ended (done)" in caplog.text
        for secret in (*URL_SECRETS, "U0VDUkVU", "token=S"):
            assert secret not in caplog.text

    async def test_keeps_a_lead_on_real_time(self, monkeypatch) -> None:
        """The audio is sent ahead of real time, not burst and not behind."""
        monkeypatch.setattr(talkback, "LEAD_IN_SECONDS", 0.0)
        monkeypatch.setattr(talkback, "SEND_AHEAD_SECONDS", 0.1)
        server = FakeRtmpServer(needs_request=True)
        base = await server.start()
        client = _linkvisual(_url(base))
        started = asyncio.get_running_loop().time()
        try:
            # 400 ms of audio: sending must take about 300 ms (400 - 100 lead)
            await async_play_alaw(client, "iot-1", _frames(bytes(3200)), name="Box")
        finally:
            await server.stop()
        took = asyncio.get_running_loop().time() - started

        assert len(server.audio) == 1 + 20
        assert 0.2 < took < 0.6

    async def test_a_cancelled_playback_closes_the_connection(self) -> None:
        """Stopping mid-playback closes the socket, which ends the session."""
        server = FakeRtmpServer(needs_request=True)
        base = await server.start()
        client = _linkvisual(_url(base))

        async def _endless():
            while True:
                yield bytes(160)
                await asyncio.sleep(0)

        task = asyncio.create_task(
            async_play_alaw(client, "iot-1", _endless(), name="Box")
        )
        try:
            await asyncio.sleep(0.2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await server.stop()

        assert server.connections == 1
        assert server.audio  # something was playing when it was stopped

    async def test_no_talk_ready_is_an_error(self, caplog) -> None:
        """A relay that never opens the speaker is reported, not silently ignored."""
        server = FakeRtmpServer(talk_ready=False)
        base = await server.start()
        client = _linkvisual(_url(base))
        try:
            with pytest.raises(HomeAssistantError, match="did not open its speaker"):
                await async_play_alaw(client, "iot-1", _frames(bytes(160)), name="Box")
        finally:
            await server.stop()

    async def test_downlink_is_summarised(self, caplog) -> None:
        """The audio the box sends back is counted and sized, never dumped."""
        server = FakeRtmpServer(needs_request=True, downlink=3)
        base = await server.start()
        client = _linkvisual(_url(base))
        try:
            with caplog.at_level("DEBUG"):
                await async_play_alaw(client, "iot-1", _frames(bytes(320)), name="Box")
        finally:
            await server.stop()

        assert "'packets': 3" in caplog.text
        assert "'first_bytes': ['7e01'" in caplog.text


class TestMasking:
    """Nothing about a session may reach the log."""

    def test_rtmp_url_shape_has_no_values(self) -> None:
        """The shape log carries counts, lengths and parameter names only."""
        shape = rtmp_url_shape("rtmp://1.2.3.4:8000/live/SECRETNAME?auth=SECRETTOKEN&sid=S")

        assert shape == {
            "scheme": "rtmp", "host": "1.2.3.4:8000",
            "segments": 2, "segment_lens": [4, 10],
            "query": True, "query_names": ["auth", "sid"],
            "port": 8000, "app_len": 4, "app_has_query": False,
            "playpath_len": 33,
        }
        assert "SECRET" not in str(shape)

    def test_mask_rtmp_output_keeps_the_server_messages(self) -> None:
        """Values are masked, the server's own words survive."""
        url = "rtmp://1.2.3.4:8000/live/SECRETNAME?auth=SECRETTOKENVALUE123"
        masks = {url: "<url>", "/live/SECRETNAME?auth=SECRETTOKENVALUE123": "<path>",
                 "live": "<app>", "SECRETNAME?auth=SECRETTOKENVALUE123": "<playpath>",
                 "SECRETTOKENVALUE123": "<value>", "SECRETKEY": "<key>"}
        text = (
            f"[tcp @ 0x1] Connection to {url} failed\n"
            "[rtmp @ 0x2] Server error: NetStream.Publish.BadName\n"
            "[rtmp @ 0x2] level=error code=403 description=forbidden\n"
            "Delivering live frames with key SECRETKEY and SECRETTOKENVALUE123\n"
            "[rtmp @ 0x2] Sending rtmp://1.2.3.4:8000/other/AAAABBBBCCCCDDDD1234\n"
        )

        masked = mask_rtmp_output(text, masks)

        assert "SECRET" not in masked and "AAAABBBB" not in masked
        assert "NetStream.Publish.BadName" in masked
        assert "level=error code=403 description=forbidden" in masked
        assert "<url>" in masked and "<key>" in masked and "<app>" in masked

    def test_session_masks_cover_url_and_key(self) -> None:
        """URL, its parts, its query values and the crypto key are all masked."""
        url = "rtmp://1.2.3.4:8000/live?token=SECRETTOKENVALUE123&session=SECRETSESSION99"

        masks = session_masks(url, CRYPTO_KEY)
        masked = mask_rtmp_output(f"{url} with {CRYPTO_KEY}", masks)

        assert "SECRET" not in masked and "U0VDUkVU" not in masked


class TestFfmpeg:
    """Decoding media to A-law with Home Assistant's ffmpeg."""

    @staticmethod
    def _process(stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> MagicMock:
        process = MagicMock()
        process.stdout.read = AsyncMock(side_effect=[stdout, b""])
        process.stderr.read = AsyncMock(return_value=stderr)
        process.returncode = returncode
        process.wait = AsyncMock(return_value=returncode)
        return process

    async def test_frames_come_from_stdout(self) -> None:
        """The binary is asked for 8 kHz mono A-law on stdout."""
        hass = MagicMock()
        process = self._process(b"\xd5" * 160)
        with patch(
            "custom_components.catlink.modules.talkback.get_ffmpeg_manager"
        ) as manager, patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=process)
        ) as exec_:
            manager.return_value.binary = "/usr/bin/ffmpeg"
            async with FfmpegAlawSource(hass, "http://host/song.mp3") as source:
                frames = [frame async for frame in source.async_frames()]

        assert frames == [b"\xd5" * 160]
        args = exec_.await_args.args
        assert args[0] == "/usr/bin/ffmpeg"
        assert "http://host/song.mp3" in args
        assert args[-7:] == ("-f", "alaw", "-ar", "8000", "-ac", "1", "-")

    async def test_failure_is_warned_about(self, caplog) -> None:
        """ffmpeg's last words are logged when it fails."""
        hass = MagicMock()
        process = self._process(b"", b"No such file or directory\n", returncode=1)
        with patch(
            "custom_components.catlink.modules.talkback.get_ffmpeg_manager"
        ), patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with caplog.at_level("WARNING"):
                async with FfmpegAlawSource(hass, "http://host/missing.mp3") as source:
                    assert [frame async for frame in source.async_frames()] == []

        assert "No such file or directory" in caplog.text

    async def test_stop_kills_ffmpeg(self) -> None:
        """Leaving the context kills a still-running ffmpeg."""
        hass = MagicMock()
        process = self._process(b"\xd5" * 160)
        process.returncode = None
        with patch(
            "custom_components.catlink.modules.talkback.get_ffmpeg_manager"
        ), patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            async with FfmpegAlawSource(hass, "http://host/song.mp3"):
                pass

        process.kill.assert_called_once()
