"""Tests for the live talk websocket API (`catlink/talk`)."""

from __future__ import annotations

import asyncio
import base64
from array import array
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.catlink import websocket_api as catlink_ws
from custom_components.catlink.devices.scooper_pro_ultra import ScooperProUltraDevice
from custom_components.catlink.entities.media_player import CatlinkMediaPlayerEntity
from custom_components.catlink.modules import talkback
from custom_components.catlink.modules.rtmp_talk import crypto_key_material
from custom_components.catlink.modules.talkback import LiveTalkSession
import pytest

from homeassistant.setup import async_setup_component

from tests.test_rtmp_talk import FakeRtmpServer
from tests.test_talkback import CRYPTO_KEY, _linkvisual, _url

ENTITY_ID = "media_player.catlink_speaker"
KEY, IV = crypto_key_material(CRYPTO_KEY)

PRO_ULTRA = {
    "id": "ultra1",
    "mac": "44:72:AC:0D:89:37",
    "model": "MODEL_00",
    "deviceName": "Ultra",
    "deviceType": "VISUAL_PRO_ULTRA",
    "iotId": "iot-ws",
}


@pytest.fixture(autouse=True)
def fast_live(monkeypatch):
    """Short lead-in and waits, so a session takes milliseconds."""
    monkeypatch.setattr(talkback, "LEAD_IN_SECONDS", 0.02)
    monkeypatch.setattr(talkback, "TALK_READY_WAIT", 1.0)
    monkeypatch.setattr(talkback, "LIVE_IDLE_SECONDS", 5.0)
    monkeypatch.setattr(talkback, "INTERCOM_BUSY_RETRY", 0.01)


def _speaker(hass, linkvisual) -> CatlinkMediaPlayerEntity:
    """Build a Pro Ultra speaker entity bound to this LinkVisual client."""
    device = ScooperProUltraDevice(PRO_ULTRA, MagicMock())
    device.iot_online = True
    device.account.linkvisual = linkvisual
    option = dict(device.hass_media_player["speaker"])
    entity = CatlinkMediaPlayerEntity("speaker", device, option)
    entity.hass = hass
    entity.entity_id = ENTITY_ID
    entity.async_write_ha_state = MagicMock()
    return entity


async def _setup(hass, entity) -> None:
    """Register the command and make the entity findable by its id."""
    assert await async_setup_component(hass, "websocket_api", {})
    hass.data["media_player"] = SimpleNamespace(
        get_entity=lambda eid: entity if eid == ENTITY_ID else None
    )
    catlink_ws.async_register(hass)


async def _talk(client, **kwargs) -> dict:
    """Send the talk command and return the result message."""
    await client.send_json({"id": 5, "type": "catlink/talk", "entity_id": ENTITY_ID, **kwargs})
    return await client.receive_json()


class TestRegistration:
    """How the command gets into Home Assistant."""

    async def test_registration_is_idempotent(self, hass) -> None:
        """Registering twice does not raise (setup and setup_entry both call it)."""
        assert await async_setup_component(hass, "websocket_api", {})

        catlink_ws.async_register(hass)
        catlink_ws.async_register(hass)

        assert hass.data["catlink"][catlink_ws.REGISTERED] is True


