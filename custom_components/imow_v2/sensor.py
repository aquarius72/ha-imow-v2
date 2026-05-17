"""Sensor platform for STIHL iMow v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from datetime import datetime, timezone

UNIT_SQUARE_METERS = "m²"  # UnitOfArea not in all HA versions


def _parse_dt(v: object) -> datetime | None:
    """Parse an ISO-8601 string to a timezone-aware datetime for HA timestamp sensors."""
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ImowCoordinator


@dataclass(frozen=True, kw_only=True)
class ImowSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a key path into mower data dict."""
    value_path: tuple[str, ...]  # nested key path, e.g. ("battery", "level")
    transform: Any = None        # optional callable to post-process the raw value


def _deep_get(data: dict, path: tuple[str, ...]) -> Any:
    val = data
    for key in path:
        if not isinstance(val, dict):
            return None
        val = val.get(key)
    return val


def _fmt_seconds(v) -> str | None:
    """Convert seconds to a human-readable string like '1130 h 37 min'."""
    if v is None:
        return None
    try:
        total = int(v)
    except (ValueError, TypeError):
        return None
    h, remainder = divmod(total, 3600)
    m = remainder // 60
    return f"{h} h {m} min"


SENSOR_DESCRIPTIONS: tuple[ImowSensorDescription, ...] = (
    # ── Status ──────────────────────────────────────────────────────────
    ImowSensorDescription(
        key="job_state",
        name="Job State",
        icon="mdi:state-machine",
        value_path=("job", "state"),
    ),
    ImowSensorDescription(
        key="overall_state",
        name="Overall State",
        icon="mdi:robot-mower",
        value_path=("device", "overallState", "state"),
    ),
    ImowSensorDescription(
        key="state_trigger",
        name="State Trigger",
        icon="mdi:message-text",
        value_path=("device", "overallState", "trigger"),
    ),
    ImowSensorDescription(
        key="machine_error",
        name="Error Code",
        icon="mdi:lightning-bolt-outline",
        value_path=("device", "errorsActive"),
        transform=lambda v: v[0] if isinstance(v, list) and v else None,
    ),
    # ── Battery ─────────────────────────────────────────────────────────
    ImowSensorDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path=("battery", "level"),
        transform=lambda v: round(float(v) * 100) if v is not None else None,
    ),
    # ── GPS ─────────────────────────────────────────────────────────────
    ImowSensorDescription(
        key="gps_latitude",
        name="GPS Latitude",
        icon="mdi:latitude",
        value_path=("gps", "latitude"),
    ),
    ImowSensorDescription(
        key="gps_longitude",
        name="GPS Longitude",
        icon="mdi:longitude",
        value_path=("gps", "longitude"),
    ),
    # ── Job times ───────────────────────────────────────────────────────
    ImowSensorDescription(
        key="job_start_time",
        name="Job Start Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
        value_path=("job", "startTime"),
        transform=_parse_dt,
    ),
    ImowSensorDescription(
        key="job_end_time",
        name="Job End Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-end",
        value_path=("job", "endTime"),
        transform=_parse_dt,
    ),
    ImowSensorDescription(
        key="next_start",
        name="Next Scheduled Start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
        value_path=("_nextStart",),
        transform=_parse_dt,
    ),
    ImowSensorDescription(
        key="last_seen",
        name="Last Seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check",
        value_path=("device", "lastConnectionStateUpdate"),
        transform=_parse_dt,
    ),
    # ── Device info ─────────────────────────────────────────────────────
    ImowSensorDescription(
        key="area",
        name="Current Area",
        icon="mdi:map-marker-radius",
        value_path=("device", "currentArea"),
    ),
    ImowSensorDescription(
        key="model",
        name="Model",
        icon="mdi:robot-mower",
        value_path=("device", "type"),
    ),
    ImowSensorDescription(
        key="timezone",
        name="Time Zone",
        icon="mdi:map-clock-outline",
        value_path=("device", "deviceTimeZone"),
    ),
    ImowSensorDescription(
        key="firmware",
        name="Firmware",
        icon="mdi:information-outline",
        value_path=("setting", "deviceSoftwarePackageVersionInstalled"),
    ),
    ImowSensorDescription(
        key="nickname",
        name="Nickname",
        icon="mdi:tag",
        value_path=("setting", "deviceNickname"),
    ),
    # ── Statistics ──────────────────────────────────────────────────────
    ImowSensorDescription(
        key="stat_total_operating_time",
        name="Total Operating Time",
        icon="mdi:watch",
        value_path=("statistics", "totalWorkingSeconds"),
        transform=lambda v: _fmt_seconds(v),
    ),
    ImowSensorDescription(
        key="stat_total_distance",
        name="Total Distance",
        icon="mdi:map-marker-distance",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_path=("statistics", "totalDrivenDistance"),
        transform=lambda v: round(int(v) / 1000, 1) if v is not None else None,
    ),
    ImowSensorDescription(
        key="stat_blade_time",
        name="Blade Operating Time",
        icon="mdi:knife",
        value_path=("statistics", "totalWorkingTimeOfCurrentCuttingKnifes"),
        transform=lambda v: _fmt_seconds(v),
    ),
    ImowSensorDescription(
        key="stat_total_jobs",
        name="Total Mowing Jobs",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_path=("statistics", "totalStartedMowingJobs"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ImowCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ImowSensor] = []
    for mower_id in coordinator.data:
        mower_data = coordinator.data[mower_id]
        for desc in SENSOR_DESCRIPTIONS:
            entities.append(ImowSensor(coordinator, mower_id, mower_data, desc))

    async_add_entities(entities)


class ImowSensor(CoordinatorEntity[ImowCoordinator], SensorEntity):
    """A single sensor entity for an iMow mower."""

    entity_description: ImowSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImowCoordinator,
        mower_id: str,
        mower_data: dict[str, Any],
        description: ImowSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._mower_id = mower_id
        self._attr_unique_id = f"{mower_id}_{description.key}"
        # Store these directly to avoid HA entity descriptor lookup issues
        self._value_path = description.value_path
        self._transform = description.transform

        device_name = mower_data.get("_deviceName") or f"iMow {mower_id[-6:]}"
        model = (
            mower_data.get("device", {}).get("type")
            or mower_data.get("device", {}).get("modelDescription")
            or "STIHL iMow Gen5+"
        )
        sw = mower_data.get("setting", {}).get("deviceSoftwarePackageVersionInstalled")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=sw,
        )

    @property
    def native_value(self) -> Any:
        mower = self.coordinator.data.get(self._mower_id, {})
        raw = _deep_get(mower, self._value_path)
        if raw is None:
            return None
        if self._transform:
            return self._transform(raw)
        return raw
