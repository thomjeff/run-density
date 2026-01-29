"""
Segment map snapshot generator.

Creates per-segment PNG images with LOS-colored polylines and start/end markers.
Uses Carto Light tiles to match UI basemap styling.
"""

from __future__ import annotations

import io
import logging
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

from app.common.config import load_reporting
from app.utils.constants import LOCATION_MAP_TILE_SUBDOMAINS, LOCATION_MAP_TILE_URL

logger = logging.getLogger(__name__)

_TILE_SIZE = 256
_TILE_SUBDOMAINS = LOCATION_MAP_TILE_SUBDOMAINS
_TILE_URL = LOCATION_MAP_TILE_URL

_MAP_SIZE = (900, 520)
_MAP_PADDING_PX = 36
_MAP_MIN_ZOOM = 12
_MAP_MAX_ZOOM = 18
_LINE_WIDTH_PX = 4
_LINE_OUTLINE_PX = 7
_MARKER_RADIUS_PX = 6
_MARKER_OUTLINE_PX = 2


def export_segment_map_pngs(
    segments_geojson: Dict[str, Any],
    segment_metrics: Dict[str, Dict[str, Any]],
    output_dir: Path
) -> int:
    """
    Generate LOS-colored map snapshots for each segment feature.

    Args:
        segments_geojson: Day-scoped segments.geojson (features in EPSG:3857 or EPSG:4326).
        segment_metrics: Per-segment metrics (must include worst_los).
        output_dir: Directory to store output PNGs.

    Returns:
        Number of PNGs generated.
    """
    features = segments_geojson.get("features", []) if isinstance(segments_geojson, dict) else []
    if not features:
        raise ValueError("segments.geojson contains no features for segment map generation.")

    reporting_config = load_reporting()
    los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
    _validate_los_colors(los_colors)

    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for feature in features:
        seg_id = _feature_segment_id(feature)
        if not seg_id:
            raise ValueError("Segment feature missing seg_id; cannot generate map snapshot.")

        metrics = segment_metrics.get(seg_id)
        if not metrics or "worst_los" not in metrics:
            raise ValueError(f"Missing worst_los for segment {seg_id} in segment_metrics.")

        los_grade = str(metrics.get("worst_los"))
        color = los_colors.get(los_grade)
        if not color:
            raise ValueError(f"LOS color missing for grade {los_grade} (segment {seg_id}).")

        coords = _extract_feature_coords(feature)
        if not coords:
            raise ValueError(f"Segment {seg_id} has no geometry coordinates.")

        output_path = output_dir / f"{seg_id}.png"
        _render_segment_snapshot(coords, color, output_path, seg_id)
        count += 1

    logger.info(f"✅ Segment maps generated — Count: {count} PNG files — Location: {output_dir}")
    return count


def _validate_los_colors(los_colors: Dict[str, str]) -> None:
    missing = [grade for grade in ["A", "B", "C", "D", "E", "F"] if grade not in los_colors]
    if missing:
        raise ValueError(f"LOS colors missing grades: {missing}")


def _feature_segment_id(feature: Dict[str, Any]) -> Optional[str]:
    props = feature.get("properties", {}) if isinstance(feature, dict) else {}
    seg_id = props.get("seg_id") or props.get("segment_id") or props.get("id")
    return str(seg_id) if seg_id else None


def _extract_feature_coords(feature: Dict[str, Any]) -> List[Tuple[float, float]]:
    geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
    coords: List[Tuple[float, float]] = []
    if geometry.get("type") == "LineString":
        coords = _normalize_coords(geometry.get("coordinates", []))
    elif geometry.get("type") == "MultiLineString":
        for line in geometry.get("coordinates", []):
            coords.extend(_normalize_coords(line))
    return coords


def _normalize_coords(raw_coords: Sequence[Sequence[float]]) -> List[Tuple[float, float]]:
    coords: List[Tuple[float, float]] = []
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    for pair in raw_coords:
        if not pair or len(pair) < 2:
            continue
        x_val, y_val = float(pair[0]), float(pair[1])
        if _looks_like_wgs84(x_val, y_val):
            lon, lat = x_val, y_val
        else:
            lon, lat = transformer.transform(x_val, y_val)
        coords.append((lon, lat))
    return coords


def _looks_like_wgs84(lon: float, lat: float) -> bool:
    return abs(lon) <= 180.0 and abs(lat) <= 90.0


