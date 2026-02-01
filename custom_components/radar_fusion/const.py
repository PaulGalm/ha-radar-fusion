"""Constants for the Radar Fusion integration."""

from __future__ import annotations

import json
import math
import re
from typing import Any

# Option for test mode
CONF_TEST_MODE = "test_mode"

DOMAIN = "radar_fusion"

# Configuration keys
CONF_SENSORS = "sensors"
CONF_ZONES = "zones"
CONF_BLOCK_ZONES = "block_zones"
CONF_STALENESS_TIMEOUT = "staleness_timeout"
CONF_POSITION_X = "position_x"
CONF_POSITION_Y = "position_y"
CONF_ROTATION = "rotation"
CONF_FLOOR_ID = "floor_id"
CONF_VERTICES = "vertices"
CONF_TARGET_ENTITIES = "target_entities"

# Defaults
DEFAULT_STALENESS_TIMEOUT = 10  # seconds
DEFAULT_NAME = "Radar Fusion"

# Service names
SERVICE_GET_FLOOR_DATA = "get_floor_data"
SERVICE_RESET_HEATMAP = "reset_heatmap"

# Heatmap settings
HEATMAP_RES_MM = 500  # 0.5 meter bins
HEATMAP_HOURLY_SECONDS = 3600
HEATMAP_24H_SECONDS = 24 * 3600

# Persistence keys
CONF_HEATMAPS_ALLTIME = "heatmaps_alltime"


def parse_vertices(text: str) -> list[list[float]]:
    """Parse vertex coordinates from text input.

    Accepts formats:
    - Space-separated pairs: "0,0 100,0 100,100 0,100"
    - JSON array: "[[0,0], [100,0], [100,100], [0,100]]"

    Returns normalized format: [[x1, y1], [x2, y2], ...]
    """

    def _validate_vertex_item(item):
        """Validate and convert a single vertex item."""
        if isinstance(item, (list, tuple)) and len(item) == 2:
            return [float(item[0]), float(item[1])]
        raise ValueError(f"Invalid vertex format: {item}")

    text = text.strip()

    # Try JSON array format first
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                # Normalize to list of [x, y] pairs
                return [_validate_vertex_item(item) for item in data]
        except (json.JSONDecodeError, ValueError) as err:
            raise ValueError(f"Invalid JSON vertex format: {err}") from err

    # Parse space-separated coordinate pairs
    # Match patterns like "0,0" or "0.5,10.2"
    pattern = r"(-?\d+\.?\d*),\s*(-?\d+\.?\d*)"
    matches = re.findall(pattern, text)

    if not matches:
        raise ValueError("Invalid vertex format. Use '[[x,y], ...]' or 'x,y x,y ...'")

    return [[float(x), float(y)] for x, y in matches]


def transform_coordinates(
    x: float,
    y: float,
    sensor_x: float,
    sensor_y: float,
    rotation_deg: float,
) -> tuple[float, float]:
    """Transform local coordinates to global coordinates.

    Args:
        x: Local X coordinate from sensor
        y: Local Y coordinate from sensor
        sensor_x: Sensor position X in global coordinates
        sensor_y: Sensor position Y in global coordinates
        rotation_deg: Sensor rotation in degrees (0 = no rotation)

    Returns:
        Tuple of (global_x, global_y)
    """
    # Convert rotation to radians
    theta = math.radians(rotation_deg)

    # Apply rotation matrix
    x_rot = x * math.cos(theta) - y * math.sin(theta)
    y_rot = x * math.sin(theta) + y * math.cos(theta)

    # Apply translation
    return x_rot + sensor_x, y_rot + sensor_y


def point_in_polygon(x: float, y: float, vertices: list[list[float]]) -> bool:
    """Test if point is inside polygon using ray casting algorithm.

    Args:
        x: Point X coordinate
        y: Point Y coordinate
        vertices: List of [x, y] vertex coordinates

    Returns:
        True if point is inside polygon, False otherwise
    """
    if len(vertices) < 3:
        return False

    inside = False
    j = len(vertices) - 1

    for i, (xi, yi) in enumerate(vertices):
        xj, yj = vertices[j][0], vertices[j][1]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


