"""DataUpdateCoordinator for STIHL iMow v2."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import ImowAuth, ImowAuthError
from .api import ImowApi, ImowApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Job states where the mower is (or is about to be) actively working.
_ACTIVE_JOB_STATES = frozenset({
    "plannedJobRunning",
    "mowing",
    "manualMowing",
    "edgeMowing",
    "returning",
    "paused",
})

# Cached overallState values that often lag behind an active job.
_STALE_OVERALL_STATES = frozenset({
    "charging",
    "docked",
    "parked",
    "idle",
})

# Job states that imply the mower has left the dock (isDocked often lags in the cloud twin).
_UNDOCKED_JOB_STATES = frozenset({
    "plannedJobRunning",
    "manualJobRunning",
    "mowing",
    "manualMowing",
    "edgeMowing",
    "returning",
    "drivingToZone",
    "paused",
})


class ImowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches data for all mowers and computes derived fields."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth: ImowAuth,
        api: ImowApi,
        scan_interval_minutes: int,
        username: str,
        password: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self._auth = auth
        self._api = api
        self._username = username
        self._password = password
        self._entry = entry
        # mower_id → full merged data dict
        self.mowers: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # DataUpdateCoordinator overrides
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data for every mower."""
        try:
            return await self._fetch_all()
        except UpdateFailed as err:
            if self.data is not None:
                _LOGGER.warning(
                    "iMow update failed (%s) — keeping last known state", err
                )
                return self.data
            raise

    async def _fetch_all(self) -> dict[str, Any]:
        """Inner fetch — raises UpdateFailed on any unrecoverable error."""
        if self._auth.token_needs_refresh:
            _LOGGER.debug("Proactively refreshing token before poll")
            await self._try_refresh_and_retry()
        try:
            mowers = await self._api.get_mowers()
        except ImowAuthError:
            await self._try_refresh_and_retry()
            try:
                mowers = await self._api.get_mowers()
            except (ImowApiError, ImowAuthError) as err:
                raise UpdateFailed(str(err)) from err
        except ImowApiError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[str, Any] = {}

        for mower in mowers:
            mower_id = mower.get("id") or mower.get("deviceId") or mower.get("serialNumber")
            if not mower_id:
                continue
            try:
                dashboard = await self._api.get_dashboard(str(mower_id))
                plan = await self._api.get_mowing_plan(str(mower_id))
                stats = await self._api.get_statistics(str(mower_id))
            except ImowAuthError:
                await self._try_refresh_and_retry()
                try:
                    dashboard = await self._api.get_dashboard(str(mower_id))
                    plan = await self._api.get_mowing_plan(str(mower_id))
                    stats = await self._api.get_statistics(str(mower_id))
                except (ImowApiError, ImowAuthError) as err:
                    _LOGGER.warning(
                        "Could not fetch data for mower %s after re-auth: %s",
                        mower_id,
                        err,
                    )
                    continue
            except ImowApiError as err:
                _LOGGER.warning("Could not fetch data for mower %s: %s", mower_id, err)
                continue

            merged = {**mower, **dashboard}
            # Fix job times: API returns local device time without timezone.
            # Convert to proper UTC so HA displays the correct local time.
            tz_offset_s = merged.get("device", {}).get("deviceTimeZoneOffsetInSeconds", 0)
            if tz_offset_s and merged.get("job"):
                job = merged["job"]
                for _key in ("startTime", "endTime"):
                    _val = job.get(_key, "")
                    # Only fix naive strings (no Z, no +, no offset in time part)
                    if _val and "Z" not in _val and len(_val) <= 20 and "+" not in _val[10:]:
                        try:
                            _local = datetime.fromisoformat(_val)
                            _utc = (_local - timedelta(seconds=tz_offset_s)).replace(
                                tzinfo=timezone.utc
                            )
                            job[_key] = _utc.isoformat()
                        except ValueError:
                            pass
            merged["_plan"] = plan
            merged["_nextStart"] = self._compute_next_start(plan, merged)
            merged["_defaultDuration"] = max(int(merged.get("setting", {}).get("defaultManualMowingDuration", 10800) or 10800), 10800)
            self._resolve_overall_state(merged)
            self._resolve_docked(merged)
            if stats:
                merged["statistics"] = stats
            # Resolve device display name: nickname > type > fallback
            merged["_deviceName"] = (
                merged.get("setting", {}).get("deviceNickname")
                or merged.get("device", {}).get("type")
                or f"iMow {str(mower_id)[-6:]}"
            )
            result[str(mower_id)] = merged
            self.mowers[str(mower_id)] = merged

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _try_refresh_and_retry(self) -> None:
        """Refresh the access token, falling back to full re-login if needed."""
        try:
            await self._auth.refresh()
            _LOGGER.debug("Token refreshed successfully")
            self._persist_auth_tokens()
            return
        except Exception as err:
            _LOGGER.warning("Token refresh failed (%s), attempting full re-login", err)
        try:
            await self._auth.login(self._username, self._password)
            _LOGGER.info("Re-login successful")
            self._persist_auth_tokens()
        except ImowAuthError as err:
            raise UpdateFailed(f"Re-authentication failed: {err}") from err

    def _persist_auth_tokens(self) -> None:
        rt = self._auth.refresh_token
        if rt and rt != self._entry.data.get("refresh_token"):
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, "refresh_token": rt},
            )

    @staticmethod
    def _resolve_overall_state(mower: dict) -> None:
        """Align device.overallState with job when the cloud twin is inconsistent.

        STIHL often returns job.state=plannedJobRunning while device.overallState
        still says charging (especially on cached dashboard data without force-update).
        """
        job_state = (mower.get("job") or {}).get("state")
        if job_state not in _ACTIVE_JOB_STATES:
            return

        device = mower.setdefault("device", {})
        overall = dict(device.get("overallState") or {})
        raw_state = overall.get("state")
        is_docked = device.get("isDocked")

        # isDocked often lags while the mower is already mowing — trust job state.
        if raw_state in _STALE_OVERALL_STATES:
            _LOGGER.debug(
                "Correcting stale overallState %s -> mowing (job=%s, isDocked=%s)",
                raw_state,
                job_state,
                is_docked,
            )
            overall["state"] = "mowing"

        device["overallState"] = overall

    @staticmethod
    def _resolve_docked(mower: dict) -> None:
        """Clear stale isDocked when job state shows the mower is working."""
        job_state = (mower.get("job") or {}).get("state")
        if job_state not in _UNDOCKED_JOB_STATES:
            return
        device = mower.setdefault("device", {})
        if device.get("isDocked"):
            _LOGGER.debug("Correcting stale isDocked -> False (job=%s)", job_state)
            device["isDocked"] = False

    @staticmethod
    def _compute_next_start(plan: dict, mower: dict) -> str | None:
        """Return ISO-8601 timestamp of next scheduled mow start.

        The Gen5+ API already provides the next job start time in job.startTime,
        so we use that directly. When state is nextPlannedJobAvailable it is the
        future start; when mowing it is the current job start.
        """
        job = mower.get("job", {})
        return job.get("startTime")

    # ------------------------------------------------------------------
    # Command helpers (used by button/select entities)
    # ------------------------------------------------------------------

    async def async_start_mowing(self, mower_id: str) -> None:
        await self._api.send_command(mower_id, "startMowing")
        await self.async_request_refresh()

    async def async_stop_mowing(self, mower_id: str) -> None:
        await self._api.send_command(mower_id, "stopMowing")
        await self.async_request_refresh()

    async def async_park(self, mower_id: str) -> None:
        await self._api.send_command(mower_id, "park")
        await self.async_request_refresh()
