"""Play audio through a CatLink box's speaker over the talk-back channel.

An intercom session (`/vision/customer/voice/intercom/start`) gives a
short-lived RTMP URL and a `cryptoKey`; `modules/rtmp_talk.py` speaks the
protocol. This module is the audio side:

* `async_open_session` asks for a session (code 9543 means the box already
  has one open, usually the app's),
* `async_play_alaw` plays a finished piece of audio on one connection,
* `LiveTalkSession` keeps a session open and sends audio as it arrives,
* `FfmpegAlawSource` decodes any media URL to A-law with HA's ffmpeg.

Nothing secret is ever logged: the URL, its query values and the crypto key
only appear as masked shapes.
"""

from __future__ import annotations

from array import array
import asyncio
from collections.abc import AsyncIterator, Callable
import contextlib
import re
import sys
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..const import _LOGGER
from .linkvisual import LinkVisualError
from .rtmp_talk import (
    RtmpError,
    RtmpTalkClient,
    crypto_key_material,
    crypto_key_shape,
    linear_to_alaw,
    parse_rtmp_url,
)

if TYPE_CHECKING:
    from .linkvisual import LinkVisualClient

# The intercom reply's code when the box already has a session open; an
# abandoned session clears by itself after a few minutes.
INTERCOM_BUSY_CODE = 9543
INTERCOM_BUSY_RETRY = 3.0
BUSY_MESSAGE = "The box is busy with another talk session (the CatLink app?)"

# Sent before play; audio type 1 is G.711 A-law.
REQUEST_AUDIO_CODE = "NetStream.RequestAudioType"
AUDIO_TYPE_ALAW = "1"
TALK_READY_CODE = "NetStream.TalkReady"
TALK_READY_WAIT = 8.0

# G.711 A-law 8 kHz mono, 20 ms per frame.
AUDIO_RATE = 8000
FRAME_MS = 20
FRAME_BYTES = AUDIO_RATE * FRAME_MS // 1000
ALAW_SILENCE = 0xD5
# Silence sent right after TalkReady, so the box has something buffered
# before the real audio starts, and how far ahead of real time the frames
# are sent afterwards (a small lead absorbs jitter without bursting).
LEAD_IN_SECONDS = 0.3
SEND_AHEAD_SECONDS = 0.2
# Held open after the last frame, so the tail is played before the close.
HOLD_SECONDS = 0.5
# A single playback never lasts longer than this.
MAX_PLAYBACK_SECONDS = 600

# Sample rates a live talker may send PCM at; A-law is always 8 kHz.
PCM_SAMPLE_RATES = (8000, 16000, 24000, 32000, 44100, 48000)
FORMAT_PCM = "pcm_s16le"
FORMAT_ALAW = "alaw"
AUDIO_FORMATS = (FORMAT_PCM, FORMAT_ALAW)
# The jitter buffer: start sending once this much audio is queued, and never
# let it grow past the second value (the oldest audio is dropped instead, so
# the talker stays close to real time).
JITTER_START_SECONDS = 0.08
JITTER_MAX_SECONDS = 0.5
JITTER_START_BYTES = int(AUDIO_RATE * JITTER_START_SECONDS)
JITTER_MAX_BYTES = int(AUDIO_RATE * JITTER_MAX_SECONDS)
# A talk-only live session with no incoming audio for this long ends by itself
# (a listening one stays open between push-to-talk presses), and no session
# outlives the second value.
LIVE_IDLE_SECONDS = 20.0
LIVE_MAX_SECONDS = 600.0
# How much of the box's own audio is batched into one downlink callback.
DOWNLINK_BATCH_BYTES = AUDIO_RATE * 40 // 1000  # 40 ms


# --------------------------------------------------------------------------
# One talk session per box
# --------------------------------------------------------------------------

