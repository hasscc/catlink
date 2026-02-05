"""Config flow for CatLink integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    API_SERVERS,
    CONF_API_BASE,
    CONF_DEVICE_IDS,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ERROR_INVALID_AUTH,
    SUPPORTED_DEVICE_TYPES,
)
from .helpers import discover_region, parse_phone_number
from .modules.account import Account


def _device_label(dat: dict, supported: bool) -> str:
    """Build a human-readable label for a device."""
    name = dat.get("deviceName") or dat.get("model") or "Unknown"
    model = dat.get("model", "")
    device_type = dat.get("deviceType", "")
    suffix = "Supported" if supported else "Limited support"
    if model and model != name:
        return f"{name} ({model}) - {suffix}"
    return f"{name} ({device_type}) - {suffix}"


class CatlinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a CatLink config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CatlinkOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CatlinkOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._account: Account | None = None
        self._config: dict[str, Any] = {}
        self._discovered_devices: list[dict] = []
        self._device_options: dict[str, str] = {}
        self._supported_ids: list[str] = []

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone_raw = user_input[CONF_PHONE].strip()
            password = user_input[CONF_PASSWORD]

            phone_iac, phone_number = parse_phone_number(phone_raw)
            region = await discover_region(self.hass, phone_iac, phone_number, password)
            if region is None:
                errors["base"] = ERROR_INVALID_AUTH
            else:
                api_base = API_SERVERS[region]
                config = {
                    CONF_API_BASE: api_base,
                    CONF_PHONE: phone_number,
                    CONF_PHONE_IAC: phone_iac,
                    CONF_PASSWORD: password,
                }
                account = Account(self.hass, config)
                await account.async_check_auth()

                self._account = account
                self._config = config

                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=self._config
                    )

                devices = await account.get_devices()
                if not devices:
                    return self.async_create_entry(
                        title=f"+{phone_iac}{phone_number}",
                        data=self._config,
                        options={CONF_DEVICE_IDS: [], CONF_UPDATE_INTERVAL: 60},
                    )

                self._discovered_devices = devices
                self._device_options = {}
                self._supported_ids = []
                for dat in devices:
                    did = dat.get("id")
                    if not did:
                        continue
                    supported = dat.get("deviceType", "") in SUPPORTED_DEVICE_TYPES
                    self._device_options[did] = _device_label(dat, supported)
                    if supported:
                        self._supported_ids.append(did)

                return await self.async_step_discovery()

        reauth_entry = (
            self._get_reauth_entry() if self.source == SOURCE_REAUTH else None
        )
        default_phone = ""
        if reauth_entry:
            piac = reauth_entry.data.get(CONF_PHONE_IAC, "")
            pnum = reauth_entry.data.get(CONF_PHONE, "")
            default_phone = f"+{piac}{pnum}" if piac and pnum else ""

        schema = vol.Schema(
            {
                vol.Required(CONF_PHONE, default=default_phone): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device discovery step."""
        if user_input is not None:
            selected_ids = user_input.get(CONF_DEVICE_IDS, [])
            update_interval = user_input.get(CONF_UPDATE_INTERVAL, 60)
            uid = self._account.uid if self._account else ""
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"+{self._config[CONF_PHONE_IAC]}{self._config[CONF_PHONE]}",
                data=self._config,
                options={
                    CONF_DEVICE_IDS: selected_ids,
                    CONF_UPDATE_INTERVAL: update_interval,
                },
            )

        supported_count = len(self._supported_ids)
        unsupported_count = len(self._device_options) - supported_count

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEVICE_IDS,
                        default=self._supported_ids,
                    ): cv.multi_select(self._device_options),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=60,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30,
                            max=3600,
                            step=30,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
            description_placeholders={
                "supported_count": str(supported_count),
                "unsupported_count": str(unsupported_count),
                "total_count": str(len(self._device_options)),
            },
        )


class CatlinkOptionsFlowHandler(OptionsFlowWithReload):
    """Handle CatLink options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage device selection and refresh interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        account = Account(
            self.hass,
            {**dict(self.config_entry.data), **dict(self.config_entry.options or {})},
        )
        await account.async_check_auth()
        devices = await account.get_devices() or []

        device_options: dict[str, str] = {}
        supported_ids: list[str] = []
        for dat in devices:
            did = dat.get("id")
            if not did:
                continue
            supported = dat.get("deviceType", "") in SUPPORTED_DEVICE_TYPES
            device_options[did] = _device_label(dat, supported)
            if supported:
                supported_ids.append(did)

        current_ids = self.config_entry.options.get(CONF_DEVICE_IDS)
        if current_ids is None:
            current_ids = (
                supported_ids if supported_ids else list(device_options.keys())
            )

        current_interval = self.config_entry.options.get(CONF_UPDATE_INTERVAL, 60)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEVICE_IDS,
                        default=current_ids,
                    ): cv.multi_select(device_options),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current_interval,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30,
                            max=3600,
                            step=30,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
        )
