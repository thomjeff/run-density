"""
One-pager generator for location summaries (Issue #702).

Creates a PDF per location flagged onepage='y' using:
- locations_results.json (static fields: label/type/GPS/equipment/contact/notes)
- Locations.csv report (timings aligned with UI)
"""

from __future__ import annotations

import json
import logging
import math
import re
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.utils.constants import (
    LOCATION_MAP_RADIUS_M,
    LOCATION_MAP_TILE_URL,
    LOCATION_MAP_TILE_SUBDOMAINS,
)

logger = logging.getLogger(__name__)

# Map tile configuration (matches Leaflet Carto Light)
_TILE_SUBDOMAINS = LOCATION_MAP_TILE_SUBDOMAINS
_TILE_URL = LOCATION_MAP_TILE_URL
_TILE_SIZE = 256

# Output sizing
_MAP_SIZE = (640, 360)  # px (width, height)
_PAGE_SIZE = A4
_MARGIN = 0.75 * inch
_SECTION_GAP = 10

# Map radius guideline (not strict)
_DEFAULT_RADIUS_M = LOCATION_MAP_RADIUS_M


def generate_location_onepagers(
    run_id: str,
    day: str,
    locations_results_json_path: Path,
    locations_report_csv_path: Path,
    maps_dir: Path,
    output_dir: Path,
    radius_m: float = _DEFAULT_RADIUS_M
) -> int:
    """
    Generate one-pager PDFs for locations flagged onepage='y'.

    Returns:
        Number of PDFs generated.
    """
    locations_data = _load_locations_results(locations_results_json_path)
    if not locations_data:
        logger.warning(
            f"Issue #702: locations_results.json empty or unreadable at {locations_results_json_path}"
        )
        return 0

    report_lookup = _load_locations_report(locations_report_csv_path)
    if not report_lookup:
        logger.warning(
            f"Issue #702: Locations report not found or empty at {locations_report_csv_path}"
        )
        return 0

    maps_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for location in locations_data:
        if not _is_onepager_location(location, day):
            continue

        loc_id = location.get("loc_id")
        if loc_id is None:
            logger.warning("Issue #702: Skipping location with missing loc_id")
            continue

        report_row = report_lookup.get(int(loc_id))
        if not report_row:
            logger.warning(
                f"Issue #702: No Locations.csv row found for loc_id={loc_id}, skipping one-pager"
            )
            continue

        map_path = _build_map_path(maps_dir, location)
        try:
            _create_map_snapshot(location, map_path, radius_m=radius_m)
        except Exception as exc:
            logger.warning(
                f"Issue #702: Map snapshot failed for loc_id={loc_id}: {exc}. "
                "Using placeholder image."
            )
            _write_map_placeholder(map_path)

        pdf_path = _build_pdf_path(output_dir, location)
        _render_onepager_pdf(location, report_row, map_path, pdf_path)
        count += 1

    logger.info(f"Issue #702: Generated {count} one-pager PDFs for day {day}")
    return count


