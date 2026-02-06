"""Account module for CatLink."""

from asyncio import TimeoutError
import base64
import datetime
import hashlib
import time

from aiohttp import ClientConnectorError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store

from ..const import (
    _LOGGER,
    CONF_API_BASE,
    CONF_LANGUAGE,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_API_BASE,
    DOMAIN,
    RSA_PUBLIC_KEY,
    SCAN_INTERVAL,
    SIGN_KEY,
)
from ..helpers import Helper


class Account:
    """Account class for CatLink integration."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize the account."""
        self._config = config
        self.hass = hass
        self.http = aiohttp_client.async_create_clientsession(hass, auto_cleanup=False)

    def get_config(self, key, default=None) -> str:
        """Return the config of the account."""
        val = self._config.get(key)
        if val is not None:
            return val
        domain_data = self.hass.data.get(DOMAIN) or {}
        global_config = domain_data.get("config") or {}
        return global_config.get(key, default)

    @property
    def phone(self) -> str:
        """Return the phone of the account."""
        return self._config.get(CONF_PHONE)

    @property
    def password(self) -> str:
        """Return the password of the account."""
        pwd = self._config.get(CONF_PASSWORD)
        if len(pwd) <= 16:
            pwd = self.encrypt_password(pwd)
        return pwd

    @property
    def uid(self):
        """Return the unique id of the account."""
        return f"{self._config.get(CONF_PHONE_IAC)}-{self.phone}"

    @property
    def token(self) -> str:
        """Return the token of the account."""
        return self._config.get(CONF_TOKEN) or ""

    @property
    def update_interval(self) -> datetime.timedelta:
        """Return the update interval of the account. Default is 1 minute."""
        interval = (
            self.get_config(CONF_UPDATE_INTERVAL)
            or self.get_config(CONF_SCAN_INTERVAL)
            or SCAN_INTERVAL
        )
        return Helper.calculate_update_interval(interval)

    def api_url(self, api="") -> str:
        """Return the full url of the api."""
        if api[:6] == "https:" or api[:5] == "http:":
            return api
        bas = self.get_config(CONF_API_BASE) or DEFAULT_API_BASE
        return f"{bas.rstrip('/')}/{api.lstrip('/')}"

    async def request(self, api, pms=None, method="GET", **kwargs) -> dict:
        """Request the api."""
        method = method.upper()
        url = self.api_url(api)
        kws = {
            "timeout": 60,
            "headers": {
                "language": self.get_config(CONF_LANGUAGE, "en_GB"),
                "User-Agent": "okhttp/3.10.0",
                "token": self.token,
            },
        }
        kws.update(kwargs)
        if pms is None:
            pms = {}
        pms["noncestr"] = int(time.time() * 1000)
        if self.token:
            pms[CONF_TOKEN] = self.token
        pms["sign"] = self.params_sign(pms)
        if method in ["GET"]:
            kws["params"] = pms
        elif method in ["POST_GET"]:
            method = "POST"
            kws["params"] = pms
        else:
            kws["data"] = pms
        try:
            req = await self.http.request(method, url, **kws)
            result = await req.json() or {}
            _LOGGER.debug("API response %s %s: %s", method, api, result)
            return result
        except (ClientConnectorError, TimeoutError) as exc:  # noqa: UP041
            _LOGGER.error("Request api failed: %s", [method, url, pms, exc])
        return {}

    async def async_login(self) -> bool:
        """Login the account."""
        pms = {
            "platform": "ANDROID",
            "internationalCode": self._config.get(CONF_PHONE_IAC),
            "mobile": str(self.phone),
            "password": self.password,
        }
        self._config.update(
            {
                CONF_TOKEN: None,
            }
        )
        rsp = await self.request("login/password", pms, "POST")
        tok = rsp.get("data", {}).get("token")
        if not tok:
            _LOGGER.error("Login %s failed: %s", self.phone, [rsp, pms])
            return False
        self._config.update(
            {
                CONF_TOKEN: tok,
            }
        )
        await self.async_check_auth(True)
        return True

    async def async_check_auth(self, save=False) -> dict:
        """Check the auth of the account."""
        fnm = f"{DOMAIN}/auth-{self.uid}.json"
        sto = Store(self.hass, 1, fnm)
        old = await sto.async_load() or {}
        if save:
            cfg = {
                CONF_PHONE: self.phone,
                CONF_TOKEN: self.token,
            }
            if cfg.get(CONF_TOKEN) == old.get(CONF_TOKEN):
                cfg["update_at"] = old.get("update_at")
            else:
                cfg["update_at"] = f"{datetime.datetime.today()}"
            await sto.async_save(cfg)
            return cfg
        if old.get(CONF_TOKEN):
            self._config.update(
                {
                    CONF_TOKEN: old.get(CONF_TOKEN),
                }
            )
        else:
            await self.async_login()
        return old

    async def get_devices(self) -> list:
        """Get the devices of the account."""
        if not self.token:
            if not await self.async_login():
                return []
        api = "token/device/union/list/sorted"
        rsp = await self.request(api, {"type": "NONE"})
        eno = rsp.get("returnCode", 0)
        if eno == 1002:  # Illegal token
            if await self.async_login():
                rsp = await self.request(api, {"type": "NONE"})
        dls = rsp.get("data", {}).get(CONF_DEVICES) or []
        if not dls:
            _LOGGER.warning("Got devices for %s failed: %s", self.phone, rsp)
        return dls

    async def get_cats(self, timezone_id: str | None = None) -> list:
        """Get the cats of the account."""
        if not self.token:
            if not await self.async_login():
                return []
        api = "token/pet/health/v3/cats"
        params: dict[str, str] = {}
        if timezone_id:
            params["timezoneId"] = timezone_id
        rsp = await self.request(api, params)
        eno = rsp.get("returnCode", 0)
        if eno == 1002:  # Illegal token
            if await self.async_login():
                rsp = await self.request(api, params)
        cats = rsp.get("data", {}).get("cats") or []
        if not cats:
            _LOGGER.warning("Got cats for %s failed: %s", self.phone, rsp)
        return cats

    async def get_cat_summary_simple(
        self,
        pet_id: str,
        date: str,
        timezone_id: str | None,
        sport: int = 1,
    ) -> dict:
        """Get a cat summary for a given date."""
        if not self.token:
            if not await self.async_login():
                return {}
        api = "token/pet/health/v3/summarySimple"
        params = {
            "petId": pet_id,
            "date": date,
            "sport": sport,
        }
        if timezone_id:
            params["timezoneId"] = timezone_id
        rsp = await self.request(api, params)
        eno = rsp.get("returnCode", 0)
        if eno == 1002:  # Illegal token
            if await self.async_login():
                rsp = await self.request(api, params)
        return rsp.get("data") or {}

    @staticmethod
    def params_sign(pms: dict) -> str:
        """Sign the params."""
        lst = list(pms.items())
        lst.sort()
        pms = [f"{k}={v}" for k, v in lst]
        pms.append(f"key={SIGN_KEY}")
        pms = "&".join(pms)
        return hashlib.md5(pms.encode()).hexdigest().upper()

    @staticmethod
    def encrypt_password(pwd) -> str:
        """Encrypt the password."""
        pwd = f"{pwd}"
        md5 = hashlib.md5(pwd.encode()).hexdigest().lower()
        sha = hashlib.sha1(md5.encode()).hexdigest().upper()
        pub = serialization.load_der_public_key(
            base64.b64decode(RSA_PUBLIC_KEY), default_backend()
        )
        pad = padding.PKCS1v15()
        return base64.b64encode(pub.encrypt(sha.encode(), pad)).decode()
