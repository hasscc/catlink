"""Tests for live talk: the resampler, the jitter buffer and the session."""

from __future__ import annotations

import asyncio
from array import array

from custom_components.catlink.modules import talkback
from custom_components.catlink.modules.rtmp_talk import (
    ALAW_DECODE_TABLE,
    alaw_to_linear,
    alaw_to_pcm16,
    crypto_key_material,
    linear_to_alaw,
)
from custom_components.catlink.modules.talkback import (
    AUDIO_RATE,
    LiveTalkSession,
    PcmResampler,
    async_play_alaw,
    talk_holder,
)
import pytest

from homeassistant.exceptions import HomeAssistantError

from tests.test_rtmp_talk import FakeRtmpServer
from tests.test_talkback import CRYPTO_KEY, _linkvisual, _url

KEY, IV = crypto_key_material(CRYPTO_KEY)


def _pcm(samples: list[int]) -> bytes:
    """Pack samples as little-endian 16-bit PCM."""
    return array("h", samples).tobytes()


@pytest.fixture(autouse=True)
def fast_live(monkeypatch):
    """Keep the shape of the pacing but make a session take milliseconds."""
    monkeypatch.setattr(talkback, "LEAD_IN_SECONDS", 0.02)
    monkeypatch.setattr(talkback, "TALK_READY_WAIT", 1.0)
    monkeypatch.setattr(talkback, "HOLD_SECONDS", 0.01)
    monkeypatch.setattr(talkback, "LIVE_IDLE_SECONDS", 1.0)


class TestResampler:
    """PCM s16le at any supported rate down to 8 kHz A-law."""

    def test_integer_ratios_shrink_by_the_ratio(self) -> None:
        """16, 24, 32 and 48 kHz give one A-law byte per n input samples."""
        for rate in (16000, 24000, 32000, 48000):
            samples = rate // 10  # 100 ms
            out = PcmResampler(rate)(_pcm([0] * samples))
            assert len(out) == AUDIO_RATE // 10
            assert set(out) == {0xD5}  # silence stays silence

    def test_eight_kilohertz_only_encodes(self) -> None:
        """At 8 kHz nothing is resampled, one byte per sample."""
        out = PcmResampler(8000)(_pcm([0, 1000, -1000]))

        assert out == bytes(linear_to_alaw(s) for s in (0, 1000, -1000))

    def test_chunks_and_odd_bytes_carry_over(self) -> None:
        """A split sample and a half-frame are kept for the next chunk."""
        resampler = PcmResampler(16000)
        raw = _pcm([5000] * 8)

        first = resampler(raw[:5])  # 2 samples + 1 stray byte
        second = resampler(raw[5:])

        assert len(first) == 1
        assert len(first) + len(second) == 4

    def test_forty_four_one_interpolates(self) -> None:
        """44.1 kHz is linearly interpolated to about 8 kHz, chunk by chunk."""
        resampler = PcmResampler(44100)
        one_second = _pcm([0] * 44100)

        out = b"".join(resampler(one_second[i:i + 4410]) for i in range(0, 88200, 4410))

        assert abs(len(out) - AUDIO_RATE) <= 2
        assert set(out) == {0xD5}

    def test_a_tone_keeps_its_shape(self) -> None:
        """Averaging 16 kHz down does not turn a loud tone into silence."""
        import math  # noqa: PLC0415

        samples = [int(20000 * math.sin(2 * math.pi * 300 * n / 16000)) for n in range(1600)]

        out = PcmResampler(16000)(_pcm(samples))
        decoded = [alaw_to_linear(b) for b in out]

        assert len(out) == 800
        assert max(decoded) > 15000 and min(decoded) < -15000

    def test_unsupported_rate(self) -> None:
        """A rate the box cannot be fed is refused."""
        with pytest.raises(ValueError, match="unsupported sample rate"):
            PcmResampler(11025)