def generate_ascii_map(
    sensors: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    block_zones: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    floor_id: str | None,
    width: int = 80,
    height: int = 40,
) -> str:
    """Generate ASCII art visualization of sensor layout, zones, and targets.

    Args:
        sensors: List of sensor configs with position_x, position_y
        zones: List of zone configs with vertices
        block_zones: List of block zone configs with vertices
        targets: List of current target positions with x, y
        floor_id: Floor ID to filter (None for all floors)
        width: Character width of map
        height: Character height of map

    Returns:
        ASCII art string representation
    """
    # Filter by floor
    floor_sensors = [s for s in sensors if s.get("floor_id") == floor_id]
    floor_zones = [z for z in zones if z.get("floor_id") == floor_id]
    floor_block_zones = [z for z in block_zones if z.get("floor_id") == floor_id]
    floor_targets = [t for t in targets if t.get("floor_id") == floor_id]

    if not floor_sensors and not floor_zones and not floor_block_zones:
        return f"Floor: {floor_id or 'None'}\nNo data available"

    # Find coordinate bounds
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    for sensor in floor_sensors:
        min_x = min(min_x, sensor["position_x"])
        max_x = max(max_x, sensor["position_x"])
        min_y = min(min_y, sensor["position_y"])
        max_y = max(max_y, sensor["position_y"])

    for zone in floor_zones + floor_block_zones:
        for vertex in zone["vertices"]:
            min_x = min(min_x, vertex[0])
            max_x = max(max_x, vertex[0])
            min_y = min(min_y, vertex[1])
            max_y = max(max_y, vertex[1])

    for target in floor_targets:
        min_x = min(min_x, target["x"])
        max_x = max(max_x, target["x"])
        min_y = min(min_y, target["y"])
        max_y = max(max_y, target["y"])

    # Add padding
    padding = max((max_x - min_x) * 0.1, (max_y - min_y) * 0.1, 100)
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding

    # Create grid
    grid = [[" " for _ in range(width)] for _ in range(height)]

    def scale_x(x: float) -> int:
        """Scale X coordinate to grid."""
        if max_x == min_x:
            return width // 2
        return int((x - min_x) / (max_x - min_x) * (width - 3)) + 1

    def scale_y(y: float) -> int:
        """Scale Y coordinate to grid (inverted for display)."""
        if max_y == min_y:
            return height // 2
        return int((max_y - y) / (max_y - min_y) * (height - 3)) + 1

    # Draw border
    for x in range(width):
        grid[0][x] = "-"
        grid[height - 1][x] = "-"
    for y in range(height):
        grid[y][0] = "|"
        grid[y][width - 1] = "|"
    grid[0][0] = grid[0][width - 1] = "+"
    grid[height - 1][0] = grid[height - 1][width - 1] = "+"

    # Draw zones
    for zone in floor_zones:
        vertices = zone["vertices"]
        for i, vertex in enumerate(vertices):
            x1, y1 = scale_x(vertex[0]), scale_y(vertex[1])
            next_vertex = vertices[(i + 1) % len(vertices)]
            x2, y2 = scale_x(next_vertex[0]), scale_y(next_vertex[1])
            # Simple line drawing
            if 0 < x1 < width and 0 < y1 < height:
                grid[y1][x1] = "+"
            if 0 < x2 < width and 0 < y2 < height:
                grid[y2][x2] = "+"

    # Draw block zones
    for zone in floor_block_zones:
        vertices = zone["vertices"]
        for i, vertex in enumerate(vertices):
            x1, y1 = scale_x(vertex[0]), scale_y(vertex[1])
            next_vertex = vertices[(i + 1) % len(vertices)]
            x2, y2 = scale_x(next_vertex[0]), scale_y(next_vertex[1])
            if 0 < x1 < width and 0 < y1 < height:
                grid[y1][x1] = "#"
            if 0 < x2 < width and 0 < y2 < height:
                grid[y2][x2] = "#"

    # Draw sensors
    for i, sensor in enumerate(floor_sensors):
        x, y = scale_x(sensor["position_x"]), scale_y(sensor["position_y"])
        if 0 < x < width and 0 < y < height:
            grid[y][x] = str(i + 1) if i < 9 else "S"

    # Draw targets
    for target in floor_targets:
        x, y = scale_x(target["x"]), scale_y(target["y"])
        if 0 < x < width and 0 < y < height:
            grid[y][x] = "*"

    # Convert grid to string
    lines = ["".join(row) for row in grid]

    # Add header and legend
    header = f"Floor: {floor_id or 'None'}"
    legend = "Legend: S=Sensor *=Target +=Zone #=BlockZone"
    scale_info = f"Scale: {min_x:.0f},{min_y:.0f} to {max_x:.0f},{max_y:.0f}"

    return "\n".join([header, *lines, legend, scale_info])