class TestTalk:
    """Talking to the box through the websocket."""

    async def test_ready_audio_and_stop(self, hass, hass_ws_client, socket_enabled) -> None:
        """Ready arrives after TalkReady, binary frames reach the box."""
        server = FakeRtmpServer(needs_request=True)
        base = await server.start()
        entity = _speaker(hass, _linkvisual(_url(base)))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)
        try:
            result = await _talk(client, sample_rate=16000)
            assert result["success"] is True
            event = (await client.receive_json())["event"]
            assert event["type"] == "ready"
            assert event["sample_rate_in"] == 16000
            assert event["format"] == "pcm_s16le"
            handler_id = event["binary_handler_id"]
            assert entity.state == "playing"
            assert entity.extra_state_attributes == {"talking": True}

            pcm = array("h", [4000] * 1600).tobytes()  # 100 ms at 16 kHz
            for _ in range(3):
                await client.send_bytes(bytes([handler_id]) + pcm)
                await asyncio.sleep(0.1)
            await client.send_bytes(bytes([handler_id]))  # empty = stop

            ended = (await client.receive_json())["event"]
        finally:
            await server.stop()

        assert ended == {"type": "ended", "reason": "stopped"}
        assert server.audio and {csid for csid, _, _ in server.audio} == {4}
        assert all(len(body) % 16 == 0 for _, _, body in server.audio)
        assert entity.extra_state_attributes == {"talking": False}

    async def test_unsubscribe_stops_the_session(
        self, hass, hass_ws_client, socket_enabled
    ) -> None:
        """Unsubscribing ends the talk and closes the connection to the box."""
        server = FakeRtmpServer()
        base = await server.start()
        entity = _speaker(hass, _linkvisual(_url(base)))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)
        try:
            await _talk(client)
            assert (await client.receive_json())["event"]["type"] == "ready"

            await client.send_json({"id": 6, "type": "unsubscribe_events", "subscription": 5})
            assert (await client.receive_json())["success"] is True
            for _ in range(50):
                if entity._live_talk is None:
                    break
                await asyncio.sleep(0.05)
        finally:
            await server.stop()

        assert entity._live_talk is None

    async def test_listening_sends_the_box_audio(
        self, hass, hass_ws_client, socket_enabled
    ) -> None:
        """With listen: true the box's microphone comes back as PCM events."""
        server = FakeRtmpServer(
            crypto=(KEY, IV), downlink=4, downlink_size=320, downlink_config=True,
            downlink_byte=0x2A,
        )
        base = await server.start()
        entity = _speaker(hass, _linkvisual(_url(base)))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)
        try:
            await _talk(client, listen=True)
            assert (await client.receive_json())["event"]["type"] == "ready"
            audio = (await client.receive_json())["event"]
        finally:
            await entity._live_talk.async_stop()
            await server.stop()

        assert audio["type"] == "audio"
        assert audio["format"] == "pcm_s16le"
        assert audio["sample_rate"] == 8000
        raw = base64.b64decode(audio["data"])
        assert len(raw) == 640  # 320 A-law bytes = 40 ms, two bytes a sample
        assert set(array("h", raw)) == {-32256}  # 0x2A decoded

    async def test_busy_box_is_an_error(self, hass, hass_ws_client) -> None:
        """A box that already has a session answers `busy`, before `ready`."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x", codes=(9543, 9543)))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)

        result = await _talk(client)

        assert result["success"] is False
        assert result["error"]["code"] == "busy"

    async def test_unknown_entity(self, hass, hass_ws_client) -> None:
        """An entity that is not a CatLink speaker is not found."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x"))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)

        await client.send_json(
            {"id": 5, "type": "catlink/talk", "entity_id": "media_player.other"}
        )
        result = await client.receive_json()

        assert result["error"]["code"] == "not_found"

    async def test_alaw_must_be_eight_kilohertz(self, hass, hass_ws_client) -> None:
        """A-law at any other rate is refused before anything is opened."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x"))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)

        result = await _talk(client, format="alaw", sample_rate=16000)

        assert result["error"]["code"] == "not_supported"

    async def test_a_rate_the_box_cannot_take(self, hass, hass_ws_client) -> None:
        """Only the documented sample rates pass the schema."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x"))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)

        result = await _talk(client, sample_rate=11025)

        assert result["success"] is False
        assert result["error"]["code"] == "invalid_format"

    async def test_a_speaker_without_live_talk(self, hass, hass_ws_client) -> None:
        """An entity whose device cannot talk live says so."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x"))
        entity._option.pop("live_talk")
        await _setup(hass, entity)
        client = await hass_ws_client(hass)

        result = await _talk(client)

        assert result["error"]["code"] == "not_supported"

    async def test_the_factory_builds_a_live_session(self, hass) -> None:
        """The device's factory makes a session bound to its box."""
        entity = _speaker(hass, _linkvisual("rtmp://127.0.0.1:1/x"))

        session = entity.live_talk_session(audio_format="alaw", sample_rate=8000)

        assert isinstance(session, LiveTalkSession)
        assert session.iot_id == "iot-ws"
        assert session.name == "Ultra"

    async def test_nothing_secret_is_logged(
        self, hass, hass_ws_client, socket_enabled, caplog
    ) -> None:
        """The session's URL, token and crypto key never reach the log."""
        server = FakeRtmpServer()
        base = await server.start()
        entity = _speaker(hass, _linkvisual(_url(base)))
        await _setup(hass, entity)
        client = await hass_ws_client(hass)
        with caplog.at_level("DEBUG"):
            try:
                await _talk(client)
                assert (await client.receive_json())["event"]["type"] == "ready"
                await entity._live_talk.async_stop()
                await client.receive_json()
            finally:
                await server.stop()

        assert "SECRETTOKENVALUE123" not in caplog.text
        assert "SECRETSESSION99" not in caplog.text
        assert CRYPTO_KEY["key"] not in caplog.text
