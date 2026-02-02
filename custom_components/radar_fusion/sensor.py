"""Sensor platform for Radar Fusion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SENSORS, DOMAIN
from .coordinator import RadarFusionCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Radar Fusion sensor entities."""
    coordinator: RadarFusionCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = config_entry.data.get(CONF_SENSORS, [])

    entities: list[SensorEntity] = []
    for idx, sensor_config in enumerate(sensors):
        # Add target count sensor for each radar sensor
        entities.append(
            RadarSensorTargetCount(coordinator, config_entry, sensor_config, idx)
        )
        # Add target positions sensor for debugging
        entities.append(
            RadarSensorTargetPositions(coordinator, config_entry, sensor_config, idx)
        )

    async_add_entities(entities)


class RadarSensorTargetCount(CoordinatorEntity[RadarFusionCoordinator], SensorEntity):
    """Sensor showing number of targets detected by a radar sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "targets"
    _attr_icon = "mdi:target"

    def __init__(
        self,
        coordinator: RadarFusionCoordinator,
        config_entry: ConfigEntry,
        sensor_config: dict[str, Any],
        idx: int,
    ) -> None:
        """Initialize the target count sensor."""
        super().__init__(coordinator)

        self._sensor_config = sensor_config
        self._sensor_idx = idx
        sensor_unique_id = f"{config_entry.entry_id}_sensor_{idx}"

        # Entity attributes
        self._attr_name = "Target count"
        self._attr_unique_id = f"{config_entry.entry_id}_sensor_{idx}_target_count"

        # Associate with the sensor device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, sensor_unique_id)},
        )

    @property
    def native_value(self) -> int:
        """Return the number of targets detected by this sensor."""
        if not self.coordinator.data:
            return 0

        target_entities = self._sensor_config.get("target_entities", [])
        if not target_entities:
            return 0

        # Count targets from this sensor across all floors
        all_targets = self.coordinator.data.get("all_targets", [])
        return sum(
            1
            for target in all_targets
            if any(
                entity in target.get("sensor_entities", [])
                for entity in target_entities
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "sensor_index": self._sensor_idx,
            "target_entities": self._sensor_config.get("target_entities", []),
        }


class RadarSensorTargetPositions(
    CoordinatorEntity[RadarFusionCoordinator], SensorEntity
):
    """Sensor showing target positions detected by a radar sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(
        self,
        coordinator: RadarFusionCoordinator,
        config_entry: ConfigEntry,
        sensor_config: dict[str, Any],
        idx: int,
    ) -> None:
        """Initialize the target positions sensor."""
        super().__init__(coordinator)

        self._sensor_config = sensor_config
        self._sensor_idx = idx
        sensor_unique_id = f"{config_entry.entry_id}_sensor_{idx}"

        # Entity attributes
        self._attr_name = "Target positions"
        self._attr_unique_id = f"{config_entry.entry_id}_sensor_{idx}_target_positions"

        # Associate with the sensor device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, sensor_unique_id)},
        )

    @property
    def native_value(self) -> str:
        """Return a summary of target positions."""
        if not self.coordinator.data:
            return "No data"

        target_entities = self._sensor_config.get("target_entities", [])
        if not target_entities:
            return "No targets"

        # Get targets from this sensor across all floors
        all_targets = self.coordinator.data.get("all_targets", [])
        targets = [
            target
            for target in all_targets
            if any(
                entity in target.get("sensor_entities", [])
                for entity in target_entities
            )
        ]

        if not targets:
            return "No targets detected"

        # Show count as state
        return f"{len(targets)} active"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return target positions and details."""
        if not self.coordinator.data:
            return {}

        target_entities = self._sensor_config.get("target_entities", [])
        if not target_entities:
            return {}

        # Get targets from this sensor across all floors
        all_targets = self.coordinator.data.get("all_targets", [])
        targets = [
            target
            for target in all_targets
            if any(
                entity in target.get("sensor_entities", [])
                for entity in target_entities
            )
        ]

        # Format target data for attributes
        target_data = []
        for i, target in enumerate(targets):
            target_data.append(
                {
                    "target_num": i + 1,
                    "x": target.get("x"),
                    "y": target.get("y"),
                    "floor_id": target.get("floor_id"),
                    "age_seconds": round(target.get("age_seconds", 0), 2),
                }
            )

        return {
            "sensor_index": self._sensor_idx,
            "target_count": len(targets),
            "targets": target_data,
        }
