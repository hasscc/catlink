"""Aliyun IoT "mobile channel": the app-side MQTT push connection.

The account's iotToken is bound to an MQTT client of its own, and Aliyun
then pushes property changes, thing events and online status for every
device on the account (on .../app/down/thing/properties, /thing/events and
/thing/status, with the device's iotId in params). This is how the Pro Ultra
has live state without polling. See docs/PRO_ULTRA.md.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import ssl
import string
import time
from typing import TYPE_CHECKING, Any
import uuid

from ..const import _LOGGER, ALIYUN_APP_KEY, ALIYUN_APP_SECRET

if TYPE_CHECKING:
    from .linkvisual import LinkVisualClient

AEPAUTH_PATH = "/app/aepauth/handle"
AEPAUTH_API_VER = "1.0.0"
MQTT_PORT = 1883
MQTT_HOST_TEMPLATE = "{product_key}.iot-as-mqtt.{region}.aliyuncs.com"
MQTT_KEEPALIVE = 65
BIND_TIMEOUT = 15
RECONNECT_MIN_DELAY = 5
RECONNECT_MAX_DELAY = 600
# Reconnect and bind a fresh iotToken this long before the old one expires.
TOKEN_REFRESH_MARGIN = 600
# The broker's chain ends at the 1998 GlobalSign Root CA, which current trust
# stores no longer carry, so that root is bundled.
BROKER_ROOT_CA = Path(__file__).parent / "certs" / "globalsign_root_ca_r1.pem"
_SECRET_KEY_RE = re.compile(r"token|secret|password|sign|url", re.I)


class AliyunPushError(Exception):
    """Raised when the push connection can't be set up."""


@dataclass(frozen=True)
class MqttCredentials:
    """Everything needed to open the mobile-channel MQTT session."""

    host: str
    port: int
    client_id: str
    username: str
    password: str
    product_key: str
    device_name: str

    @property
    def topic_prefix(self) -> str:
        """Return the /sys/<pk>/<dn> topic namespace of this client."""
        return f"/sys/{self.product_key}/{self.device_name}"


def _hmac_sha1_hex(key: str, text: str) -> str:
    return hmac.new(key.encode(), text.encode(), hashlib.sha1).hexdigest()


