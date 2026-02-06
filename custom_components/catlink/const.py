"""Constants for the CatLink integration."""

import datetime
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL

DOMAIN = "catlink"
_LOGGER = logging.getLogger(__name__)

CONFIG = "config"
SCAN_INTERVAL = datetime.timedelta(minutes=1)

CONF_ACCOUNTS = "accounts"
CONF_API_BASE = "api_base"
CONF_REGION = "region"
CONF_USER_ID = "uid"
CONF_PHONE = "phone"
CONF_PHONE_IAC = "phone_iac"
CONF_LANGUAGE = "language"

CONF_CATS = "cats"
CONF_DEVICE_IDS = "device_ids"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_API_BASE = "https://app.catlinks.cn/api/"

# Device types with full support (sensors, switches, selects, etc.)
SUPPORTED_DEVICE_TYPES = frozenset({"C08", "SCOOPER", "LITTER_BOX_599", "FEEDER"})

# API server regions: value is the API base URL
API_SERVERS: dict[str, str] = {
    "global": "https://app.catlinks.cn/api/",
    "china": "https://app-sh.catlinks.cn/api/",
    "usa": "https://app-usa.catlinks.cn/api/",
    "singapore": "https://app-sgp.catlinks.cn/api/",
}

# Config flow error keys
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"

SIGN_KEY = "00109190907746a7ad0e2139b6d09ce47551770157fe4ac5922f3a5454c82712"
RSA_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCCA9I+iEl2AI8dnhdwwxPxHVK8iNAt6aTq6UhNsLsguWS5qtbLnuGz2RQdfNS"
    "aKSU2B6D/vE2gb1fM6f1A5cKndqF/riWGWn1EfL3FFQZduOTxoA0RTQzhrTa5LHcJ/an/NuHUwShwIOij0Mf4g8faTe4FT7/HdA"
    "oK7uW0cG9mZwIDAQAB"
)
RSA_PRIVATE_KEY = (
    "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAIID0j6ISXYAjx2eF3DDE/EdUryI0C3ppOrpSE2wuyC5ZLmq1s"
    "ue4bPZFB181JopJTYHoP+8TaBvV8zp/UDlwqd2oX+uJYZafUR8vcUVBl245PGgDRFNDOGtNrksdwn9qf824dTBKHAg6KPQx/iD"
    "x9pN7gVPv8d0Cgru5bRwb2ZnAgMBAAECgYAccTuQRH5Vmz+zyf70wyhcqf6Mkh2Avck/PrN7k3sMaKJZX79HokVb89RLsyBLbU"
    "7fqAGXkJkmzNTXViT6Colvi1T7QQWhkvPsPEsu/89s5yo0ME2+rtvBA/niy1iQs6UYTzZivSKosLVgCTmcOYbp5eUCP8IPtKy/"
    "3vzkIBMZqQJBALn0bAgCeXwctYqznCboNHAX7kGk9HjX8VCOfaBh1WcAYWk7yKzYZemMKXMw5ifeopT0uUpLEk5mlN4nxwBsTp"
    "sCQQCy/SHTlQyt/yauVyrJipZflUK/hq6hIZFIu1Mc40L6BDNAboi42P9suznXbV7DD+LNpxFnkYlee8sitY0R474lAkEAsjBV"
    "lRdJ8nRQQij6aQ35sbA8zwqSeXnz842XNCiLpbfnoD95fKeggLuevJMO+QWOJc6b/2UQlbAW1wqm1vDyIQJAUhYVNVvd/M5Phx"
    "Ui4ltUq3Fgs0WpQOyMHLcMXus7BD544svOmDesrMkQtePK2dqnQXmlWcI9Jb/QYZKxp8qyoQJAP2kK4dc3AA4BDVQUMHYiSnGp"
    "I0eGQrD/W4rBeoCX8sJDCH49lMsec52TFI2Gn8tTKOCqqgGvRSKDJ005HlnmKw=="
)

SUPPORTED_DOMAINS = [
    "sensor",
    "binary_sensor",
    "switch",
    "select",
    "button",
]

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_BASE, default=DEFAULT_API_BASE): cv.string,
        vol.Optional(CONF_PHONE): cv.string,
        vol.Optional(CONF_PHONE_IAC, default="86"): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LANGUAGE, default="zh_CN"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: ACCOUNT_SCHEMA.extend(
            {
                vol.Optional(CONF_ACCOUNTS): vol.All(cv.ensure_list, [ACCOUNT_SCHEMA]),
            },
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