# A box accepts one intercom session at a time, so playback (the media
# player) and live talk (the websocket API) have to take turns: whoever
# starts claims the box here and the previous holder is stopped first.
_TALK_HOLDERS: dict[str, Any] = {}


async def async_claim_talk(iot_id: str, holder: Any, reason: str = "replaced") -> None:
    """Claim the box's talk channel, stopping whoever held it before.

    `holder` only has to offer `async_stop_talk(reason)`; it is stopped (and
    waited for) before the new claim is recorded.
    """
    previous = _TALK_HOLDERS.get(iot_id)
    _TALK_HOLDERS[iot_id] = holder
    if previous is not None and previous is not holder:
        with contextlib.suppress(Exception):
            await previous.async_stop_talk(reason)


def release_talk(iot_id: str, holder: Any) -> None:
    """Give the box back, unless somebody else has already claimed it."""
    if _TALK_HOLDERS.get(iot_id) is holder:
        del _TALK_HOLDERS[iot_id]


def talk_holder(iot_id: str) -> Any:
    """Return who is talking to this box right now, if anybody."""
    return _TALK_HOLDERS.get(iot_id)


# --------------------------------------------------------------------------
# PCM -> A-law 8 kHz
# --------------------------------------------------------------------------


class PcmResampler:
    """Turn PCM s16le at one rate into 8 kHz mono A-law, chunk by chunk.

    Pure Python because `audioop` is gone in 3.13, and cheap enough for a
    live talker. Integer ratios are averaged down, 44.1 kHz is interpolated;
    state carries across calls so chunk boundaries do not click.
    """

    def __init__(self, rate: int) -> None:
        """Set up a resampler for input at `rate` Hz."""
        if rate not in PCM_SAMPLE_RATES:
            raise ValueError(f"unsupported sample rate {rate}")
        self.rate = rate
        self.ratio = rate // AUDIO_RATE if rate % AUDIO_RATE == 0 else 0
        self._tail = b""
        self._pending: array = array("h")
        self._position = 0.0

    def _samples(self, data: bytes) -> array:
        """Decode the bytes (plus any odd byte left over) to samples."""
        data = self._tail + data
        usable = len(data) - len(data) % 2
        self._tail = data[usable:]
        samples = array("h")
        samples.frombytes(data[:usable])
        if sys.byteorder == "big":  # pragma: no cover - CI is little-endian
            samples.byteswap()
        return samples

    def __call__(self, data: bytes) -> bytes:
        """Resample and encode one chunk; returns A-law bytes (may be empty)."""
        samples = self._pending
        samples.extend(self._samples(data))
        if self.ratio == 1:
            out, self._pending = samples, array("h")
            return bytes(linear_to_alaw(value) for value in out)
        if self.ratio:
            step = self.ratio
            count = len(samples) // step
            out = bytes(
                linear_to_alaw(sum(samples[i * step:i * step + step]) // step)
                for i in range(count)
            )
            self._pending = samples[count * step:]
            return out
        # 44.1 kHz: read at 5.5125 input samples per output sample.
        step = self.rate / AUDIO_RATE
        encoded = bytearray()
        position = self._position
        while position + 1 < len(samples):
            index = int(position)
            frac = position - index
            first, second = samples[index], samples[index + 1]
            encoded.append(linear_to_alaw(int(first + (second - first) * frac)))
            position += step
        used = int(position)
        self._pending = samples[used:]
        self._position = position - used
        return bytes(encoded)

# Anything long enough to be a token, so nothing secret slips through a log
# line the known-value masking missed.
TOKEN_RE = re.compile(r"[A-Za-z0-9_+/-]{16,}={0,2}")


def rtmp_url_shape(url: str) -> dict:
    """Describe a session URL without any of its values, so it can be logged."""
    scheme, _, rest = url.partition("://")
    host, slash, tail = rest.partition("/")
    path = f"{slash}{tail}"
    body, _, query = path.lstrip("/").partition("?")
    segments = [seg for seg in body.split("/") if seg]
    parts = parse_rtmp_url(url)
    return {
        "scheme": scheme,
        "host": host,
        "segments": len(segments),
        "segment_lens": [len(seg) for seg in segments],
        "query": bool(query),
        "query_names": [item.split("=", 1)[0] for item in query.split("&") if item],
        "port": parts.port,
        "app_len": len(parts.app),
        "app_has_query": "?" in parts.app,
        "playpath_len": len(parts.playpath),
    }


def mask_rtmp_output(text: str, masks: dict[str, str]) -> str:
    """Mask every session value before it is logged, keeping the messages.

    Known values become placeholders, then leftover URLs, query values and
    token-like runs are masked too. Short values are only masked between word
    boundaries, so a two-letter app name cannot shred the rest of the text.
    """
    for value, name in sorted(masks.items(), key=lambda item: -len(item[0])):
        if len(value) >= 8:
            text = text.replace(value, name)
        elif value:
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", name, text)
    text = re.sub(r"rtmps?://\S+", "rtmp://<url>", text)
    text = re.sub(r"([?&][\w.-]{1,32}=)[^&\s'\"]+", r"\1<value>", text)
    return TOKEN_RE.sub(
        lambda m: m.group(0) if m.group(0).isalpha() and len(m.group(0)) < 24 else "<token>",
        text,
    )


def session_masks(url: str, crypto_key: Any = None) -> dict[str, str]:
    """Build the mask table for one session: URL, its parts, the key."""
    parts = parse_rtmp_url(url)
    path = url.partition("://")[2].partition("/")[2]
    query = path.partition("?")[2]
    masks: dict[str, str] = {
        url: "<url>", path: "<path>",
        parts.tcurl: "<tcurl>", parts.app: "<app>", parts.playpath: "<playpath>",
    }
    masks.update(
        {part.split("=", 1)[1]: "<value>" for part in query.split("&") if "=" in part}
    )
    if crypto_key is not None:
        masks[str(crypto_key)] = "<cryptokey>"
        values = crypto_key.values() if isinstance(crypto_key, dict) else [crypto_key]
        masks.update({str(value): "<cryptokey>" for value in values})
    masks.pop("", None)
    return masks


async def async_open_session(
    linkvisual: LinkVisualClient, iot_id: str
) -> tuple[str, Any]:
    """Open an intercom session; return its URL and `cryptoKey` (never logged).

    A box has one session at a time, so a busy reply is retried once a few
    seconds later before giving up.
    """
    for attempt in (0, 1):
        try:
            rsp = await linkvisual.async_start_intercom(iot_id)
        except LinkVisualError as exc:
            raise HomeAssistantError(f"Could not open a talk session: {exc}") from exc
        code = rsp.get("code")
        data = rsp.get("data") if isinstance(rsp.get("data"), dict) else {}
        if code == 200 and data.get("url"):
            return str(data["url"]), data.get("cryptoKey")
        if code == INTERCOM_BUSY_CODE and attempt == 0:
            _LOGGER.debug("Talk session busy (code %s); trying again shortly", code)
            await asyncio.sleep(INTERCOM_BUSY_RETRY)
            continue
        if code == INTERCOM_BUSY_CODE:
            raise HomeAssistantError(BUSY_MESSAGE)
        message = rsp.get("message") or rsp.get("localizedMsg") or ""
        raise HomeAssistantError(f"Could not open a talk session: code {code} {message}".strip())
    raise HomeAssistantError(BUSY_MESSAGE)  # pragma: no cover - loop always returns


class _PlaybackHolder:
    """Holds the box for one playback; stopping it cancels that playback."""

    def __init__(self, task: asyncio.Task | None, name: str) -> None:
        """Remember the task running the playback."""
        self.task = task
        self.name = name

    async def async_stop_talk(self, reason: str) -> None:
        """Stop the playback so somebody else can talk to the box."""
        _LOGGER.debug("Playback on %s ends (%s)", self.name, reason)
        task = self.task
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)


