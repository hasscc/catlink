"""Tests for the small RTMP talk-back client."""

from __future__ import annotations

import asyncio
import contextlib
import struct

import pytest

from custom_components.catlink.modules.rtmp_talk import (
    SOUND_BYTE_SDK,
    RtmpError,
    RtmpTalkClient,
    _ChunkState,
    _aes_cbc,
    amf0_decode,
    amf0_decode_all,
    amf0_encode,
    crypto_key_material,
    crypto_key_shape,
    linear_to_alaw,
    parse_rtmp_url,
)

MSG_AMF0_COMMAND = 20
MSG_AUDIO = 8


class FakeRtmpServer:
    """A tiny asyncio RTMP server that answers like the box is expected to.

    Handshake, `_result` for `connect` and `createStream`, `onStatus`
    NetStream.Play.Start and (optionally) NetStream.TalkReady, then it records
    every type-8 audio message it receives.
    """

    def __init__(
        self,
        *,
        talk_ready: bool = True,
        close_after_play: bool = False,
        needs_request: bool = False,
        close_after_audio: int | None = None,
        downlink: int = 0,
        downlink_size: int = 64,
        crypto: tuple[bytes, bytes] | None = None,
        downlink_config: bool = False,
        downlink_byte: int = 0xD5,
    ) -> None:
        """Set up the server's behaviour; nothing listens until `start`.

        `needs_request`: TalkReady only once the client has asked for an
        audio type (NetStream.RequestAudioType), like the real relay.
        """
        self.talk_ready = talk_ready
        self.close_after_play = close_after_play
        self.needs_request = needs_request
        self.close_after_audio = close_after_audio
        # How many audio messages the "box" sends back once talk is ready
        # (its microphone), and how big each one is.
        self.downlink = downlink
        self.downlink_size = downlink_size
        # When `crypto` is set the downlink is framed and encrypted the way
        # the real relay does it (`72 01 <A-law>`, PKCS#7, AES-128-CBC with
        # the session key, the IV reloaded per packet), optionally preceded
        # by the config packet the box sends first (`72 00 b0 00`).
        self.crypto = crypto
        self.downlink_config = downlink_config
        self.downlink_byte = downlink_byte
        self.statuses: list[dict] = []
        self._requested = False
        self._playing = False
        self.stream_id = 7
        self.audio: list[tuple[int, int, bytes]] = []
        self.commands: list[str] = []
        self.connect_arg: dict = {}
        self.play_arg = None
        self.connections = 0
        self._server: asyncio.base_events.Server | None = None
        self.port = 0

    async def start(self) -> str:
        """Listen on 127.0.0.1 and return the URL base."""
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return f"rtmp://127.0.0.1:{self.port}"

    async def stop(self) -> None:
        """Stop listening."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        try:
            await reader.readexactly(1 + 1536)
            writer.write(b"\x03" + bytes(1536) + bytes(1536))
            await writer.drain()
            await reader.readexactly(1536)
            self._send(writer, 2, 1, 0, struct.pack(">I", 4096))  # Set Chunk Size
            await writer.drain()
            states: dict[int, _ChunkState] = {}
            self._requested = self._playing = False
            audio_here = 0
            while True:
                type_id, csid, msid, body = await self._read_message(reader, states)
                if type_id == MSG_AUDIO:
                    self.audio.append((csid, msid, body))
                    audio_here += 1
                    if self.close_after_audio and audio_here >= self.close_after_audio:
                        break
                elif type_id == MSG_AMF0_COMMAND:
                    if await self._command(writer, body):
                        break
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            writer.close()

    async def _command(self, writer: asyncio.StreamWriter, body: bytes) -> bool:
        """Answer one command; return True when the connection should close."""
        values = amf0_decode_all(body)
        name, transaction = values[0], values[1]
        self.commands.append(name)
        if name == "onStatus":
            info = values[3] if len(values) > 3 and isinstance(values[3], dict) else {}
            self.statuses.append(info)
            if info.get("code") == "NetStream.RequestAudioType":
                self._requested = True
                if self._playing and self.talk_ready:
                    self._status(writer, "NetStream.TalkReady", "talk ready")
        elif name == "connect":
            self.connect_arg = values[2] if len(values) > 2 and isinstance(values[2], dict) else {}
            self._result(writer, transaction, {"fmsVer": "FMS/3,0"}, {
                "level": "status", "code": "NetConnection.Connect.Success",
                "description": "Connection succeeded.",
            })
        elif name == "createStream":
            self._result(writer, transaction, None, float(self.stream_id))
        elif name == "play":
            self.play_arg = values[3] if len(values) > 3 else None
            if self.close_after_play:
                await writer.drain()
                return True
            self._status(writer, "NetStream.Play.Start", "Start live")
            self._playing = True
            if self.talk_ready and (self._requested or not self.needs_request):
                self._status(writer, "NetStream.TalkReady", "talk ready")
                self._send_downlink(writer)
        await writer.drain()
        return False

    def _send_downlink(self, writer) -> None:
        """Send the box's own audio back, as the real relay does (FLV A-law)."""
        if self.crypto is None:
            for _ in range(self.downlink):
                body = bytes([0x7E, 0x01]) + bytes(self.downlink_size - 2)
                self._send(writer, 4, MSG_AUDIO, self.stream_id, body)
            return
        key, iv = self.crypto
        bodies = [bytes([0x72, 0x00, 0xB0, 0x00])] if self.downlink_config else []
        bodies += [
            bytes([0x72, 0x01]) + bytes([self.downlink_byte]) * self.downlink_size
            for _ in range(self.downlink)
        ]
        for body in bodies:
            pad = 16 - (len(body) % 16)
            self._send(
                writer, 4, MSG_AUDIO, self.stream_id,
                _aes_cbc(key, iv, body + bytes([pad]) * pad),
            )

    def _result(self, writer, transaction, properties, info) -> None:
        body = (
            amf0_encode("_result") + amf0_encode(float(transaction))
            + amf0_encode(properties) + amf0_encode(info)
        )
        self._send(writer, 3, MSG_AMF0_COMMAND, 0, body)

    def _status(self, writer, code: str, description: str) -> None:
        body = (
            amf0_encode("onStatus") + amf0_encode(0.0) + amf0_encode(None)
            + amf0_encode({"level": "status", "code": code, "description": description})
        )
        self._send(writer, 5, MSG_AMF0_COMMAND, self.stream_id, body)

    @staticmethod
    def _send(writer, csid: int, type_id: int, msid: int, body: bytes) -> None:
        head = (
            bytes([csid]) + b"\x00\x00\x00" + struct.pack(">I", len(body))[1:]
            + bytes([type_id]) + struct.pack("<I", msid)
        )
        writer.write(head + body)

    @staticmethod
    async def _read_message(reader, states) -> tuple[int, int, int, bytes]:
        """Read whole messages, assuming the client's 128-byte chunks."""
        while True:
            first = (await reader.readexactly(1))[0]
            fmt, csid = first >> 6, first & 0x3F
            state = states.setdefault(csid, _ChunkState())
            if fmt <= 2:
                timestamp = int.from_bytes(await reader.readexactly(3), "big")
                if timestamp == 0xFFFFFF:
                    timestamp = 0
                state.timestamp = timestamp
            if fmt <= 1:
                state.length = int.from_bytes(await reader.readexactly(3), "big")
                state.type_id = (await reader.readexactly(1))[0]
            if fmt == 0:
                state.msid = struct.unpack("<I", await reader.readexactly(4))[0]
            size = min(128, state.length - len(state.body))
            state.body += await reader.readexactly(size)
            if len(state.body) >= state.length:
                body, state.body = bytes(state.body), bytearray()
                return state.type_id, csid, state.msid, body


