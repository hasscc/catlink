"""Tests for the Aliyun mobile-channel push client."""

import asyncio
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import aiomqtt
from custom_components.catlink.const import ALIYUN_APP_KEY, ALIYUN_APP_SECRET
from custom_components.catlink.modules import aliyun_push
from custom_components.catlink.modules.aliyun_push import (
    BROKER_ROOT_CA,
    AliyunPushClient,
    AliyunPushError,
    MqttCredentials,
    build_auth_info,
    mqtt_credentials,
    redact,
    region_from_gateway,
    short_topic,
)
from custom_components.catlink.modules.linkvisual import LinkVisualClient
import pytest

API_HOST = "us-east-1.api-iot.aliyuncs.com"
TRIPLE = {"productKey": "pk1", "deviceName": "dn1", "deviceSecret": "secret"}


def _sha1(key: str, text: str) -> str:
    return hmac.new(key.encode(), text.encode(), hashlib.sha1).hexdigest()


class TestCredentials:
    """Tests for the bootstrap signature and the MQTT login."""

    def test_auth_info(self) -> None:
        """Signed over appKey, clientId, deviceSn, timestamp in that order; appKey not sent."""
        info = build_auth_info(timestamp_ms=1700000000000, client_id="abcd1234", device_sn="x" * 32)

        expected = _sha1(
            ALIYUN_APP_SECRET,
            f"appKey{ALIYUN_APP_KEY}clientIdabcd1234deviceSn{'x' * 32}timestamp1700000000000",
        ).lower()
        assert info == {
            "clientId": "abcd1234",
            "deviceSn": "x" * 32,
            "timestamp": "1700000000000",
            "sign": expected,
        }

    def test_auth_info_random_parts(self) -> None:
        """Random clientId (8) and deviceSn (32), alphanumeric like the SDK."""
        info = build_auth_info()
        assert len(info["clientId"]) == 8 and info["clientId"].isalnum()
        assert len(info["deviceSn"]) == 32 and info["deviceSn"].isalnum()

    def test_mqtt_credentials(self) -> None:
        """Same derivation as MqttNet and neakasa-litterbox-sdk's test vector."""
        creds = mqtt_credentials(TRIPLE, API_HOST)

        assert creds.host == "pk1.iot-as-mqtt.us-east-1.aliyuncs.com"
        assert creds.port == 1883
        assert creds.username == "dn1&pk1"
        assert creds.client_id == "dn1&pk1|securemode=2,signmethod=hmacsha1,ext=1|"
        assert creds.password == _sha1(
            "secret", "clientIddn1&pk1deviceNamedn1productKeypk1"
        ).upper()
        assert creds.topic_prefix == "/sys/pk1/dn1"

    def test_missing_triple(self) -> None:
        """An incomplete triple is an error."""
        with pytest.raises(AliyunPushError, match="deviceSecret"):
            mqtt_credentials({"productKey": "pk1"}, API_HOST)

    @pytest.mark.parametrize(
        ("host", "region"),
        [(API_HOST, "us-east-1"), ("eu-central-1.api-iot.aliyuncs.com", "eu-central-1")],
    )
    def test_region(self, host, region) -> None:
        """The broker region comes from the gateway host."""
        assert region_from_gateway(host) == region

    def test_unexpected_gateway(self) -> None:
        """A gateway host of another shape is refused rather than guessed."""
        with pytest.raises(AliyunPushError):
            region_from_gateway("api.link.aliyun.com")

    def test_bundled_root_ca(self) -> None:
        """The GlobalSign root the broker chains to ships with the integration."""
        assert "BEGIN CERTIFICATE" in BROKER_ROOT_CA.read_text()