async def async_play_alaw(
    linkvisual: LinkVisualClient,
    iot_id: str,
    frames: AsyncIterator[bytes],
    *,
    name: str = "the device",
    on_started: Callable[[], None] | None = None,
) -> None:
    """Play G.711 A-law 8 kHz mono audio through the box's speaker.

    One playback is one connection; the session ends when it closes, which
    also happens when the caller cancels. `on_started` fires once the speaker
    is open, so a caller need not wait the whole playback out. A live talk
    session on the same box is stopped first.
    """
    holder = _PlaybackHolder(asyncio.current_task(), name)
    await async_claim_talk(iot_id, holder)
    try:
        await _async_play_alaw(
            linkvisual, iot_id, frames, name=name, on_started=on_started
        )
    finally:
        release_talk(iot_id, holder)


async def _async_play_alaw(
    linkvisual: LinkVisualClient,
    iot_id: str,
    frames: AsyncIterator[bytes],
    *,
    name: str,
    on_started: Callable[[], None] | None,
) -> None:
    """Run one playback on one connection (see `async_play_alaw`)."""
    url, crypto_key = await async_open_session(linkvisual, iot_id)
    masks = session_masks(url, crypto_key)
    _LOGGER.debug(
        "Talk session for %s: URL %s, cryptoKey %s",
        name,
        mask_rtmp_output(str(rtmp_url_shape(url)), masks),
        mask_rtmp_output(str(crypto_key_shape(crypto_key)), masks),
    )
    key, iv = crypto_key_material(crypto_key) or (None, None)
    client = RtmpTalkClient(url, key=key, iv=iv)
    reason = "done"
    try:
        async with asyncio.timeout(MAX_PLAYBACK_SECONDS):
            await client.async_connect()
            await client.async_send_status(REQUEST_AUDIO_CODE, audio_type=AUDIO_TYPE_ALAW)
            await client.async_create_stream()
            await client.async_play()
            client.start_keepalive()
            ready = await client.async_wait_for_code(TALK_READY_CODE, TALK_READY_WAIT)
            if ready is None:
                raise HomeAssistantError(
                    f"{name} did not open its speaker (no {TALK_READY_CODE})"
                )
            if on_started is not None:
                on_started()
            await _async_stream_frames(client, frames)
            await asyncio.sleep(HOLD_SECONDS)
    except asyncio.CancelledError:
        reason = "stopped"
        raise
    except TimeoutError as exc:
        reason = "playback took too long"
        raise HomeAssistantError(f"Playing audio on {name} took too long") from exc
    except RtmpError as exc:
        reason = f"{type(exc).__name__}: {exc}"
        raise HomeAssistantError(
            f"Playing audio on {name} failed: {mask_rtmp_output(str(exc), masks)}"
        ) from exc
    except OSError as exc:
        reason = f"{type(exc).__name__}: {exc}"
        raise HomeAssistantError(f"Playing audio on {name} failed: {exc}") from exc
    finally:
        with contextlib.suppress(Exception):
            await client.async_close()
        _log_session(client, name, reason, masks)


