# Radar Fusion Card

Custom Lovelace card for visualizing the Radar Fusion integration.

## Installation

1. **Copy the card file** to your Home Assistant `www` folder:
   ```
   config/www/radar-fusion-card.js
   ```

2. **Add the resource** to your Lovelace configuration:
   - Go to Settings → Dashboards → Resources (three-dot menu → Resources)
   - Click "Add Resource"
   - URL: `/local/radar-fusion-card.js`
   - Resource type: JavaScript Module

3. **Restart Home Assistant** or refresh your browser cache (Ctrl+F5)

## Usage

Add the card to your dashboard:

```yaml
type: custom:radar-fusion-card
config_entry_id: abc123def456  # Your radar fusion config entry ID
floor_id: null  # Optional: filter by floor ID
width: 800  # Optional: canvas width in pixels
height: 600  # Optional: canvas height in pixels
grid_size: 5000  # Optional: grid size in mm (default 5000 = 5 meters)
show_grid: true  # Optional: show background grid
title: Radar Fusion  # Optional: card title
```

### Finding Your Config Entry ID

1. Go to Settings → Devices & Services
2. Click on your Radar Fusion integration
3. Look at the URL - it will be like: `config/integrations/integration/radar_fusion?config_entry=abc123def456`
4. Copy the part after `config_entry=` - that's your config_entry_id

## Features

### Visual Elements

- **Sensors**: Colored markers showing sensor positions with direction indicators
- **Detection Zones**: Translucent cones showing each sensor's 3m detection range
- **Zones**: Green polygons representing occupancy detection zones
- **Block Zones**: Red dashed polygons showing filtered/blocked areas
- **Targets**: Colored dots showing detected targets (color-coded by sensor)
- **Grid**: Optional background grid with 1-meter spacing

### Toggle Controls

Three buttons at the top of the card allow you to show/hide:
- **Zones**: Toggle visibility of detection zones (green polygons)
- **Sensors**: Toggle visibility of sensor positions and markers
- **Detection Zones**: Toggle visibility of sensor range cones

### Color Coding

Each sensor is assigned a unique color, and all targets detected by that sensor are shown in the same color. This makes it easy to see which sensor is detecting which targets.

### Real-time Updates

The card automatically updates when:
- New targets are detected
- Targets move
- Zones are added/removed
- Sensors are reconfigured

### Stats Bar

At the bottom of the card:
- Total number of active targets
- Number of active sensors (with targets) / total sensors
- Total number of zones

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `config_entry_id` | string | **Required** | The radar fusion config entry ID (from URL) |
| `floor_id` | string | `null` | Filter to show only one floor |
| `width` | number | `800` | Canvas width in pixels |
| `height` | number | `600` | Canvas height in pixels |
| `grid_size` | number | `5000` | Grid coverage in mm (5000 = 5 meters) |
| `show_grid` | boolean | `true` | Show background grid |
| `title` | string | `'Radar Fusion'` | Card title |

## Example Configurations

### Basic Card
```yaml
type: custom:radar-fusion-card
config_entry_id: abc123def456  # Replace with your config entry ID
```

### Multi-Floor Setup
```yaml
type: custom:radar-fusion-card
config_entry_id: abc123def456
floor_id: ground_floor
title: Ground Floor Radar
width: 1000
height: 800
grid_size: 10000  # 10 meters
```

### Compact View
```yaml
type: custom:radar-fusion-card
config_entry_id: abc123def456
width: 600
height: 400
show_grid: false
title: Radar Overview
```

## Troubleshooting

### Card Not Loading
- Check browser console for errors (F12)
- Verify the resource is added correctly
- Clear browser cache (Ctrl+F5)
- Make sure the file is in `config/www/`

### No Data Showing
- Verify the config_entry_id is correct (check the URL when viewing the integration)
- Check that sensors are configured in the integration
- Make sure zones are defined
- Check that the `get_floor_data` service is working:
  ```yaml
  service: radar_fusion.get_floor_data
  data:
    config_entry_id: abc123def456  # Your config entry ID
    floor_id: null
  ```

### Targets Not Showing
- Check that your sensor entities are providing valid data
- Verify coordinates are not -1 (inactive targets)
- Check staleness timeout setting

## Tips

1. **Adjust grid_size** to match your room dimensions
2. **Use floor_id** to create separate cards for each floor
3. **Toggle detection zones off** for a cleaner view when you have many sensors
4. **Watch target colors** to identify which sensor is detecting what

## Support

For issues or feature requests, please open an issue on the Home Assistant GitHub repository.
