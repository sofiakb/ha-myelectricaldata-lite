"""Ajout de l'intégration depuis l'interface : Linky ou Gazpar."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import client_factory
from .api import MedAuthError, MedError
from .const import CONF_KIND, CONF_SECRET, DOMAIN, KIND_GAZPAR, KIND_LINKY

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
SCHEMAS = {
    KIND_LINKY: vol.Schema({vol.Required(CONF_SECRET): PASSWORD}),
    KIND_GAZPAR: vol.Schema(
        {
            vol.Required(CONF_USERNAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): PASSWORD,
        }
    ),
}


class MedConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
        client = client_factory(self.hass, data)
        try:
            meters = await client.meters()
        except MedAuthError:
            return [], {"base": "invalid_auth"}
        except MedError:
            return [], {"base": "cannot_connect"}
        finally:
            await client.close()
        if not meters:
            return [], {"base": "no_pdl"}
        return meters, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=[KIND_LINKY, KIND_GAZPAR])

    async def async_step_linky(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_step_kind(KIND_LINKY, user_input)

    async def async_step_gazpar(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_step_kind(KIND_GAZPAR, user_input)

    async def _async_step_kind(
        self, kind: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**user_input, CONF_KIND: kind}
            meters, errors = await self._validate(data)
            if not errors:
                prefix = "Linky" if kind == KIND_LINKY else "Gazpar"
                await self.async_set_unique_id("-".join(sorted(meters)))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"{prefix} {', '.join(meters)}", data=data)
        return self.async_show_form(step_id=kind, data_schema=SCHEMAS[kind], errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        kind = entry.data.get(CONF_KIND, KIND_LINKY)
        errors: dict[str, str] = {}
        if user_input is not None:
            _, errors = await self._validate({**entry.data, **user_input})
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=SCHEMAS[kind], errors=errors
        )
