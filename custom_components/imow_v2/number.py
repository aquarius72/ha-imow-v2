"""Number platform for STIHL iMow v2 — exposes configurable mowing duration."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ImowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ImowCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for mower_id, mower_data in coordinator.data.items():
        entities.append(ImowMowingDurationNumber(coordinator, mower_id, mower_data))
    async_add_entities(entities)


class ImowMowingDurationNumber(CoordinatorEntity[ImowCoordinator], NumberEntity, RestoreEntity):
    """Number entity for default manual mowing duration (minutes)."""

    _attr_has_entity_name = True
    _attr_name = "Default Mowing Duration"
    _attr_icon = "mdi:timer-edit"
    _attr_native_min_value = 1
    _attr_native_max_value = 480
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: ImowCoordinator, mower_id: str, mower_data: dict) -> None:
        super().__init__(coordinator)
        self._mower_id = mower_id
        self._attr_unique_id = f"{mower_id}_default_mowing_duration"
        self._current_value: float | None = None

        device_name = mower_data.get("_deviceName") or f"iMow {mower_id[-6:]}"
        model = mower_data.get("device", {}).get("type") or "STIHL iMow Gen5+"
        sw = mower_data.get("setting", {}).get("deviceSoftwarePackageVersionInstalled")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=sw,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restore previous value, fall back to device default
        if (last_state := await self.async_get_last_state()) and last_state.state not in (
            None, "unknown", "unavailable"
        ):
            try:
                self._current_value = float(last_state.state)
                return
            except ValueError:
                pass
        # Use device's configured default (seconds → minutes)
        mower = self.coordinator.data.get(self._mower_id, {})
        default_s = mower.get("_defaultDuration", 10800)
        self._current_value = round(default_s / 60)

    @property
    def native_value(self) -> float | None:
        return self._current_value

    async def async_set_native_value(self, value: float) -> None:
        self._current_value = value
        self.async_write_ha_state()
