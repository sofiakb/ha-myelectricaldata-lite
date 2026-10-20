"""Ajout de l'intégration depuis l'interface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MedAuthError, MedClient, MedError
from .const import CONF_SECRET, DOMAIN

SCHEMA = vol.Schema(
    {vol.Required(CONF_SECRET): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class MedConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, secret: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
        client = MedClient(async_get_clientsession(self.hass), secret)
        try:
            pdls = await client.usage_points()
        except MedAuthError:
            return [], {"base": "invalid_auth"}
        except MedError:
            return [], {"base": "cannot_connect"}
        if not pdls:
            return [], {"base": "no_pdl"}
        return pdls, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            pdls, errors = await self._validate(user_input[CONF_SECRET])
            if not errors:
                ids = sorted(p["usage_point_id"] for p in pdls)
                await self.async_set_unique_id("-".join(ids))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Linky {', '.join(ids)}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            _, errors = await self._validate(user_input[CONF_SECRET])
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
        return self.async_show_form(step_id="reauth_confirm", data_schema=SCHEMA, errors=errors)