class TestHelpers:
    """Tests for topic and logging helpers."""

    def test_short_topic(self) -> None:
        """The /sys/<pk>/<dn>/app/down prefix is stripped."""
        creds = mqtt_credentials(TRIPLE, API_HOST)
        assert short_topic("/sys/pk1/dn1/app/down/thing/properties", creds) == "/thing/properties"
        assert short_topic("/other/topic", creds) == "/other/topic"

    def test_redact(self) -> None:
        """Credential-looking keys are masked at any depth; the rest is kept."""
        value = {
            "iotId": "iot-1",
            "iotToken": "t",
            "items": {"ExtInfo": {"value": "catSatus=1"}, "relayUrl": "rtmp://x"},
            "list": [{"deviceSecret": "s", "a": 1}],
        }
        assert redact(value) == {
            "iotId": "iot-1",
            "iotToken": "***",
            "items": {"ExtInfo": {"value": "catSatus=1"}, "relayUrl": "***"},
            "list": [{"deviceSecret": "***", "a": 1}],
        }


class FakeBroker:
    """Stands in for aiomqtt.Client: answers the bind and replays queued pushes."""

    def __init__(self, bind_code=200, pushes=None, fail_connect=False):
        self.bind_code = bind_code
        self.pushes = pushes or []
        self.fail_connect = fail_connect
        self.kwargs = None
        self.subscribed = []
        self.published = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self

    async def __aenter__(self):
        if self.fail_connect:
            raise aiomqtt.MqttError("Connection refused: not authorised")
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    async def publish(self, topic, payload=None, qos=0):
        self.published.append((topic, json.loads(payload), qos))
        body = json.loads(payload)
        reply = {"id": body["id"], "code": self.bind_code, "message": "denied"}
        await self.queue.put(("/sys/pk1/dn1/app/down/account/bind_reply", reply))
        for push in self.pushes:
            await self.queue.put(push)

    @property
    def messages(self):
        broker = self

        class _Iter:
            def __aiter__(self):
                return self

            async def __anext__(self):
                if broker.queue.empty():
                    raise aiomqtt.MqttError("Disconnected during message iteration")
                topic, body = await broker.queue.get()
                msg = MagicMock()
                msg.topic = topic
                msg.payload = json.dumps(body).encode()
                return msg

        return _Iter()


@pytest.fixture
def linkvisual():
    """LinkVisual stub with a session and a successful aepauth."""
    lv = MagicMock()
    lv.async_session_info = AsyncMock(return_value=(API_HOST, "iot-token-1", 9e12))
    lv.async_raw_request = AsyncMock(return_value={"code": 200, "data": dict(TRIPLE)})
    return lv


@pytest.fixture
def hass_stub():
    """Enough of hass for the client: an executor for the TLS context."""
    hass = MagicMock()

    async def _job(fun, *args):
        return MagicMock()  # an SSL context stand-in

    hass.async_add_executor_job = _job
    return hass


