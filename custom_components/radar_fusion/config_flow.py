"""Config flow for the Radar Fusion integration."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_BLOCK_ZONES,
    CONF_FLOOR_ID,
    CONF_POSITION_X,
    CONF_POSITION_Y,
    CONF_ROTATION,
    CONF_SENSORS,
    CONF_STALENESS_TIMEOUT,
    CONF_TARGET_ENTITIES,
    CONF_TEST_MODE,
    CONF_VERTICES,
    CONF_ZONES,
    DEFAULT_NAME,
    DEFAULT_STALENESS_TIMEOUT,
    DOMAIN,
    parse_vertices,
)


class RadarFusionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radar Fusion."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow one config entry for this integration
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={CONF_SENSORS: []},
                options={
                    CONF_ZONES: [],
                    CONF_BLOCK_ZONES: [],
                    CONF_STALENESS_TIMEOUT: user_input.get(
                        CONF_STALENESS_TIMEOUT, DEFAULT_STALENESS_TIMEOUT
                    ),
                    CONF_TEST_MODE: user_input.get(CONF_TEST_MODE, False),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(
                        CONF_STALENESS_TIMEOUT, default=DEFAULT_STALENESS_TIMEOUT
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=300, unit_of_measurement="seconds"
                        )
                    ),
                    vol.Optional(
                        CONF_TEST_MODE, default=False
                    ): selector.BooleanSelector(),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RadarFusionOptionsFlow:
        """Get the options flow for this handler."""
        return RadarFusionOptionsFlow()


class RadarFusionOptionsFlow(OptionsFlow):
    """Handle options flow for Radar Fusion."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._sensors: list[dict[str, Any]] = []
        self._zones: list[dict[str, Any]] = []
        self._block_zones: list[dict[str, Any]] = []
        self._edit_index: int | None = None

    def _build_zone_schema(
        self, current_zone: dict[str, Any] | None = None
    ) -> vol.Schema:
        """Build schema for zone forms."""
        if current_zone is None:
            return vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Optional(CONF_FLOOR_ID): selector.FloorSelector(),
                    vol.Required(CONF_VERTICES): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            )

        # Edit mode: build schema with defaults
        vertices = current_zone.get(CONF_VERTICES, [])
        vertices_str = json.dumps(vertices) if vertices else "[]"

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_NAME, default=current_zone.get(CONF_NAME, "")): str,
        }

        floor_id = current_zone.get(CONF_FLOOR_ID)
        if floor_id is not None:
            schema_dict[vol.Optional(CONF_FLOOR_ID, default=floor_id)] = (
                selector.FloorSelector()
            )
        else:
            schema_dict[vol.Optional(CONF_FLOOR_ID)] = selector.FloorSelector()

        schema_dict[vol.Required(CONF_VERTICES, default=vertices_str)] = (
            selector.TextSelector(selector.TextSelectorConfig(multiline=True))
        )

        return vol.Schema(schema_dict)

    def _get_zone_label(self, zone: dict[str, Any]) -> str:
        """Generate display label for a zone."""
        return f"{zone.get(CONF_NAME)} (Floor: {zone.get(CONF_FLOOR_ID, 'None')})"

    def _validate_zone_name(
        self,
        zone_name: str,
        floor_id: str | None,
        zones: list[dict[str, Any]],
        exclude_index: int | None = None,
    ) -> bool:
        """Check if zone name is unique on the floor."""
        existing_names = [
            z[CONF_NAME]
            for i, z in enumerate(zones)
            if z.get(CONF_FLOOR_ID) == floor_id and i != exclude_index
        ]
        return zone_name not in existing_names

    def _get_target_entities_from_device(self, device_id: str) -> list[str]:
        """Get target entities from a device."""
        entity_registry = er.async_get(self.hass)
        target_entities = []

        # Find all entities for this device
        entities = er.async_entries_for_device(entity_registry, device_id)

        # Look for target entities (target1_x, target1_y, target2_x, etc.)
        for entity in entities:
            if entity.domain == "sensor" and entity.entity_id:
                entity_id = entity.entity_id
                # Check if it matches the target pattern
                if "target" in entity_id.lower() and entity_id.endswith(("_x", "_y")):
                    target_entities.append(entity_id)

        # Sort to ensure consistent order: target1_x, target1_y, target2_x, etc.
        target_entities.sort()
        return target_entities

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["sensors", "zones", "block_zones", "settings"],
        )

    # Sensor management
    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage sensors."""
        self._sensors = self.config_entry.data.get(CONF_SENSORS, []).copy()
        return self.async_show_menu(
            step_id="sensors",
            menu_options=["add_sensor", "edit_sensor", "remove_sensor"],
        )

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new sensor."""
        errors = {}

        if user_input is not None:
            try:
                # Get device and auto-discover target entities
                device_id = user_input["device_id"]
                target_entities = self._get_target_entities_from_device(device_id)

                if not target_entities:
                    errors["base"] = "no_target_entities"
                elif len(target_entities) != 6:
                    errors["base"] = "invalid_target_count"
                else:
                    sensor_config = {
                        CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                        CONF_POSITION_X: user_input[CONF_POSITION_X],
                        CONF_POSITION_Y: user_input[CONF_POSITION_Y],
                        CONF_ROTATION: user_input.get(CONF_ROTATION, 0),
                        CONF_TARGET_ENTITIES: target_entities,
                    }
                    self._sensors.append(sensor_config)

                    # Update config entry data
                    new_data = {**self.config_entry.data, CONF_SENSORS: self._sensors}
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )

                    return await self.async_step_sensors()
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FLOOR_ID): selector.FloorSelector(),
                    vol.Required(CONF_POSITION_X, default=0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10000, max=10000, unit_of_measurement="mm"
                        )
                    ),
                    vol.Required(CONF_POSITION_Y, default=0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10000, max=10000, unit_of_measurement="mm"
                        )
                    ),
                    vol.Optional(CONF_ROTATION, default=0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=359, unit_of_measurement="degrees"
                        )
                    ),
                    vol.Required("device_id"): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(
                            entity=[
                                selector.EntityFilterSelectorConfig(domain="sensor")
                            ]
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing sensor."""
        self._sensors = self.config_entry.data.get(CONF_SENSORS, []).copy()

        if not self._sensors:
            return await self.async_step_sensors()

        # First step: select which sensor to edit
        if self._edit_index is None:
            if user_input is not None:
                # Extract index from selection like "0: Floor None - Position..."
                selected = user_input["sensor_index"]
                self._edit_index = int(selected.split(":")[0])
                return await self.async_step_edit_sensor_form()

            sensor_options = [
                f"{i}: Floor {s.get(CONF_FLOOR_ID, 'None')} - "
                f"Position ({s.get(CONF_POSITION_X)}, {s.get(CONF_POSITION_Y)})"
                for i, s in enumerate(self._sensors)
            ]

            return self.async_show_form(
                step_id="edit_sensor",
                data_schema=vol.Schema(
                    {
                        vol.Required("sensor_index"): selector.SelectSelector(
                            selector.SelectSelectorConfig(options=sensor_options)
                        ),
                    }
                ),
            )

        return await self.async_step_edit_sensor_form(user_input)

    async def async_step_edit_sensor_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor form with current values."""
        errors = {}

        if user_input is not None:
            try:
                # Validate target entities
                target_entities = user_input[CONF_TARGET_ENTITIES]
                if len(target_entities) != 6:
                    errors["base"] = "invalid_target_count"
                elif self._edit_index is None:
                    # Update the sensor at the edit index - internal error
                    errors["base"] = "internal_error"
                else:
                    idx = self._edit_index
                    assert isinstance(idx, int)
                    self._sensors[idx] = {
                        CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                        CONF_POSITION_X: user_input[CONF_POSITION_X],
                        CONF_POSITION_Y: user_input[CONF_POSITION_Y],
                        CONF_ROTATION: user_input.get(CONF_ROTATION, 0),
                        CONF_TARGET_ENTITIES: target_entities,
                    }

                    new_data = {
                        **self.config_entry.data,
                        CONF_SENSORS: self._sensors,
                    }
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )

                    self._edit_index = None
                    return await self.async_step_sensors()
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"

        # Get current sensor values for defaults
        if self._edit_index is None:
            return await self.async_step_sensors()

        # Narrow the type for mypy: assert _edit_index is int and use local var
        idx = self._edit_index
        assert isinstance(idx, int)
        current_sensor = self._sensors[idx]

        return self.async_show_form(
            step_id="edit_sensor_form",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FLOOR_ID, default=current_sensor.get(CONF_FLOOR_ID)
                    ): selector.FloorSelector(),
                    vol.Required(
                        CONF_POSITION_X, default=current_sensor.get(CONF_POSITION_X, 0)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10000, max=10000, unit_of_measurement="mm"
                        )
                    ),
                    vol.Required(
                        CONF_POSITION_Y, default=current_sensor.get(CONF_POSITION_Y, 0)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10000, max=10000, unit_of_measurement="mm"
                        )
                    ),
                    vol.Optional(
                        CONF_ROTATION, default=current_sensor.get(CONF_ROTATION, 0)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=359, unit_of_measurement="degrees"
                        )
                    ),
                    vol.Required(
                        CONF_TARGET_ENTITIES,
                        default=current_sensor.get(CONF_TARGET_ENTITIES, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a sensor."""
        self._sensors = self.config_entry.data.get(CONF_SENSORS, []).copy()

        if not self._sensors:
            return await self.async_step_sensors()

        if user_input is not None:
            # Extract index from selection like "0: Floor None - Position..."
            selected = user_input["sensor_index"]
            sensor_index = int(selected.split(":")[0])
            if 0 <= sensor_index < len(self._sensors):
                self._sensors.pop(sensor_index)
                new_data = {**self.config_entry.data, CONF_SENSORS: self._sensors}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
            return await self.async_step_sensors()

        sensor_options = [
            f"{i}: Floor {s.get(CONF_FLOOR_ID, 'None')} - "
            f"Position ({s.get(CONF_POSITION_X)}, {s.get(CONF_POSITION_Y)})"
            for i, s in enumerate(self._sensors)
        ]

        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("sensor_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=sensor_options)
                    ),
                }
            ),
        )

    # Zone management
    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage zones."""
        self._zones = self.config_entry.options.get(CONF_ZONES, []).copy()
        return self.async_show_menu(
            step_id="zones",
            menu_options=["add_zone", "edit_zone", "remove_zone"],
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new zone."""
        errors = {}

        if user_input is not None:
            try:
                vertices = parse_vertices(user_input[CONF_VERTICES])
                if len(vertices) < 3:
                    errors["base"] = "insufficient_vertices"
                elif not self._validate_zone_name(
                    user_input[CONF_NAME], user_input.get(CONF_FLOOR_ID), self._zones
                ):
                    errors["base"] = "duplicate_zone_name"
                else:
                    self._zones.append(
                        {
                            CONF_NAME: user_input[CONF_NAME],
                            CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                            CONF_VERTICES: vertices,
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        options={**self.config_entry.options, CONF_ZONES: self._zones},
                    )
                    return await self.async_step_zones()
            except ValueError:
                errors["base"] = "invalid_vertices"

        return self.async_show_form(
            step_id="add_zone",
            data_schema=self._build_zone_schema(),
            errors=errors,
            description_placeholders={
                "vertices_example": "[[0,0], [1000,0], [1000,1000], [0,1000]]"
            },
        )

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing zone."""
        self._zones = self.config_entry.options.get(CONF_ZONES, []).copy()

        if not self._zones:
            return await self.async_step_zones()

        if self._edit_index is None:
            if user_input is not None:
                self._edit_index = int(user_input["zone_index"].split(":")[0])
                return await self.async_step_edit_zone_form()

            return self.async_show_form(
                step_id="edit_zone",
                data_schema=vol.Schema(
                    {
                        vol.Required("zone_index"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    f"{i}: {self._get_zone_label(z)}"
                                    for i, z in enumerate(self._zones)
                                ]
                            )
                        ),
                    }
                ),
            )

        return await self.async_step_edit_zone_form(user_input)

    async def async_step_edit_zone_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit zone form with current values."""
        if self._edit_index is None or not (0 <= self._edit_index < len(self._zones)):
            self._edit_index = None
            return await self.async_step_zones()

        current_zone = self._zones[self._edit_index]
        errors = {}

        if user_input is not None:
            try:
                vertices = parse_vertices(user_input[CONF_VERTICES])
                if len(vertices) < 3:
                    errors["base"] = "insufficient_vertices"
                elif not self._validate_zone_name(
                    user_input[CONF_NAME],
                    user_input.get(CONF_FLOOR_ID),
                    self._zones,
                    self._edit_index,
                ):
                    errors["base"] = "duplicate_zone_name"
                else:
                    self._zones[self._edit_index] = {
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                        CONF_VERTICES: vertices,
                    }
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        options={**self.config_entry.options, CONF_ZONES: self._zones},
                    )
                    self._edit_index = None
                    return await self.async_step_zones()
            except ValueError:
                errors["base"] = "invalid_vertices"

        return self.async_show_form(
            step_id="edit_zone_form",
            data_schema=self._build_zone_schema(current_zone),
            errors=errors,
            description_placeholders={
                "vertices_example": "[[0,0], [1000,0], [1000,1000], [0,1000]]"
            },
        )

    async def async_step_remove_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a zone."""
        self._zones = self.config_entry.options.get(CONF_ZONES, []).copy()

        if not self._zones:
            return await self.async_step_zones()

        if user_input is not None:
            zone_index = int(user_input["zone_index"].split(":")[0])
            if 0 <= zone_index < len(self._zones):
                self._zones.pop(zone_index)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, CONF_ZONES: self._zones},
                )
            return await self.async_step_zones()

        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                f"{i}: {self._get_zone_label(z)}"
                                for i, z in enumerate(self._zones)
                            ]
                        )
                    ),
                }
            ),
        )

    # Block zone management
    async def async_step_block_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage block zones."""
        self._block_zones = self.config_entry.options.get(CONF_BLOCK_ZONES, []).copy()
        return self.async_show_menu(
            step_id="block_zones",
            menu_options=["add_block_zone", "edit_block_zone", "remove_block_zone"],
        )

    async def async_step_add_block_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new block zone."""
        errors = {}

        if user_input is not None:
            try:
                vertices = parse_vertices(user_input[CONF_VERTICES])
                if len(vertices) < 3:
                    errors["base"] = "insufficient_vertices"
                elif not self._validate_zone_name(
                    user_input[CONF_NAME],
                    user_input.get(CONF_FLOOR_ID),
                    self._block_zones,
                ):
                    errors["base"] = "duplicate_zone_name"
                else:
                    self._block_zones.append(
                        {
                            CONF_NAME: user_input[CONF_NAME],
                            CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                            CONF_VERTICES: vertices,
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        options={
                            **self.config_entry.options,
                            CONF_BLOCK_ZONES: self._block_zones,
                        },
                    )
                    return await self.async_step_block_zones()
            except ValueError:
                errors["base"] = "invalid_vertices"

        return self.async_show_form(
            step_id="add_block_zone",
            data_schema=self._build_zone_schema(),
            errors=errors,
            description_placeholders={
                "vertices_example": "[[100,100], [200,100], [200,200], [100,200]]"
            },
        )

    async def async_step_edit_block_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing block zone."""
        self._block_zones = self.config_entry.options.get(CONF_BLOCK_ZONES, []).copy()

        if not self._block_zones:
            return await self.async_step_block_zones()

        if self._edit_index is None:
            if user_input is not None:
                self._edit_index = int(user_input["zone_index"].split(":")[0])
                return await self.async_step_edit_block_zone_form()

            return self.async_show_form(
                step_id="edit_block_zone",
                data_schema=vol.Schema(
                    {
                        vol.Required("zone_index"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    f"{i}: {self._get_zone_label(z)}"
                                    for i, z in enumerate(self._block_zones)
                                ]
                            )
                        ),
                    }
                ),
            )

        return await self.async_step_edit_block_zone_form(user_input)

    async def async_step_edit_block_zone_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit block zone form with current values."""
        if self._edit_index is None or not (
            0 <= self._edit_index < len(self._block_zones)
        ):
            self._edit_index = None
            return await self.async_step_block_zones()

        current_zone = self._block_zones[self._edit_index]
        errors = {}

        if user_input is not None:
            try:
                vertices = parse_vertices(user_input[CONF_VERTICES])
                if len(vertices) < 3:
                    errors["base"] = "insufficient_vertices"
                elif not self._validate_zone_name(
                    user_input[CONF_NAME],
                    user_input.get(CONF_FLOOR_ID),
                    self._block_zones,
                    self._edit_index,
                ):
                    errors["base"] = "duplicate_zone_name"
                else:
                    self._block_zones[self._edit_index] = {
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_FLOOR_ID: user_input.get(CONF_FLOOR_ID),
                        CONF_VERTICES: vertices,
                    }
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        options={
                            **self.config_entry.options,
                            CONF_BLOCK_ZONES: self._block_zones,
                        },
                    )
                    self._edit_index = None
                    return await self.async_step_block_zones()
            except ValueError:
                errors["base"] = "invalid_vertices"

        return self.async_show_form(
            step_id="edit_block_zone_form",
            data_schema=self._build_zone_schema(current_zone),
            errors=errors,
            description_placeholders={
                "vertices_example": "[[100,100], [200,100], [200,200], [100,200]]"
            },
        )

    async def async_step_remove_block_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a block zone."""
        self._block_zones = self.config_entry.options.get(CONF_BLOCK_ZONES, []).copy()

        if not self._block_zones:
            return await self.async_step_block_zones()

        if user_input is not None:
            zone_index = int(user_input["zone_index"].split(":")[0])
            if 0 <= zone_index < len(self._block_zones):
                self._block_zones.pop(zone_index)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={
                        **self.config_entry.options,
                        CONF_BLOCK_ZONES: self._block_zones,
                    },
                )
            return await self.async_step_block_zones()

        return self.async_show_form(
            step_id="remove_block_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                f"{i}: {self._get_zone_label(z)}"
                                for i, z in enumerate(self._block_zones)
                            ]
                        )
                    ),
                }
            ),
        )

    # Settings
    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage settings."""
        if user_input is not None:
            new_options = {**self.config_entry.options, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=new_options
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALENESS_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_STALENESS_TIMEOUT, DEFAULT_STALENESS_TIMEOUT
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=300, unit_of_measurement="seconds"
                        )
                    ),
                    vol.Optional(
                        CONF_TEST_MODE,
                        default=self.config_entry.options.get(CONF_TEST_MODE, False),
                    ): selector.BooleanSelector(),
                }
            ),
        )