def _random_alnum(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_auth_info(
    *,
    timestamp_ms: int | None = None,
    client_id: str | None = None,
    device_sn: str | None = None,
) -> dict[str, str]:
    """Return the signed authInfo for /app/aepauth/handle.

    The appKey takes part in the signature but isn't sent; the gateway
    headers carry it.
    """
    timestamp = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    client_id = client_id or _random_alnum(8)
    device_sn = device_sn or _random_alnum(32)
    text = f"appKey{ALIYUN_APP_KEY}clientId{client_id}deviceSn{device_sn}timestamp{timestamp}"
    return {
        "clientId": client_id,
        "deviceSn": device_sn,
        "timestamp": timestamp,
        "sign": _hmac_sha1_hex(ALIYUN_APP_SECRET, text).lower(),
    }


def region_from_gateway(api_host: str) -> str:
    """Return the region id of a "<region>.api-iot.aliyuncs.com" gateway host."""
    region = (api_host or "").split(".api-iot.aliyuncs.com", 1)[0]
    if not region or "." in region:
        raise AliyunPushError(f"Unexpected Aliyun gateway host: {api_host}")
    return region


def mqtt_credentials(triple: dict, api_host: str) -> MqttCredentials:
    """Derive the MQTT login from the aepauth triple."""
    product_key = triple.get("productKey")
    device_name = triple.get("deviceName")
    device_secret = triple.get("deviceSecret")
    if not product_key or not device_name or not device_secret:
        raise AliyunPushError("aepauth returned no productKey/deviceName/deviceSecret")
    bare = f"{device_name}&{product_key}"
    password = _hmac_sha1_hex(
        device_secret, f"clientId{bare}deviceName{device_name}productKey{product_key}"
    ).upper()
    return MqttCredentials(
        host=MQTT_HOST_TEMPLATE.format(
            product_key=product_key, region=region_from_gateway(api_host)
        ),
        port=MQTT_PORT,
        client_id=f"{bare}|securemode=2,signmethod=hmacsha1,ext=1|",
        username=bare,
        password=password,
        product_key=product_key,
        device_name=device_name,
    )


def bind_payload(request_id: str, client_id: str, iot_token: str) -> bytes:
    """Return the /account/bind request body."""
    return json.dumps(
        {
            "id": request_id,
            "system": {"version": "1.0", "time": str(int(time.time() * 1000))},
            "request": {"clientId": client_id},
            "params": {"iotToken": iot_token},
        }
    ).encode()


def redact(value: Any) -> Any:
    """Return value with anything that looks like a credential masked."""
    if isinstance(value, dict):
        return {
            k: "***" if _SECRET_KEY_RE.search(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def short_topic(topic: str, creds: MqttCredentials) -> str:
    """Strip the /sys/<pk>/<dn>/app/down prefix before dispatching."""
    prefix = f"{creds.topic_prefix}/app/down"
    return topic[len(prefix):] if topic.startswith(prefix) else topic


class AliyunPushClient:
    """Keep one mobile-channel session open and hand each push to a callback.

    on_message(short_topic, payload) gets the decoded JSON; the client
    reconnects with backoff and re-binds before the iotToken expires.
    """

    def __init__(
        self,
        linkvisual: LinkVisualClient,
        on_message: Callable[[str, dict], None],
    ) -> None:
        """Initialize the client."""
        self._linkvisual = linkvisual
        self._on_message = on_message
        self._task: asyncio.Task | None = None
        self._triple: dict | None = None
        self._triple_host: str | None = None
        self._tls: ssl.SSLContext | None = None
        self.connected = False
        self.messages = 0

    @property
    def running(self) -> bool:
        """Return whether the connection task is alive."""
        return self._task is not None and not self._task.done()

    def start(self, hass) -> None:
        """Start the connection task (no-op if it's running)."""
        if self.running:
            return
        self._task = hass.async_create_background_task(
            self._async_run(hass), "catlink-aliyun-push"
        )

    def stop(self) -> None:
        """Stop the connection task."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self.connected = False

    async def _async_run(self, hass) -> None:
        delay = RECONNECT_MIN_DELAY
        while True:
            started = time.monotonic()
            try:
                await self._async_session(hass)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep retrying, never crash HA
                _LOGGER.warning("Aliyun push connection failed: %s", exc)
            self.connected = False
            if time.monotonic() - started > RECONNECT_MAX_DELAY:
                delay = RECONNECT_MIN_DELAY
            _LOGGER.debug("Aliyun push reconnecting in %ss", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _async_credentials(self, api_host: str) -> MqttCredentials:
        if self._triple is None or self._triple_host != api_host:
            rsp = await self._linkvisual.async_raw_request(
                api_host, AEPAUTH_PATH, AEPAUTH_API_VER, {"authInfo": build_auth_info()}
            )
            if rsp.get("code") != 200:
                raise AliyunPushError(
                    f"aepauth failed: {rsp.get('code')} {rsp.get('message')}"
                )
            self._triple = rsp.get("data") or {}
            self._triple_host = api_host
        return mqtt_credentials(self._triple, api_host)

    def _build_tls(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=str(BROKER_ROOT_CA))
        return context

    async def _async_session(self, hass) -> None:
        import aiomqtt  # noqa: PLC0415 - only needed once a Pro Ultra starts push

        api_host, iot_token, expires_at = await self._linkvisual.async_session_info()
        creds = await self._async_credentials(api_host)
        if self._tls is None:
            self._tls = await hass.async_add_executor_job(self._build_tls)
        try:
            client = aiomqtt.Client(
                hostname=creds.host,
                port=creds.port,
                identifier=creds.client_id,
                username=creds.username,
                password=creds.password,
                tls_context=self._tls,
                keepalive=MQTT_KEEPALIVE,
                clean_session=True,
            )
            await client.__aenter__()
        except aiomqtt.MqttError:
            # A rejected login may mean the cached triple is no longer valid.
            self._triple = None
            raise
        try:
            await client.subscribe(f"{creds.topic_prefix}/app/down/#", qos=0)
            messages = client.messages
            request_id = uuid.uuid4().hex
            await client.publish(
                f"{creds.topic_prefix}/app/up/account/bind",
                bind_payload(request_id, creds.username, iot_token),
                qos=1,
            )
            async with asyncio.timeout(BIND_TIMEOUT):
                while True:
                    topic, payload = self._decode(await anext(messages), creds)
                    if payload.get("id") == request_id:
                        if payload.get("code") != 200:
                            raise AliyunPushError(
                                f"account bind failed: {payload.get('code')} "
                                f"{payload.get('message')}"
                            )
                        break
                    self._dispatch(topic, payload)
            self.connected = True
            _LOGGER.info("Aliyun push connected to %s and bound", creds.host)
            remaining = max(expires_at - time.time() - TOKEN_REFRESH_MARGIN, 60)
            try:
                async with asyncio.timeout(remaining):
                    while True:
                        topic, payload = self._decode(await anext(messages), creds)
                        self._dispatch(topic, payload)
            except TimeoutError:
                _LOGGER.debug("Aliyun push re-binding with a fresh iotToken")
        finally:
            self.connected = False
            try:
                await client.__aexit__(None, None, None)
            except aiomqtt.MqttError:
                pass

    @staticmethod
    def _decode(message, creds: MqttCredentials) -> tuple[str, dict]:
        topic = short_topic(str(message.topic), creds)
        try:
            payload = json.loads(bytes(message.payload or b"").decode() or "{}")
        except (UnicodeDecodeError, ValueError):
            payload = {}
        return topic, payload if isinstance(payload, dict) else {}

    def _dispatch(self, topic: str, payload: dict) -> None:
        self.messages += 1
        try:
            self._on_message(topic, payload)
        except Exception:  # noqa: BLE001 - one bad message mustn't end the session
            _LOGGER.exception("Handling Aliyun push on %s failed", topic)
