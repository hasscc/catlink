"""Tests for CatLink Account module."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from aiohttp import ContentTypeError

from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_TOKEN
from homeassistant.exceptions import HomeAssistantError

from custom_components.catlink.const import (
    CONF_API_BASE,
    CONF_LANGUAGE,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_API_BASE,
    DOMAIN,
    SCAN_INTERVAL,
)
from custom_components.catlink.modules.account import Account


@pytest.fixture
def account_config():
    """Sample account config."""
    return {
        CONF_PHONE_IAC: "86",
        CONF_PHONE: "13812345678",
        CONF_PASSWORD: "testpass",
        CONF_TOKEN: "existing-token",
    }


@pytest.fixture
def mock_http_session():
    """Mock aiohttp client session."""
    with patch(
        "custom_components.catlink.modules.account.aiohttp_client.async_create_clientsession"
    ) as mock_create:
        session = MagicMock()
        mock_create.return_value = session
        yield session


@pytest.fixture
def account(hass, account_config, mock_http_session):
    """Create Account instance with mocked HTTP."""
    return Account(hass, account_config)


class TestAccountProperties:
    """Tests for Account properties."""

    def test_phone(self, account) -> None:
        """Test phone property."""
        assert account.phone == "13812345678"

    def test_uid(self, account) -> None:
        """Test uid property."""
        assert account.uid == "86-13812345678"

    def test_token(self, account) -> None:
        """Test token property."""
        assert account.token == "existing-token"

    def test_token_empty_when_missing(self, hass, mock_http_session) -> None:
        """Test token returns empty string when not in config."""
        config = {CONF_PHONE_IAC: "86", CONF_PHONE: "13812345678", CONF_PASSWORD: "pwd"}
        acc = Account(hass, config)
        assert acc.token == ""


class TestAccountGetConfig:
    """Tests for Account get_config."""

    def test_get_config_from_account(self, account) -> None:
        """Test get_config returns value from account config."""
        assert account.get_config(CONF_PHONE) == "13812345678"

    def test_get_config_from_global(self, hass, mock_http_session) -> None:
        """Test get_config falls back to global config."""
        hass.data[DOMAIN] = {"config": {CONF_LANGUAGE: "en_US"}}
        config = {CONF_PHONE_IAC: "86", CONF_PHONE: "13812345678", CONF_PASSWORD: "pwd"}
        acc = Account(hass, config)
        assert acc.get_config(CONF_LANGUAGE) == "en_US"

    def test_get_config_default(self, account) -> None:
        """Test get_config returns default when key missing."""
        assert account.get_config("missing_key", "default") == "default"


class TestAccountUpdateInterval:
    """Tests for Account update_interval."""

    def test_update_interval_from_config(self, hass, mock_http_session) -> None:
        """Test update_interval from account config."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "pwd",
            CONF_UPDATE_INTERVAL: 120,
        }
        acc = Account(hass, config)
        assert acc.update_interval == timedelta(seconds=120)

    def test_update_interval_from_global(self, hass, mock_http_session) -> None:
        """Test update_interval falls back to global config."""
        hass.data[DOMAIN] = {"config": {CONF_UPDATE_INTERVAL: 90}}
        config = {CONF_PHONE_IAC: "86", CONF_PHONE: "13812345678", CONF_PASSWORD: "pwd"}
        acc = Account(hass, config)
        assert acc.update_interval == timedelta(seconds=90)

    def test_update_interval_default(self, account) -> None:
        """Test update_interval defaults to SCAN_INTERVAL."""
        assert account.update_interval == SCAN_INTERVAL