def _log_session(
    client: RtmpTalkClient, name: str, reason: str, masks: dict[str, str]
) -> None:
    """Write one debug summary of a finished session (everything masked)."""
    statuses = [
        f"{message.at}s {message.as_log()}"
        for message in client.messages
        if message.name != "_result" or message.code
    ]
    _LOGGER.debug(
        "Talk session for %s ended (%s): encrypted %s, %s packets / %s bytes sent,"
        " server said %s, connection ended %s (%s), box sent back %s",
        name,
        mask_rtmp_output(reason, masks),
        client.encrypted,
        client.audio_packets,
        client.audio_bytes,
        mask_rtmp_output(" | ".join(statuses), masks),
        f"at {round(client.server_closed_at, 3)}s"
        if client.server_closed_at is not None else "no",
        mask_rtmp_output(client.close_reason or "-", masks),
        client.downlink_summary(),
    )


async def _async_stream_frames(
    client: RtmpTalkClient, frames: AsyncIterator[bytes]
) -> None:
    """Send A-law audio, 20 ms at a time, keeping a small lead on real time."""
    start = time.monotonic()
    sent = 0

    async def _send(frame: bytes) -> bool:
        """Send one frame and wait until it is nearly due; False when closed."""
        nonlocal sent
        await client.async_send_frame(frame, rate=AUDIO_RATE)
        sent += len(frame)
        if client.server_closed_at is not None:
            return False
        due = start + sent / AUDIO_RATE - SEND_AHEAD_SECONDS
        await asyncio.sleep(max(0.0, due - time.monotonic()))
        return True

    lead_in = bytes([ALAW_SILENCE]) * int(AUDIO_RATE * LEAD_IN_SECONDS)
    for index in range(0, len(lead_in), FRAME_BYTES):
        if not await _send(lead_in[index:index + FRAME_BYTES]):
            return
    buffer = bytearray()
    async for chunk in frames:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            frame, buffer = bytes(buffer[:FRAME_BYTES]), buffer[FRAME_BYTES:]
            if not await _send(frame):
                return
    if buffer:
        await _send(bytes(buffer))


