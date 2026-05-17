"""Binary sensor platform for STIHL iMow v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ImowCoordinator


@dataclass(frozen=True, kw_only=True)
class ImowBinarySensorDescription(BinarySensorEntityDescription):
    value_path: tuple[str, ...]


BINARY_SENSOR_DESCRIPTIONS: tuple[ImowBinarySensorDescription, ...] = (
    ImowBinarySensorDescription(
        key="is_raining",
        name="Rain Sensor",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_path=("sensor", "sensorIsRaining"),
    ),
    ImowBinarySensorDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_path=("device", "isCurrentlyConnected"),
    ),
    ImowBinarySensorDescription(
        key="docked",
        name="Docked",
        icon="mdi:home",
        value_path=("device", "isDocked"),
    ),
    ImowBinarySensorDescription(
        key="software_update",
        name="Software Update Available",
        device_class=BinarySensorDeviceClass.UPDATE,
        value_path=("device", "isSoftwareUpdateAvailableForInstallation"),
    ),
)


def _deep_get(data: dict, path: tuple[str, ...]) -> Any:
    val = data
    for key in path:
        if not isinstance(val, dict):
            return None
        val = val.get(key)
    return val


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ImowCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ImowBinarySensor] = []
    for mower_id in coordinator.data:
        mower_data = coordinator.data[mower_id]
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(ImowBinarySensor(coordinator, mower_id, mower_data, desc))
    async_add_entities(entities)


class ImowBinarySensor(CoordinatorEntity[ImowCoordinator], BinarySensorEntity):
    """A binary sensor entity for an iMow mower."""

    entity_description: ImowBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImowCoordinator,
        mower_id: str,
        mower_data: dict[str, Any],
        description: ImowBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._mower_id = mower_id
        self._attr_unique_id = f"{mower_id}_{description.key}"

        device_name = mower_data.get("_deviceName") or f"iMow {mower_id[-6:]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
        )

    @property
    def is_on(self) -> bool | None:
        mower = self.coordinator.data.get(self._mower_id, {})
        val = _deep_get(mower, self.entity_description.value_path)
        if val is None:
            return None
        return bool(val)
