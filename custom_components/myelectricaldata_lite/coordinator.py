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
    statistic_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import MedAuthError, MedClient, MedError
from .const import (
    CHUNK_DAYS,
    CONF_HISTORY_VERSION,
    DOMAIN,
    HISTORY_DAYS,
    HISTORY_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PdlData:
    """Dernier jour connu et comparaisons pour un PDL."""

    last_day: date | None = None
    last_day_kwh: float | None = None
    last_7_days_kwh: float | None = None
    month_kwh: float | None = None
    month_last_year_kwh: float | None = None
    year_kwh: float | None = None
    year_last_year_kwh: float | None = None


def statistic_id(usage_point_id: str) -> str:
    return f"{DOMAIN}:consommation_{usage_point_id}"


def _local_midnight(day: date) -> datetime:
    return dt_util.start_of_local_day(datetime.combine(day, datetime.min.time()))


def _one_year_before(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 février
        return day.replace(year=day.year - 1, day=28)


class MedCoordinator(DataUpdateCoordinator[dict[str, PdlData]]):
    """Un appel par PDL et par mise à jour, sauf reconstruction de l'historique."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: MedClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.client = client
        self.usage_points: list[str] = []

    async def _async_update_data(self) -> dict[str, PdlData]:
        entry = self.config_entry
        rebuild = entry.data.get(CONF_HISTORY_VERSION, 1) < HISTORY_VERSION
        try:
            if not self.usage_points:
                pdls = await self.client.usage_points()
                self.usage_points = [p["usage_point_id"] for p in pdls]
            result = {}
            for usage_point_id in self.usage_points:
                result[usage_point_id] = await self._update_pdl(usage_point_id, rebuild)
        except MedAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MedError as err:
            raise UpdateFailed(str(err)) from err
        if rebuild:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_HISTORY_VERSION: HISTORY_VERSION}
            )
        return result

    async def _fetch_history(self, usage_point_id: str, today: date) -> dict[date, float]:
        """Tout l'historique disponible, par tranches ; une tranche trop ancienne est ignorée."""
        days: dict[date, float] = {}
        end = today
        oldest = today - timedelta(days=HISTORY_DAYS)
        while end > oldest:
            start = max(end - timedelta(days=CHUNK_DAYS), oldest)
            try:
                days.update(await self.client.daily_consumption(usage_point_id, start, end))
            except MedAuthError:
                raise
            except MedError as err:
                if not days:
                    raise
                _LOGGER.info("%s : historique arrêté avant %s (%s)", usage_point_id, end, err)
                break
            end = start
        return days

    async def _update_pdl(self, usage_point_id: str, rebuild: bool) -> PdlData:
        stat_id = statistic_id(usage_point_id)
        today = dt_util.now().date()
        recorder = get_instance(self.hass)
        last = await recorder.async_add_executor_job(
            get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
        )
        if last.get(stat_id) and not rebuild:
            row = last[stat_id][0]
            last_day = dt_util.as_local(dt_util.utc_from_timestamp(row["start"])).date()
            total = row["sum"] or 0.0
            start = min(last_day + timedelta(days=1), today - timedelta(days=7))
            days = await self.client.daily_consumption(usage_point_id, start, today)
        else:
            # Réimporte tout avec des sommes repartant de zéro : les lignes existantes
            # sont écrasées, la série reste cohérente.
            last_day, total = None, 0.0
            days = await self._fetch_history(usage_point_id, today)

        stats = []
        for day in sorted(days):
            if last_day is not None and day <= last_day:
                continue
            kwh = days[day] / 1000
            total += kwh
            stats.append(StatisticData(start=_local_midnight(day), state=kwh, sum=total))
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
            # Les comparaisons lisent les statistiques : attendre que l'import soit écrit.
            await recorder.async_block_till_done()

        data = PdlData()
        if not days:
            return data
        newest = max(days)
        data.last_day = newest
        data.last_day_kwh = round(days[newest] / 1000, 2)
        week = [v for d, v in days.items() if d > newest - timedelta(days=7)]
        data.last_7_days_kwh = round(sum(week) / 1000, 2)

        # Périodes arrêtées au dernier jour connu, comparées aux mêmes dates un an plus tôt.
        end = newest + timedelta(days=1)
        month_start = newest.replace(day=1)
        year_start = newest.replace(month=1, day=1)
        data.month_kwh = await self._change(stat_id, month_start, end)
        data.year_kwh = await self._change(stat_id, year_start, end)
        data.month_last_year_kwh = await self._change(
            stat_id, _one_year_before(month_start), _one_year_before(end)
        )
        data.year_last_year_kwh = await self._change(
            stat_id, _one_year_before(year_start), _one_year_before(end)
        )
        return data

    async def _change(self, stat_id: str, start: date, end: date) -> float | None:
        result = await get_instance(self.hass).async_add_executor_job(
            statistic_during_period,
            self.hass,
            _local_midnight(start),
            _local_midnight(end),
            stat_id,
            {"change"},
            None,
        )
        change = result.get("change")
        return None if change is None else round(change, 1)
