"""The component."""
import logging
import base64
import hashlib
import datetime
import time
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_TOKEN,CONF_DEVICES,STATE_ON,STATE_OFF,CONF_PASSWORD,CONF_SCAN_INTERVAL,CONF_LANGUAGE
from homeassistant.components import persistent_notification
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from asyncio import TimeoutError
from aiohttp import ClientConnectorError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'catlink'
SCAN_INTERVAL = datetime.timedelta(minutes=1)

CONF_ACCOUNTS = 'accounts'
CONF_API_BASE = 'api_base'
CONF_USER_ID = 'uid'
CONF_PHONE = 'phone'
CONF_PHONE_IAC = 'phone_iac'
CONF_LANGUAGE = 'language'

DEFAULT_API_BASE = 'https://app.catlinks.cn/api/'

SIGN_KEY = '00109190907746a7ad0e2139b6d09ce47551770157fe4ac5922f3a5454c82712'
RSA_PUBLIC_KEY = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCCA9I+iEl2AI8dnhdwwxPxHVK8iNAt6aTq6UhNsLsguWS5qtbLnuGz2RQdfNS' \
                 'aKSU2B6D/vE2gb1fM6f1A5cKndqF/riWGWn1EfL3FFQZduOTxoA0RTQzhrTa5LHcJ/an/NuHUwShwIOij0Mf4g8faTe4FT7/HdA' \
                 'oK7uW0cG9mZwIDAQAB'
RSA_PRIVATE_KEY = 'MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAIID0j6ISXYAjx2eF3DDE/EdUryI0C3ppOrpSE2wuyC5ZLmq1s' \
                  'ue4bPZFB181JopJTYHoP+8TaBvV8zp/UDlwqd2oX+uJYZafUR8vcUVBl245PGgDRFNDOGtNrksdwn9qf824dTBKHAg6KPQx/iD' \
                  'x9pN7gVPv8d0Cgru5bRwb2ZnAgMBAAECgYAccTuQRH5Vmz+zyf70wyhcqf6Mkh2Avck/PrN7k3sMaKJZX79HokVb89RLsyBLbU' \
                  '7fqAGXkJkmzNTXViT6Colvi1T7QQWhkvPsPEsu/89s5yo0ME2+rtvBA/niy1iQs6UYTzZivSKosLVgCTmcOYbp5eUCP8IPtKy/' \
                  '3vzkIBMZqQJBALn0bAgCeXwctYqznCboNHAX7kGk9HjX8VCOfaBh1WcAYWk7yKzYZemMKXMw5ifeopT0uUpLEk5mlN4nxwBsTp' \
                  'sCQQCy/SHTlQyt/yauVyrJipZflUK/hq6hIZFIu1Mc40L6BDNAboi42P9suznXbV7DD+LNpxFnkYlee8sitY0R474lAkEAsjBV' \
                  'lRdJ8nRQQij6aQ35sbA8zwqSeXnz842XNCiLpbfnoD95fKeggLuevJMO+QWOJc6b/2UQlbAW1wqm1vDyIQJAUhYVNVvd/M5Phx' \
                  'Ui4ltUq3Fgs0WpQOyMHLcMXus7BD544svOmDesrMkQtePK2dqnQXmlWcI9Jb/QYZKxp8qyoQJAP2kK4dc3AA4BDVQUMHYiSnGp' \
                  'I0eGQrD/W4rBeoCX8sJDCH49lMsec52TFI2Gn8tTKOCqqgGvRSKDJ005HlnmKw=='

SUPPORTED_DOMAINS = [
    'sensor',
    'binary_sensor',
    'switch',
    'select',
]

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_BASE, default=DEFAULT_API_BASE): cv.string,
        vol.Optional(CONF_PHONE): cv.string,
        vol.Optional(CONF_PHONE_IAC, default='86'): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LANGUAGE, default='zh_CN'): cv.string,
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


