# Radar Fusion Integration

A Home Assistant integration for fusing and visualizing data from multiple radar sensors with advanced spatial analysis capabilities.

## Features

- **Multi-Sensor Fusion**: Combine data from multiple radar sensors with different orientations and positions
- **Coordinate Transformation**: Automatic transformation of local sensor coordinates to global coordinates
- **Zone Management**: Define detection zones and block zones for filtering target detections
- **Heatmap Visualization**: Generate real-time heatmaps showing detection density with hourly, 24-hour, and all-time views
- **Staleness Filtering**: Automatically filter out stale targets based on configurable timeout
- **Test Mode**: Mock data generation for testing and development without real sensors
- **Custom Cards**: Display data with dedicated Home Assistant frontend cards

## Installation

1. Copy the `radar_fusion` directory to your `homeassistant/components/` folder
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Create Integration → Radar Fusion

## Configuration

### Initial Setup

When adding the integration, configure:

- **Name**: Display name for the integration (default: "Radar Fusion")
- **Staleness Timeout**: How long (in seconds) to keep targets without updates before filtering (default: 10 seconds)
- **Test Mode**: Enable mock data generation for testing (default: disabled)

### Managing Sensors

Each sensor requires:

- **Device**: The radar device containing target sensor entities
- **Floor**: Optional floor assignment for multi-level buildings
- **Position X**: X-coordinate of sensor location in millimeters
- **Position Y**: Y-coordinate of sensor location in millimeters
- **Rotation**: Sensor rotation in degrees (0-359°)

The integration automatically discovers target entities from the selected device (expects 6 entities: target1_x, target1_y, target2_x, target2_y, target3_x, target3_y).

### Managing Zones

Define detection areas:

- **Name**: Zone identifier
- **Floor**: Floor assignment
- **Vertices**: Polygon vertices defining the zone boundary in format:
  - JSON: `[[x1,y1], [x2,y2], [x3,y3], ...]`
  - Space-separated: `x1,y1 x2,y2 x3,y3 ...`

### Managing Block Zones

Exclude areas from detection (useful for filtering out unwanted regions):

- Same configuration as zones
- Targets within block zones are filtered out from results

### Settings

Modify configuration options anytime:

- **Staleness Timeout**: Adjust target filter timeout
- **Test Mode**: Toggle mock data generation

## Services

### `radar_fusion.get_floor_data`

Retrieve current data for a specific floor.

**Parameters:**
- `config_entry_id` (required): The config entry ID of the integration
- `floor_id` (optional): Floor to query (None for general data)

**Response (when in test mode or with real data):**
```json
{
  "floor_id": "living_room",
  "sensors": [
    {
      "position_x": 0,
      "position_y": 0,
      "rotation": 0,
      "target_entities": ["sensor.radar_target1_x", "sensor.radar_target1_y"],
      "target_count": 1
    }
  ],
  "zones": [
    {
      "name": "room_zone",
      "vertices": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
    }
  ],
  "block_zones": [],
  "targets": [
    {
      "x": 500,
      "y": 500,
      "age": 1.23,
      "sensor_entities": ["sensor.radar_target1_x", "sensor.radar_target1_y"]
    }
  ],
  "heatmap": {
    "resolution_mm": 500,
    "hourly": {"1_1": 5, "2_2": 3},
    "24h": {"1_1": 10, "2_2": 7},
    "all_time": {"1_1": 20, "2_2": 15}
  }
}
```

**Example (YAML automation):**
```yaml
service: radar_fusion.get_floor_data
data:
  config_entry_id: "a1b2c3d4e5f6"
  floor_id: "living_room"
```

### `radar_fusion.reset_heatmap`

Clear heatmap data for a floor or all floors.

**Parameters:**
- `config_entry_id` (required): The config entry ID of the integration
- `floor_id` (optional): Floor to reset (None for all floors)

**Example:**
```yaml
service: radar_fusion.reset_heatmap
data:
  config_entry_id: "a1b2c3d4e5f6"
  floor_id: "living_room"
```

### `radar_fusion.set_test_mode`

Enable or disable test mode (alternative to using settings UI).

**Parameters:**
- `config_entry_id` (required): The config entry ID of the integration
- `enabled` (required): Boolean to enable/disable test mode

**Example:**
```yaml
service: radar_fusion.set_test_mode
data:
  config_entry_id: "a1b2c3d4e5f6"
  enabled: true
```

## Test Mode

When test mode is enabled, the integration generates mock radar data including:

- Multiple simulated sensors at different positions
- Random target detections in defined zones
- Simulated heatmap data
- Block zone filtering demonstration

Useful for:
- Testing frontend card visualizations
- Developing automations without real hardware
- Demonstrating integration capabilities

## Frontend Cards

### Radar Fusion Card

Display sensor data, zones, and targets:

```yaml
type: custom:radar-fusion-card
entity: binary_sensor.radar_fusion_presence
floor_id: living_room
```

### Radar Fusion Heatmap Card

Visualize detection density as a heatmap:

```yaml
type: custom:radar-fusion-heatmap-card
entity: binary_sensor.radar_fusion_presence
floor_id: living_room
heatmap_type: hourly
```

## Coordinate System

All coordinates use a Cartesian coordinate system in millimeters:

- **X-axis**: Left (-) to Right (+)
- **Y-axis**: Down (-) to Up (+)
- **Rotation**: Clockwise from 0° (pointing right)

### Coordinate Transformation

Local sensor coordinates are transformed to global coordinates using:

```
global_x = local_x * cos(rotation) - local_y * sin(rotation) + sensor_x
global_y = local_x * sin(rotation) + local_y * cos(rotation) + sensor_y
```

## Heatmap Resolution

- **Resolution**: 500mm (0.5 meters) per bin
- **Hourly**: Last 3600 seconds
- **24-hour**: Last 86400 seconds
- **All-time**: Persisted across restarts

## Troubleshooting

### Integration won't load

1. Check Home Assistant logs for import errors
2. Ensure all required dependencies are installed
3. Verify `manifest.json` is present and valid

### No targets detected

1. Check sensor entities are properly configured and reporting values
2. Verify staleness timeout isn't too aggressive
3. Review zone definitions - targets outside zones won't be included
4. Check block zone settings aren't filtering all targets

### Heatmap shows no data

1. Enable test mode to verify heatmap functionality
2. Ensure targets are being detected (check `get_floor_data` service response)
3. Wait for targets to be detected (heatmap updates over time)
4. Check heatmap resolution matches expected scale

### Coordinates seem inverted

1. Verify sensor position and rotation settings
2. Check floor layout in zone definitions
3. Use `generate_ascii_map` function for debugging (available in development)

## Development

### Mock Data in Test Mode

When test mode is enabled, the service returns:

- 2 simulated sensors at different positions
- 2-3 mock targets moving randomly
- Predefined zones and block zones
- Sample heatmap data

### Extending the Integration

To add new features:

1. Modify `coordinator.py` for data processing logic
2. Add new services in `__init__.py`
3. Create entity platforms in `sensor.py`, `binary_sensor.py`, etc.
4. Update `manifest.json` with new dependencies

## Notes

- Coordinates are in millimeters for precision
- All operations are asynchronous (non-blocking)
- Heatmap data is persisted in config entry options
- Multiple floors are supported through `floor_id` field
- Block zones use ray-casting algorithm for point-in-polygon tests

## Support

For issues, feature requests, or contributions, please refer to the Home Assistant integration documentation or community forums.
