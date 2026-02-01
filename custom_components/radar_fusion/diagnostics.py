"""Diagnostics support for Radar Fusion."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FLOOR_ID,
    CONF_POSITION_X,
    CONF_POSITION_Y,
    CONF_TARGET_ENTITIES,
    DOMAIN,
    generate_ascii_map,
)
from .coordinator import RadarFusionCoordinator

TO_REDACT = {CONF_TARGET_ENTITIES}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RadarFusionCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Get all unique floor IDs
    floor_ids: set[str | None] = set()
    for sensor in coordinator.sensors:
        floor_ids.add(sensor.get(CONF_FLOOR_ID))
    for zone in coordinator.zones:
        floor_ids.add(zone.get(CONF_FLOOR_ID))
    for zone in coordinator.block_zones:
        floor_ids.add(zone.get(CONF_FLOOR_ID))

    # Generate ASCII maps for each floor
    ascii_maps = {}
    for floor_id in floor_ids:
        targets = coordinator.get_targets_for_floor(floor_id)

        # Prepare data for ASCII map
        sensors_data = [
            {
                CONF_POSITION_X: s.get(CONF_POSITION_X, 0),
                CONF_POSITION_Y: s.get(CONF_POSITION_Y, 0),
                CONF_FLOOR_ID: s.get(CONF_FLOOR_ID),
            }
            for s in coordinator.sensors
        ]

        zones_data = [
            {
                "name": z.get("name"),
                "vertices": z.get("vertices", []),
                CONF_FLOOR_ID: z.get(CONF_FLOOR_ID),
            }
            for z in coordinator.zones
        ]

        block_zones_data = [
            {
                "name": z.get("name"),
                "vertices": z.get("vertices", []),
                CONF_FLOOR_ID: z.get(CONF_FLOOR_ID),
            }
            for z in coordinator.block_zones
        ]

        targets_data = [
            {"x": t["x"], "y": t["y"], CONF_FLOOR_ID: t["floor_id"]} for t in targets
        ]

        ascii_maps[str(floor_id)] = generate_ascii_map(
            sensors_data,
            zones_data,
            block_zones_data,
            targets_data,
            floor_id,
        )

    # Compile diagnostics data
    diagnostics = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "coordinator_data": {
            "sensor_count": coordinator.data.get("sensor_count", 0)
            if coordinator.data
            else 0,
            "zone_count": coordinator.data.get("zone_count", 0)
            if coordinator.data
            else 0,
            "block_zone_count": coordinator.data.get("block_zone_count", 0)
            if coordinator.data
            else 0,
        },
        "targets_summary": {},
        "ascii_maps": ascii_maps,
    }

    # Add per-floor target summary
    if coordinator.data:
        for floor_id in floor_ids:
            targets = coordinator.get_targets_for_floor(floor_id)
            all_targets = [
                t
                for t in coordinator.data.get("all_targets", [])
                if t.get(CONF_FLOOR_ID) == floor_id
            ]

            diagnostics["targets_summary"][str(floor_id)] = {
                "total_detected": len(all_targets),
                "after_filtering": len(targets),
                "stale_count": len(all_targets) - len(targets),
                "targets": [
                    {
                        "x": round(t["x"], 2),
                        "y": round(t["y"], 2),
                        "local_x": round(t["local_x"], 2),
                        "local_y": round(t["local_y"], 2),
                        "age_seconds": round(t["age_seconds"], 2),
                    }
                    for t in targets
                ],
            }

    return diagnostics