class TestAccountApiUrl:
    """Tests for Account api_url."""

    def test_api_url_relative_path(self, account) -> None:
        """Test api_url builds URL from base and path."""
        url = account.api_url("token/device/list")
        assert url == f"{DEFAULT_API_BASE.rstrip('/')}/token/device/list"

    def test_api_url_absolute_https(self, account) -> None:
        """Test api_url returns full URL as-is for https."""
        url = account.api_url("https://other.api/endpoint")
        assert url == "https://other.api/endpoint"

    def test_api_url_absolute_http(self, account) -> None:
        """Test api_url returns full URL as-is for http."""
        url = account.api_url("http://other.api/endpoint")
        assert url == "http://other.api/endpoint"

    def test_api_url_custom_base(self, hass, mock_http_session) -> None:
        """Test api_url uses custom API base from config."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "pwd",
            CONF_API_BASE: "https://custom.api/v1/",
        }
        acc = Account(hass, config)
        url = acc.api_url("login")
        assert url == "https://custom.api/v1/login"


class TestAccountParamsSign:
    """Tests for Account.params_sign static method."""

    def test_params_sign_deterministic(self) -> None:
        """Test params_sign produces consistent output."""
        pms = {"a": "1", "b": "2"}
        sig1 = Account.params_sign(pms)
        sig2 = Account.params_sign(pms)
        assert sig1 == sig2
        assert len(sig1) == 32
        assert sig1.isupper()

    def test_params_sign_different_inputs_different_output(self) -> None:
        """Test params_sign differs for different params."""
        sig1 = Account.params_sign({"a": "1"})
        sig2 = Account.params_sign({"a": "2"})
        assert sig1 != sig2


class TestAccountEncryptPassword:
    """Tests for Account.encrypt_password static method."""

    def test_encrypt_password_returns_base64(self) -> None:
        """Test encrypt_password returns base64 string."""
        result = Account.encrypt_password("short")
        assert isinstance(result, str)
        assert len(result) > 0
        try:
            import base64

            base64.b64decode(result)
        except Exception:
            pytest.fail("Result should be valid base64")

    def test_encrypt_password_same_length_for_same_input(self) -> None:
        """Test encrypt_password produces consistent output length for same input."""
        r1 = Account.encrypt_password("test123")
        r2 = Account.encrypt_password("test123")
        assert len(r1) == len(r2)
        assert len(r1) > 50


class TestAccountPassword:
    """Tests for Account password property (encryption of short passwords)."""

    def test_short_password_gets_encrypted(self, hass, mock_http_session) -> None:
        """Test password <= 16 chars is encrypted."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "short",
        }
        acc = Account(hass, config)
        pwd = acc.password
        assert pwd != "short"
        assert len(pwd) > 16

    def test_long_password_unchanged(self, hass, mock_http_session) -> None:
        """Test password > 16 chars is returned as-is (already encrypted)."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "a" * 20,
        }
        acc = Account(hass, config)
        assert acc.password == "a" * 20


class TestAccountRequest:
    """Tests for Account request method."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_request_get_returns_json(self, account) -> None:
        """Test request GET returns parsed JSON."""
        request_kwargs = {}

        async def mock_request(method, url, **kwargs):
            request_kwargs.clear()
            request_kwargs.update(kwargs)
            resp = MagicMock()
            resp.json = AsyncMock(return_value={"returnCode": 0, "data": {}})
            return resp

        account.http.request = mock_request

        result = await account.request("token/device/list", {"type": "NONE"})

        assert result == {"returnCode": 0, "data": {}}
        params = request_kwargs.get("params") or {}
        assert "noncestr" in params

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_request_includes_token_in_params(self, account) -> None:
        """Test request includes token in params when present."""
        call_params = {}

        async def mock_request(method, url, **kwargs):
            call_params.update(kwargs)
            resp = MagicMock()
            resp.json = AsyncMock(return_value={})
            return resp

        account.http.request = mock_request
        await account.request("api", {"key": "val"})

        params = call_params.get("params") or call_params.get("data") or {}
        assert CONF_TOKEN in params
        assert params[CONF_TOKEN] == "existing-token"


