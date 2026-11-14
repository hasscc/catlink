"""A small asyncio RTMP client for the CatLink intercom channel.

The device never accepts a publish: the intercom URL is opened as an ordinary
*player* (connect / createStream / play) and the microphone is pushed upstream
as audio messages on that same play stream, once the device answers
`NetStream.TalkReady`. That is what the Aliyun LinkVisual SDK does, so this
module implements just enough RTMP for it: librtmp's URL split, the plain
handshake, a chunk reader/writer, AMF0, and audio messages that can be
AES-128-CBC encrypted (the relay requires it when the session has a
`cryptoKey`). The session URL is used exactly as it was handed out: appending
`private=0` to it makes the relay hang up right after `createStream`.

Nothing here logs: the caller gets the collected server messages and decides
what is safe to write.
"""

from __future__ import annotations

from array import array
import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import struct
import sys
import time
from typing import Any

# librtmp's defaults, so the connect object looks like the SDK's.
FLASH_VER = "LNX 10,0,32,18"
AUDIO_CODECS = 3191.0
VIDEO_CODECS = 252.0
CAPABILITIES = 15.0
BUFFER_MS = 3600000
DEFAULT_PORT = 1935
# Chunk stream ids: 2 protocol control, 3 commands, 4 audio.
CSID_CONTROL = 2
CSID_COMMAND = 3
CSID_AUDIO = 4
MSG_SET_CHUNK_SIZE = 1
MSG_ACK = 3
MSG_USER_CONTROL = 4
MSG_WINDOW_ACK_SIZE = 5
MSG_SET_PEER_BANDWIDTH = 6
MSG_AUDIO = 8
MSG_AMF0_DATA = 18
MSG_AMF0_COMMAND = 20
UC_PING_REQUEST = 6
UC_PING_RESPONSE = 7
UC_SET_BUFFER_LENGTH = 3
# FLV sound byte: (format << 4) | (rate << 2) | (bits << 1) | channels, with
# the rate bits left at 0 as the SDK does, i.e. G.711 A-law 16-bit mono.
SOUND_BYTE_SDK = 0x72
# AAC-style sample rate index, only used in the one-off sequence header.
SAMPLE_RATE_INDEX_8K = 11
# How many downlink audio messages have their first bytes remembered.
DOWNLINK_HEADS = 3
# Downlink framing (decrypted): body[0] >> 4 is the FLV codec id, body[1] is 0
# for the one-off config packet and 1 for audio, the rest is the payload.
CODEC_ALAW = 7


class RtmpError(Exception):
    """Anything that stops the client: protocol, timeout or a refusal."""


@dataclass(slots=True)
class RtmpUrl:
    """A librtmp-style split of an RTMP URL."""

    host: str
    port: int
    app: str
    playpath: str

    @property
    def tcurl(self) -> str:
        """Return the tcUrl librtmp would build."""
        return f"rtmp://{self.host}:{self.port}/{self.app}"


def parse_rtmp_url(url: str) -> RtmpUrl:
    """Split an RTMP URL the way librtmp's RTMP_ParseURL does.

    The relay expects exactly that split: with no slash after the host the app
    is the whole remainder, query string included, and the playpath is empty
    (the intercom URL's case).
    """
    scheme, sep, rest = url.partition("://")
    if not sep or scheme.lower() not in ("rtmp", "rtmpt", "rtmpe"):
        raise RtmpError("not an rtmp url")
    hostport, _, path = rest.partition("/")
    host, _, port = hostport.partition(":")
    if not host:
        raise RtmpError("no host in url")
    query = path[path.find("?") + 1:] if "?" in path else ""
    if "slist=" in query:
        app, playpath = path, query.split("slist=", 1)[1].split("&", 1)[0]
    elif path.startswith("ondemand/"):
        app, playpath = "ondemand", path[len("ondemand/"):]
    else:
        # app runs up to the last of (at most) the next three slashes.
        slashes = [i for i, c in enumerate(path) if c == "/"][:3]
        if not slashes:
            app, playpath = path, ""
        else:
            app, playpath = path[:slashes[-1]], path[slashes[-1] + 1:]
    return RtmpUrl(host, int(port) if port.isdigit() else DEFAULT_PORT, app, playpath)