class TestUrl:
    """librtmp's URL split."""

    def test_intercom_url_is_all_app(self) -> None:
        """`live?token=..` is the app; there is no playpath (RTMP_ParseURL)."""
        parts = parse_rtmp_url("rtmp://1.2.3.4:8000/live?token=T&session=S")

        assert (parts.host, parts.port) == ("1.2.3.4", 8000)
        assert parts.app == "live?token=T&session=S"
        assert parts.playpath == ""
        assert parts.tcurl == "rtmp://1.2.3.4:8000/live?token=T&session=S"

    def test_other_shapes(self) -> None:
        """Two segments split app from playpath; slist and ondemand are special."""
        assert parse_rtmp_url("rtmp://h/a/b/c").app == "a/b"
        assert parse_rtmp_url("rtmp://h/a/b/c").playpath == "c"
        assert parse_rtmp_url("rtmp://h/ondemand/x/y").playpath == "x/y"
        assert parse_rtmp_url("rtmp://h/a/i?slist=S1&x=1").playpath == "S1"
        assert parse_rtmp_url("rtmp://h/live").port == 1935

    def test_bad_urls(self) -> None:
        """Anything that is not an RTMP URL with a host is refused."""
        with pytest.raises(RtmpError):
            parse_rtmp_url("http://h/live")
        with pytest.raises(RtmpError):
            parse_rtmp_url("rtmp:///live")


