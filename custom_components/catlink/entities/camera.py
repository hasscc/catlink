"""Camera entity for CatLink integration."""

import asyncio
from contextvars import ContextVar
import time

from homeassistant.components.camera import ENTITY_ID_FORMAT, Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.core import callback
from webrtc_models import RTCIceCandidateInit

from ..const import _LOGGER
from ..modules.linkvisual import LinkVisualError
from .base import CatlinkEntity

# Snapshots never wake the camera; they show the newest image already at
# hand. While a live view is open (the camera is awake anyway) a frame is
# kept this often, the first once the stream has had time to start.
FRAME_INTERVAL = 15
FRAME_FIRST_DELAY = 8

# Set while Home Assistant's own stream component asks for the source; it
# needs the plain URL, while go2rtc needs it wrapped in "ffmpeg:".
_creating_ha_stream: ContextVar[bool] = ContextVar("_creating_ha_stream", default=False)


class CatlinkCameraEntity(Camera, CatlinkEntity):
    """Camera entity whose stream URL is fetched on demand and expires quickly.

    Camera comes first in the MRO so its (final) state property wins.
    """

    _attr_supported_features = CameraEntityFeature.STREAM
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(self, name, device, option=None) -> None:
        """Initialize the camera."""
        CatlinkEntity.__init__(self, name, device, option)
        Camera.__init__(self)
        self._frame: bytes | None = None
        self._frame_time = 0.0
        self._frame_task: asyncio.Task | None = None
        self._webrtc_sessions: set[str] = set()
        self._refreshing_source = False

    async def stream_source(self) -> str | None:
        """Return a freshly issued stream URL.

        go2rtc's built-in RTMP reader can't open the cloud relay (HEVC in FLV),
        so for go2rtc the URL is handed to ffmpeg instead.
        """
        url = await self._async_live_url()
        if url and not _creating_ha_stream.get() and "go2rtc" in self.hass.config.components:
            return f"ffmpeg:{url}"
        return url

    async def _async_live_url(self) -> str | None:
        fun = self._option.get("stream_source")
        if not callable(fun):
            return None
        try:
            return await fun()
        except LinkVisualError as exc:
            _LOGGER.warning("Getting stream for %s failed: %s", self.entity_id, exc)
            return None

    async def async_create_stream(self):
        """Create the stream, swapping in a fresh URL before an idle stream restarts."""
        token = _creating_ha_stream.set(True)
        try:
            restarting = self.stream is not None and not self.stream.outputs()
            stream = await super().async_create_stream()
        finally:
            _creating_ha_stream.reset(token)
        if stream is None:
            return None
        if restarting and (source := await self._async_live_url()):
            stream.source = source
        stream.set_update_callback(self._async_stream_state_changed)
        self._start_keeping_frames()
        return stream

    @callback
    def _async_stream_state_changed(self) -> None:
        """Write state, and give a failing stream worker a fresh URL to retry with."""
        self.async_write_ha_state()
        if self.stream and not self.stream.available and not self._refreshing_source:
            self._refreshing_source = True
            self.hass.async_create_task(self._async_refresh_stream_source())

    async def _async_refresh_stream_source(self) -> None:
        try:
            if self.stream and (source := await self._async_live_url()):
                self.stream.source = source
        finally:
            self._refreshing_source = False

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Pass a WebRTC candidate on; a session sending them is a live view.

        HA also asks for the stream source when nobody is watching, so only
        real sessions count as viewing.
        """
        self._webrtc_sessions.add(session_id)
        self._start_keeping_frames()
        await super().async_on_webrtc_candidate(session_id, candidate)

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session; the last kept frame stays as the snapshot."""
        self._webrtc_sessions.discard(session_id)
        super().close_webrtc_session(session_id)

    def _viewing(self) -> bool:
        if self._webrtc_sessions:
            return True
        return self.stream is not None and bool(self.stream.outputs())

    def _start_keeping_frames(self) -> None:
        if self._frame_task is None or self._frame_task.done():
            self._frame_task = self.hass.async_create_background_task(
                self._async_keep_frames(), f"{self.entity_id} frames"
            )

    async def _async_keep_frames(self) -> None:
        """Grab a frame now and then while someone watches the live view."""
        await asyncio.sleep(FRAME_FIRST_DELAY)
        while self._viewing():
            if (source := await self._async_live_url()) and (
                image := await async_get_image(self.hass, source)
            ):
                self._frame = image
                self._frame_time = time.time()
                _LOGGER.debug("Kept live frame for %s (%s bytes)", self.entity_id, len(image))
            await asyncio.sleep(FRAME_INTERVAL)

    async def async_will_remove_from_hass(self) -> None:
        """Stop keeping frames."""
        if self._frame_task is not None:
            self._frame_task.cancel()
        await super().async_will_remove_from_hass()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the newest image at hand without waking the camera."""
        image, when = self._frame, self._frame_time
        fun = self._option.get("still_image")
        if callable(fun):
            still, still_time = fun()
            if still and still_time >= when:
                image, when = still, still_time
        return image
