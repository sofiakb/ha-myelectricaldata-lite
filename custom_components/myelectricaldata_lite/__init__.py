"""MyElectricalData Lite : consommation Linky (MyElectricalData v2) et Gazpar (GRDF)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .api import GrdfClient, MedClient
from .const import CONF_KIND, CONF_SECRET, KIND_GAZPAR, KIND_LINKY
from .coordinator import MedCoordinator

PLATFORMS = [Platform.SENSOR]

type MedConfigEntry = ConfigEntry[MedCoordinator]


def client_factory(hass: HomeAssistant, data: dict) -> MedClient | GrdfClient:
    if data.get(CONF_KIND, KIND_LINKY) == KIND_GAZPAR:
        return GrdfClient(
            async_create_clientsession(hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
    return MedClient(async_get_clientsession(hass), data[CONF_SECRET])


async def async_setup_entry(hass: HomeAssistant, entry: MedConfigEntry) -> bool:
    coordinator = MedCoordinator(hass, entry, lambda: client_factory(hass, entry.data))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MedConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return unloaded