# --------------------------------------------------------------------------
# G.711 A-law
# --------------------------------------------------------------------------

# Segment ends of the A-law companding curve (ITU-T G.711 / G.191 g711.c).
_ALAW_SEGMENTS = (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF)


def linear_to_alaw(sample: int) -> int:
    """Encode one 16-bit PCM sample as a G.711 A-law byte (ITU-T G.191)."""
    value = max(-32768, min(32767, sample)) >> 3
    if value >= 0:
        mask = 0xD5
    else:
        mask = 0x55
        value = -value - 1
    segment = next(
        (i for i, end in enumerate(_ALAW_SEGMENTS) if value <= end), len(_ALAW_SEGMENTS)
    )
    if segment >= len(_ALAW_SEGMENTS):
        return 0x7F ^ mask
    shift = 1 if segment < 2 else segment
    return ((segment << 4) | ((value >> shift) & 0x0F)) ^ mask


def alaw_to_linear(byte: int) -> int:
    """Decode one G.711 A-law byte to a 16-bit PCM sample (ITU-T G.191)."""
    value = byte ^ 0x55
    segment = (value & 0x70) >> 4
    magnitude = (value & 0x0F) << 4
    if segment == 0:
        magnitude += 8
    elif segment == 1:
        magnitude += 0x108
    else:
        magnitude = (magnitude + 0x108) << (segment - 1)
    return magnitude if value & 0x80 else -magnitude


# Built once: decoding downlink audio in real time must not run the curve
# for every sample.
ALAW_DECODE_TABLE: tuple[int, ...] = tuple(alaw_to_linear(b) for b in range(256))


def alaw_to_pcm16(alaw: bytes) -> bytes:
    """Decode G.711 A-law bytes to little-endian 16-bit PCM."""
    samples = array("h", [ALAW_DECODE_TABLE[b] for b in alaw])
    if sys.byteorder == "big":  # pragma: no cover - CI is little-endian
        samples.byteswap()
    return samples.tobytes()


# --------------------------------------------------------------------------
# AMF0
# --------------------------------------------------------------------------

AMF_NUMBER = 0x00
AMF_BOOLEAN = 0x01
AMF_STRING = 0x02
AMF_OBJECT = 0x03
AMF_NULL = 0x05
AMF_UNDEFINED = 0x06
AMF_ECMA_ARRAY = 0x08
AMF_OBJECT_END = 0x09
AMF_STRICT_ARRAY = 0x0A


def amf0_encode(value: Any) -> bytes:
    """Encode one Python value as AMF0."""
    if value is None:
        return bytes([AMF_NULL])
    if isinstance(value, bool):
        return bytes([AMF_BOOLEAN, 1 if value else 0])
    if isinstance(value, (int, float)):
        return bytes([AMF_NUMBER]) + struct.pack(">d", float(value))
    if isinstance(value, str):
        raw = value.encode()
        return bytes([AMF_STRING]) + struct.pack(">H", len(raw)) + raw
    if isinstance(value, dict):
        out = bytearray([AMF_OBJECT])
        for key, item in value.items():
            raw = str(key).encode()
            out += struct.pack(">H", len(raw)) + raw + amf0_encode(item)
        out += b"\x00\x00" + bytes([AMF_OBJECT_END])
        return bytes(out)
    if isinstance(value, (list, tuple)):
        out = bytearray([AMF_STRICT_ARRAY]) + struct.pack(">I", len(value))
        for item in value:
            out += amf0_encode(item)
        return bytes(out)
    raise RtmpError(f"cannot encode {type(value).__name__} as AMF0")