class TestAlawDecode:
    """Decoding what the box sends back."""

    def test_round_trip(self) -> None:
        """Every A-law byte decodes to a sample that encodes back to it."""
        assert len(ALAW_DECODE_TABLE) == 256
        assert all(linear_to_alaw(alaw_to_linear(b)) == b for b in range(256))

    def test_pcm16_bytes(self) -> None:
        """Decoding gives little-endian 16-bit samples, two bytes each."""
        raw = alaw_to_pcm16(bytes([0xD5, 0x55]))

        assert len(raw) == 4
        assert array("h", raw).tolist() == [8, -8]


class TestFeeding:
    """The jitter buffer, before anything is connected."""

    def _session(self, **kwargs) -> LiveTalkSession:
        return LiveTalkSession(None, "iot-1", name="Ultra", **kwargs)

    def test_alaw_is_passed_through(self) -> None:
        """A-law callers feed bytes straight into the buffer."""
        session = self._session(audio_format="alaw", sample_rate=8000)

        session.feed(b"\xd5" * 100)

        assert bytes(session._buffer) == b"\xd5" * 100
        assert session.fed_bytes == 100

    def test_drops_the_oldest_when_it_grows(self) -> None:
        """More than 500 ms queued means the oldest audio is thrown away."""
        session = self._session(audio_format="alaw", sample_rate=8000)

        session.feed(b"\x01" * 3000)
        session.feed(b"\x02" * 3000)

        assert len(session._buffer) == talkback.JITTER_MAX_BYTES
        assert session.dropped_bytes == 6000 - talkback.JITTER_MAX_BYTES
        assert bytes(session._buffer).endswith(b"\x02" * 100)  # the newest is kept

    def test_bad_arguments(self) -> None:
        """Only the two formats exist, and A-law is 8 kHz."""
        with pytest.raises(ValueError, match="unsupported format"):
            self._session(audio_format="mp3")
        with pytest.raises(ValueError, match="8000"):
            self._session(audio_format="alaw", sample_rate=16000)