async def async_setup(hass: HomeAssistant, hass_config: dict):
    hass.data.setdefault(DOMAIN, {})
    config = hass_config.get(DOMAIN) or {}
    hass.data[DOMAIN]['config'] = config
    hass.data[DOMAIN].setdefault(CONF_ACCOUNTS, {})
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault('coordinators', {})
    hass.data[DOMAIN].setdefault('add_entities', {})

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    hass.data[DOMAIN]['component'] = component
    await component.async_setup(config)

    als = config.get(CONF_ACCOUNTS) or []
    if CONF_PASSWORD in config:
        acc = {**config}
        acc.pop(CONF_ACCOUNTS, None)
        als.append(acc)
    for cfg in als:
        if not cfg.get(CONF_PASSWORD) and not cfg.get(CONF_TOKEN):
            continue
        acc = Account(hass, cfg)
        coordinator = DevicesCoordinator(acc)
        await acc.async_check_auth()
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][CONF_ACCOUNTS][acc.uid] = acc
        hass.data[DOMAIN]['coordinators'][coordinator.name] = coordinator

    for platform in SUPPORTED_DOMAINS:
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    return True


async def async_setup_accounts(hass: HomeAssistant, domain):
    for coordinator in hass.data[DOMAIN]['coordinators'].values():
        for k, sta in coordinator.data.items():
            await coordinator.update_hass_entities(domain, sta)


class Account:
    def __init__(self, hass: HomeAssistant, config: dict):
        self._config = config
        self.hass = hass
        self.http = aiohttp_client.async_create_clientsession(hass, auto_cleanup=False)

    def get_config(self, key, default=None):
        return self._config.get(key, self.hass.data[DOMAIN]['config'].get(key, default))

    @property
    def phone(self):
        return self._config.get(CONF_PHONE)

    @property
    def password(self):
        pwd = self._config.get(CONF_PASSWORD)
        if len(pwd) <= 16:
            pwd = self.encrypt_password(pwd)
        return pwd

    @property
    def uid(self):
        return f'{self._config.get(CONF_PHONE_IAC)}-{self.phone}'

    @property
    def token(self):
        return self._config.get(CONF_TOKEN) or ''

    @property
    def update_interval(self):
        return self.get_config(CONF_SCAN_INTERVAL) or SCAN_INTERVAL

    def api_url(self, api=''):
        if api[:6] == 'https:' or api[:5] == 'http:':
            return api
        bas = self.get_config(CONF_API_BASE) or DEFAULT_API_BASE
        return f"{bas.rstrip('/')}/{api.lstrip('/')}"

    async def request(self, api, pms=None, method='GET', **kwargs):
        method = method.upper()
        url = self.api_url(api)
        kws = {
            'timeout': 60,
            'headers': {
                'language': self.get_config(CONF_LANGUAGE),
                'User-Agent': 'okhttp/3.10.0',
            },
        }
        kws.update(kwargs)
        if pms is None:
            pms = {}
        pms['noncestr'] = int(time.time() * 1000)
        if self.token:
            pms[CONF_TOKEN] = self.token
        pms['sign'] = self.params_sign(pms)
        if method in ['GET']:
            kws['params'] = pms
        elif method in ['POST_GET']:
            method = 'POST'
            kws['params'] = pms
        else:
            kws['data'] = pms
        try:
            req = await self.http.request(method, url, **kws)
            return await req.json() or {}
        except (ClientConnectorError, TimeoutError) as exc:
            _LOGGER.error('Request api failed: %s', [method, url, pms, exc])
        return {}

    async def async_login(self):
        pms = {
            'platform': 'ANDROID',
            'internationalCode': self._config.get(CONF_PHONE_IAC),
            'mobile': self.phone,
            'password': self.password,
        }
        self._config.update({
            CONF_TOKEN: None,
        })
        rsp = await self.request('login/password', pms, 'POST')
        tok = rsp.get('data', {}).get('token')
        if not tok:
            _LOGGER.error('Login %s failed: %s', self.phone, [rsp, pms])
            return False
        self._config.update({
            CONF_TOKEN: tok,
        })
        await self.async_check_auth(True)
        return True

    async def async_check_auth(self, save=False):
        fnm = f'{DOMAIN}/auth-{self.uid}.json'
        sto = Store(self.hass, 1, fnm)
        old = await sto.async_load() or {}
        if save:
            cfg = {
                CONF_PHONE: self.phone,
                CONF_TOKEN: self.token,
            }
            if cfg.get(CONF_TOKEN) == old.get(CONF_TOKEN):
                cfg['update_at'] = old.get('update_at')
            else:
                cfg['update_at'] = f'{datetime.datetime.today()}'
            await sto.async_save(cfg)
            return cfg
        if old.get(CONF_TOKEN):
            self._config.update({
                CONF_TOKEN: old.get(CONF_TOKEN),
            })
        else:
            await self.async_login()
        return old

    async def get_devices(self):
        if not self.token:
            if not await self.async_login():
                return []
        api = 'token/device/union/list/sorted'
        rsp = await self.request(api, {'type': 'NONE'})
        eno = rsp.get('returnCode', 0)
        if eno == 1002:  # Illegal token
            if await self.async_login():
                rsp = await self.request(api, {'type': 'NONE'})
        dls = rsp.get('data', {}).get(CONF_DEVICES) or []
        if not dls:
            _LOGGER.warning('Got devices for %s failed: %s', self.phone, rsp)
        return dls

    @staticmethod
    def params_sign(pms: dict):
        lst = list(pms.items())
        lst.sort()
        pms = [
            f'{k}={v}'
            for k, v in lst
        ]
        pms.append(f'key={SIGN_KEY}')
        pms = '&'.join(pms)
        return hashlib.md5(pms.encode()).hexdigest().upper()

    @staticmethod
    def encrypt_password(pwd):
        pwd = f'{pwd}'
        md5 = hashlib.md5(pwd.encode()).hexdigest().lower()
        sha = hashlib.sha1(md5.encode()).hexdigest().upper()
        pub = serialization.load_der_public_key(base64.b64decode(RSA_PUBLIC_KEY), default_backend())
        pad = padding.PKCS1v15()
        return base64.b64encode(pub.encrypt(sha.encode(), pad)).decode()


