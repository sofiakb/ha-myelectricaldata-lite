"""Client minimal de la passerelle MyElectricalData v2."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp

from .const import API_URL


class MedError(Exception):
    """Erreur de la passerelle."""


class MedAuthError(MedError):
    """Secret refusé."""


class MedClient:
    """Le secret sert directement de jeton Bearer."""

    def __init__(self, session: aiohttp.ClientSession, secret: str) -> None:
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {secret}",
            "Accept": "application/json",
            "X-MED-Format": "2026",
        }

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{API_URL}{path}",
                headers=self._headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status in (401, 403):
                    raise MedAuthError(f"HTTP {resp.status}")
                if resp.status == 429:
                    raise MedError("quota dépassé (HTTP 429)")
                resp.raise_for_status()
                body = await resp.json()
        except aiohttp.ClientError as err:
            raise MedError(str(err)) from err
        # PARTIAL_DATA arrive avec success=true et des données : on les garde.
        if not body.get("success") and not body.get("data"):
            error = body.get("error") or {}
            raise MedError(error.get("code") or "réponse invalide")
        return body.get("data")

    async def usage_points(self) -> list[dict[str, Any]]:
        """PDL actifs du compte."""
        pdls = await self._get("/pdl") or []
        return [p for p in pdls if p.get("is_active", True)]

    async def daily_consumption(
        self, usage_point_id: str, start: date, end: date
    ) -> dict[date, float]:
        """Consommation par jour en Wh, de start inclus à end exclu."""
        data = await self._get(
            f"/enedis/consumption/daily/{usage_point_id}",
            {"start": start.isoformat(), "end": end.isoformat(), "use_cache": "true"},
        )
        days: dict[date, float] = {}
        for grandeur in (data or {}).get("grandeur", []):
            factor = 1000 if grandeur.get("unite") == "kWh" else 1
            for point in grandeur.get("points", []):
                days[date.fromisoformat(point["d"][:10])] = float(point["v"]) * factor
        return days