class TestSession:
    """A live session against the fake relay."""

    async def _started(self, server: FakeRtmpServer, **kwargs) -> LiveTalkSession:
        base = await server.start()
        session = LiveTalkSession(
            _linkvisual(_url(base)), "iot-1", name="Ultra", **kwargs
        )
        await session.async_start()
        return session

    async def test_audio_reaches_the_box_and_stop_ends_it(self, socket_enabled) -> None:
        """Fed PCM comes out as encrypted A-law audio messages on csid 4."""
        server = FakeRtmpServer(needs_request=True)
        session = await self._started(server, sample_rate=16000)
        try:
            for _ in range(10):  # 200 ms of 16 kHz PCM
                session.feed(_pcm([1000] * 320))
            await asyncio.sleep(0.4)
            assert talk_holder("iot-1") is session
            await session.async_stop("stopped")
        finally:
            await server.stop()

        assert session.reason == "stopped"
        assert talk_holder("iot-1") is None
        assert {csid for csid, _, _ in server.audio} == {4}
        assert all(len(body) % 16 == 0 for _, _, body in server.audio)
        assert server.audio and len(server.audio) > 1

    async def test_it_waits_for_talk_ready(self, socket_enabled) -> None:
        """No TalkReady means the session never opens, and says so."""
        server = FakeRtmpServer(talk_ready=False)
        base = await server.start()
        session = LiveTalkSession(_linkvisual(_url(base)), "iot-1", name="Ultra")
        try:
            with pytest.raises(HomeAssistantError, match="did not open its speaker"):
                await session.async_start()
        finally:
            await server.stop()

        assert talk_holder("iot-1") is None

    async def test_busy_box(self, socket_enabled) -> None:
        """Code 9543 twice is reported as the box being busy."""
        session = LiveTalkSession(
            _linkvisual("rtmp://127.0.0.1:1/live?token=T", codes=(9543, 9543)),
            "iot-1",
            name="Ultra",
        )
        talkback.INTERCOM_BUSY_RETRY = 0.01
        with pytest.raises(HomeAssistantError, match="busy"):
            await session.async_start()

    async def test_idle_timeout(self, socket_enabled, monkeypatch) -> None:
        """A session nobody talks into ends by itself."""
        monkeypatch.setattr(talkback, "LIVE_IDLE_SECONDS", 0.2)
        server = FakeRtmpServer()
        session = await self._started(server)
        try:
            reason = await asyncio.wait_for(session.async_wait(), 5)
        finally:
            await server.stop()

        assert reason == "idle"
        assert session.active is False

    async def test_listening_session_does_not_idle_out(
        self, socket_enabled, monkeypatch
    ) -> None:
        """With a listener the session stays open between push-to-talk presses."""
        monkeypatch.setattr(talkback, "LIVE_IDLE_SECONDS", 0.2)
        server = FakeRtmpServer()
        session = await self._started(server, on_audio=lambda _audio: None)
        try:
            await asyncio.sleep(0.6)
            assert session.active is True
            await session.async_stop("stopped")
        finally:
            await server.stop()

        assert session.reason == "stopped"

    async def test_max_duration(self, socket_enabled, monkeypatch) -> None:
        """No session outlives the maximum, even with audio flowing."""
        monkeypatch.setattr(talkback, "LIVE_MAX_SECONDS", 0.1)
        server = FakeRtmpServer()
        session = await self._started(server, audio_format="alaw", sample_rate=8000)
        try:
            session.feed(b"\xd5" * 800)
            reason = await asyncio.wait_for(session.async_wait(), 5)
        finally:
            await server.stop()

        assert reason == "max duration"

    async def test_listening_decodes_the_box_microphone(self, socket_enabled) -> None:
        """With on_audio set the box's own audio comes back decrypted."""
        heard: list[bytes] = []
        server = FakeRtmpServer(
            crypto=(KEY, IV), downlink=4, downlink_size=320, downlink_config=True,
            downlink_byte=0x2A,
        )
        session = await self._started(server, on_audio=heard.append)
        try:
            await asyncio.sleep(0.3)
        finally:
            await session.async_stop()
            await server.stop()

        # The config packet carries no audio; the rest are 320 B batches.
        assert heard and all(len(batch) == 320 for batch in heard)
        assert set(b"".join(heard)) == {0x2A}

    async def test_live_talk_replaces_a_playback(self, socket_enabled) -> None:
        """Starting live talk stops a playback that holds the same box."""
        server = FakeRtmpServer()
        base = await server.start()
        linkvisual = _linkvisual(_url(base), codes=(200, 200))
        stopped = asyncio.Event()

        async def _frames():
            try:
                while True:
                    yield b"\xd5" * 160
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                stopped.set()
                raise

        playback = asyncio.create_task(
            async_play_alaw(linkvisual, "iot-1", _frames(), name="Ultra")
        )
        try:
            await asyncio.sleep(0.3)
            assert talk_holder("iot-1") is not None
            session = LiveTalkSession(linkvisual, "iot-1", name="Ultra")
            await session.async_start()
            await asyncio.wait_for(stopped.wait(), 5)
            assert talk_holder("iot-1") is session
            await session.async_stop()
        finally:
            playback.cancel()
            await asyncio.gather(playback, return_exceptions=True)
            await server.stop()

    async def test_a_playback_replaces_live_talk(self, socket_enabled) -> None:
        """A play_media during live talk ends the talk with 'replaced'."""
        server = FakeRtmpServer()
        base = await server.start()
        linkvisual = _linkvisual(_url(base), codes=(200, 200))
        session = LiveTalkSession(linkvisual, "iot-1", name="Ultra")
        await session.async_start()

        async def _frames():
            yield b"\xd5" * 160

        try:
            await async_play_alaw(linkvisual, "iot-1", _frames(), name="Ultra")
            assert await asyncio.wait_for(session.async_wait(), 5) == "replaced"
        finally:
            await session.async_stop()
            await server.stop()