def amf0_decode(data: bytes, pos: int = 0) -> tuple[Any, int]:
    """Decode one AMF0 value, returning it and the new position."""
    if pos >= len(data):
        raise RtmpError("truncated AMF0")
    marker, pos = data[pos], pos + 1
    if marker == AMF_NUMBER:
        return struct.unpack_from(">d", data, pos)[0], pos + 8
    if marker == AMF_BOOLEAN:
        return bool(data[pos]), pos + 1
    if marker == AMF_STRING:
        size = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        return data[pos:pos + size].decode(errors="replace"), pos + size
    if marker in (AMF_NULL, AMF_UNDEFINED):
        return None, pos
    if marker in (AMF_OBJECT, AMF_ECMA_ARRAY):
        if marker == AMF_ECMA_ARRAY:
            pos += 4  # the (unreliable) element count
        obj: dict[str, Any] = {}
        while pos < len(data):
            size = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            key = data[pos:pos + size].decode(errors="replace")
            pos += size
            if not key and pos < len(data) and data[pos] == AMF_OBJECT_END:
                return obj, pos + 1
            obj[key], pos = amf0_decode(data, pos)
        return obj, pos
    if marker == AMF_STRICT_ARRAY:
        count = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        items = []
        for _ in range(count):
            item, pos = amf0_decode(data, pos)
            items.append(item)
        return items, pos
    raise RtmpError(f"unknown AMF0 marker 0x{marker:02x}")


def amf0_decode_all(data: bytes) -> list[Any]:
    """Decode every AMF0 value in a message body, stopping at the first error."""
    values: list[Any] = []
    pos = 0
    while pos < len(data):
        try:
            value, pos = amf0_decode(data, pos)
        except (RtmpError, struct.error, IndexError):
            break
        values.append(value)
    return values


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

@dataclass(slots=True)
class DownlinkFrame:
    """One decrypted audio message from the box: codec, header, payload."""

    codec: int
    header: bytes
    payload: bytes


@dataclass(slots=True)
class ServerMessage:
    """One command message from the server, flattened for logging."""

    name: str
    transaction: float | None = None
    level: str | None = None
    code: str | None = None
    description: str | None = None
    at: float = 0.0

    def as_log(self) -> str:
        """Return a short one-line form (values still need masking)."""
        parts = [self.name]
        if self.level:
            parts.append(f"level={self.level}")
        if self.code:
            parts.append(f"code={self.code}")
        if self.description:
            parts.append(f"description={self.description}")
        return " ".join(parts)


@dataclass(slots=True)
class _ChunkState:
    """What a chunk stream remembers between chunks."""

    timestamp: int = 0
    delta: int = 0
    length: int = 0
    type_id: int = 0
    msid: int = 0
    extended: bool = False
    body: bytearray = field(default_factory=bytearray)


