"""Binary sensor platform for Radar Fusion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FLOOR_ID, CONF_VERTICES, CONF_ZONES, DOMAIN, point_in_polygon
from .coordinator import RadarFusionCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Radar Fusion binary sensors."""
    coordinator: RadarFusionCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    zones = config_entry.options.get(CONF_ZONES, [])

    entities = [
        RadarFusionZoneSensor(coordinator, config_entry, zone, idx)
        for idx, zone in enumerate(zones)
    ]

    async_add_entities(entities)


class RadarFusionZoneSensor(
    CoordinatorEntity[RadarFusionCoordinator], BinarySensorEntity
):
    """Binary sensor for zone presence detection."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RadarFusionCoordinator,
        config_entry: ConfigEntry,
        zone_config: dict[str, Any],
        idx: int,
    ) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator)

        self._zone_config = zone_config
        self._zone_name = zone_config.get("name", f"Zone {idx + 1}")
        self._floor_id = zone_config.get(CONF_FLOOR_ID)
        self._vertices = zone_config.get(CONF_VERTICES, [])

        # Entity attributes
        self._attr_name = self._zone_name
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{idx}"

        # Add device info to group zone sensors
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{config_entry.entry_id}_zones")},
            name="Radar Fusion Zones",
            manufacturer="Radar Fusion",
            model="Detection Zones",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        # Extra state attributes
        self._attr_extra_state_attributes = {
            "floor_id": self._floor_id,
            "vertex_count": len(self._vertices),
            "zone_index": idx,
        }

    @property
    def is_on(self) -> bool:
        """Return true if zone is occupied."""
        if not self.coordinator.data:
            return False

        # Get targets for this floor
        targets = self.coordinator.get_targets_for_floor(self._floor_id)

        # Check if any target is in zone
        for target in targets:
            if point_in_polygon(target["x"], target["y"], self._vertices):
                return True

        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Zone is available if coordinator has data, even if last update had issues
        return self.coordinator.data is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update extra attributes with current target count
        if self.coordinator.data:
            targets = self.coordinator.get_targets_for_floor(self._floor_id)
            targets_in_zone = sum(
                1
                for target in targets
                if point_in_polygon(target["x"], target["y"], self._vertices)
            )

            self._attr_extra_state_attributes = {
                **self._attr_extra_state_attributes,
                "targets_in_zone": targets_in_zone,
                "floor_targets_total": len(targets),
            }

        super()._handle_coordinator_update()
