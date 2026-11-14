"""Live talk over Home Assistant's websocket API (Scooper Pro Ultra).

A panel subscribes to `catlink/talk` with the speaker's entity id and gets a
binary handler id back; every binary frame it then sends is microphone audio
that comes out of the box's speaker. With `listen: true` the box's own
microphone comes back as `audio` events. docs/LIVE_TALK_API.md is the
panel's side of this.

Any logged-in user may talk: `media_player.play_media` already allows the
same thing, so requiring an admin would only get in a dashboard's way.
"""

from __future__ import annotations

import base64
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import _LOGGER, DOMAIN
from .entities.media_player import CatlinkMediaPlayerEntity
from .modules.rtmp_talk import alaw_to_pcm16
from .modules.talkback import (
    AUDIO_FORMATS,
    AUDIO_RATE,
    BUSY_MESSAGE,
    FORMAT_ALAW,
    FORMAT_PCM,
    PCM_SAMPLE_RATES,
    LiveTalkSession,
)

TALK_COMMAND = "catlink/talk"
REGISTERED = "websocket_api_registered"


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the websocket commands once per Home Assistant run."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(REGISTERED):
        return
    data[REGISTERED] = True
    websocket_api.async_register_command(hass, websocket_talk)


def _find_speaker(hass: HomeAssistant, entity_id: str) -> CatlinkMediaPlayerEntity | None:
    """Return the CatLink speaker entity with this id, if there is one."""
    component = hass.data.get(MEDIA_PLAYER_DOMAIN)
    entity = component.get_entity(entity_id) if component is not None else None
    return entity if isinstance(entity, CatlinkMediaPlayerEntity) else None


@websocket_api.websocket_command(
    {
        vol.Required("type"): TALK_COMMAND,
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("format", default=FORMAT_PCM): vol.In(AUDIO_FORMATS),
        vol.Optional("sample_rate", default=16000): vol.In(PCM_SAMPLE_RATES),
        vol.Optional("listen", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_talk(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Hold a live talk session open for as long as the subscription lasts."""
    entity_id: str = msg["entity_id"]
    audio_format: str = msg["format"]
    sample_rate: int = msg["sample_rate"]
    msg_id: int = msg["id"]

    if audio_format == FORMAT_ALAW and sample_rate != AUDIO_RATE:
        connection.send_error(
            msg_id,
            "not_supported",
            f"alaw audio is always {AUDIO_RATE} Hz; send sample_rate {AUDIO_RATE}",
        )
        return
    speaker = _find_speaker(hass, entity_id)
    if speaker is None:
        connection.send_error(
            msg_id, websocket_api.const.ERR_NOT_FOUND, f"{entity_id} is not a CatLink speaker"
        )
        return

    unsubscribed = False
    ready = False
    early: list[bytes] = []

    @callback
    def _send_audio(alaw: bytes) -> None:
        """Pass the box's microphone on to the panel (~40 ms per event).

        The box can start talking before the subscription is confirmed, and
        no event may go out before that, so early audio is held back.
        """
        if not ready:
            if len(early) < 25:  # ~1 s, then drop it
                early.append(alaw)
            return
        payload = alaw if audio_format == FORMAT_ALAW else alaw_to_pcm16(alaw)
        connection.send_event(
            msg_id,
            {
                "type": "audio",
                "format": audio_format,
                "sample_rate": AUDIO_RATE,
                "data": base64.b64encode(payload).decode(),
            },
        )

    try:
        session: LiveTalkSession = speaker.live_talk_session(
            audio_format=audio_format,
            sample_rate=sample_rate,
            on_audio=_send_audio if msg["listen"] else None,
        )
    except (NotImplementedError, ValueError) as err:
        connection.send_error(msg_id, "not_supported", str(err))
        return

    try:
        await session.async_start()
    except HomeAssistantError as err:
        code = "busy" if BUSY_MESSAGE in str(err) else "talk_failed"
        connection.send_error(msg_id, code, str(err))
        return
    except Exception as err:  # noqa: BLE001 - the panel gets an error, not a traceback
        _LOGGER.exception("Live talk on %s could not start", entity_id)
        connection.send_error(msg_id, "talk_failed", str(err) or type(err).__name__)
        return

    @callback
    def _handle_binary(
        _hass: HomeAssistant,
        _connection: websocket_api.ActiveConnection,
        data: bytes,
    ) -> None:
        """Take one binary frame: audio, or an empty frame to stop."""
        if not data:
            hass.async_create_task(session.async_stop("stopped"))
            return
        session.feed(data)

    handler_id, unregister_handler = connection.async_register_binary_handler(
        _handle_binary
    )

    @callback
    def _unsubscribe() -> None:
        """Stop the session when the panel unsubscribes or disconnects."""
        nonlocal unsubscribed
        unsubscribed = True
        hass.async_create_task(session.async_stop("stopped"))

    connection.subscriptions[msg_id] = _unsubscribe
    connection.send_result(msg_id)
    speaker.note_live_talk(session)
    connection.send_event(
        msg_id,
        {
            "type": "ready",
            "binary_handler_id": handler_id,
            "sample_rate_in": sample_rate,
            "format": audio_format,
            "listen": msg["listen"],
        },
    )
    _LOGGER.debug("Live talk on %s started (%s %s Hz)", entity_id, audio_format, sample_rate)
    ready = True
    for batch in early:
        _send_audio(batch)
    early.clear()

    try:
        reason = await session.async_wait()
    finally:
        unregister_handler()
        speaker.note_live_talk(None)
    if not unsubscribed:
        connection.send_event(msg_id, {"type": "ended", "reason": reason})