class TestAmf0:
    """AMF0 encoding and decoding."""

    def test_round_trip(self) -> None:
        """Every type the client uses survives a round trip."""
        value = {
            "app": "live?token=T", "flashVer": "LNX 10,0,32,18",
            "fpad": False, "capabilities": 15.0, "nothing": None,
            "list": [1.0, "two", True],
        }

        decoded, pos = amf0_decode(amf0_encode(value))

        assert decoded == value
        assert pos == len(amf0_encode(value))

    def test_decode_all_and_errors(self) -> None:
        """A command body decodes to its values; junk stops the scan."""
        body = amf0_encode("_result") + amf0_encode(1.0) + amf0_encode(None)

        assert amf0_decode_all(body) == ["_result", 1.0, None]
        assert amf0_decode_all(body + b"\xee\xee") == ["_result", 1.0, None]
        with pytest.raises(RtmpError):
            amf0_encode(object())


class TestAlaw:
    """G.711 A-law, against the ITU-T G.191 table."""

    def test_known_values(self) -> None:
        """Silence and both rails match the reference encoder."""
        assert linear_to_alaw(0) == 0xD5
        assert linear_to_alaw(32767) == 0xAA
        assert linear_to_alaw(-32768) == 0x2A
        assert linear_to_alaw(-1) == 0x55
        # segment 0 keeps four mantissa bits of (sample >> 3) >> 1 ...
        assert linear_to_alaw(16) == 0xD4
        assert linear_to_alaw(-100) == 0x53
        # ... segment 2 shifts by the segment number (G.191 linear2alaw)
        assert linear_to_alaw(1000) == 0xFA
        assert linear_to_alaw(-1000) == 0x7A

    def test_clipping(self) -> None:
        """Out-of-range samples clip to the rails."""
        assert linear_to_alaw(99999) == linear_to_alaw(32767)
        assert linear_to_alaw(-99999) == linear_to_alaw(-32768)


class TestCrypto:
    """cryptoKey handling and the SDK's padding."""

    def test_shape_never_shows_a_value(self) -> None:
        """The shape log has lengths and field names only."""
        shape = crypto_key_shape({"key": "c2VjcmV0a2V5MTIzNDU2", "iv": "aXZpdml2aXZpdml2aXY="})

        assert shape["type"] == "object" and shape["keys"] == ["iv", "key"]
        assert shape["fields"]["key"]["decoded_len"] == 15
        assert "c2Vjc" not in str(shape)

    def test_material_from_object_and_string(self) -> None:
        """Object form is key/iv; a 32-byte string splits into key || iv."""
        import base64

        key, iv = b"k" * 16, b"i" * 16
        crypto = {"key": base64.b64encode(key).decode(), "iv": base64.b64encode(iv).decode()}

        assert crypto_key_material(crypto) == (key, iv)
        assert crypto_key_material((key + iv).hex()) == (key, iv)
        assert crypto_key_material("short") is None
        assert crypto_key_material(None) is None

    def test_padding_is_pkcs7_with_a_fixed_iv(self) -> None:
        """Every packet is padded to 16 and encrypted from the same IV."""
        client = RtmpTalkClient("rtmp://h/live", key=b"k" * 16, iv=b"i" * 16)
        client._writer = _Recorder()

        client.send_audio(b"\x01\x02\x03", 0)
        header, packet = client._writer.chunks[0], client._writer.chunks[1]

        assert client.encrypted is True
        assert len(header) == 12 + 16 and len(packet) == 12 + 16
        # the 4-byte sequence header pads with 0x0C, as the SDK does
        assert header[12:] == _aes_cbc(b"k" * 16, b"i" * 16, bytes(
            [SOUND_BYTE_SDK, 0x00, 11 << 4, 0x00]) + bytes([0x0C]) * 12)
        # the IV is reloaded, so the same body always gives the same bytes
        assert packet[12:] == _aes_cbc(b"k" * 16, b"i" * 16, bytes(
            [SOUND_BYTE_SDK, 0x01, 1, 2, 3]) + bytes([11]) * 11)