class DevicesCoordinator(DataUpdateCoordinator):
    def __init__(self, account: Account):
        super().__init__(
            account.hass,
            _LOGGER,
            name=f'{DOMAIN}-{account.uid}-{CONF_DEVICES}',
            update_interval=account.update_interval,
        )
        self.account = account
        self._subs = {}

    async def _async_update_data(self):
        dls = await self.account.get_devices()
        for dat in dls:
            did = dat.get('id')
            if not did:
                continue
            old = self.hass.data[DOMAIN][CONF_DEVICES].get(did)
            if old:
                dvc = old
                dvc.update_data(dat)
            else:
                typ = dat.get('deviceType')
                if typ in ['SCOOPER']:
                    dvc = ScooperDevice(dat, self)
                else:
                    dvc = Device(dat, self)
                self.hass.data[DOMAIN][CONF_DEVICES][did] = dvc
            await dvc.async_init()
            for d in SUPPORTED_DOMAINS:
                await self.update_hass_entities(d, dvc)
        return self.hass.data[DOMAIN][CONF_DEVICES]

    async def update_hass_entities(self, domain, dvc):
        from .sensor import CatlinkSensorEntity
        from .binary_sensor import CatlinkBinarySensorEntity
        from .switch import CatlinkSwitchEntity
        from .select import CatlinkSelectEntity
        hdk = f'hass_{domain}'
        add = self.hass.data[DOMAIN]['add_entities'].get(domain)
        if not add or not hasattr(dvc, hdk):
            return
        for k, cfg in getattr(dvc, hdk).items():
            key = f'{domain}.{k}.{dvc.id}'
            new = None
            if key in self._subs:
                pass
            elif domain == 'sensor':
                new = CatlinkSensorEntity(k, dvc, cfg)
            elif domain == 'binary_sensor':
                new = CatlinkBinarySensorEntity(k, dvc, cfg)
            elif domain == 'switch':
                new = CatlinkSwitchEntity(k, dvc, cfg)
            elif domain == 'select':
                new = CatlinkSelectEntity(k, dvc, cfg)
            if new:
                self._subs[key] = new
                add([new])


