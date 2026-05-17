"""Device tracker platform — shows the mower on the HA map."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ImowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ImowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ImowTrackerEntity(coordinator, mower_id, coordinator.data[mower_id])
        for mower_id in coordinator.data
    )


class ImowTrackerEntity(CoordinatorEntity[ImowCoordinator], TrackerEntity):
    """Represents the mower as a GPS device tracker."""

    _attr_has_entity_name = True
    _attr_name = "Location"
    _attr_icon = "mdi:robot-mower"

    def __init__(self, coordinator: ImowCoordinator, mower_id: str, mower_data: dict) -> None:
        super().__init__(coordinator)
        self._mower_id = mower_id
        self._attr_unique_id = f"{mower_id}_tracker"

        device_name = mower_data.get("_deviceName") or f"iMow {mower_id[-6:]}"
        model = mower_data.get("device", {}).get("type") or "STIHL iMow Gen5+"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=model,
        )

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._get_gps("latitude", "lat", "Latitude")

    @property
    def longitude(self) -> float | None:
        return self._get_gps("longitude", "lng", "lon", "Longitude")

    @property
    def location_accuracy(self) -> int:
        mower = self.coordinator.data.get(self._mower_id, {})
        gps = mower.get("gps") or {}
        acc = gps.get("accuracy") or gps.get("Accuracy")
        return int(acc) if acc is not None else 10

    def _get_gps(self, *keys: str) -> float | None:
        mower = self.coordinator.data.get(self._mower_id, {})
        # Try top-level gps dict
        gps = mower.get("gps") or {}
        for k in keys:
            if gps.get(k) is not None:
                try:
                    return float(gps[k])
                except (ValueError, TypeError):
                    pass
        # Try coordinates at top level (some API versions)
        for k in keys:
            candidate = mower.get(f"coordinate{k.capitalize()}") or mower.get(k)
            if candidate is not None:
                try:
                    return float(candidate)
                except (ValueError, TypeError):
                    pass
        return None
