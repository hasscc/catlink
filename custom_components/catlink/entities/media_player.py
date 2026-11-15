"""Media player entity for CatLink integration.

A device offering an "async_play_stream" option gets a speaker: any audio HA
can reach (a media-source item, a URL, a TTS message) is decoded to G.711
A-law 8 kHz mono and pushed through the talk-back channel
(`modules/talkback.py`).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ENTITY_ID_FORMAT,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)

from ..const import _LOGGER
from ..devices.base import Device
from ..modules.talkback import FfmpegAlawSource, LiveTalkSession
from .base import CatlinkEntity

# How long play_media waits for the box to start playing before it returns
# anyway; the talk-back code gives up on its own well before this.
START_TIMEOUT = 30.0


class CatlinkMediaPlayerEntity(MediaPlayerEntity, CatlinkEntity):
    """Speaker that plays audio through the device's talk-back channel.

    MediaPlayerEntity comes first in the MRO so its own state property wins.
    Only one playback runs at a time: a new one stops the one before it.
    """

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
    )
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(self, name, device: Device, option=None) -> None:
        """Initialize the speaker."""
        CatlinkEntity.__init__(self, name, device, option)
        self._attr_state = MediaPlayerState.IDLE
        self._playing: asyncio.Task | None = None
        self._live_talk: LiveTalkSession | None = None

    @property
    def state(self) -> MediaPlayerState:
        """Return whether audio is playing right now.

        A live talk session also holds the speaker open, so the entity is
        PLAYING then too; the `talking` attribute tells the two apart.
        """
        playing = self._playing is not None and not self._playing.done()
        return (
            MediaPlayerState.PLAYING
            if playing or self._live_talk is not None
            else MediaPlayerState.IDLE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Say whether somebody is talking live through the box right now."""
        return {"talking": self._live_talk is not None}

    def live_talk_session(self, **kwargs: Any) -> LiveTalkSession:
        """Build a live talk session for this box (used by the websocket API)."""
        factory = self._option.get("live_talk")
        if not callable(factory):
            raise NotImplementedError(f"{self.entity_id} cannot talk live")
        return factory(**kwargs)

    def note_live_talk(self, session: LiveTalkSession | None) -> None:
        """Remember a live talk session so the speaker shows it (or forget it)."""
        if session is None and self._live_talk is None:
            return
        self._live_talk = session
        self.async_write_ha_state()

    def update(self) -> None:
        """Keep the coordinator from overwriting the playback state."""
        state = self._attr_state
        CatlinkEntity.update(self)
        self._attr_state = state

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant's media sources, audio only."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a media source item, a URL or a TTS message on the speaker.

        Any media type is accepted: the box only ever gets A-law audio. An
        announcement is just a playback, there is nothing to duck or resume.
        """
        await self.async_media_stop()
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url
        media_id = async_process_play_media_url(self.hass, media_id)
        started: asyncio.Event = asyncio.Event()
        task = self.hass.async_create_task(self._async_play(media_id, started))
        self._playing = task
        self.async_write_ha_state()
        # Return as soon as the box is playing, so a tts.speak in an
        # automation is not held for the whole message. Failures before that
        # are raised to the caller, later ones only reach the log.
        waiter = self.hass.async_create_task(started.wait())
        try:
            await asyncio.wait(
                {task, waiter},
                timeout=START_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            waiter.cancel()
        if task.done() and not started.is_set():
            # It never got as far as playing: the caller gets the error.
            self._playing = None
            self.async_write_ha_state()
            if not task.cancelled() and (err := task.exception()):
                raise err
            return
        if task.done():
            self._playback_done(task)
            return
        task.add_done_callback(self._playback_done)

    def _playback_done(self, task: asyncio.Task) -> None:
        """Log a playback that failed after it had started, and go idle."""
        if self._playing is task:
            self._playing = None
            self.async_write_ha_state()
        if task.cancelled():
            return
        if err := task.exception():
            _LOGGER.warning("Playback on %s stopped: %s", self.entity_id, err)

    async def _async_play(self, url: str, started: asyncio.Event | None = None) -> None:
        """Decode the audio and push it through the talk-back channel."""
        play = self._option.get("async_play_stream")
        if not callable(play):
            raise NotImplementedError(f"{self.entity_id} cannot play audio")
        async with FfmpegAlawSource(self.hass, url) as source:
            await play(source.async_frames(), on_started=started.set if started else None)

    async def async_media_stop(self) -> None:
        """Stop whatever is playing, live talk included (the session closes)."""
        session, self._live_talk = self._live_talk, None
        if session is not None:
            with contextlib.suppress(Exception):
                await session.async_stop("stopped")
            self.async_write_ha_state()
        task, self._playing = self._playing, None
        if task is None or task.done():
            return
        _LOGGER.debug("Stopping playback on %s", self.entity_id)
        task.cancel()
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await task
        self.async_write_ha_state()