class TestAccountAsyncLogin:
    """Tests for Account async_login."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_login_success(self, account) -> None:
        """Test async_login succeeds with valid token in response."""
        with patch.object(account, "request", new_callable=AsyncMock) as mock_request:
            with patch.object(
                account, "async_check_auth", new_callable=AsyncMock
            ) as mock_check:
                mock_request.return_value = {
                    "data": {"token": "new-token"},
                    "returnCode": 0,
                }
                result = await account.async_login()

                assert result is True
                assert account.token == "new-token"
                mock_check.assert_called_once_with(True)

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_login_fails_no_token(self, account) -> None:
        """Test async_login returns False when no token in response."""
        with patch.object(account, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {}, "returnCode": 0}
            result = await account.async_login()

            assert result is False
            assert account.token == ""


class TestAccountGetDevices:
    """Tests for Account get_devices."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_get_devices_returns_list(self, account) -> None:
        """Test get_devices returns device list from API."""
        with patch.object(account, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "returnCode": 0,
                "data": {
                    CONF_DEVICES: [
                        {"id": "dev1", "deviceName": "Litter Box"},
                    ]
                },
            }
            devices = await account.get_devices()

            assert devices == [{"id": "dev1", "deviceName": "Litter Box"}]
            mock_request.assert_awaited_once_with(
                "token/device/union/sortedListV2", {"type": "NONE"}, _retried=True
            )

    @pytest.mark.parametrize("wrapper", ["direct", "devices", "records"])
    async def test_list_formats_preserve_all_device_types(
        self, account, wrapper
    ) -> None:
        """A complete V2 list takes precedence over partial legacy lists."""
        expected = [
            {"id": "scooper", "deviceType": "SCOOPER"},
            {"id": "feeder", "deviceType": "FEEDER_PRO"},
            {"id": "future", "deviceType": "FUTURE_DEVICE"},
        ]
        data = expected
        if wrapper == "devices":
            data = {"devices": expected}
        elif wrapper == "records":
            data = {"devices": {"records": expected}}
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = {"returnCode": 0, "data": data}
            assert await account.get_devices() == expected
            request.assert_awaited_once()

    @pytest.mark.parametrize(
        "v2_response",
        [
            {"returnCode": 0, "data": []},
            {"returnCode": 404, "data": []},
            {"returnCode": 0, "data": None},
            {"returnCode": 0, "data": {"devices": "invalid"}},
            {},
        ],
    )
    async def test_legacy_fallback(self, account, v2_response) -> None:
        """Old accounts still discover devices when V2 is empty or unavailable."""
        old_devices = [{"id": "old-feeder", "deviceType": "FEEDER", "online": True}]
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.side_effect = [
                v2_response,
                {"returnCode": 0, "data": {"devices": old_devices}},
            ]
            assert await account.get_devices() == old_devices
            assert request.await_args_list == [
                call(
                    "token/device/union/sortedListV2", {"type": "NONE"}, _retried=True
                ),
                call("token/device/union/list/sorted", {"type": "NONE"}, _retried=True),
            ]

    async def test_final_legacy_endpoint(self, account) -> None:
        """The device/list endpoint remains available as a last fallback."""
        expected = [{"id": "old-scooper", "deviceType": "SCOOPER"}]
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.side_effect = [
                {"returnCode": 0, "data": []},
                {"returnCode": 0, "data": {"devices": []}},
                {"returnCode": 0, "data": {"devices": {"records": expected}}},
            ]
            assert await account.get_devices() == expected
            assert request.await_args_list[-1] == call(
                "token/device/list", {"type": "NONE"}, _retried=True
            )

    @pytest.mark.parametrize(
        "error",
        [
            ContentTypeError(MagicMock(), (), message="Expected JSON"),
            ValueError("Invalid JSON"),
        ],
    )
    async def test_non_json_v2_response_falls_back(self, account, error) -> None:
        """Servers without V2 may return HTML or invalid JSON for that path."""
        unsupported = MagicMock()
        unsupported.json = AsyncMock(side_effect=error)
        legacy = MagicMock()
        expected = [{"id": "old-feeder", "deviceType": "FEEDER"}]
        legacy.json = AsyncMock(
            return_value={"returnCode": 0, "data": {"devices": expected}}
        )
        account.http.request = AsyncMock(side_effect=[unsupported, legacy])
        assert await account.get_devices() == expected
        assert account.http.request.await_count == 2

    async def test_non_json_auth_retry_falls_back(self, account) -> None:
        """A failed response after token renewal still allows the legacy path."""
        expected = [{"id": "old-scooper", "deviceType": "SCOOPER"}]
        with (
            patch.object(account, "request", new_callable=AsyncMock) as request,
            patch.object(account, "async_login", new_callable=AsyncMock) as login,
        ):
            request.side_effect = [
                {"returnCode": 1002},
                ValueError("Invalid JSON"),
                {"returnCode": 0, "data": {"devices": expected}},
            ]
            login.return_value = True
            assert await account.get_devices() == expected
            login.assert_awaited_once()

    async def test_all_non_json_responses_fail_discovery(self, account) -> None:
        """Broken responses never become a successful empty device list."""
        response = MagicMock()
        response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        account.http.request = AsyncMock(return_value=response)
        with pytest.raises(HomeAssistantError, match="Unable to retrieve"):
            await account.get_devices()
        assert account.http.request.await_count == 3

    @pytest.mark.parametrize("online", [True, False])
    async def test_boolean_online_status(self, account, online) -> None:
        """V2 booleans override a conflicting legacy flag without changing input."""
        item = {"id": "feeder", "onlineStatus": online, "online": not online}
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = {"returnCode": 0, "data": [item]}
            devices = await account.get_devices()
        assert devices[0]["online"] is online
        assert devices[0]["onlineStatus"] is online
        assert item["online"] is not online

    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            ({"onlineStatus": "ONLINE"}, True),
            ({"onlineStatus": "OFFLINE"}, False),
            ({"onlineStatus": None, "online": False}, False),
            ({"online": True}, True),
            ({"online": "ONLINE"}, True),
            ({"online": "OFFLINE"}, False),
        ],
    )
    async def test_legacy_online_status(self, account, fields, expected) -> None:
        """Legacy availability values survive device discovery."""
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = {"returnCode": 0, "data": [{"id": "old", **fields}]}
            devices = await account.get_devices()
        assert devices[0]["online"] is expected

    async def test_invalid_list_entries_are_skipped(self, account) -> None:
        """Null entries cannot prevent the remaining devices being discovered."""
        expected = {"id": "scooper", "deviceType": "SCOOPER"}
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = {
                "returnCode": 0, "data": [None, "invalid", expected]
            }
            assert await account.get_devices() == [expected]

    async def test_all_empty_lists(self, account) -> None:
        """An account with no devices returns an empty list."""
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = {"returnCode": 0, "data": []}
            assert await account.get_devices() == []
            assert request.await_count == 3

    @pytest.mark.parametrize(
        "response",
        [
            {},
            None,
            [],
            {"returnCode": 503, "data": []},
            {"returnCode": 0, "data": None},
            {"returnCode": 0, "data": [None]},
        ],
    )
    async def test_failed_discovery_is_not_empty_success(
        self, account, response
    ) -> None:
        """Protocol and API failures must not look like an account without devices."""
        with patch.object(account, "request", new_callable=AsyncMock) as request:
            request.return_value = response
            with pytest.raises(HomeAssistantError, match="Unable to retrieve"):
                await account.get_devices()

    async def test_token_expiry_retries_same_endpoint_once(self, account) -> None:
        """An expired token gets one retry before discovery continues."""
        expected = [{"id": "scooper"}]
        with (
            patch.object(account, "request", new_callable=AsyncMock) as request,
            patch.object(account, "async_login", new_callable=AsyncMock) as login,
        ):
            request.side_effect = [
                {"returnCode": 1002},
                {"returnCode": 0, "data": expected},
            ]
            login.return_value = True
            assert await account.get_devices() == expected
            login.assert_awaited_once()
            assert request.await_args_list[0] == request.await_args_list[1]

    @pytest.mark.parametrize("login_success", [True, False])
    async def test_persistent_token_expiry_stops(self, account, login_success) -> None:
        """Do not retry authentication indefinitely or query every endpoint."""
        with (
            patch.object(account, "request", new_callable=AsyncMock) as request,
            patch.object(account, "async_login", new_callable=AsyncMock) as login,
        ):
            request.return_value = {"returnCode": 1002}
            login.return_value = login_success
            with pytest.raises(HomeAssistantError, match="authentication failed"):
                await account.get_devices()
            login.assert_awaited_once()
            assert request.await_count == (2 if login_success else 1)

    async def test_token_refresh_is_shared_by_fallbacks(self, account) -> None:
        """A second endpoint cannot cause a second authentication refresh."""
        with (
            patch.object(account, "request", new_callable=AsyncMock) as request,
            patch.object(account, "async_login", new_callable=AsyncMock) as login,
        ):
            request.side_effect = [
                {"returnCode": 1002},
                {"returnCode": 0, "data": []},
                {"returnCode": 1002},
            ]
            login.return_value = True
            with pytest.raises(HomeAssistantError, match="authentication failed"):
                await account.get_devices()
            login.assert_awaited_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_get_devices_login_when_no_token(
        self, hass, mock_http_session
    ) -> None:
        """Test get_devices calls async_login when token is empty."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "short",
        }
        acc = Account(hass, config)
        acc._config[CONF_TOKEN] = None

        with patch.object(acc, "async_login", new_callable=AsyncMock) as mock_login:
            mock_login.return_value = False
            devices = await acc.get_devices()

            assert devices == []
            mock_login.assert_called_once()


class TestAccountGetCats:
    """Tests for Account get_cats."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_get_cats_returns_list(self, account) -> None:
        """Test get_cats returns cats list from API."""
        with patch.object(account, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "returnCode": 0,
                "data": {"cats": [{"id": "cat1", "petName": "Zulu"}]},
            }
            cats = await account.get_cats("Europe/Belgrade")

            assert cats == [{"id": "cat1", "petName": "Zulu"}]
            mock_request.assert_called_once()

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_get_cats_login_when_no_token(
        self, hass, mock_http_session
    ) -> None:
        """Test get_cats calls async_login when token is empty."""
        config = {
            CONF_PHONE_IAC: "86",
            CONF_PHONE: "13812345678",
            CONF_PASSWORD: "short",
        }
        acc = Account(hass, config)
        acc._config[CONF_TOKEN] = None

        with patch.object(acc, "async_login", new_callable=AsyncMock) as mock_login:
            mock_login.return_value = False
            cats = await acc.get_cats("Europe/Belgrade")

            assert cats == []
            mock_login.assert_called_once()


