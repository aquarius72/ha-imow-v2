"""STIHL iMow v2 Home Assistant integration (Gen5+)."""
from __future__ import annotations

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import ImowAuth, ImowAuthError
from .api import ImowApi
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import ImowCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iMow from a config entry."""
    session = async_get_clientsession(hass)
    auth = ImowAuth(session)

    # Restore tokens from stored data (no full login needed on restart)
    if entry.data.get("refresh_token"):
        auth.refresh_token = entry.data["refresh_token"]
        try:
            await auth.refresh()
        except ImowAuthError:
            _LOGGER.warning("Token refresh failed, falling back to full login")
            await auth.login(entry.data["username"], entry.data["password"])
    else:
        await auth.login(entry.data["username"], entry.data["password"])

    # Persist refreshed tokens
    if auth.refresh_token and auth.refresh_token != entry.data.get("refresh_token"):
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "refresh_token": auth.refresh_token},
        )

    api = ImowApi(session, auth)
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = ImowCoordinator(
        hass,
        auth,
        api,
        scan_interval,
        entry.data["username"],
        entry.data["password"],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
