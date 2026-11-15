"""Tests for the LinkVisual (Aliyun camera streaming) client."""

import base64
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from custom_components.catlink.modules import linkvisual
from custom_components.catlink.modules.linkvisual import (
    API_AUTH_CODE,
    CREATE_SESSION_PATH,
    OA_LOGIN_PATH,
    PROPERTIES_GET_PATH,
    PROPERTIES_SET_PATH,
    PICTURE_QUERY_PATH,
    SERVICE_INVOKE_PATH,
    STATUS_GET_PATH,
    REGION_HOST,
    REGION_PATH,
    STREAM_QUERY_PATH,
    LinkVisualClient,
    LinkVisualError,
    build_gateway_headers,
)
import pytest

API_HOST = "us-east-1.api-iot.aliyuncs.com"
OA_HOST = "living-account.us-east-1.aliyuncs.com"
RELAY_URL = "rtmp://203.0.113.5:8000/live?token=t&session=s"


def _sign(secret: str, string_to_sign: str) -> str:
    digest = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


class TestBuildGatewayHeaders:
    """Tests for build_gateway_headers."""

    def test_body_request_signs_content_md5(self) -> None:
        """Body requests sign Content-MD5 and the bare path."""
        body = b'{"a":1}'
        headers = build_gateway_headers(
            "/x/y",
            body,
            "application/octet-stream; charset=utf-8",
            app_key="key",
            app_secret="secret",
            timestamp_ms=1700000000000,
            nonce="n-1",
        )
        md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
        expected = (
            "POST\n"
            "application/json; charset=utf-8\n"
            f"{md5}\n"
            "application/octet-stream; charset=utf-8\n"
            "Tue, 14 Nov 2023 22:13:20 GMT\n"
            "x-ca-key:key\n"
            "x-ca-nonce:n-1\n"
            "x-ca-signature-method:HmacSHA1\n"
            "x-ca-timestamp:1700000000000\n"
            "x-ca-version:1\n"
            "/x/y"
        )
        assert headers["content-md5"] == md5
        assert headers["x-ca-signature"] == _sign("secret", expected)
        assert headers["x-ca-signature-headers"] == (
            "x-ca-key,x-ca-nonce,x-ca-signature-method,x-ca-timestamp,x-ca-version"
        )

    def test_form_request_signs_sorted_form_params(self) -> None:
        """Form requests sign sorted form params and send no Content-MD5."""
        headers = build_gateway_headers(
            "/api/prd/x.json",
            b"ignored",
            "application/x-www-form-urlencoded; charset=utf-8",
            {"b": "2", "a": "1"},
            app_key="key",
            app_secret="secret",
            timestamp_ms=1700000000000,
            nonce="n-1",
        )
        expected = (
            "POST\n"
            "application/json; charset=utf-8\n"
            "\n"
            "application/x-www-form-urlencoded; charset=utf-8\n"
            "Tue, 14 Nov 2023 22:13:20 GMT\n"
            "x-ca-key:key\n"
            "x-ca-nonce:n-1\n"
            "x-ca-signature-method:HmacSHA1\n"
            "x-ca-timestamp:1700000000000\n"
            "x-ca-version:1\n"
            "/api/prd/x.json?a=1&b=2"
        )
        assert "content-md5" not in headers
        assert headers["x-ca-signature"] == _sign("secret", expected)


