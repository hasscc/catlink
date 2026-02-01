"""Config flow for CatLink integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_BASE,
    CONF_LANGUAGE,
    CONF_PHONE,
    CONF_PHONE_IAC,
    CONF_SCAN_INTERVAL,
    DEFAULT_API_BASE,
    DOMAIN,
)
from .modules.account import Account


class CatlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CatLink."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE]
            phone_iac = user_input[CONF_PHONE_IAC]
            uid = f"{phone_iac}-{phone}"
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()

            if await self._async_validate_credentials(self.hass, user_input):
                return self.async_create_entry(
                    title=f"{phone_iac} {phone}",
                    data=user_input,
                )
            errors["base"] = "auth_failed"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PHONE): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PHONE_IAC, default="86"): cv.string,
                vol.Optional(CONF_API_BASE, default=DEFAULT_API_BASE): cv.string,
                vol.Optional(CONF_LANGUAGE, default="zh_CN"): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default="00:01:00",
                ): cv.time_period_str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict) -> FlowResult:
        """Handle import from YAML."""
        phone = user_input.get(CONF_PHONE)
        phone_iac = user_input.get(CONF_PHONE_IAC, "86")
        if phone:
            uid = f"{phone_iac}-{phone}"
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{phone_iac} {phone}" if phone else DOMAIN,
            data=user_input,
        )

    async def _async_validate_credentials(
        self, hass: HomeAssistant, data: dict
    ) -> bool:
        """Validate credentials by logging in."""
        try:
            account = Account(hass, data)
            return await account.async_login()
        except Exception:  # pragma: no cover - safety net
            return False