class Device:
    data: dict

    def __init__(self, dat: dict, coordinator: DevicesCoordinator):
        self.coordinator = coordinator
        self.account = coordinator.account
        self.listeners = {}
        self.update_data(dat)
        self.detail = {}

    async def async_init(self):
        await self.update_device_detail()

    def update_data(self, dat: dict):
        self.data = dat
        self._handle_listeners()
        _LOGGER.info('Update device data: %s', dat)

    def _handle_listeners(self):
        for fun in self.listeners.values():
            fun()

    @property
    def id(self):
        return self.data.get('id')

    @property
    def mac(self):
        return self.data.get('mac', '')

    @property
    def model(self):
        return self.data.get('model', '')

    @property
    def type(self):
        return self.data.get('deviceType', '')

    @property
    def name(self):
        return self.data.get('deviceName', '')

    @property
    def error(self):
        return self.detail.get('currentMessage') or self.data.get('currentErrorMessage', '')

    async def update_device_detail(self):
        api = 'token/device/info'
        pms = {
            'deviceId': self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get('data', {}).get('deviceInfo') or {}
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error('Got device detail for %s failed: %s', self.name, exc)
        if not rdt:
            _LOGGER.warning('Got device detail for %s failed: %s', self.name, rsp)
        self.detail = rdt
        self._handle_listeners()
        return rdt

    @property
    def state(self):
        sta = self.detail.get('workStatus', '')
        dic = {
            '00': 'idle',
            '01': 'running',
            '02': 'need_reset',
        }
        return dic.get(f'{sta}'.strip(), sta)

    def state_attrs(self):
        return {
            'work_status': self.detail.get('workStatus'),
            'alarm_status': self.detail.get('alarmStatus'),
            'atmosphere_status': self.detail.get('atmosphereStatus'),
            'temperature': self.detail.get('temperature'),
            'humidity': self.detail.get('humidity'),
            'weight': self.detail.get('weight'),
            'key_lock': self.detail.get('keyLock'),
            'safe_time': self.detail.get('safeTime'),
            'pave_second': self.detail.get('catLitterPaveSecond'),
        }

    def error_attrs(self):
        return {
            'weight': self.detail.get('weight'),
        }

    @property
    def mode(self):
        return self.modes.get(self.detail.get('workModel', ''))

    @property
    def modes(self):
        return {}

    def mode_attrs(self):
        return {
            'work_mode': self.detail.get('workModel'),
        }

    async def select_mode(self, mode, **kwargs):
        api = 'token/device/changeMode'
        mod = None
        for k, v in self.modes.items():
            if v == mode:
                mod = k
                break
        if mod is None:
            _LOGGER.warning('Select mode failed for %s in %s', mode, self.modes)
            return False
        pms = {
            'workModel': mod,
            'deviceId': self.id,
        }
        rdt = await self.account.request(api, pms, 'POST')
        eno = rdt.get('returnCode', 0)
        if eno:
            _LOGGER.error('Select mode failed: %s', [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info('Select mode: %s', [rdt, pms])
        return rdt

    @property
    def action(self):
        return None

    @property
    def actions(self):
        return {}

    async def select_action(self, action, **kwargs):
        api = 'token/device/actionCmd'
        val = None
        for k, v in self.actions.items():
            if v == action:
                val = k
                break
        if val is None:
            _LOGGER.warning('Select action failed for %s in %s', action, self.actions)
            return False
        pms = {
            'cmd': val,
            'deviceId': self.id,
        }
        rdt = await self.account.request(api, pms, 'POST')
        eno = rdt.get('returnCode', 0)
        if eno:
            _LOGGER.error('Select action failed: %s', [rdt, pms])
            return False
        await self.update_device_detail()
        _LOGGER.info('Select action: %s', [rdt, pms])
        return rdt

    @property
    def hass_sensor(self):
        return {
            'state': {
                'icon': 'mdi:information',
                'state_attrs': self.state_attrs,
            },
            'error': {
                'icon': 'mdi:alert-circle',
                'state_attrs': self.error_attrs,
            },
        }

    @property
    def hass_binary_sensor(self):
        return {
        }

    @property
    def hass_switch(self):
        return {
        }

    @property
    def hass_select(self):
        return {
            'mode': {
                'icon': 'mdi:menu',
                'options': list(self.modes.values()),
                'state_attrs': self.mode_attrs,
                'async_select': self.select_mode,
            },
            'action': {
                'icon': 'mdi:play-box',
                'options': list(self.actions.values()),
                'async_select': self.select_action,
                'delay_update': 5,
            },
        }


class ScooperDevice(Device):
    logs: list
    coordinator_logs = None

    async def async_init(self):
        await super().async_init()
        self.logs = []
        self.coordinator_logs = DataUpdateCoordinator(
            self.account.hass,
            _LOGGER,
            name=f'{DOMAIN}-{self.id}-logs',
            update_method=self.update_logs,
            update_interval=datetime.timedelta(minutes=1),
        )
        await self.coordinator_logs.async_config_entry_first_refresh()

    @property
    def modes(self):
        return {
            '00': 'auto',
            '01': 'manual',
            '02': 'time',
            '03': 'empty',
        }

    @property
    def actions(self):
        return {
            '00': 'pause',
            '01': 'start',
        }

    @property
    def _last_log(self):
        log = {}
        if self.logs:
            log = self.logs[0] or {}
        return log

    @property
    def last_log(self):
        log = self._last_log
        if not log:
            return None
        return f"{log.get('time')} {log.get('event')}"

    def last_log_attrs(self):
        log = self._last_log
        return {
            **log,
            'logs': self.logs,
        }

    async def update_logs(self):
        api = 'token/device/scooper/stats/log/top5'
        pms = {
            'deviceId': self.id,
        }
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            rdt = rsp.get('data', {}).get('scooperLogTop5') or []
        except (TypeError, ValueError) as exc:
            rdt = {}
            _LOGGER.error('Got device logs for %s failed: %s', self.name, exc)
        if not rdt:
            _LOGGER.warning('Got device logs for %s failed: %s', self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt

    @property
    def hass_sensor(self):
        return {
            **super().hass_sensor,
            'last_log': {
                'icon': 'mdi:message',
                'state_attrs': self.last_log_attrs,
            },
        }


class CatlinkEntity(CoordinatorEntity):
    def __init__(self, name, device: Device, option=None):
        self.coordinator = device.coordinator
        CoordinatorEntity.__init__(self, self.coordinator)
        self.account = self.coordinator.account
        self._name = name
        self._device = device
        self._option = option or {}
        self._attr_name = f'{device.name} {name}'.strip()
        self._attr_device_id = f'{device.type}_{device.mac}'
        self._attr_unique_id = f'{self._attr_device_id}-{name}'
        mac = device.mac[-4:] if device.mac else device.id
        self.entity_id = f'{DOMAIN}.{device.type.lower()}_{mac}_{name}'
        self._attr_icon = self._option.get('icon')
        self._attr_device_class = self._option.get('class')
        self._attr_unit_of_measurement = self._option.get('unit')
        self._attr_device_info = {
            'identifiers': {(DOMAIN, self._attr_device_id)},
            'name': device.name,
            'model': device.model,
            'manufacturer': 'CatLink',
            'sw_version': device.detail.get('firmwareVersion'),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._device.listeners[self.entity_id] = self._handle_coordinator_update
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        self.update()
        self.async_write_ha_state()

    def update(self):
        if hasattr(self._device, self._name):
            self._attr_state = getattr(self._device, self._name)
            _LOGGER.debug('Entity update: %s', [self.entity_id, self._name, self._attr_state])

        fun = self._option.get('state_attrs')
        if callable(fun):
            self._attr_extra_state_attributes = fun()

    @property
    def state(self):
        return self._attr_state

    async def async_request_api(self, api, params=None, method='GET', **kwargs):
        throw = kwargs.pop('throw', None)
        rdt = await self.account.request(api, params, method, **kwargs)
        if throw:
            persistent_notification.create(
                self.hass,
                f'{rdt}',
                f'Request: {api}',
                f'{DOMAIN}-request',
            )
        return rdt


class CatlinkBinaryEntity(CatlinkEntity):
    def __init__(self, name, device: Device, option=None):
        super().__init__(name, device, option)
        self._attr_is_on = False

    def update(self):
        super().update()
        if hasattr(self._device, self._name):
            self._attr_is_on = not not getattr(self._device, self._name)
        else:
            self._attr_is_on = False

    @property
    def state(self):
        return STATE_ON if self._attr_is_on else STATE_OFF
