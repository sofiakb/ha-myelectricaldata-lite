"""Clients minimaux : passerelle MyElectricalData v2 (électricité) et GRDF (gaz)."""

from __future__ import annotations

from datetime import date
import json
import re
from typing import Any

import aiohttp

from .const import API_URL


class MedError(Exception):
    """Erreur de la source de données."""


class MedAuthError(MedError):
    """Identifiants refusés."""


class MedClient:
    """Linky via MyElectricalData : le secret sert directement de jeton Bearer."""

    label = "Linky"
    stat_prefix = "consommation"

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

    async def meters(self) -> list[str]:
        """PDL actifs du compte."""
        pdls = await self._get("/pdl") or []
        return [p["usage_point_id"] for p in pdls if p.get("is_active", True)]

    async def daily(self, meter: str, start: date, end: date) -> dict[date, float]:
        """Consommation par jour en kWh, de start inclus à end exclu."""
        data = await self._get(
            f"/enedis/consumption/daily/{meter}",
            {"start": start.isoformat(), "end": end.isoformat(), "use_cache": "true"},
        )
        days: dict[date, float] = {}
        for grandeur in (data or {}).get("grandeur", []):
            factor = 1 if grandeur.get("unite") == "kWh" else 0.001
            for point in grandeur.get("points", []):
                days[date.fromisoformat(point["d"][:10])] = float(point["v"]) * factor
        return days

    async def close(self) -> None:
        """Session partagée de HA : rien à fermer."""


GRDF_START_URL = "https://monespace.grdf.fr/"
GRDF_IDENTIFY_URL = "https://connexion.grdf.fr/idp/idx/identify"
GRDF_ANSWER_URL = "https://connexion.grdf.fr/idp/idx/challenge/answer"
GRDF_API_URL = "https://monespace.grdf.fr/api"
OKTA_HEADERS = {
    "Accept": "application/json; okta-version=1.0.0",
    "Content-Type": "application/json",
}


class GrdfClient:
    """Gazpar via l'espace client GRDF, même parcours de connexion que PyGazpar."""

    label = "Gazpar"
    stat_prefix = "gaz"

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        # Session dédiée : la connexion GRDF repose sur ses cookies.
        self._session = session
        self._username = username
        self._password = password
        self._logged_in = False

    async def _login(self) -> None:
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            async with self._session.get(GRDF_START_URL, timeout=timeout) as resp:
                html = await resp.text()
            match = re.search(r'"stateToken"\s*:\s*"([^"]+)"', html)
            if not match:
                raise MedError("jeton de connexion GRDF introuvable")
            state_token = match.group(1).replace("\\x2D", "-")

            self._session.cookie_jar.update_cookies({"ln": self._username})
            async with self._session.post(
                GRDF_IDENTIFY_URL,
                data=json.dumps({"identifier": self._username, "stateHandle": state_token}),
                headers=OKTA_HEADERS,
                timeout=timeout,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise MedAuthError(f"identifiant refusé (HTTP {resp.status})")
                resp.raise_for_status()
                state_handle = (await resp.json(content_type=None)).get("stateHandle")

            async with self._session.post(
                GRDF_ANSWER_URL,
                data=json.dumps(
                    {"credentials": {"passcode": self._password}, "stateHandle": state_handle}
                ),
                headers=OKTA_HEADERS,
                timeout=timeout,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise MedAuthError(f"mot de passe refusé (HTTP {resp.status})")
                resp.raise_for_status()
                success_url = (await resp.json(content_type=None))["success"]["href"]

            async with self._session.get(success_url, timeout=timeout) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, KeyError, ValueError) as err:
            raise MedError(f"connexion GRDF : {err}") from err
        self._logged_in = True

    async def _get(self, path: str, params: dict[str, str] | list[tuple[str, str]]) -> Any:
        if not self._logged_in:
            await self._login()
        try:
            async with self._session.get(
                f"{GRDF_API_URL}{path}", params=params, timeout=aiohttp.ClientTimeout(total=90)
            ) as resp:
                if "text/html" in resp.headers.get("Content-Type", ""):
                    raise MedError(f"réponse HTML de GRDF sur {path}")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise MedError(str(err)) from err

    async def meters(self) -> list[str]:
        """PCE du compte."""
        pces = await self._get("/e-conso/pce", {"details": "false"})
        return [p["idObject"] for p in pces]

    async def daily(self, meter: str, start: date, end: date) -> dict[date, float]:
        """Énergie consommée par journée gazière, en kWh."""
        data = await self._get(
            "/e-conso/pce/consommation/informatives",
            [
                ("dateDebut", start.isoformat()),
                ("dateFin", end.isoformat()),
                ("pceList[]", meter),
            ],
        )
        days: dict[date, float] = {}
        if not isinstance(data, dict):
            return days
        for releve in (data.get(meter) or {}).get("releves", []):
            energy = releve.get("energieConsomme")
            if energy is None or not releve.get("journeeGaziere"):
                continue
            day = date.fromisoformat(releve["journeeGaziere"][:10])
            if start <= day < end:
                days[day] = float(energy)
        return days

    async def close(self) -> None:
        """Oublie la connexion ; la session appartient à Home Assistant, qui la ferme."""
        self._session.cookie_jar.clear()
        self._logged_in = False