class TestSession:
    """Tests for one connect-bind-receive session against a fake broker."""

    async def test_bind_and_dispatch(self, monkeypatch, linkvisual, hass_stub) -> None:
        """Subscribes the wildcard, binds the iotToken, then hands pushes over."""
        push = (
            "/sys/pk1/dn1/app/down/thing/properties",
            {"method": "thing.properties", "params": {"iotId": "iot-1", "items": {}}},
        )
        broker = FakeBroker(pushes=[push])
        monkeypatch.setattr(aiomqtt, "Client", broker)
        received = []
        client = AliyunPushClient(linkvisual, lambda t, p: received.append((t, p)))

        with pytest.raises(aiomqtt.MqttError):
            await client._async_session(hass_stub)

        assert broker.kwargs["hostname"] == "pk1.iot-as-mqtt.us-east-1.aliyuncs.com"
        assert broker.kwargs["port"] == 1883
        assert broker.kwargs["username"] == "dn1&pk1"
        assert broker.subscribed == ["/sys/pk1/dn1/app/down/#"]
        topic, body, qos = broker.published[0]
        assert topic == "/sys/pk1/dn1/app/up/account/bind"
        assert qos == 1
        assert body["params"] == {"iotToken": "iot-token-1"}
        assert body["request"] == {"clientId": "dn1&pk1"}
        assert received == [("/thing/properties", push[1])]
        assert broker.closed
        assert client.connected is False
        req = linkvisual.async_raw_request.await_args.args
        assert req[:3] == (API_HOST, "/app/aepauth/handle", "1.0.0")
        assert set(req[3]["authInfo"]) == {"clientId", "deviceSn", "timestamp", "sign"}

    async def test_bind_rejected(self, monkeypatch, linkvisual, hass_stub) -> None:
        """A bind reply other than 200 ends the session with an error."""
        monkeypatch.setattr(aiomqtt, "Client", FakeBroker(bind_code=2043))
        client = AliyunPushClient(linkvisual, MagicMock())

        with pytest.raises(AliyunPushError, match="2043"):
            await client._async_session(hass_stub)

    async def test_triple_cached_and_reset(self, monkeypatch, linkvisual, hass_stub) -> None:
        """The triple is reused across reconnects and fetched again after a refused login."""
        monkeypatch.setattr(aiomqtt, "Client", FakeBroker())
        client = AliyunPushClient(linkvisual, MagicMock())
        for _ in range(2):
            with pytest.raises(aiomqtt.MqttError):
                await client._async_session(hass_stub)
        assert linkvisual.async_raw_request.await_count == 1

        monkeypatch.setattr(aiomqtt, "Client", FakeBroker(fail_connect=True))
        with pytest.raises(aiomqtt.MqttError):
            await client._async_session(hass_stub)
        assert client._triple is None

    async def test_aepauth_failure(self, linkvisual, hass_stub) -> None:
        """A failed bootstrap is an error naming the code."""
        linkvisual.async_raw_request = AsyncMock(return_value={"code": 401, "message": "sign"})
        client = AliyunPushClient(linkvisual, MagicMock())

        with pytest.raises(AliyunPushError, match="aepauth failed: 401"):
            await client._async_session(hass_stub)


class TestLinkVisualPush:
    """Tests for the push hooks on LinkVisualClient."""

    def test_routes_by_iot_id(self, monkeypatch) -> None:
        """Pushes go to the listener registered for their iotId."""
        started = []
        monkeypatch.setattr(AliyunPushClient, "start", lambda self, hass: started.append(hass))
        lv = LinkVisualClient(MagicMock())
        mine = MagicMock()

        lv.start_push("hass", "iot-1", mine)
        lv.start_push("hass", "iot-1", mine)
        lv._dispatch_push("/thing/properties", {"params": {"iotId": "iot-1"}})
        lv._dispatch_push("/thing/properties", {"params": {"iotId": "other"}})
        lv._dispatch_push("/account/bind_reply", {"code": 200})

        mine.assert_called_once_with("/thing/properties", {"params": {"iotId": "iot-1"}})
        assert started == ["hass", "hass"]

    def test_close_stops_push(self, monkeypatch) -> None:
        """close() stops the connection and forgets the listeners."""
        monkeypatch.setattr(AliyunPushClient, "start", lambda self, hass: None)
        stop = MagicMock()
        monkeypatch.setattr(AliyunPushClient, "stop", stop)
        lv = LinkVisualClient(MagicMock())
        lv.start_push("hass", "iot-1", MagicMock())

        lv.close()

        stop.assert_called_once()
        assert lv._push is None and lv._push_listeners == {}

    def test_close_without_push(self) -> None:
        """close() is harmless when push never started."""
        LinkVisualClient(MagicMock()).close()


def test_credentials_dataclass_is_frozen() -> None:
    """Credentials can't be changed after derivation."""
    creds = MqttCredentials("h", 1, "c", "u", "p", "pk", "dn")
    with pytest.raises(AttributeError):
        creds.host = "x"


def test_module_constants() -> None:
    """Broker port and bootstrap endpoint as in the SDK."""
    assert aliyun_push.MQTT_PORT == 1883
    assert aliyun_push.AEPAUTH_PATH == "/app/aepauth/handle"
