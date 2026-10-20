"""MyElectricalData Lite : consommation Linky via la passerelle MyElectricalData v2."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MedClient
from .const import CONF_SECRET
from .coordinator import MedCoordinator

PLATFORMS = [Platform.SENSOR]

type MedConfigEntry = ConfigEntry[MedCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MedConfigEntry) -> bool:
    client = MedClient(async_get_clientsession(hass), entry.data[CONF_SECRET])
    coordinator = MedCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MedConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