class RtmpTalkClient:
    """Open an intercom URL as a player and send audio upstream on it."""

    def __init__(
        self,
        url: str,
        *,
        key: bytes | None = None,
        iv: bytes | None = None,
        sound_byte: int = SOUND_BYTE_SDK,
        timeout: float = 8.0,
        on_downlink_audio: Callable[[bytes], None] | None = None,
    ) -> None:
        """Set up the client; nothing is opened until `async_connect`.

        `on_downlink_audio` is called with the box's own A-law audio (8 kHz
        mono, decrypted and de-framed) as it arrives, for a listening caller.
        """
        self.url = url
        self.on_downlink_audio = on_downlink_audio
        self.parts = parse_rtmp_url(url)
        self.key = key
        self.iv = iv
        self.sound_byte = sound_byte
        self.timeout = timeout
        self.messages: list[ServerMessage] = []
        self.server_closed_at: float | None = None
        self.audio_packets = 0
        self.audio_bytes = 0
        self.stream_id = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pump: asyncio.Task | None = None
        self._in_chunk_size = 128
        self._out_chunk_size = 128
        self._window = 2500000
        self._received = 0
        self._acked = 0
        self._chunks: dict[int, _ChunkState] = {}
        self._transactions: dict[int, asyncio.Future] = {}
        self._next_transaction = 1
        self._codes: dict[str, float] = {}
        self._code_event = asyncio.Event()
        self._started = time.monotonic()
        self._sequence_header_sent = False
        self._audio_samples = 0
        self.close_reason: str | None = None
        # message type -> (count, bytes) of everything the server sent
        self.received: dict[int, list[int]] = {}
        # What the box sends back on the same stream (its microphone).
        self.downlink_packets = 0
        self.downlink_bytes = 0
        self.downlink_sizes: dict[int, int] = {}
        self.downlink_heads: list[str] = []
        self._keepalive: asyncio.Task | None = None

    @property
    def elapsed(self) -> float:
        """Return seconds since the client was created."""
        return time.monotonic() - self._started

    @property
    def encrypted(self) -> bool:
        """Return whether audio bodies are AES-128-CBC encrypted."""
        return bool(self.key and self.iv)

    # -- connection ---------------------------------------------------

    async def async_connect(self) -> dict:
        """Open the socket, shake hands and send `connect`; return its reply."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.parts.host, self.parts.port), self.timeout
        )
        await self._async_handshake()
        self._pump = asyncio.create_task(self._async_pump())
        reply = await self._async_command(
            "connect",
            {
                "app": self.parts.app,
                "flashVer": FLASH_VER,
                "tcUrl": self.parts.tcurl,
                "fpad": False,
                "capabilities": CAPABILITIES,
                "audioCodecs": AUDIO_CODECS,
                "videoCodecs": VIDEO_CODECS,
                "videoFunction": 1.0,
            },
            csid=CSID_COMMAND,
            msid=0,
        )
        return reply if isinstance(reply, dict) else {}

    async def async_create_stream(self) -> int:
        """Send `createStream` and keep the stream id the server answers."""
        reply = await self._async_command("createStream", None, csid=CSID_COMMAND, msid=0)
        self.stream_id = int(reply) if isinstance(reply, (int, float)) else 0
        return self.stream_id

    async def async_play(self) -> None:
        """Send `play` (live, start -1000) and the buffer length, as librtmp does."""
        body = (
            amf0_encode("play")
            + amf0_encode(float(self._take_transaction()))
            + amf0_encode(None)
            + amf0_encode(self.parts.playpath)
            + amf0_encode(-1000.0)
        )
        self._send_message(CSID_COMMAND, MSG_AMF0_COMMAND, self.stream_id, 0, body)
        self._send_message(
            CSID_CONTROL,
            MSG_USER_CONTROL,
            0,
            0,
            struct.pack(">HII", UC_SET_BUFFER_LENGTH, self.stream_id, BUFFER_MS),
        )
        await self._async_drain()

    async def async_wait_for_code(self, code: str, timeout: float) -> float | None:
        """Wait for an onStatus code; return how long it took, or None."""
        deadline = time.monotonic() + timeout
        while True:
            if code in self._codes:
                return self._codes[code]
            left = deadline - time.monotonic()
            if left <= 0 or self.server_closed_at is not None:
                return None
            self._code_event.clear()
            try:
                await asyncio.wait_for(self._code_event.wait(), left)
            except TimeoutError:
                return None

    # -- the SDK's own onStatus messages ---------------------------------

    async def async_send_status(
        self, code: str, description: str = "desc", *, audio_type: str | None = None
    ) -> None:
        """Send an `onStatus` command (chunk stream 3, message stream 0).

        The device only joins the session, and the server only answers
        `NetStream.TalkReady`, after `NetStream.RequestAudioType` has asked
        for an audio type.
        """
        info: dict[str, Any] = {"level": "status", "code": code, "description": description}
        if audio_type is not None:
            info["audio_type"] = audio_type
        body = (
            amf0_encode("onStatus")
            + amf0_encode(float(self._take_transaction()))
            + amf0_encode(None)
            + amf0_encode(info)
        )
        self._send_message(CSID_COMMAND, MSG_AMF0_COMMAND, 0, 0, body)
        await self._async_drain()

    def start_keepalive(self, keepalive: float = 5.0, ping: float = 30.0) -> None:
        """Send `NetStream.Keepalive` every 5 s and `NetStream.Ping.Start` every 30 s."""
        async def _loop() -> None:
            last_ping = time.monotonic()
            while self.server_closed_at is None:
                await asyncio.sleep(keepalive)
                try:
                    await self.async_send_status("NetStream.Keepalive")
                    if time.monotonic() - last_ping >= ping:
                        last_ping = time.monotonic()
                        await self.async_send_status("NetStream.Ping.Start")
                except RtmpError:
                    return

        if self._keepalive is None:
            self._keepalive = asyncio.create_task(_loop())

    # -- audio --------------------------------------------------------

    def send_audio(self, payload: bytes, timestamp: int) -> None:
        """Send one FLV audio tag body upstream (type 8, chunk 4, full header).

        Like AAC, G.711 needs a one-off sequence header before the audio, and
        every body carries the `0x01` marker after the sound byte.
        """
        if not self._sequence_header_sent:
            header = bytes(
                [self.sound_byte, 0x00, SAMPLE_RATE_INDEX_8K << 4, 0x00]
            )
            self._send_audio_body(header, timestamp)
            self._sequence_header_sent = True
        self._send_audio_body(bytes([self.sound_byte, 0x01]) + payload, timestamp)

    def _send_audio_body(self, body: bytes, timestamp: int) -> None:
        """Pad (PKCS#7), encrypt if a key is set, and send one audio message.

        The IV is reloaded for every packet, so the cipher never chains.
        """
        if self.encrypted:
            pad = 16 - (len(body) % 16)
            body = _aes_cbc(self.key, self.iv, body + bytes([pad]) * pad)
        self._send_message(CSID_AUDIO, MSG_AUDIO, self.stream_id, timestamp, body)
        self.audio_packets += 1
        self.audio_bytes += len(body)

    async def async_send_frame(self, alaw: bytes, *, rate: int = 8000) -> None:
        """Send one A-law frame, keeping a running timestamp across calls."""
        self.send_audio(alaw, int(self._audio_samples * 1000 / rate))
        self._audio_samples += len(alaw)
        await self._async_drain()

    def downlink_summary(self) -> dict:
        """Describe the audio the box sent back, for a debug log."""
        sizes = self.downlink_sizes
        return {
            "packets": self.downlink_packets,
            "bytes": self.downlink_bytes,
            "min": min(sizes, default=0),
            "max": max(sizes, default=0),
            "sizes": dict(sorted(sizes.items())),
            "first_bytes": self.downlink_heads,
        }

    # -- plumbing -----------------------------------------------------

    async def _async_handshake(self) -> None:
        """Do the plain RTMP handshake (C0 = 3, 1536-byte C1/C2, no digest)."""
        c1 = struct.pack(">II", 0, 0) + bytes(
            (i * 37 + 11) & 0xFF for i in range(1528)
        )
        self._write(b"\x03" + c1)
        await self._async_drain()
        s0s1 = await self._async_read_exact(1 + 1536)
        if s0s1[0] != 3:
            raise RtmpError(f"server answered handshake type {s0s1[0]}")
        self._write(s0s1[1:])
        await self._async_drain()
        await self._async_read_exact(1536)

    def _take_transaction(self) -> int:
        """Return the next transaction id."""
        self._next_transaction += 1
        return self._next_transaction - 1

    async def _async_command(
        self, name: str, argument: Any, *, csid: int, msid: int
    ) -> Any:
        """Send a command and wait for its `_result` (or raise on `_error`)."""
        transaction = self._take_transaction()
        body = amf0_encode(name) + amf0_encode(float(transaction)) + amf0_encode(argument)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._transactions[transaction] = future
        self._send_message(csid, MSG_AMF0_COMMAND, msid, 0, body)
        await self._async_drain()
        try:
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError as exc:
            raise RtmpError(f"no answer to {name}") from exc
        finally:
            self._transactions.pop(transaction, None)

    def _send_message(
        self, csid: int, type_id: int, msid: int, timestamp: int, body: bytes
    ) -> None:
        """Write one message, split into chunks (fmt 0 then fmt 3)."""
        extended = timestamp >= 0xFFFFFF
        head = bytes([csid]) + struct.pack(">I", 0xFFFFFF if extended else timestamp)[1:]
        head += struct.pack(">I", len(body))[1:] + bytes([type_id])
        head += struct.pack("<I", msid)
        if extended:
            head += struct.pack(">I", timestamp)
        out = bytearray(head)
        for index in range(0, len(body), self._out_chunk_size):
            if index:
                out += bytes([0xC0 | csid])
                if extended:
                    out += struct.pack(">I", timestamp)
            out += body[index:index + self._out_chunk_size]
        self._write(bytes(out))

    def _write(self, data: bytes) -> None:
        """Write to the socket if it is still open."""
        if self._writer is None or self._writer.is_closing():
            self._note_closed("socket already closed when writing")
            raise RtmpError("connection closed")
        self._writer.write(data)

    async def _async_drain(self) -> None:
        """Flush the socket, tolerating a server that already hung up."""
        if self._writer is None:
            return
        try:
            await self._writer.drain()
        except (OSError, ConnectionError) as exc:
            self._note_closed(f"write failed: {type(exc).__name__}: {exc}")
            raise RtmpError("connection closed while writing") from exc

    async def _async_read_exact(self, size: int) -> bytes:
        """Read exactly `size` bytes, counting them for acknowledgements."""
        if self._reader is None:
            raise RtmpError("not connected")
        data = await asyncio.wait_for(self._reader.readexactly(size), self.timeout)
        self._received += len(data)
        return data

    async def _async_pump(self) -> None:
        """Read chunks until the server closes or the client is closed."""
        try:
            while True:
                await self._async_read_chunk()
                if self._received - self._acked >= self._window // 2:
                    self._acked = self._received
                    self._send_message(
                        CSID_CONTROL, MSG_ACK, 0, 0, struct.pack(">I", self._received)
                    )
                    await self._async_drain()
        except asyncio.IncompleteReadError as exc:
            self._note_closed(f"server closed (EOF after {len(exc.partial)} of {exc.expected} B)")
        except (ConnectionError, OSError, TimeoutError, RtmpError) as exc:
            self._note_closed(f"{type(exc).__name__}: {exc}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a reader bug, not the server
            self._note_closed(f"reader failed: {type(exc).__name__}: {exc}")

    def _note_closed(self, reason: str = "write failed") -> None:
        """Remember when and why the connection ended and wake every waiter."""
        if self.server_closed_at is None:
            self.server_closed_at = time.monotonic() - self._started
            self.close_reason = reason
        for future in self._transactions.values():
            if not future.done():
                future.set_exception(RtmpError("connection closed by server"))
        self._code_event.set()

    async def _async_read_chunk(self) -> None:
        """Read one chunk and dispatch the message when it is complete."""
        first = (await self._async_read_exact(1))[0]
        fmt, csid = first >> 6, first & 0x3F
        if csid == 0:
            csid = 64 + (await self._async_read_exact(1))[0]
        elif csid == 1:
            low, high = await self._async_read_exact(2)
            csid = 64 + low + (high << 8)
        state = self._chunks.setdefault(csid, _ChunkState())
        timestamp = None
        if fmt <= 2:
            timestamp = int.from_bytes(await self._async_read_exact(3), "big")
        if fmt <= 1:
            state.length = int.from_bytes(await self._async_read_exact(3), "big")
            state.type_id = (await self._async_read_exact(1))[0]
        if fmt == 0:
            state.msid = struct.unpack("<I", await self._async_read_exact(4))[0]
        if timestamp is not None:
            state.extended = timestamp == 0xFFFFFF
        if timestamp == 0xFFFFFF or (fmt == 3 and state.extended):
            # fmt 3 chunks repeat the extended timestamp (as librtmp reads it)
            extended = int.from_bytes(await self._async_read_exact(4), "big")
            if timestamp is not None:
                timestamp = extended
        if fmt == 0 and timestamp is not None:
            state.timestamp = timestamp
        elif timestamp is not None:
            state.delta = timestamp
            state.timestamp += timestamp
        elif fmt == 3:
            state.timestamp += state.delta
        size = min(self._in_chunk_size, state.length - len(state.body))
        if size > 0:
            state.body += await self._async_read_exact(size)
        if len(state.body) >= state.length:
            body, state.body = bytes(state.body), bytearray()
            seen = self.received.setdefault(state.type_id, [0, 0])
            seen[0] += 1
            seen[1] += len(body)
            if state.type_id == MSG_AUDIO:
                self._note_downlink(body)
            self._handle_message(state.type_id, body)

    def _note_downlink(self, body: bytes) -> None:
        """Record one audio message the box sent back (sizes and first bytes)."""
        self.downlink_packets += 1
        self.downlink_bytes += len(body)
        self.downlink_sizes[len(body)] = self.downlink_sizes.get(len(body), 0) + 1
        if self.on_downlink_audio is None:
            if len(self.downlink_heads) < DOWNLINK_HEADS:
                self.downlink_heads.append(body[:2].hex())
            return
        frame = self.decode_downlink(body)
        if len(self.downlink_heads) < DOWNLINK_HEADS:
            self.downlink_heads.append((frame.header if frame else body[:2]).hex())
        if frame is not None and frame.payload and frame.codec == CODEC_ALAW:
            self.on_downlink_audio(frame.payload)

    def decode_downlink(self, body: bytes) -> DownlinkFrame | None:
        """Decrypt and de-frame one downlink audio message, or None if it fails.

        The box answers in the uplink's own shape (same key and IV, PKCS#7
        padding, `codec, marker, payload`). A marker of 0 is the one-off
        config packet and carries no audio.
        """
        if self.encrypted:
            if len(body) < 16 or len(body) % 16:
                return None
            try:
                plain = _aes_cbc(self.key, self.iv, body, decrypt=True)
            except Exception:  # noqa: BLE001 - a broken packet is not fatal
                return None
            pad = plain[-1] if plain else 0
            if not 1 <= pad <= 16 or pad > len(plain):
                return None
            plain = plain[:-pad]
        else:
            plain = body
        if len(plain) < 2:
            return None
        return DownlinkFrame(
            codec=plain[0] >> 4,
            header=plain[:2],
            payload=plain[2:] if plain[1] else b"",
        )

    def _handle_message(self, type_id: int, body: bytes) -> None:
        """Act on one complete message."""
        if type_id == MSG_SET_CHUNK_SIZE and len(body) >= 4:
            self._in_chunk_size = max(1, struct.unpack(">I", body[:4])[0] & 0x7FFFFFFF)
        elif type_id == MSG_WINDOW_ACK_SIZE and len(body) >= 4:
            self._window = max(1, struct.unpack(">I", body[:4])[0])
        elif type_id == MSG_USER_CONTROL and len(body) >= 2:
            event = struct.unpack(">H", body[:2])[0]
            if event == UC_PING_REQUEST:
                self._send_message(
                    CSID_CONTROL,
                    MSG_USER_CONTROL,
                    0,
                    0,
                    struct.pack(">H", UC_PING_RESPONSE) + body[2:6],
                )
        elif type_id in (MSG_AMF0_COMMAND, MSG_AMF0_DATA):
            self._handle_command(amf0_decode_all(body))

    def _handle_command(self, values: list[Any]) -> None:
        """Record a command message and settle whatever is waiting for it."""
        if not values or not isinstance(values[0], str):
            return
        name = values[0]
        transaction = values[1] if len(values) > 1 and isinstance(values[1], float) else None
        dicts = [v for v in values[2:] if isinstance(v, dict)]
        # `_result` for connect carries the properties object first and the
        # status object (level/code/description) second.
        info = next((v for v in dicts if "code" in v or "level" in v), dicts[0] if dicts else {})
        message = ServerMessage(
            name=name,
            transaction=transaction,
            level=info.get("level"),
            code=info.get("code"),
            description=info.get("description"),
            at=round(time.monotonic() - self._started, 3),
        )
        self.messages.append(message)
        if message.code:
            self._codes.setdefault(message.code, message.at)
            self._code_event.set()
        future = self._transactions.get(int(transaction)) if transaction is not None else None
        if future is not None and not future.done():
            payload = next((v for v in values[3:]), None)
            if name == "_error":
                future.set_exception(RtmpError(message.as_log()))
            else:
                future.set_result(payload if payload is not None else info)

    async def async_close(self) -> None:
        """Close the connection and stop the reader."""
        if self._keepalive is not None:
            self._keepalive.cancel()
            try:
                await self._keepalive
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - closing
                pass
            self._keepalive = None
        if self._pump is not None:
            self._pump.cancel()
            try:
                await self._pump
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - closing
                pass
            self._pump = None
        if self._writer is not None:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), 2)
            except (OSError, ConnectionError, TimeoutError):
                pass
            self._writer = None
        self._reader = None


def _aes_cbc(key: bytes, iv: bytes, data: bytes, *, decrypt: bool = False) -> bytes:
    """AES-128-CBC with the IV reloaded for every call, so it never chains."""
    from cryptography.hazmat.primitives.ciphers import (  # noqa: PLC0415
        Cipher,
        algorithms,
        modes,
    )

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    worker = cipher.decryptor() if decrypt else cipher.encryptor()
    return worker.update(data) + worker.finalize()


def crypto_key_shape(crypto_key: Any) -> dict:
    """Describe a `cryptoKey` safely for a log: shape only, never a value."""
    import base64  # noqa: PLC0415
    import binascii  # noqa: PLC0415

    if isinstance(crypto_key, dict):
        return {
            "type": "object",
            "keys": sorted(crypto_key),
            "fields": {
                name: crypto_key_shape(value) for name, value in sorted(crypto_key.items())
            },
        }
    if not isinstance(crypto_key, str):
        return {"type": type(crypto_key).__name__}
    shape: dict[str, Any] = {"type": "string", "len": len(crypto_key)}
    if all(c in "0123456789abcdefABCDEF" for c in crypto_key) and crypto_key:
        shape["chars"] = "hex"
        shape["decoded_len"] = len(crypto_key) // 2
        return shape
    shape["chars"] = "base64" if crypto_key else "empty"
    try:
        shape["decoded_len"] = len(base64.b64decode(crypto_key, validate=True))
    except (binascii.Error, ValueError):
        shape["chars"] = "other"
    return shape


def crypto_key_material(crypto_key: Any) -> tuple[bytes, bytes] | None:
    """Turn a `cryptoKey` into (key, iv), or None when it cannot be read.

    Object form `{"key": b64, "iv": b64}`, or a 32-byte string as key || iv.
    """
    import base64  # noqa: PLC0415
    import binascii  # noqa: PLC0415

    def _decode(value: Any) -> bytes | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            if len(value) in (32, 64) and all(c in "0123456789abcdefABCDEF" for c in value):
                return bytes.fromhex(value)
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return None

    if isinstance(crypto_key, dict):
        key, iv = _decode(crypto_key.get("key")), _decode(crypto_key.get("iv"))
        if key and iv and len(key) >= 16 and len(iv) >= 16:
            return key[:16], iv[:16]
        return None
    raw = _decode(crypto_key)
    if raw is None or len(raw) < 32:
        return None
    return raw[:16], raw[16:32]
