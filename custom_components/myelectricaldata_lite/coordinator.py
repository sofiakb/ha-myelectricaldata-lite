"""Récupère la consommation et l'importe dans les statistiques HA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import MedAuthError, MedClient, MedError
from .const import BACKFILL_DAYS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class PdlData:
    """Dernier jour connu pour un PDL."""

    last_day: date | None = None
    last_day_kwh: float | None = None
    last_7_days_kwh: float | None = None


def statistic_id(usage_point_id: str) -> str:
    return f"{DOMAIN}:consommation_{usage_point_id}"


class MedCoordinator(DataUpdateCoordinator[dict[str, PdlData]]):
    """Un appel par PDL et par mise à jour."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: MedClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.client = client
        self.usage_points: list[str] = []

    async def _async_update_data(self) -> dict[str, PdlData]:
        try:
            if not self.usage_points:
                pdls = await self.client.usage_points()
                self.usage_points = [p["usage_point_id"] for p in pdls]
            result = {}
            for usage_point_id in self.usage_points:
                result[usage_point_id] = await self._update_pdl(usage_point_id)
        except MedAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MedError as err:
            raise UpdateFailed(str(err)) from err
        return result

    async def _update_pdl(self, usage_point_id: str) -> PdlData:
        stat_id = statistic_id(usage_point_id)
        today = dt_util.now().date()
        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
        )
        if last.get(stat_id):
            row = last[stat_id][0]
            last_day = dt_util.as_local(dt_util.utc_from_timestamp(row["start"])).date()
            total = row["sum"] or 0.0
            start = min(last_day + timedelta(days=1), today - timedelta(days=7))
        else:
            last_day, total = None, 0.0
            start = today - timedelta(days=BACKFILL_DAYS)

        days = await self.client.daily_consumption(usage_point_id, start, today)

        stats = []
        for day in sorted(days):
            if last_day is not None and day <= last_day:
                continue
            kwh = days[day] / 1000
            total += kwh
            stats.append(
                StatisticData(
                    start=dt_util.start_of_local_day(datetime.combine(day, datetime.min.time())),
                    state=kwh,
                    sum=total,
                )
            )
        if stats:
            async_add_external_statistics(
                self.hass,
                StatisticMetaData(
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"Linky {usage_point_id}",
                    source=DOMAIN,
                    statistic_id=stat_id,
                    unit_class=EnergyConverter.UNIT_CLASS,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                ),
                stats,
            )
            _LOGGER.debug("%s : %s jours importés", usage_point_id, len(stats))

        data = PdlData()
        if days:
            newest = max(days)
            data.last_day = newest
            data.last_day_kwh = round(days[newest] / 1000, 2)
            week = [v for d, v in days.items() if d > newest - timedelta(days=7)]
            data.last_7_days_kwh = round(sum(week) / 1000, 2)
        return data