def _render_segment_snapshot(
    coords: Sequence[Tuple[float, float]],
    line_color: str,
    output_path: Path,
    seg_id: str
) -> None:
    min_lon, max_lon, min_lat, max_lat = _coords_bounds(coords)
    if min_lon == max_lon or min_lat == max_lat:
        min_lon, max_lon, min_lat, max_lat = _pad_bounds(min_lon, max_lon, min_lat, max_lat)

    zoom = _select_zoom(min_lon, max_lon, min_lat, max_lat)
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2

    try:
        img, top_left_x, top_left_y = _render_map_tiles(center_lat, center_lon, zoom, _MAP_SIZE)
    except Exception as exc:
        logger.warning(f"Segment {seg_id}: Map tiles unavailable ({exc}); using placeholder.")
        img, top_left_x, top_left_y = _render_placeholder(_MAP_SIZE)

    draw = ImageDraw.Draw(img)
    pixel_points = [
        _latlon_to_image_px(lat, lon, zoom, top_left_x, top_left_y)
        for lon, lat in coords
    ]

    if len(pixel_points) >= 2:
        draw.line(pixel_points, fill="#ffffff", width=_LINE_OUTLINE_PX, joint="curve")
        draw.line(pixel_points, fill=line_color, width=_LINE_WIDTH_PX, joint="curve")

    _draw_start_end_markers(draw, pixel_points, line_color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")


def _coords_bounds(coords: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    lons = [lon for lon, _ in coords]
    lats = [lat for _, lat in coords]
    return min(lons), max(lons), min(lats), max(lats)


def _pad_bounds(
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> Tuple[float, float, float, float]:
    pad_lon = 0.001 if min_lon == max_lon else (max_lon - min_lon) * 0.1
    pad_lat = 0.001 if min_lat == max_lat else (max_lat - min_lat) * 0.1
    return min_lon - pad_lon, max_lon + pad_lon, min_lat - pad_lat, max_lat + pad_lat


def _select_zoom(min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> int:
    width_px = _MAP_SIZE[0] - 2 * _MAP_PADDING_PX
    height_px = _MAP_SIZE[1] - 2 * _MAP_PADDING_PX
    for zoom in range(_MAP_MAX_ZOOM, _MAP_MIN_ZOOM - 1, -1):
        min_x, min_y = _latlon_to_pixels(min_lat, min_lon, zoom)
        max_x, max_y = _latlon_to_pixels(max_lat, max_lon, zoom)
        span_x = abs(max_x - min_x)
        span_y = abs(max_y - min_y)
        if span_x <= width_px and span_y <= height_px:
            return zoom
    return _MAP_MIN_ZOOM


def _render_map_tiles(
    lat: float,
    lon: float,
    zoom: int,
    size: Tuple[int, int]
) -> Tuple[Image.Image, float, float]:
    width_px, height_px = size
    center_x, center_y = _latlon_to_pixels(lat, lon, zoom)
    top_left_x = center_x - width_px / 2
    top_left_y = center_y - height_px / 2

    x_start = int(math.floor(top_left_x / _TILE_SIZE))
    y_start = int(math.floor(top_left_y / _TILE_SIZE))
    x_end = int(math.floor((top_left_x + width_px) / _TILE_SIZE))
    y_end = int(math.floor((top_left_y + height_px) / _TILE_SIZE))

    tile_cols = x_end - x_start + 1
    tile_rows = y_end - y_start + 1
    canvas = Image.new("RGB", (tile_cols * _TILE_SIZE, tile_rows * _TILE_SIZE), "white")

    tiles_fetched = 0
    for x in range(x_start, x_end + 1):
        for y in range(y_start, y_end + 1):
            tile = _fetch_tile(zoom, x, y)
            if tile is None:
                continue
            tiles_fetched += 1
            px = (x - x_start) * _TILE_SIZE
            py = (y - y_start) * _TILE_SIZE
            canvas.paste(tile, (px, py))

    if tiles_fetched == 0:
        raise RuntimeError("No map tiles fetched")

    crop_left = int(top_left_x - (x_start * _TILE_SIZE))
    crop_upper = int(top_left_y - (y_start * _TILE_SIZE))
    crop_box = (
        crop_left,
        crop_upper,
        crop_left + width_px,
        crop_upper + height_px,
    )
    return canvas.crop(crop_box), top_left_x, top_left_y


def _fetch_tile(zoom: int, x: int, y: int) -> Optional[Image.Image]:
    max_tile = 2**zoom
    x_wrapped = x % max_tile
    if y < 0 or y >= max_tile:
        return None
    subdomain = _TILE_SUBDOMAINS[(x_wrapped + y) % len(_TILE_SUBDOMAINS)]
    url = _TILE_URL.format(s=subdomain, z=zoom, x=x_wrapped, y=y)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None


def _render_placeholder(size: Tuple[int, int]) -> Tuple[Image.Image, float, float]:
    img = Image.new("RGB", size, color="#f2f2f2")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text = "Map unavailable"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2
    draw.text((x, y), text, fill="#666666", font=font)
    return img, 0.0, 0.0


def _latlon_to_pixels(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    siny = math.sin(math.radians(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    x = _TILE_SIZE * (0.5 + lon / 360.0) * (2**zoom)
    y = _TILE_SIZE * (
        0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)
    ) * (2**zoom)
    return x, y


def _latlon_to_image_px(
    lat: float,
    lon: float,
    zoom: int,
    top_left_x: float,
    top_left_y: float
) -> Tuple[float, float]:
    world_x, world_y = _latlon_to_pixels(lat, lon, zoom)
    return world_x - top_left_x, world_y - top_left_y


def _draw_start_end_markers(
    draw: ImageDraw.ImageDraw,
    points: Sequence[Tuple[float, float]],
    color: str
) -> None:
    if not points:
        return
    start = points[0]
    end = points[-1]
    for point, label in [(start, "S"), (end, "E")]:
        _draw_marker(draw, point, color, label)


def _draw_marker(
    draw: ImageDraw.ImageDraw,
    point: Tuple[float, float],
    color: str,
    label: str
) -> None:
    x, y = point
    radius = _MARKER_RADIUS_PX
    outline = _MARKER_OUTLINE_PX
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=color,
        outline="#ffffff",
        width=outline,
    )
    try:
        font = ImageFont.load_default()
        draw.text((x + radius + 2, y - radius - 2), label, fill="#111111", font=font)
    except Exception:
        pass