class TestAccountGetCatSummarySimple:
    """Tests for Account get_cat_summary_simple."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_get_cat_summary_simple_returns_data(self, account) -> None:
        """Test get_cat_summary_simple returns summary data."""
        with patch.object(account, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "returnCode": 0,
                "data": {"statusDescription": "Good"},
            }
            summary = await account.get_cat_summary_simple(
                "169004", "2026-02-06", "Europe/Belgrade"
            )

            assert summary == {"statusDescription": "Good"}
            mock_request.assert_called_once()

class TestAccountAsyncCheckAuth:
    """Tests for Account async_check_auth."""

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_check_auth_save_stores_token(self, account) -> None:
        """Test async_check_auth with save=True stores token to Store."""
        with patch(
            "custom_components.catlink.modules.account.Store"
        ) as mock_store_cls:
            mock_store = MagicMock()
            mock_store.async_load = AsyncMock(return_value={})
            mock_store.async_save = AsyncMock()
            mock_store_cls.return_value = mock_store

            result = await account.async_check_auth(save=True)

            assert result[CONF_PHONE] == "13812345678"
            assert result[CONF_TOKEN] == "existing-token"
            mock_store.async_save.assert_called_once()
            saved = mock_store.async_save.call_args[0][0]
            assert saved[CONF_TOKEN] == "existing-token"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_check_auth_load_restores_token_from_store(
        self, account
    ) -> None:
        """Test async_check_auth loads token from Store when present."""
        with patch(
            "custom_components.catlink.modules.account.Store"
        ) as mock_store_cls:
            mock_store = MagicMock()
            mock_store.async_load = AsyncMock(
                return_value={CONF_PHONE: "13812345678", CONF_TOKEN: "stored-token"}
            )
            mock_store_cls.return_value = mock_store

            with patch.object(
                account, "async_login", new_callable=AsyncMock
            ) as mock_login:
                result = await account.async_check_auth(save=False)

                assert account.token == "stored-token"
                mock_login.assert_not_called()
                assert result[CONF_TOKEN] == "stored-token"

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_check_auth_calls_login_when_store_empty(
        self, account
    ) -> None:
        """Test async_check_auth calls async_login when Store has no token."""
        with patch(
            "custom_components.catlink.modules.account.Store"
        ) as mock_store_cls:
            mock_store = MagicMock()
            mock_store.async_load = AsyncMock(return_value={})
            mock_store_cls.return_value = mock_store

            with patch.object(
                account, "async_login", new_callable=AsyncMock
            ) as mock_login:
                mock_login.return_value = True
                await account.async_check_auth(save=False)

                mock_login.assert_called_once()


class TestAccountRequestErrors:
    """Tests for Account request error handling."""

    async def test_auth_retry_flag_is_not_sent_to_http(self, account) -> None:
        """Discovery owns its retry budget; the internal flag is not an HTTP option."""
        response = MagicMock()
        response.json = AsyncMock(return_value={"returnCode": 1002})
        account.http.request = AsyncMock(return_value=response)
        with patch.object(account, "async_login", new_callable=AsyncMock) as login:
            result = await account.request("token/device/union/sortedListV2", _retried=True)
            assert result == {"returnCode": 1002}
            login.assert_not_awaited()
        assert "_retried" not in account.http.request.call_args.kwargs

    async def test_auth_retry_flag_is_consumed_on_retry(self, account) -> None:
        """The existing request-level retry also leaves aiohttp options intact."""
        expired = MagicMock()
        expired.json = AsyncMock(return_value={"returnCode": 1002})
        success = MagicMock()
        success.json = AsyncMock(return_value={"returnCode": 0, "data": []})
        account.http.request = AsyncMock(side_effect=[expired, success])
        with patch.object(account, "async_login", new_callable=AsyncMock) as login:
            login.return_value = True
            assert await account.request("token/device/list") == {
                "returnCode": 0, "data": []
            }
            login.assert_awaited_once()
        assert account.http.request.await_count == 2
        assert all(
            "_retried" not in args.kwargs
            for args in account.http.request.await_args_list
        )

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_request_returns_empty_on_connector_error(self, account) -> None:
        """Test request returns empty dict on ClientConnectorError."""
        from aiohttp import ClientConnectorError

        async def mock_request_fail(*args, **kwargs):
            raise ClientConnectorError(MagicMock(), OSError("Connection refused"))

        account.http.request = mock_request_fail

        result = await account.request("token/device/list")

        assert result == {}

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_request_returns_empty_on_timeout(self, account) -> None:
        """Test request returns empty dict on TimeoutError."""
        async def mock_request_timeout(*args, **kwargs):
            raise TimeoutError("Request timed out")

        account.http.request = mock_request_timeout

        result = await account.request("token/device/list")

        assert result == {}

    @pytest.mark.usefixtures("enable_custom_integrations")
    async def test_request_returns_empty_when_json_is_none(self, account) -> None:
        """Test request returns empty dict when response json is None."""
        async def mock_request_json_none(*args, **kwargs):
            resp = MagicMock()
            resp.json = AsyncMock(return_value=None)
            return resp

        account.http.request = mock_request_json_none

        result = await account.request("token/device/list")

        assert result == {}