def _load_locations_results(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Issue #702: Failed to load locations_results.json: {exc}")
        return []

    return data.get("locations", []) if isinstance(data, dict) else []


def _load_locations_report(path: Path) -> Dict[int, Dict[str, Any]]:
    if not path.exists():
        return {}

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        logger.warning(f"Issue #702: Failed to read Locations.csv: {exc}")
        return {}

    if df.empty or "loc_id" not in df.columns:
        return {}

    df = df.replace([math.inf, -math.inf], None)
    df["loc_id"] = pd.to_numeric(df["loc_id"], errors="coerce")
    df = df.dropna(subset=["loc_id"])
    df["loc_id"] = df["loc_id"].astype(int)
    return df.set_index("loc_id").to_dict("index")


def _is_onepager_location(location: Dict[str, Any], day: str) -> bool:
    loc_day = str(location.get("day", "")).strip().lower()
    if loc_day and loc_day != str(day).strip().lower():
        return False

    onepage_flag = str(location.get("onepage", "")).strip().lower()
    return onepage_flag == "y"


def _build_map_path(maps_dir: Path, location: Dict[str, Any]) -> Path:
    loc_id = location.get("loc_id", "unknown")
    label = location.get("loc_label", "")
    name = _slugify(f"{loc_id}-{label}") or f"{loc_id}"
    return maps_dir / f"{name}.png"


def _build_pdf_path(output_dir: Path, location: Dict[str, Any]) -> Path:
    loc_id = location.get("loc_id", "unknown")
    label = location.get("loc_label", "")
    name = _slugify(f"{loc_id}-{label}") or f"{loc_id}"
    return output_dir / f"{name}.pdf"


def _create_map_snapshot(
    location: Dict[str, Any],
    output_path: Path,
    radius_m: float
) -> None:
    lat = location.get("lat")
    lon = location.get("lon")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        raise ValueError("Missing lat/lon for map snapshot")

    zoom = _estimate_zoom(lat, radius_m, _MAP_SIZE[0])
    img = _render_map_tiles(lat, lon, zoom, _MAP_SIZE)
    _draw_map_pin(img)
    img.save(output_path, format="PNG")


def _estimate_zoom(lat: float, radius_m: float, width_px: int) -> int:
    meters_per_pixel = max((radius_m * 2) / float(width_px), 1.0)
    zoom = math.log2(
        (156543.03392 * math.cos(math.radians(lat))) / meters_per_pixel
    )
    zoom_int = int(max(12, min(18, round(zoom))))
    return zoom_int


def _render_map_tiles(lat: float, lon: float, zoom: int, size: Tuple[int, int]) -> Image.Image:
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

    crop_left = int(top_left_x - (x_start * _TILE_SIZE))
    crop_upper = int(top_left_y - (y_start * _TILE_SIZE))
    crop_box = (
        crop_left,
        crop_upper,
        crop_left + width_px,
        crop_upper + height_px,
    )
    if tiles_fetched == 0:
        raise RuntimeError("No map tiles fetched")

    return canvas.crop(crop_box)


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


def _latlon_to_pixels(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    siny = math.sin(math.radians(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    x = _TILE_SIZE * (0.5 + lon / 360.0) * (2**zoom)
    y = _TILE_SIZE * (
        0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)
    ) * (2**zoom)
    return x, y


def _write_map_placeholder(output_path: Path) -> None:
    img = Image.new("RGB", _MAP_SIZE, color="#f2f2f2")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text = "Map unavailable"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (_MAP_SIZE[0] - text_width) / 2
    y = (_MAP_SIZE[1] - text_height) / 2
    draw.text((x, y), text, fill="#666666", font=font)
    img.save(output_path, format="PNG")


def _draw_map_pin(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    center_x = img.width // 2
    center_y = img.height // 2
    radius = 8
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        fill="#d7261e",
        outline="white",
        width=2,
    )


def _render_onepager_pdf(
    location: Dict[str, Any],
    report_row: Dict[str, Any],
    map_path: Path,
    output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=_PAGE_SIZE)
    page_w, page_h = _PAGE_SIZE

    font_regular, font_bold, font_body = _register_fonts()
    y = page_h - _MARGIN

    loc_id = location.get("loc_id", "")
    loc_label = location.get("loc_label", "")
    title = f"LOCATION: {loc_id} - {loc_label}"
    y = _draw_text_block(c, title, font_bold, 16, _MARGIN, y, page_w - 2 * _MARGIN)

    loc_type = location.get("loc_type", "")
    y = _draw_label_value(c, "TYPE", loc_type, font_bold, font_body, 14, 12, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)

    lat = location.get("lat", "")
    lon = location.get("lon", "")
    gps_line = f"{lat}, {lon}"
    maps_url = _build_google_maps_url(lat, lon)
    y = _draw_gps_with_link(
        c,
        gps_line,
        maps_url,
        font_bold,
        font_body,
        12,
        _MARGIN,
        y - 4,
        page_w - 2 * _MARGIN,
    )

    map_width = (page_w - 2 * _MARGIN) * 0.85
    map_height = map_width * (_MAP_SIZE[1] / _MAP_SIZE[0])
    if map_path.exists():
        c.drawImage(
            ImageReader(str(map_path)),
            _MARGIN,
            y - map_height,
            width=map_width,
            height=map_height,
            preserveAspectRatio=True,
        )
    y = y - map_height - _SECTION_GAP

    loc_start = _format_time(report_row.get("loc_start"))
    loc_end = _format_time(report_row.get("loc_end"))
    duration = report_row.get("duration")
    duration_text = f"{duration} min" if duration not in [None, "", "NA"] else "NA"
    y = _draw_text_block(c, "⏰ LOCATION TIMES", font_bold, 14, _MARGIN, y, page_w - 2 * _MARGIN)
    y = _draw_text_block(
        c,
        f"{loc_start} - {loc_end} (Duration: {duration_text})",
        font_body,
        12,
        _MARGIN + 16,
        y - 2,
        page_w - 2 * _MARGIN,
    )

    y = _draw_text_block(c, "⏱️ RUNNER TIMINGS", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    timings_lines = [
        f"First: {_format_time(report_row.get('first_runner'))}",
        f"Peak Start: {_format_time(report_row.get('peak_start'))}",
        f"Peak End: {_format_time(report_row.get('peak_end'))}",
        f"Last: {_format_time(report_row.get('last_runner'))}",
    ]
    for line in timings_lines:
        y = _draw_text_block(c, f"- {line}", font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    y = _draw_text_block(c, "🏃 EVENTS", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    events = _extract_events(location)
    if events:
        for event_name in events:
            y = _draw_text_block(c, f"- {event_name}", font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)
    else:
        y = _draw_text_block(c, "- NA", font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    proxy_loc_id = location.get("proxy_loc_id")
    if proxy_loc_id not in [None, "", "nan"] and not pd.isna(proxy_loc_id):
        proxy_note = "This location is near the course, but not directly on one or more events' course."
        y = _draw_text_block(c, proxy_note, font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    y = _draw_text_block(c, "📄 NOTES", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    y = _draw_text_block(c, _format_bullets(location.get("notes", "") or "NA"), font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    y = _draw_text_block(c, "📦 EQUIPMENT", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    y = _draw_text_block(c, _format_bullets(location.get("equipment", "") or "NA"), font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    y = _draw_text_block(c, "📞 CONTACT", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    y = _draw_text_block(c, _format_bullets(location.get("contact", "") or "NA"), font_body, 12, _MARGIN + 16, y - 2, page_w - 2 * _MARGIN)

    y = _draw_text_block(c, "⛈️ WEATHER", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    y = _draw_text_block(
        c,
        "- Dress for the weather conditions for the duration of your shift.",
        font_body,
        12,
        _MARGIN + 16,
        y - 2,
        page_w - 2 * _MARGIN,
    )
    y = _draw_text_block(c, "👟 FOOTWEAR", font_bold, 14, _MARGIN, y - _SECTION_GAP, page_w - 2 * _MARGIN)
    _draw_text_block(
        c,
        "- Wear comfortable shoes as you will be standing for most of your shift.\n"
        "- You are welcome to bring a lawn chair to wait outside of peak hours.",
        font_body,
        12,
        _MARGIN + 16,
        y - 2,
        page_w - 2 * _MARGIN,
    )

    c.showPage()
    c.save()


def _extract_events(location: Dict[str, Any]) -> List[str]:
    events = []
    for name in ["full", "half", "10k", "elite", "open"]:
        value = str(location.get(name, "")).strip().lower()
        if value == "y":
            events.append(name)
    return events


def _build_google_maps_url(lat: Any, lon: Any) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"


def _format_time(value: Any) -> str:
    if value is None:
        return "NA"
    text = str(value).strip()
    if not text or text.lower() in {"na", "nan", "none"}:
        return "NA"
    if len(text) >= 5 and ":" in text:
        return text[:5]
    return text


def _slugify(value: str) -> str:
    value = value.strip()
    value = value.replace("/", "-")
    value = re.sub(r'[\\:*?"<>|]', "", value)
    return value.strip()


def _register_fonts() -> Tuple[str, str, str]:
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_body = font_regular
    try:
        font_paths = [
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        bold_paths = [
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        regular_path = next((p for p in font_paths if Path(p).exists()), None)
        bold_path = next((p for p in bold_paths if Path(p).exists()), None)
        if regular_path and bold_path:
            pdfmetrics.registerFont(TTFont("DejaVuSans", regular_path))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
            font_regular = "DejaVuSans"
            font_bold = "DejaVuSans-Bold"
            font_body = "DejaVuSans"
    except Exception:
        # Fall back to built-in Helvetica if custom fonts unavailable
        pass
    return font_regular, font_bold, font_body


def _draw_label_value(
    c: canvas.Canvas,
    label: str,
    value: str,
    label_font: str,
    value_font: str,
    label_size: int,
    value_size: int,
    x: float,
    y: float,
    max_width: float
) -> float:
    c.setFont(label_font, label_size)
    label_text = f"{label}: "
    c.drawString(x, y, label_text)
    label_width = pdfmetrics.stringWidth(label_text, label_font, label_size)
    c.setFont(value_font, value_size)
    value_lines = _wrap_line(value, value_font, value_size, max_width - label_width)
    if not value_lines:
        value_lines = ["NA"]
    first_line = value_lines[0]
    c.drawString(x + label_width, y, first_line)
    y -= (value_size + 2)
    for line in value_lines[1:]:
        c.drawString(x, y, line)
        y -= (value_size + 2)
    return y


def _draw_gps_with_link(
    c: canvas.Canvas,
    gps_value: str,
    maps_url: str,
    label_font: str,
    value_font: str,
    font_size: int,
    x: float,
    y: float,
    max_width: float
) -> float:
    label_text = "GPS: "
    c.setFont(label_font, font_size)
    c.drawString(x, y, label_text)
    label_width = pdfmetrics.stringWidth(label_text, label_font, font_size)

    c.setFont(value_font, font_size)
    gps_width = pdfmetrics.stringWidth(gps_value, value_font, font_size)
    c.drawString(x + label_width, y, gps_value)

    link_text = "Google Maps"
    link_x = x + label_width + gps_width + 8
    link_width = pdfmetrics.stringWidth(link_text, value_font, font_size)

    if link_x + link_width > x + max_width:
        # If it won't fit on the same line, place directly after GPS with minimal spacing
        link_x = x + label_width + gps_width + 2

    c.setFillColorRGB(0, 0, 1)
    c.drawString(link_x, y, link_text)
    c.setLineWidth(0.5)
    c.line(link_x, y - 1, link_x + link_width, y - 1)
    c.setFillColorRGB(0, 0, 0)
    c.linkURL(maps_url, (link_x, y - 2, link_x + link_width, y + font_size))

    return y - _SECTION_GAP


def _format_bullets(text: str) -> str:
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "- NA"
    return "\n".join(f"- {line}" for line in lines)


def _draw_text_block(
    c: canvas.Canvas,
    text: str,
    font_name: str,
    font_size: int,
    x: float,
    y: float,
    max_width: float
) -> float:
    c.setFont(font_name, font_size)
    for line in text.splitlines() if "\n" in text else [text]:
        for wrapped_line in _wrap_line(line, font_name, font_size, max_width):
            c.drawString(x, y, wrapped_line)
            y -= (font_size + 2)
    return y


def _wrap_line(
    text: str,
    font_name: str,
    font_size: int,
    max_width: float
) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