class FfmpegAlawSource:
    """Decode any media URL to A-law 8 kHz mono frames with HA's ffmpeg.

    Leaving the context kills ffmpeg, so a stopped playback stops decoding.
    """

    def __init__(self, hass: HomeAssistant, media_id: str) -> None:
        """Remember what to decode; nothing starts until the context is entered."""
        self.hass = hass
        self.media_id = media_id
        self._process: asyncio.subprocess.Process | None = None
        self._stderr: asyncio.Task | None = None

    async def __aenter__(self) -> FfmpegAlawSource:
        """Start ffmpeg, writing raw A-law to its stdout."""
        binary = get_ffmpeg_manager(self.hass).binary
        try:
            self._process = await asyncio.create_subprocess_exec(
                binary,
                "-hide_banner",
                "-loglevel", "error",
                "-i", self.media_id,
                "-vn",
                "-f", "alaw",
                "-ar", str(AUDIO_RATE),
                "-ac", "1",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise HomeAssistantError(f"Could not run ffmpeg: {exc}") from exc
        if self._process.stderr is not None:
            self._stderr = asyncio.create_task(self._process.stderr.read())
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Stop ffmpeg and report what it had to say when it failed."""
        process, self._process = self._process, None
        if process is None:
            return
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
        errors = b""
        if self._stderr is not None:
            # ffmpeg is gone, so its stderr is at EOF; never wait long for it.
            with contextlib.suppress(Exception, asyncio.CancelledError):
                errors = await asyncio.wait_for(self._stderr, 2)
            self._stderr.cancel()
            self._stderr = None
        if process.returncode:
            _LOGGER.warning(
                "ffmpeg could not decode the audio (exit %s): %s",
                process.returncode,
                errors.decode(errors="replace").strip()[-500:] or "no output",
            )

    async def async_frames(self) -> AsyncIterator[bytes]:
        """Yield the decoded A-law bytes until ffmpeg is done."""
        if self._process is None or self._process.stdout is None:
            return
        while True:
            chunk = await self._process.stdout.read(FRAME_BYTES)
            if not chunk:
                return
            yield chunk


# --------------------------------------------------------------------------
# Live talk
# --------------------------------------------------------------------------


class LiveTalkSession:
    """A two-way talk session fed with audio as it arrives (live talk).

    The session stays open and a sender task paces 20 ms frames out of a
    small jitter buffer, so the talker stays close to real time. With
    `on_audio` set, the box's own microphone comes back in ~40 ms A-law
    batches.
    """

    def __init__(
        self,
        linkvisual: LinkVisualClient,
        iot_id: str,
        *,
        name: str = "the device",
        audio_format: str = FORMAT_PCM,
        sample_rate: int = 16000,
        on_audio: Callable[[bytes], None] | None = None,
        on_ended: Callable[[str], None] | None = None,
    ) -> None:
        """Set up a session; nothing is opened until `async_start`."""
        if audio_format not in AUDIO_FORMATS:
            raise ValueError(f"unsupported format {audio_format}")
        if audio_format == FORMAT_ALAW and sample_rate != AUDIO_RATE:
            raise ValueError("alaw is always 8000 Hz")
        self.linkvisual = linkvisual
        self.iot_id = iot_id
        self.name = name
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.on_audio = on_audio
        self.on_ended = on_ended
        self.reason: str | None = None
        self.fed_bytes = 0
        self.dropped_bytes = 0
        self._resampler = (
            PcmResampler(sample_rate) if audio_format == FORMAT_PCM else None
        )
        self._buffer = bytearray()
        self._downlink = bytearray()
        self._wake = asyncio.Event()
        self._ended = asyncio.Event()
        self._client: RtmpTalkClient | None = None
        self._task: asyncio.Task | None = None
        self._masks: dict[str, str] = {}
        self._stopping: str | None = None
        self._last_audio = time.monotonic()

    @property
    def active(self) -> bool:
        """Return whether the session is open and sending."""
        return self._task is not None and not self._ended.is_set()

    async def async_start(self) -> None:
        """Open the session and wait until the box's speaker is ready.

        Everything that can go wrong before then is raised here, so the caller
        can answer the panel with an error instead of a half-open session.
        """
        await async_claim_talk(self.iot_id, self)
        url, crypto_key = await async_open_session(self.linkvisual, self.iot_id)
        self._masks = session_masks(url, crypto_key)
        _LOGGER.debug(
            "Live talk session for %s: URL %s, cryptoKey %s",
            self.name,
            mask_rtmp_output(str(rtmp_url_shape(url)), self._masks),
            mask_rtmp_output(str(crypto_key_shape(crypto_key)), self._masks),
        )
        key, iv = crypto_key_material(crypto_key) or (None, None)
        client = RtmpTalkClient(
            url,
            key=key,
            iv=iv,
            on_downlink_audio=self._note_audio if self.on_audio else None,
        )
        self._client = client
        try:
            await client.async_connect()
            await client.async_send_status(
                REQUEST_AUDIO_CODE, audio_type=AUDIO_TYPE_ALAW
            )
            await client.async_create_stream()
            await client.async_play()
            client.start_keepalive()
            ready = await client.async_wait_for_code(TALK_READY_CODE, TALK_READY_WAIT)
        except (RtmpError, OSError) as exc:
            await self._async_shutdown(f"{type(exc).__name__}: {exc}")
            raise HomeAssistantError(
                f"Live talk to {self.name} failed: "
                f"{mask_rtmp_output(str(exc), self._masks)}"
            ) from exc
        if ready is None:
            await self._async_shutdown("no talk ready")
            raise HomeAssistantError(
                f"{self.name} did not open its speaker (no {TALK_READY_CODE})"
            )
        self._last_audio = time.monotonic()
        self._task = asyncio.create_task(self._async_run())

    def feed(self, data: bytes) -> None:
        """Queue audio from the talker, never blocking.

        Called straight from the websocket's binary handler, so it only
        converts and appends; the sender task does the waiting. Audio past the
        jitter buffer's limit is dropped, keeping the latest.
        """
        if not data or self._stopping is not None:
            return
        self.fed_bytes += len(data)
        alaw = self._resampler(data) if self._resampler is not None else data
        if not alaw:
            return
        self._last_audio = time.monotonic()
        self._buffer += alaw
        if len(self._buffer) > JITTER_MAX_BYTES:
            drop = len(self._buffer) - JITTER_MAX_BYTES
            del self._buffer[:drop]
            self.dropped_bytes += drop
        self._wake.set()

    async def async_stop(self, reason: str = "stopped") -> None:
        """End the session; the box's speaker closes with the connection."""
        if self._stopping is None:
            self._stopping = reason
        self._wake.set()
        task = self._task
        if task is not None and not task.done():
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        else:
            await self._async_shutdown(reason)

    async def async_stop_talk(self, reason: str) -> None:
        """Stop because somebody else wants the box (the talk registry)."""
        await self.async_stop(reason)

    async def async_wait(self) -> str:
        """Wait until the session ends and return why."""
        await self._ended.wait()
        return self.reason or "ended"

    # -- internals ----------------------------------------------------

    def _note_audio(self, alaw: bytes) -> None:
        """Batch the box's own audio into ~40 ms before passing it on."""
        if self.on_audio is None:
            return
        self._downlink += alaw
        while len(self._downlink) >= DOWNLINK_BATCH_BYTES:
            batch = bytes(self._downlink[:DOWNLINK_BATCH_BYTES])
            del self._downlink[:DOWNLINK_BATCH_BYTES]
            self.on_audio(batch)

    async def _async_run(self) -> None:
        """Send queued audio until the session ends, then clean up."""
        reason = "stopped"
        try:
            reason = await self._async_send_loop()
        except asyncio.CancelledError:
            reason = self._stopping or "stopped"
            raise
        except (RtmpError, OSError) as exc:
            reason = f"error: {mask_rtmp_output(str(exc), self._masks)}"
        except Exception as exc:  # noqa: BLE001 - never leave a session open
            reason = f"error: {type(exc).__name__}"
            _LOGGER.exception("Live talk on %s failed", self.name)
        finally:
            await self._async_shutdown(reason)

    async def _async_send_loop(self) -> str:
        """Pace frames out of the jitter buffer; return why it stopped."""
        client = self._client
        assert client is not None
        started = time.monotonic()
        lead_in = bytes([ALAW_SILENCE]) * int(AUDIO_RATE * LEAD_IN_SECONDS)
        for index in range(0, len(lead_in), FRAME_BYTES):
            await client.async_send_frame(lead_in[index:index + FRAME_BYTES])
            if client.server_closed_at is not None:
                return "server closed"
        due = time.monotonic()
        flowing = False
        while True:
            if self._stopping is not None:
                return self._stopping
            if client.server_closed_at is not None:
                return "server closed"
            now = time.monotonic()
            if now - started > LIVE_MAX_SECONDS:
                return "max duration"
            if self.on_audio is None and now - self._last_audio > LIVE_IDLE_SECONDS:
                return "idle"
            wanted = FRAME_BYTES if flowing else JITTER_START_BYTES
            if len(self._buffer) < wanted:
                # Nothing (or not enough yet): wait, never pad the stream.
                flowing = False
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), 0.2)
                due = time.monotonic()
                continue
            frame = bytes(self._buffer[:FRAME_BYTES])
            del self._buffer[:FRAME_BYTES]
            flowing = True
            await client.async_send_frame(frame)
            due += len(frame) / AUDIO_RATE
            sleep = due - time.monotonic()
            if sleep < -0.5:  # fell far behind: start the clock again
                due = time.monotonic()
                sleep = 0.0
            await asyncio.sleep(max(0.0, sleep))

    async def _async_shutdown(self, reason: str) -> None:
        """Close the connection once, log the session and tell the caller."""
        if self._ended.is_set():
            return
        self.reason = reason
        self._ended.set()
        client, self._client = self._client, None
        if client is not None:
            with contextlib.suppress(Exception):
                await client.async_close()
            _log_session(client, f"{self.name} (live)", reason, self._masks)
        release_talk(self.iot_id, self)
        if self.on_ended is not None:
            self.on_ended(reason)
