"""Capteurs d'affichage ; le tableau Énergie lit les statistiques importées."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MedConfigEntry
from .const import DOMAIN
from .coordinator import MedCoordinator, PdlData


@dataclass(frozen=True, kw_only=True)
class MedSensorDescription(SensorEntityDescription):
    value: Callable[[PdlData], object]


SENSORS = (
    MedSensorDescription(
        key="dernier_jour",
        translation_key="dernier_jour",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda d: d.last_day_kwh,
    ),
    MedSensorDescription(
        key="sept_jours",
        translation_key="sept_jours",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda d: d.last_7_days_kwh,
    ),
    MedSensorDescription(
        key="date_dernier_jour",
        translation_key="date_dernier_jour",
        device_class=SensorDeviceClass.DATE,
        value=lambda d: d.last_day,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MedSensor(coordinator, pdl, description)
        for pdl in coordinator.usage_points
        for description in SENSORS
    )


class MedSensor(CoordinatorEntity[MedCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: MedSensorDescription

    def __init__(
        self, coordinator: MedCoordinator, usage_point_id: str, description: MedSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._pdl = usage_point_id
        self._attr_unique_id = f"{usage_point_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, usage_point_id)},
            name=f"Linky {usage_point_id}",
            manufacturer="Enedis",
            model="Linky",
        )

    @property
    def native_value(self) -> object:
        data = self.coordinator.data.get(self._pdl)
        return self.entity_description.value(data) if data else None