class _Recorder:
    """A stand-in stream writer that keeps what the client wrote."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def is_closing(self) -> bool:
        return False

    def write(self, data: bytes) -> None:
        self.chunks.append(data)


class TestFraming:
    """FLV audio framing, as `IOT_RTMP_SendAudio` builds it."""

    def test_sdk_framing_has_the_header_and_the_0x01(self) -> None:
        """G.711 carries the sequence header and the 0x01 marker too."""
        client = RtmpTalkClient("rtmp://h/live")
        client.stream_id = 7
        client._writer = _Recorder()

        client.send_audio(b"\xd5\xd5", 0)
        client.send_audio(b"\xd5", 20)

        bodies = [chunk[12:] for chunk in client._writer.chunks]
        assert bodies[0] == bytes([SOUND_BYTE_SDK, 0x00, 11 << 4, 0x00])
        assert bodies[1] == bytes([SOUND_BYTE_SDK, 0x01]) + b"\xd5\xd5"
        assert bodies[2] == bytes([SOUND_BYTE_SDK, 0x01]) + b"\xd5"  # header sent once
        assert client.audio_packets == 3
        # type 8 on chunk stream 4, with the play stream's id
        head = client._writer.chunks[1]
        assert head[0] == 4 and head[7] == 8
        assert struct.unpack("<I", head[8:12])[0] == 7


class TestChunkReader:
    """The chunk reader, fmt 0-3 and the server's Set Chunk Size."""

    @staticmethod
    async def _feed(client: RtmpTalkClient, data: bytes) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        client._reader = reader
        while not reader.at_eof() or reader._buffer:
            await client._async_read_chunk()

    async def test_formats_and_set_chunk_size(self) -> None:
        """A Set Chunk Size is applied, then a split fmt 0 / fmt 3 message."""
        client = RtmpTalkClient("rtmp://h/live")
        set_size = bytes([2]) + b"\x00\x00\x00" + b"\x00\x00\x04" + bytes([1]) \
            + struct.pack("<I", 0) + struct.pack(">I", 4096)
        body = amf0_encode("onStatus") + amf0_encode(0.0) + amf0_encode(None) + amf0_encode(
            {"level": "status", "code": "NetStream.TalkReady", "description": "x" * 200}
        )
        message = bytes([5]) + b"\x00\x00\x64" + struct.pack(">I", len(body))[1:] \
            + bytes([20]) + struct.pack("<I", 7) + body

        await self._feed(client, set_size + message)

        assert client._in_chunk_size == 4096
        assert [m.code for m in client.messages] == ["NetStream.TalkReady"]
        assert client.messages[0].level == "status"

    async def test_fmt_1_2_3_carry_the_timestamp_on(self) -> None:
        """fmt 1 reuses the stream id, fmt 2 the length, fmt 3 everything."""
        client = RtmpTalkClient("rtmp://h/live")
        client._in_chunk_size = 4
        payload = b"\x00\x00\x00\x00"  # a 4-byte window-ack-size message
        fmt0 = bytes([2]) + b"\x00\x00\x01" + b"\x00\x00\x04" + bytes([5]) \
            + struct.pack("<I", 0) + payload
        fmt1 = bytes([0x40 | 2]) + b"\x00\x00\x02" + b"\x00\x00\x04" + bytes([5]) + payload
        fmt2 = bytes([0x80 | 2]) + b"\x00\x00\x03" + payload
        fmt3 = bytes([0xC0 | 2]) + payload

        await self._feed(client, fmt0 + fmt1 + fmt2 + fmt3)

        assert client._chunks[2].timestamp == 1 + 2 + 3 + 3
        assert client._window == 1  # a zero window is clamped

    async def test_extended_timestamp_repeats_on_fmt_3(self) -> None:
        """A split message with an extended timestamp carries it on fmt 3 too."""
        client = RtmpTalkClient("rtmp://h/live")
        client._in_chunk_size = 4
        big = struct.pack(">I", 0x12345678)
        head = bytes([6]) + b"\xff\xff\xff" + b"\x00\x00\x08" + bytes([9]) \
            + struct.pack("<I", 1) + big
        data = head + b"VIDE" + bytes([0xC0 | 6]) + big + b"O123"
        after = bytes([2]) + b"\x00\x00\x00" + b"\x00\x00\x04" + bytes([5]) \
            + struct.pack("<I", 0) + struct.pack(">I", 5000)

        await self._feed(client, data + after)

        assert client.received == {9: [1, 8], 5: [1, 4]}
        assert client._chunks[6].timestamp == 0x12345678
        assert client._window == 5000  # still in step after the video