class FakeAliyun:
    """Canned Aliyun responses keyed by path, recording each call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.stream_responses: list[dict] = []
        self.property_responses: list[dict] = []
        self.region_responses: list[dict] = []
        self.status_responses: list[dict] = []
        self.service_responses: list[dict] = []
        self.picture_responses: list[dict] = []

    async def post(self, client, host, path, body, content_type, form=None):
        import json

        payload = json.loads(body) if not form else {}
        self.calls.append((host, path, payload))
        if path == REGION_PATH:
            if self.region_responses:
                return self.region_responses.pop(0)
            return {
                "code": 200,
                "data": {"apiGatewayEndpoint": API_HOST, "oaApiGatewayEndpoint": OA_HOST},
            }
        if path == OA_LOGIN_PATH:
            return {"data": {"code": 1, "data": {"loginSuccessResult": {"sid": "sid-1"}}}}
        if path == CREATE_SESSION_PATH:
            return {"code": 200, "data": {"iotToken": "iot-1", "iotTokenExpire": 72000}}
        if path == STREAM_QUERY_PATH:
            if self.stream_responses:
                return self.stream_responses.pop(0)
            return {"code": 200, "data": {"relayUrl": RELAY_URL, "relayDecryptKey": {}}}
        if path in (PROPERTIES_GET_PATH, PROPERTIES_SET_PATH):
            if self.property_responses:
                return self.property_responses.pop(0)
            return {"code": 200, "data": {}}
        if path == PICTURE_QUERY_PATH:
            return self.picture_responses.pop(0)
        if path == SERVICE_INVOKE_PATH:
            if self.service_responses:
                return self.service_responses.pop(0)
            return {"code": 200, "data": {}}
        if path == STATUS_GET_PATH:
            if self.status_responses:
                return self.status_responses.pop(0)
            return {"code": 200, "data": {"status": 1, "time": 1791362635789}}
        raise AssertionError(path)

    def paths(self) -> list[str]:
        return [path for _, path, _ in self.calls]


@pytest.fixture
def account():
    """Account stub returning a CatLink auth code."""
    acc = MagicMock()
    acc.request = AsyncMock(return_value={"returnCode": 0, "data": "auth-code-1"})
    return acc


@pytest.fixture
def aliyun(monkeypatch):
    """Patch the gateway transport with canned responses."""
    fake = FakeAliyun()

    async def _post(self, host, path, body, content_type, form=None):
        return await fake.post(self, host, path, body, content_type, form)

    monkeypatch.setattr(LinkVisualClient, "_async_gateway_post", _post)
    monkeypatch.setattr(linkvisual, "REGION_RETRY_DELAY", 0)
    return fake


class TestLinkVisualClient:
    """Tests for LinkVisualClient."""

    async def test_full_login_then_stream_query(self, account, aliyun) -> None:
        """The first call logs in through every step and returns the relay URL."""
        client = LinkVisualClient(account)

        url = await client.async_get_live_url("iot-device-1")

        assert url == RELAY_URL
        account.request.assert_awaited_once_with(API_AUTH_CODE, method="POST")
        assert aliyun.paths() == [
            REGION_PATH,
            OA_LOGIN_PATH,
            CREATE_SESSION_PATH,
            STREAM_QUERY_PATH,
        ]
        hosts = [host for host, _, _ in aliyun.calls]
        assert hosts == [REGION_HOST, OA_HOST, API_HOST, API_HOST]
        _, _, session_req = aliyun.calls[2]
        assert session_req["params"]["request"]["authCode"] == "sid-1"
        _, _, stream_req = aliyun.calls[3]
        assert stream_req["request"]["iotToken"] == "iot-1"
        assert stream_req["request"]["apiVer"] == "2.2.0"
        assert stream_req["params"] == {
            "iotId": "iot-device-1",
            "streamType": 0,
            "encryptType": 0,
        }

    async def test_session_is_reused(self, account, aliyun) -> None:
        """A valid iotToken is reused instead of logging in again."""
        client = LinkVisualClient(account)

        await client.async_get_live_url("iot-device-1")
        await client.async_get_live_url("iot-device-1")

        assert account.request.await_count == 1
        assert aliyun.paths().count(STREAM_QUERY_PATH) == 2

    async def test_expired_session_logs_in_again(self, account, aliyun) -> None:
        """An expired iotToken triggers a fresh login."""
        client = LinkVisualClient(account)
        await client.async_get_live_url("iot-device-1")
        client._session.expires_at = time.time()

        await client.async_get_live_url("iot-device-1")

        assert account.request.await_count == 2

    async def test_rejected_token_logs_in_again_once(self, account, aliyun) -> None:
        """A rejected stream query re-logs in and retries once."""
        aliyun.stream_responses = [{"code": 401, "message": "iotToken invalid"}]
        client = LinkVisualClient(account)

        url = await client.async_get_live_url("iot-device-1")

        assert url == RELAY_URL
        assert account.request.await_count == 2
        assert aliyun.paths().count(STREAM_QUERY_PATH) == 2

    async def test_missing_relay_url_raises(self, account, aliyun) -> None:
        """A stream query without a relay URL raises LinkVisualError."""
        aliyun.stream_responses = [
            {"code": 9201, "message": "device offline"},
            {"code": 9201, "message": "device offline"},
        ]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="9201 device offline"):
            await client.async_get_live_url("iot-device-1")

    async def test_region_lookup_retried_once(self, account, aliyun) -> None:
        """A transient region lookup error is retried once with the same auth code."""
        aliyun.region_responses = [{"code": 500, "message": "Server error"}]
        client = LinkVisualClient(account)

        url = await client.async_get_live_url("iot-device-1")

        assert url == RELAY_URL
        assert aliyun.paths().count(REGION_PATH) == 2
        assert account.request.await_count == 1

    async def test_region_lookup_failing_twice_raises(self, account, aliyun) -> None:
        """A region lookup that fails twice raises LinkVisualError."""
        aliyun.region_responses = [
            {"code": 500, "message": "Server error"},
            {"code": 500, "message": "Server error"},
            {"code": 500, "message": "Server error"},
            {"code": 500, "message": "Server error"},
        ]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="region lookup failed: 500"):
            await client.async_get_live_url("iot-device-1")

    async def test_missing_auth_code_raises(self, account, aliyun) -> None:
        """A failed CatLink auth code request raises LinkVisualError."""
        account.request = AsyncMock(return_value={"returnCode": 1002, "msg": "bad token"})
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="1002 bad token"):
            await client.async_get_live_url("iot-device-1")
        assert aliyun.calls == []


class TestThingProperties:
    """Tests for reading and writing thing properties."""

    async def test_get_properties_flattens_values(self, account, aliyun) -> None:
        """Property values are unwrapped from their {value, time} records."""
        aliyun.property_responses = [
            {
                "code": 200,
                "data": {
                    "CatLitterBalance": {"value": 75, "time": 1791362635789},
                    "RunStatus": {"value": "runStatus=0&biz=1", "time": 1791362635789},
                },
            }
        ]
        client = LinkVisualClient(account)

        props = await client.async_get_properties("iot-device-1")

        assert props == {"CatLitterBalance": 75, "RunStatus": "runStatus=0&biz=1"}
        _, path, req = aliyun.calls[-1]
        assert path == PROPERTIES_GET_PATH
        assert req["request"]["apiVer"] == "1.0.0"
        assert req["request"]["iotToken"] == "iot-1"
        assert req["params"] == {"iotId": "iot-device-1"}

    async def test_get_properties_shares_session_with_stream(self, account, aliyun) -> None:
        """Property reads reuse the session created for streaming."""
        client = LinkVisualClient(account)

        await client.async_get_live_url("iot-device-1")
        await client.async_get_properties("iot-device-1")

        assert account.request.await_count == 1

    async def test_get_properties_rejected_token_logs_in_again_once(
        self, account, aliyun
    ) -> None:
        """A rejected property read re-logs in and retries once."""
        aliyun.property_responses = [
            {"code": 401, "message": "iotToken invalid"},
            {"code": 200, "data": {"ChildLock": {"value": 0}}},
        ]
        client = LinkVisualClient(account)

        props = await client.async_get_properties("iot-device-1")

        assert props == {"ChildLock": 0}
        assert account.request.await_count == 2

    async def test_get_properties_failure_raises(self, account, aliyun) -> None:
        """A property read that keeps failing raises LinkVisualError."""
        aliyun.property_responses = [
            {"code": 9201, "message": "device offline"},
            {"code": 9201, "message": "device offline"},
        ]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="9201 device offline"):
            await client.async_get_properties("iot-device-1")

    async def test_set_properties_sends_items(self, account, aliyun) -> None:
        """Property writes send the items to the set endpoint."""
        client = LinkVisualClient(account)

        await client.async_set_properties("iot-device-1", {"PromptSoundSwitch": 0})

        _, path, req = aliyun.calls[-1]
        assert path == PROPERTIES_SET_PATH
        assert req["request"]["apiVer"] == "1.0.0"
        assert req["params"] == {
            "iotId": "iot-device-1",
            "items": {"PromptSoundSwitch": 0},
        }

    async def test_set_properties_failure_raises(self, account, aliyun) -> None:
        """A rejected property write raises LinkVisualError."""
        aliyun.property_responses = [
            {"code": 6205, "message": "property not writable"},
            {"code": 6205, "message": "property not writable"},
        ]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="6205 property not writable"):
            await client.async_set_properties("iot-device-1", {"Foo": 1})


class TestInvokeService:
    """Tests for thing service calls (Reboot)."""

    async def test_invoke(self, account, aliyun) -> None:
        """A service call sends the identifier and empty args."""
        client = LinkVisualClient(account)

        await client.async_invoke_service("iot-device-1", "Reboot")

        _, path, req = aliyun.calls[-1]
        assert path == SERVICE_INVOKE_PATH
        assert req["request"]["apiVer"] == "1.0.5"
        assert req["params"] == {"iotId": "iot-device-1", "identifier": "Reboot", "args": {}}

    async def test_rejected_token_retries_once(self, account, aliyun) -> None:
        """A rejected token logs in again and calls once more."""
        aliyun.service_responses = [{"code": 401, "message": "iotToken invalid"}]
        client = LinkVisualClient(account)

        await client.async_invoke_service("iot-device-1", "Reboot")

        assert aliyun.paths().count(SERVICE_INVOKE_PATH) == 2

    async def test_other_failure_not_retried(self, account, aliyun) -> None:
        """Other failures are not retried (the service may have run) and raise."""
        aliyun.service_responses = [{"code": 9201, "message": "device offline"}]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="9201 device offline"):
            await client.async_invoke_service("iot-device-1", "Reboot")
        assert aliyun.paths().count(SERVICE_INVOKE_PATH) == 1


class TestPictures:
    """Tests for looking up uploaded pictures."""

    async def test_query(self, account, aliyun) -> None:
        """querybyids 2.1.0 with the ids; the result is keyed by pictureId."""
        aliyun.picture_responses = [{"code": 200, "data": {"pictureList": [
            {"pictureId": "p1", "thumbUrl": "t", "pictureUrl": "u"}, {"x": 1}]}}]
        client = LinkVisualClient(account)

        pictures = await client.async_query_pictures("iot-device-1", ["p1"])

        assert pictures == {"p1": {"pictureId": "p1", "thumbUrl": "t", "pictureUrl": "u"}}
        _, path, req = aliyun.calls[-1]
        assert path == PICTURE_QUERY_PATH
        assert req["request"]["apiVer"] == "2.1.0"
        assert req["params"] == {"iotId": "iot-device-1", "pictureIdList": ["p1"], "type": 0}

    async def test_query_failure(self, account, aliyun) -> None:
        """A rejected query raises after the one re-login retry."""
        aliyun.picture_responses = [{"code": 460, "message": "no"}, {"code": 460, "message": "no"}]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="460"):
            await client.async_query_pictures("iot-device-1", ["p1"])


class TestThingStatus:
    """Tests for the device online check."""

    async def test_online(self, account, aliyun) -> None:
        """Status 1 means online."""
        client = LinkVisualClient(account)

        assert await client.async_is_online("iot-device-1") is True
        _, path, req = aliyun.calls[-1]
        assert path == STATUS_GET_PATH
        assert req["request"]["apiVer"] == "1.0.5"
        assert req["params"] == {"iotId": "iot-device-1"}

    @pytest.mark.parametrize("status", [0, 3, 8, "3", None])
    async def test_not_online(self, account, aliyun, status) -> None:
        """Any other status (inactive, offline, disabled, missing) is not online."""
        aliyun.status_responses = [{"code": 200, "data": {"status": status}}]
        client = LinkVisualClient(account)

        assert await client.async_is_online("iot-device-1") is False

    async def test_failure_raises(self, account, aliyun) -> None:
        """A status query that keeps failing raises LinkVisualError."""
        aliyun.status_responses = [
            {"code": 500, "message": "Server error"},
            {"code": 500, "message": "Server error"},
        ]
        client = LinkVisualClient(account)

        with pytest.raises(LinkVisualError, match="Status query failed: 500"):
            await client.async_is_online("iot-device-1")


class TestGatewayPost:
    """Tests for the HTTP layer of LinkVisualClient."""

    def _client(self, response=None, side_effect=None) -> LinkVisualClient:
        account = MagicMock()
        account.http.post = AsyncMock(return_value=response, side_effect=side_effect)
        return LinkVisualClient(account)

    async def test_posts_signed_request(self) -> None:
        """Requests go to https://host/path with signed headers."""
        response = MagicMock(status=200)
        response.json = AsyncMock(return_value={"code": 200})
        client = self._client(response)

        result = await client._async_gateway_post(
            "h.example", "/p", b"{}", "application/octet-stream; charset=utf-8"
        )

        assert result == {"code": 200}
        args, kwargs = client._account.http.post.call_args
        assert args[0] == "https://h.example/p"
        assert kwargs["data"] == b"{}"
        assert "x-ca-signature" in kwargs["headers"]

    async def test_http_error_raises(self) -> None:
        """Non-200 gateway responses raise LinkVisualError."""
        response = MagicMock(status=403, headers={"x-ca-error-message": "Invalid Signature"})
        client = self._client(response)

        with pytest.raises(LinkVisualError, match="HTTP 403: Invalid Signature"):
            await client._async_gateway_post("h", "/p", b"", "text/plain")

    async def test_client_error_raises(self) -> None:
        """Connection errors raise LinkVisualError."""
        client = self._client(side_effect=ClientError("boom"))

        with pytest.raises(LinkVisualError, match="boom"):
            await client._async_gateway_post("h", "/p", b"", "text/plain")
