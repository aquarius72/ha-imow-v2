"""STIHL iMow REST API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .auth import ImowAuth, ImowAuthError
from .const import (
    APIM_KEY,
    API_COMMAND,
    API_DASHBOARD,
    API_MOWERS,
    API_MOWING_PLAN,
    API_STATISTICS,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

_COMMON_HEADERS = {
    "Ocp-Apim-Subscription-Key": APIM_KEY,
    "Accept": "application/json",
    "User-Agent": USER_AGENT,
}


class ImowApiError(Exception):
    """Raised for non-auth API errors."""


class ImowApi:
    """Thin wrapper around the STIHL APIM REST endpoints."""

    def __init__(self, session: aiohttp.ClientSession, auth: ImowAuth) -> None:
        self._session = session
        self._auth = auth

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_mowers(self) -> list[dict[str, Any]]:
        """Return list of mowers registered to the account."""
        data = await self._get(API_MOWERS)
        if isinstance(data, list):
            return data
        return data.get("mowers", [data]) if isinstance(data, dict) else []

    async def get_dashboard(self, mower_id: str) -> dict[str, Any]:
        """Return current mower status (forces a cloud refresh)."""
        url = API_DASHBOARD.format(id=mower_id)
        return await self._get(url)

    async def get_mowing_plan(self, mower_id: str) -> dict[str, Any]:
        """Return the mowing plan / calendar for the mower."""
        url = API_MOWING_PLAN.format(id=mower_id)
        return await self._get(url)

    async def get_statistics(self, mower_id: str) -> dict[str, Any]:
        """Return mower usage statistics (best-effort; may return {} on older firmware)."""
        try:
            url = API_STATISTICS.format(id=mower_id)
            return await self._get(url)
        except ImowApiError:
            return {}

    async def send_command(self, mower_id: str, command: str, payload: dict | None = None) -> None:
        """Send a mower control command.

        Gen5+ commands (POST to mower-commands/{id}/{cmd}):
          start-mowing, pause, resume, end-job-and-return-to-dock,
          toDocking, edgeMowing, startMowingFromPoint
        """
        url = API_COMMAND.format(id=mower_id, cmd=command)
        await self._post(url, payload or {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, url: str) -> Any:
        headers = {**_COMMON_HEADERS, "Authorization": f"Bearer {self._auth.access_token}"}
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise ImowAuthError("401 from API — token expired")
            if resp.status >= 400:
                text = await resp.text()
                raise ImowApiError(f"GET {url} → {resp.status}: {text[:200]}")
            return await resp.json(content_type=None)

    async def _post(self, url: str, payload: dict) -> Any:
        headers = {
            **_COMMON_HEADERS,
            "Authorization": f"Bearer {self._auth.access_token}",
            "Content-Type": "application/json",
        }
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 401:
                raise ImowAuthError("401 from API — token expired")
            if resp.status >= 400:
                text = await resp.text()
                raise ImowApiError(f"POST {url} → {resp.status}: {text[:200]}")
            if resp.content_length:
                return await resp.json(content_type=None)
            return None
