"""Aliyun IoT LinkVisual client for CatLink camera devices.

VISUAL_PRO_ULTRA devices live on Aliyun's IoT Living Platform: a CatLink
token buys an Aliyun auth code, which logs in to the account's region and
yields an iotToken (cached until it expires). That session gives live stream
URLs, thing properties and services, pictures and talk-back sessions.
See docs/PRO_ULTRA.md.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode
import uuid

from aiohttp import ClientError

from ..const import _LOGGER, ALIYUN_APP_KEY, ALIYUN_APP_SECRET

if TYPE_CHECKING:
    from .account import Account

API_AUTH_CODE = "token/user/auth/aliLive/authCode"
REGION_HOST = "cn-shanghai.api-iot.aliyuncs.com"
REGION_PATH = "/living/account/region/get"
OA_LOGIN_PATH = "/api/prd/loginbyoauth.json"
CREATE_SESSION_PATH = "/account/createSessionByAuthCode"
STREAM_QUERY_PATH = "/vision/customer/stream/query"
PROPERTIES_GET_PATH = "/thing/properties/get"
PROPERTIES_SET_PATH = "/living/thing/properties/set"
STATUS_GET_PATH = "/thing/status/get"
SERVICE_INVOKE_PATH = "/thing/service/invoke"
PICTURE_QUERY_PATH = "/vision/customer/picture/querybyids"
INTERCOM_START_PATH = "/vision/customer/voice/intercom/start"
# Gateway code for a rejected iotToken.
CODE_AUTH_FAILED = 401

# /thing/status/get values (Aliyun: 0 inactive, 1 online, 3 offline, 8 disabled).
THING_STATUS_ONLINE = 1

STREAM_TYPE_MAJOR = 0  # 1080p
STREAM_TYPE_MINOR = 1  # 720p

CONTENT_TYPE_STREAM = "application/octet-stream; charset=utf-8"
CONTENT_TYPE_FORM = "application/x-www-form-urlencoded; charset=utf-8"
ACCEPT_JSON = "application/json; charset=utf-8"

# OpenAccount oauth platform id the CatLink app uses for its own auth codes.
OAUTH_PLATFORM_CATLINK = 23
TOKEN_EXPIRY_MARGIN = 300
DEFAULT_TOKEN_LIFETIME = 3600
REQUEST_TIMEOUT = 30
REGION_RETRY_DELAY = 2

RISK_CONTROL_INFO = {
    "appName": "com.catlinks.app",
    "appVersion": "4.1.5",
    "osName": "android",
    "osVersion": "11",
    "umidToken": "",
}


class LinkVisualError(Exception):
    """Raised when a LinkVisual request fails."""


@dataclass
class _IoTSession:
    api_host: str
    iot_token: str
    expires_at: float

    @property
    def valid(self) -> bool:
        return time.time() < self.expires_at - TOKEN_EXPIRY_MARGIN


def build_gateway_headers(
    path: str,
    body: bytes,
    content_type: str,
    form: dict[str, str] | None = None,
    *,
    app_key: str = ALIYUN_APP_KEY,
    app_secret: str = ALIYUN_APP_SECRET,
    timestamp_ms: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Return signed headers for an Aliyun API gateway POST (HmacSHA1 scheme).

    Form requests sign their sorted form params as part of the resource, body
    requests sign the body's Content-MD5 instead.
    """
    timestamp_ms = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    ca_headers = {
        "x-ca-key": app_key,
        "x-ca-nonce": nonce or str(uuid.uuid4()),
        "x-ca-signature-method": "HmacSHA1",
        "x-ca-timestamp": str(timestamp_ms),
        "x-ca-version": "1",
    }
    date = formatdate(timestamp_ms / 1000, usegmt=True)
    content_md5 = "" if form else base64.b64encode(hashlib.md5(body).digest()).decode()
    resource = path
    if form:
        resource += "?" + "&".join(
            f"{k}={v}" if v not in (None, "") else k for k, v in sorted(form.items())
        )
    string_to_sign = (
        "\n".join(["POST", ACCEPT_JSON, content_md5, content_type, date])
        + "\n"
        + "".join(f"{k}:{ca_headers[k]}\n" for k in sorted(ca_headers))
        + resource
    )
    signature = base64.b64encode(
        hmac.new(app_secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    headers = {
        **ca_headers,
        "x-ca-signature-headers": ",".join(sorted(ca_headers)),
        "x-ca-signature": signature,
        "accept": ACCEPT_JSON,
        "content-type": content_type,
        "date": date,
    }
    if content_md5:
        headers["content-md5"] = content_md5
    return headers


class LinkVisualClient:
    """Talk to Aliyun IoT for a CatLink account: live streams and thing properties."""

    def __init__(self, account: Account) -> None:
        """Initialize the client."""
        self._account = account
        self._session: _IoTSession | None = None
        self._lock = asyncio.Lock()
        self._push = None
        self._push_listeners: dict[str, Callable[[str, dict], None]] = {}

    async def async_get_live_url(
        self, iot_id: str, stream_type: int = STREAM_TYPE_MAJOR
    ) -> str:
        """Return a fresh RTMP relay URL for the device; valid for about a minute."""
        params = {"iotId": iot_id, "streamType": stream_type, "encryptType": 0}
        rsp = await self._async_session_request(STREAM_QUERY_PATH, "2.2.0", params)
        data = rsp.get("data") or {}
        if rsp.get("code") != 200 or not data.get("relayUrl"):
            raise LinkVisualError(
                f"Stream query failed: {rsp.get('code')} {_message(rsp)}"
            )
        if data.get("relayDecryptKey"):
            _LOGGER.warning("LinkVisual stream for %s is encrypted; playback may fail", iot_id)
        return data["relayUrl"]

    async def async_get_properties(self, iot_id: str) -> dict:
        """Return the device's current thing property values, keyed by identifier."""
        rsp = await self._async_session_request(
            PROPERTIES_GET_PATH, "1.0.0", {"iotId": iot_id}
        )
        data = rsp.get("data")
        if rsp.get("code") != 200 or not isinstance(data, dict):
            raise LinkVisualError(
                f"Property query failed: {rsp.get('code')} {_message(rsp)}"
            )
        # Each property comes as {"value": ..., "time": <ms>}.
        return {
            key: item.get("value") if isinstance(item, dict) else item
            for key, item in data.items()
        }

    async def async_is_online(self, iot_id: str) -> bool:
        """Return whether Aliyun currently sees the device as connected.

        Property reads keep returning the last reported values while a device is
        offline, so this is the only way to tell whether they are current.
        """
        rsp = await self._async_session_request(
            STATUS_GET_PATH, "1.0.5", {"iotId": iot_id}
        )
        data = rsp.get("data")
        if rsp.get("code") != 200 or not isinstance(data, dict):
            raise LinkVisualError(
                f"Status query failed: {rsp.get('code')} {_message(rsp)}"
            )
        return _to_int(data.get("status")) == THING_STATUS_ONLINE

    async def async_set_properties(self, iot_id: str, items: dict) -> None:
        """Write thing properties on the device, e.g. {"PromptSoundSwitch": 0}."""
        rsp = await self._async_session_request(
            PROPERTIES_SET_PATH, "1.0.0", {"iotId": iot_id, "items": items}
        )
        _LOGGER.debug("Set properties %s on %s: %s", items, iot_id, rsp)
        if rsp.get("code") != 200:
            raise LinkVisualError(
                f"Property update failed: {rsp.get('code')} {_message(rsp)}"
            )

    async def async_query_pictures(self, iot_id: str, picture_ids: list[str]) -> dict:
        """Return {pictureId: {thumbUrl, pictureUrl, ...}} for uploaded pictures.

        The URLs are signed and short-lived, so download them right away.
        """
        rsp = await self._async_session_request(
            PICTURE_QUERY_PATH,
            "2.1.0",
            {"iotId": iot_id, "pictureIdList": list(picture_ids), "type": 0},
        )
        if rsp.get("code") != 200:
            raise LinkVisualError(
                f"Picture query failed: {rsp.get('code')} {_message(rsp)}"
            )
        data = rsp.get("data")
        pictures = data.get("pictureList") if isinstance(data, dict) else None
        return {
            p["pictureId"]: p
            for p in pictures or []
            if isinstance(p, dict) and p.get("pictureId")
        }

    async def async_start_intercom(self, iot_id: str, **params) -> dict:
        """Open a talk-back session; return the raw reply.

        It holds a short-lived URL and possibly a cryptoKey: never log them.
        Only a rejected token is worth retrying; 9543 (the box already has a
        session) would not change.
        """
        return await self._async_session_request(
            INTERCOM_START_PATH,
            "2.0.3",
            {"iotId": iot_id, **params},
            retry_codes={CODE_AUTH_FAILED},
        )

    async def async_invoke_service(
        self, iot_id: str, identifier: str, args: dict | None = None
    ) -> dict:
        """Call a thing service on the device, e.g. "Reboot".

        Retried only after a rejected token: a service may have run even when
        the call reports another failure.
        """
        rsp = await self._async_session_request(
            SERVICE_INVOKE_PATH,
            "1.0.5",
            {"iotId": iot_id, "identifier": identifier, "args": args or {}},
            retry_codes={CODE_AUTH_FAILED},
        )
        _LOGGER.debug("Service %s on %s: %s", identifier, iot_id, rsp)
        if rsp.get("code") != 200:
            raise LinkVisualError(
                f"Service {identifier} failed: {rsp.get('code')} {_message(rsp)}"
            )
        return rsp

    async def async_session_info(self) -> tuple[str, str, float]:
        """Return the gateway host, iotToken and its expiry (epoch s), logging in if needed."""
        session = await self._async_get_session()
        return session.api_host, session.iot_token, session.expires_at

    async def async_raw_request(
        self, host: str, path: str, api_ver: str, params: dict
    ) -> dict:
        """Call an IoT API without an iotToken (e.g. /app/aepauth/handle)."""
        return await self._async_iot_request(host, path, api_ver, params)

    def start_push(
        self, hass, iot_id: str, on_message: Callable[[str, dict], None]
    ) -> None:
        """Receive Aliyun pushes for iot_id; one connection serves the whole account."""
        from .aliyun_push import AliyunPushClient  # noqa: PLC0415

        self._push_listeners[iot_id] = on_message
        if self._push is None:
            self._push = AliyunPushClient(self, self._dispatch_push)
        self._push.start(hass)

    def _dispatch_push(self, topic: str, payload: dict) -> None:
        params = payload.get("params")
        iot_id = params.get("iotId") if isinstance(params, dict) else None
        listener = self._push_listeners.get(iot_id)
        if listener is not None:
            listener(topic, payload)
        else:
            _LOGGER.debug("Aliyun push on %s for another device or none", topic)

    def close(self) -> None:
        """Stop the push connection, if any."""
        if self._push is not None:
            self._push.stop()
            self._push = None
        self._push_listeners.clear()

    async def _async_session_request(
        self, path: str, api_ver: str, params: dict, retry_codes: set | None = None
    ) -> dict:
        """Call an IoT API with the cached session; log in again once if it fails.

        With retry_codes, only those failure codes are retried.
        """
        session = await self._async_get_session()
        rsp = await self._async_iot_request(
            session.api_host, path, api_ver, params, session.iot_token
        )
        if rsp.get("code") != 200 and (
            retry_codes is None or rsp.get("code") in retry_codes
        ):
            _LOGGER.debug(
                "LinkVisual %s failed (code %s), logging in again", path, rsp.get("code")
            )
            session = await self._async_get_session(force=True)
            rsp = await self._async_iot_request(
                session.api_host, path, api_ver, params, session.iot_token
            )
        return rsp

    async def _async_get_session(self, force: bool = False) -> _IoTSession:
        async with self._lock:
            if force or not self._session or not self._session.valid:
                self._session = await self._async_login()
            return self._session

    async def _async_login(self) -> _IoTSession:
        rsp = await self._account.request(API_AUTH_CODE, method="POST")
        auth_code = rsp.get("data")
        if not isinstance(auth_code, str) or not auth_code:
            raise LinkVisualError(
                f"CatLink auth code request failed: {rsp.get('returnCode')} {rsp.get('msg')}"
            )

        region_params = {"type": "THIRD_AUTHCODE", "authCode": auth_code}
        region = await self._async_iot_request(
            REGION_HOST, REGION_PATH, "1.0.2", region_params
        )
        if region.get("code") != 200:
            # A freshly issued auth code is sometimes rejected with a 500 and
            # accepted a moment later.
            _LOGGER.debug(
                "Aliyun region lookup failed (code %s), retrying", region.get("code")
            )
            await asyncio.sleep(REGION_RETRY_DELAY)
            region = await self._async_iot_request(
                REGION_HOST, REGION_PATH, "1.0.2", region_params
            )
        region_data = region.get("data") or {}
        api_host = region_data.get("apiGatewayEndpoint")
        oa_host = region_data.get("oaApiGatewayEndpoint")
        if not api_host or not oa_host:
            raise LinkVisualError(
                f"Aliyun region lookup failed: {region.get('code')} {_message(region)}"
            )

        oa = await self._async_oa_login(oa_host, auth_code)
        oa_data = oa.get("data") or {}
        sid = ((oa_data.get("data") or {}).get("loginSuccessResult") or {}).get("sid")
        if not sid:
            raise LinkVisualError(
                f"Aliyun account login failed: {oa_data.get('code')} {oa_data.get('message')}"
            )

        sess = await self._async_iot_request(
            api_host,
            CREATE_SESSION_PATH,
            "1.0.4",
            {
                "request": {
                    "authCode": sid,
                    "appKey": ALIYUN_APP_KEY,
                    "accountType": "OA_SESSION",
                }
            },
        )
        sess_data = sess.get("data") or {}
        iot_token = sess_data.get("iotToken")
        if sess.get("code") != 200 or not iot_token:
            raise LinkVisualError(
                f"Aliyun IoT session failed: {sess.get('code')} {_message(sess)}"
            )
        lifetime = _to_int(sess_data.get("iotTokenExpire")) or DEFAULT_TOKEN_LIFETIME
        _LOGGER.debug("LinkVisual session created on %s, valid for %ss", api_host, lifetime)
        return _IoTSession(api_host, iot_token, time.time() + lifetime)

    async def _async_oa_login(self, host: str, auth_code: str) -> dict:
        request = {
            "authCode": auth_code,
            "oauthPlateform": OAUTH_PLATFORM_CATLINK,
            "oauthAppKey": ALIYUN_APP_KEY,
            "riskControlInfo": RISK_CONTROL_INFO,
        }
        form = {"loginByOauthRequest": json.dumps(request, separators=(",", ":"))}
        return await self._async_gateway_post(
            host, OA_LOGIN_PATH, urlencode(form).encode(), CONTENT_TYPE_FORM, form
        )

    async def _async_iot_request(
        self,
        host: str,
        path: str,
        api_ver: str,
        params: dict,
        iot_token: str | None = None,
    ) -> dict:
        request = {"apiVer": api_ver, "language": "en-US"}
        if iot_token:
            request["iotToken"] = iot_token
        payload = {
            "id": str(uuid.uuid4()),
            "version": "1.0",
            "request": request,
            "params": params,
        }
        return await self._async_gateway_post(
            host, path, json.dumps(payload).encode(), CONTENT_TYPE_STREAM
        )

    async def _async_gateway_post(
        self,
        host: str,
        path: str,
        body: bytes,
        content_type: str,
        form: dict[str, str] | None = None,
    ) -> dict:
        headers = build_gateway_headers(path, body, content_type, form)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                rsp = await self._account.http.post(
                    f"https://{host}{path}", data=body, headers=headers
                )
                if rsp.status != 200:
                    rsp.release()
                    raise LinkVisualError(
                        f"{path} returned HTTP {rsp.status}: "
                        f"{rsp.headers.get('x-ca-error-message')}"
                    )
                return await rsp.json(content_type=None) or {}
        except (ClientError, TimeoutError, ValueError) as exc:
            raise LinkVisualError(f"{path} request failed: {exc}") from exc


def _message(rsp: dict) -> str | None:
    return rsp.get("localizedMsg") or rsp.get("message")


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
