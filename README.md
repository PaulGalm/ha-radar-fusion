# Radar Fusion for Home Assistant

Multi-sensor radar fusion for presence detection with ESPHome LD2450 sensors.

## Features

- 🎯 Fuse multiple LD2450 sensors for complete coverage
- 📍 Create custom detection zones with polygon vertices
- 🚫 Filter false positives with block zones
- 🗺️ Organize by floor
- 🔥 Track presence patterns with heatmaps
- 🎨 Includes visualization cards for Lovelace dashboard

## Requirements

- Home Assistant 2024.1.0+
- ESPHome LD2450 sensors with target entities:
  - `sensor.device_target{1-3}_{x,y}`

## Installation via HACS

1. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ (menu) → Custom repositories
   - Repository: `https://github.com/YOUR_USERNAME/radar-fusion`
   - Category: Integration
2. Click "Explore & Download Repositories"
3. Search for "Radar Fusion"
4. Click "Download"
5. Restart Home Assistant
6. Add integration via Settings → Devices & Services → Add Integration → Radar Fusion

## Lovelace Cards

The integration includes two custom Lovelace cards:

### Radar Fusion Card
Visualizes sensor coverage, zones, and detected targets in real-time.

**Add resource:**
Settings → Dashboards → Resources → Add Resource
- URL: `/radar_fusion_static/radar-fusion-card.js`
- Type: JavaScript Module

**Example configuration:**
```yaml
type: custom:radar-fusion-card
config_entry_id: YOUR_CONFIG_ENTRY_ID
floor_id: ground_floor  # optional
```

### Radar Fusion Heatmap Card
Displays presence heatmap showing where movement is detected over time.

**Add resource:**
Settings → Dashboards → Resources → Add Resource
- URL: `/radar_fusion_static/radar-fusion-heatmap-card.js`
- Type: JavaScript Module

**Example configuration:**
```yaml
type: custom:radar-fusion-heatmap-card
config_entry_id: YOUR_CONFIG_ENTRY_ID
floor_id: ground_floor  # optional
```

## Configuration

1. Add integration via UI
2. Configure sensors (position, rotation, offset calibration)
3. Create zones with JSON vertices: `[[x1,y1], [x2,y2], ...]`
4. Optional: Add block zones for filtering false positives

## Services

- `radar_fusion.get_floor_data` - Get sensor/zone/target data for visualization
- `radar_fusion.reset_heatmap` - Clear heatmap data
- `radar_fusion.set_test_mode` - Toggle test mode

## Development

This integration is developed in the [home-assistant/core](https://github.com/home-assistant/core) repository on a custom branch and synced to this HACS distribution repository.
