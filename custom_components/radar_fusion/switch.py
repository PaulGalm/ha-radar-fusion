"""Switch platform for Radar Fusion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_BLOCK_ZONES, CONF_FLOOR_ID, DOMAIN
from .coordinator import RadarFusionCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Radar Fusion block zone switches."""
    coordinator: RadarFusionCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    block_zones = config_entry.options.get(CONF_BLOCK_ZONES, [])

    entities = [
        RadarFusionBlockZoneSwitch(coordinator, config_entry, block_zone, idx)
        for idx, block_zone in enumerate(block_zones)
    ]

    async_add_entities(entities)


class RadarFusionBlockZoneSwitch(RestoreEntity, SwitchEntity):
    """Switch entity for block zone control."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RadarFusionCoordinator,
        config_entry: ConfigEntry,
        block_zone_config: dict[str, Any],
        idx: int,
    ) -> None:
        """Initialize the block zone switch."""
        self.coordinator = coordinator
        self._block_zone_config = block_zone_config
        self._zone_name = block_zone_config.get("name", f"Block Zone {idx + 1}")
        self._floor_id = block_zone_config.get(CONF_FLOOR_ID)

        # Entity attributes
        self._attr_name = f"{self._zone_name} Block"
        self._attr_unique_id = f"{config_entry.entry_id}_block_zone_{idx}"
        self._attr_is_on = False

        # Add device info to group block zone switches
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{config_entry.entry_id}_block_zones")},
            name="Radar Fusion Block Zones",
            manufacturer="Radar Fusion",
            model="Block Zones",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        # Extra state attributes
        self._attr_extra_state_attributes = {
            "floor_id": self._floor_id,
            "zone_name": self._zone_name,
            "block_zone_index": idx,
        }

    async def async_added_to_hass(self) -> None:
        """Restore last state when added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == "on"

        # Update coordinator with current state
        self.coordinator.update_block_zone_state(
            self.entity_id, self._attr_is_on or False
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the block zone on."""
        self._attr_is_on = True
        self.coordinator.update_block_zone_state(self.entity_id, True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the block zone off."""
        self._attr_is_on = False
        self.coordinator.update_block_zone_state(self.entity_id, False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