@pytest.mark.usefixtures("socket_enabled")
class TestEndToEnd:
    """The client against a fake server."""

    async def test_play_then_talk(self) -> None:
        """connect/createStream/play, TalkReady, then audio on the play stream."""
        server = FakeRtmpServer()
        base = await server.start()
        client = RtmpTalkClient(f"{base}/live?token=T&private=0")
        try:
            reply = await client.async_connect()
            stream = await client.async_create_stream()
            await client.async_play()
            ready = await client.async_wait_for_code("NetStream.TalkReady", 5)
            for _ in range(2):
                await client.async_send_frame(b"\xd5" * 160)
            await asyncio.sleep(0.1)
        finally:
            await client.async_close()
            await server.stop()

        assert reply["code"] == "NetConnection.Connect.Success"
        assert stream == 7 and ready is not None
        assert server.commands == ["connect", "createStream", "play"]
        assert server.connect_arg["app"] == "live?token=T&private=0"
        assert server.connect_arg["tcUrl"].endswith("/live?token=T&private=0")
        assert server.play_arg == ""  # the playpath is empty for this URL
        assert [m.code for m in client.messages if m.code] == [
            "NetConnection.Connect.Success", "NetStream.Play.Start",
            "NetStream.TalkReady",
        ]
        assert "code=NetStream.TalkReady" in client.messages[-1].as_log()
        csids = {csid for csid, _, _ in server.audio}
        msids = {msid for _, msid, _ in server.audio}
        assert csids == {4} and msids == {7}
        assert all(body[0] == SOUND_BYTE_SDK for _, _, body in server.audio)
        assert server.audio[1][2][1] == 0x01
        assert client.audio_packets == len(server.audio)

    async def test_server_hangs_up_after_play(self) -> None:
        """A server that closes after play is noticed, nothing raises."""
        server = FakeRtmpServer(close_after_play=True)
        base = await server.start()
        client = RtmpTalkClient(f"{base}/live?token=T")
        try:
            await client.async_connect()
            await client.async_create_stream()
            await client.async_play()
            ready = await client.async_wait_for_code("NetStream.TalkReady", 5)
            with contextlib.suppress(RtmpError):
                for _ in range(20):
                    await client.async_send_frame(b"\xd5" * 160)
                    await asyncio.sleep(0.02)
        finally:
            await client.async_close()
            await server.stop()

        assert ready is None
        assert client.server_closed_at is not None
        assert server.audio == []

    async def test_connect_is_refused(self) -> None:
        """A server that drops the connection fails the connect, not the test."""
        server = FakeRtmpServer()
        base = await server.start()
        await server.stop()
        client = RtmpTalkClient(f"{base}/live?token=T", timeout=1)

        with pytest.raises((RtmpError, OSError)):
            await client.async_connect()
        await client.async_close()

    async def test_request_audio_type_wire_format(self) -> None:
        """onStatus on csid 3, stream 0, with audio_type, as IOT_RTMP_SendMessage."""
        server = FakeRtmpServer(needs_request=True)
        base = await server.start()
        client = RtmpTalkClient(f"{base}/live?token=T")
        try:
            await client.async_connect()
            await client.async_send_status("NetStream.RequestAudioType", audio_type="1")
            await client.async_create_stream()
            await client.async_play()
            ready = await client.async_wait_for_code("NetStream.TalkReady", 2)
        finally:
            await client.async_close()
            await server.stop()

        assert ready is not None
        assert server.commands[:3] == ["connect", "onStatus", "createStream"]
        assert server.statuses[0] == {
            "level": "status", "code": "NetStream.RequestAudioType",
            "description": "desc", "audio_type": "1",
        }

