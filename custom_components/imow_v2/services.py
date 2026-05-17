"""HA services for STIHL iMow v2.

Service: imow_v2.intent
  action (required): startMowing | start-mowing | pause | resume |
                     end-job-and-return-to-dock | toDocking | edgeMowing |
                     startMowingFromPoint
  mower_device (optional): device_id from device registry
  mower_name   (optional): friendly name of the mower device
  startpoint   (optional): zone/startpoint index for startMowingFromPoint
"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import ImowApi, ImowApiError
from .auth import ImowAuth, ImowAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Accepted action names (normalised to the Gen5+ mower-commands API values)
_ACTION_MAP = {
    # Gen5+ myimow API command names
    "start-mowing":               "start-mowing",
    "pause":                      "pause",
    "resume":                     "resume",
    "end-job-and-return-to-dock": "end-job-and-return-to-dock",
    "toDocking":                  "toDocking",
    "edgeMowing":                 "edgeMowing",
    "startMowingFromPoint":       "startMowingFromPoint",
    # Friendly aliases
    "startMowing":   "start-mowing",
    "start_mowing":  "start-mowing",
    "stop":          "end-job-and-return-to-dock",
    "stop_mowing":   "end-job-and-return-to-dock",
    "park":          "toDocking",
    "dock":          "toDocking",
    "edge":          "edgeMowing",
    "edge_mowing":   "edgeMowing",
}

INTENT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("mower_device"): cv.string,
            vol.Optional("mower_name"): cv.string,
            vol.Optional("startpoint"): vol.Any(cv.string, int),
            vol.Optional("duration"): vol.Coerce(int),
            vol.Required("action"): vol.In(list(_ACTION_MAP)),
        },
        cv.has_at_least_one_key("mower_device", "mower_name"),
    )
)


async def async_setup_services(hass, entry) -> None:
    """Register iMow services."""

    async def _intent(service_call):
        await _handle_intent(hass, entry, service_call)

    hass.services.async_register(DOMAIN, "intent", _intent, schema=INTENT_SCHEMA)


async def _handle_intent(hass, entry, service_call) -> None:
    data = service_call.data
    action_raw = data["action"]
    cmd = _ACTION_MAP[action_raw]

    # Resolve mower ID from device or name
    mower_id = await _resolve_mower_id(hass, entry, data)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    api: ImowApi = coordinator._api
    auth: ImowAuth = coordinator._auth

    payload: dict = {}
    if cmd in ("start-mowing", "startMowingFromPoint"):
        # Resolve duration: explicit call arg → number entity → device default
        default_dur = 10800
        try:
            coord_data = list(coordinator.data.values())[0]
            device_name = coord_data.get("_deviceName", "").lower().replace(" ", "_")
            entity_id = f"number.{device_name}_default_mowing_duration"
            state = hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                default_dur = int(float(state.state) * 60)
            else:
                default_dur = int(coord_data.get("_defaultDuration", 10800))
        except Exception:
            pass
        duration = int(data.get("duration", default_dur))
        if cmd in ("start-mowing", "startMowingFromPoint"):
            payload = {"durationInSeconds": duration}
            if cmd == "startMowingFromPoint" and "startpoint" in data:
                payload["mowingZoneId"] = int(data["startpoint"])
            # Both use the start-mowing endpoint
            cmd = "start-mowing"

    try:
        await api.send_command(mower_id, cmd, payload)
    except ImowAuthError:
        await auth.refresh()
        await api.send_command(mower_id, cmd, payload)
    except ImowApiError as err:
        raise HomeAssistantError(f"iMow command failed: {err}") from err

    await coordinator.async_request_refresh()
    _LOGGER.info("iMow intent '%s' sent to mower %s", cmd, mower_id)


async def _resolve_mower_id(hass, entry, data: dict) -> str:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    mower_ids = list(coordinator.data.keys())

    # By device registry ID
    if "mower_device" in data:
        registry = dr.async_get(hass)
        device = registry.async_get(data["mower_device"])
        if device:
            for domain, identifier in device.identifiers:
                if domain == DOMAIN and identifier in mower_ids:
                    return identifier
        raise HomeAssistantError(f"Device '{data['mower_device']}' not found in iMow devices")

    # By friendly name
    name_query = data["mower_name"].lower()
    for mid, mdata in coordinator.data.items():
        dev_name = (mdata.get("_deviceName") or "").lower()
        if name_query in dev_name:
            return mid

    # Fall back to first mower if only one
    if len(mower_ids) == 1:
        return mower_ids[0]

    raise HomeAssistantError(
        f"Could not find mower matching '{data.get('mower_name')}'. "
        f"Available mowers: {mower_ids}"
    )
