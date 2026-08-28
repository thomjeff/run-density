"""
HTML location one-pagers (Issue #702 / #735 / #871).

Analysis writes volunteer HTML only under loc_sheets/html/{loc_id}.html.
PDFs and in-run map-tile stitching are not part of the pipeline; Results
Locations can zip the existing HTML when the user asks.
"""

from __future__ import annotations

import html
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.utils.carto_basemaps import carto_light_tile_url

logger = logging.getLogger(__name__)


def generate_location_onepagers(
    run_id: str,
    day: str,
    locations_results_json_path: Path,
    locations_report_csv_path: Path,
    output_dir: Path,
    maps_dir: Optional[Path] = None,
    radius_m: float = 0.0,
) -> int:
    """
    Generate HTML one-pagers for locations flagged onepage='y'.

    Issue #810: paired reverse-leg locations (shared location_key) produce one
    sheet with Outbound + Return runner timings. HTML is written for each
    loc_id in the group so existing /locsheets/.../{loc_id} URLs keep working.

    ``maps_dir`` / ``radius_m`` are unused (#871); kept so older callers do not break.

    Returns:
        Number of Location sheets generated (paired counts as one).
    """
    from app.core.locations.pairing import (
        effective_location_key,
        max_time_str,
        min_time_str,
        time_to_seconds,
    )

    locations_data = _load_locations_results(locations_results_json_path)
    if not locations_data:
        logger.warning(
            f"Issue #702: locations_results.json empty or unreadable at {locations_results_json_path}"
        )
        return 0

    report_lookup = _load_pass_timings_report(locations_report_csv_path)
    if not report_lookup:
        logger.warning(
            f"Issue #702: Passes/Locations report not found or empty at {locations_report_csv_path}"
        )
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    html_dir = output_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    # Keys / ids that should emit a sheet (any pass with onepage=y)
    sheet_keys: set[str] = set()
    sheet_solo_ids: set[int] = set()
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    by_id: Dict[int, Dict[str, Any]] = {}

    for location in locations_data:
        loc_day = str(location.get("day", "")).strip().lower()
        if loc_day and loc_day != str(day).strip().lower():
            continue
        pid = _pass_instance_id(location)
        if pid is None:
            continue
        by_id[pid] = location
        key = effective_location_key(location)
        if key:
            by_key.setdefault(key, []).append(location)
        if _is_onepager_location(location, day):
            if key:
                sheet_keys.add(key)
            else:
                sheet_solo_ids.add(pid)

    sheet_specs: List[Dict[str, Any]] = []

    for key in sorted(sheet_keys):
        members = by_key.get(key) or []
        passes: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for loc in members:
            pid = _pass_instance_id(loc)
            if pid is None:
                continue
            report_row = report_lookup.get(pid)
            if not report_row:
                continue
            passes.append((loc, report_row))
        if not passes:
            continue
        passes.sort(
            key=lambda pair: (
                time_to_seconds(pair[1].get("first_runner"))
                if time_to_seconds(pair[1].get("first_runner")) is not None
                else 10**9,
                _pass_instance_id(pair[0]) or 10**9,
            )
        )
        primary_loc, primary_report = passes[0]
        combined = dict(primary_report)
        combined["loc_start"] = min_time_str(r.get("loc_start") for _, r in passes)
        combined["loc_end"] = max_time_str(r.get("loc_end") for _, r in passes)
        combined["first_runner"] = min_time_str(r.get("first_runner") for _, r in passes)
        combined["last_runner"] = max_time_str(r.get("last_runner") for _, r in passes)
        human_loc_id = _human_location_id(primary_loc, primary_report)
        sheet_specs.append(
            {
                "location": {**primary_loc, "loc_id": human_loc_id},
                "report_row": {**combined, "loc_id": human_loc_id},
                "passes": passes,
                "paired": len(passes) > 1,
                "sheet_loc_id": human_loc_id,
                "all_loc_ids": [human_loc_id],
            }
        )

    for pid in sorted(sheet_solo_ids):
        location = by_id.get(pid)
        report_row = report_lookup.get(pid)
        if not location or not report_row:
            continue
        human_loc_id = _human_location_id(location, report_row)
        sheet_specs.append(
            {
                "location": {**location, "loc_id": human_loc_id},
                "report_row": {**report_row, "loc_id": human_loc_id},
                "passes": [(location, report_row)],
                "paired": False,
                "sheet_loc_id": human_loc_id,
                "all_loc_ids": [human_loc_id],
            }
        )

    count = 0
    for spec in sheet_specs:
        location = spec["location"]
        report_row = spec["report_row"]
        loc_id = spec["sheet_loc_id"]
        html_path = html_dir / f"{loc_id}.html"
        _render_onepager_html(
            location,
            report_row,
            html_path,
            day=day,
            passes=spec["passes"] if spec["paired"] else None,
            sheet_loc_ids=spec["all_loc_ids"],
        )
        count += 1

    logger.debug(
        "Issue #702/#735/#871: Generated %s HTML one-pagers for day %s (run %s)",
        count,
        day,
        run_id,
    )
    return count


def _pass_instance_id(location: Dict[str, Any]) -> Optional[int]:
    for field in ("pass_id", "id"):
        raw = location.get(field)
        if raw is None or raw == "":
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    raw = location.get("loc_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _human_location_id(
    location: Dict[str, Any], report_row: Optional[Dict[str, Any]] = None
) -> int:
    for source in (location, report_row or {}):
        raw = source.get("loc_id")
        pid = source.get("pass_id")
        try:
            lid = int(raw)
        except (TypeError, ValueError):
            continue
        try:
            if pid is not None and int(pid) != lid:
                return lid
        except (TypeError, ValueError):
            return lid
        # If only loc_id present, treat as human id (already consolidated) or legacy pass
        return lid
    pid = _pass_instance_id(location)
    return pid if pid is not None else 0


def _load_locations_results(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Issue #702: Failed to load locations_results.json: {exc}")
        return []

    return data.get("locations", []) if isinstance(data, dict) else []


def _load_pass_timings_report(path: Path) -> Dict[int, Dict[str, Any]]:
    """Prefer Passes.csv (keyed by pass_id); fall back to Locations.csv / legacy loc_id."""
    from app.location_report import parse_by_event

    candidates = []
    if path.name.lower() == "locations.csv":
        candidates.append(path.parent / "Passes.csv")
        candidates.append(path.parent / "passes.csv")
    candidates.append(path)
    if path.name.lower() == "passes.csv":
        candidates.append(path.parent / "Locations.csv")

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            df = pd.read_csv(candidate)
        except Exception as exc:
            logger.warning(f"Issue #702: Failed to read {candidate}: {exc}")
            continue
        if df.empty:
            continue
        id_col = "pass_id" if "pass_id" in df.columns else "loc_id"
        if id_col not in df.columns:
            continue
        df = df.replace([math.inf, -math.inf], None)
        df[id_col] = pd.to_numeric(df[id_col], errors="coerce")
        df = df.dropna(subset=[id_col])
        df[id_col] = df[id_col].astype(int)
        records = df.set_index(id_col).to_dict("index")
        for row in records.values():
            if "by_event" in row:
                row["by_event"] = parse_by_event(row.get("by_event"))
        return records
    return {}


def _by_event_timing_lines(report_row: Dict[str, Any]) -> List[str]:
    """Issue #828: lines for per-event first/peak/last under aggregate timings."""
    from app.location_report import parse_by_event

    by_event = parse_by_event(report_row.get("by_event"))
    if not by_event:
        return []
    lines: List[str] = []
    for event in sorted(by_event.keys(), key=lambda e: str(e).lower()):
        w = by_event[event] or {}
        lines.append(
            f"{event}: First {_format_time(w.get('first_runner'))} · "
            f"Peak {_format_time(w.get('peak_start'))}–{_format_time(w.get('peak_end'))} · "
            f"Last {_format_time(w.get('last_runner'))}"
        )
    return lines


def _by_event_timing_html(report_row: Dict[str, Any]) -> str:
    lines = _by_event_timing_lines(report_row)
    if not lines:
        return ""
    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    return f"<p><strong>By event</strong></p><ul>{items}</ul>"


def _load_locations_report(path: Path) -> Dict[int, Dict[str, Any]]:
    return _load_pass_timings_report(path)


def _is_onepager_location(location: Dict[str, Any], day: str) -> bool:
    loc_day = str(location.get("day", "") or "").strip().lower()
    if loc_day in ("", "nan", "none", "null"):
        loc_day = ""
    if loc_day and loc_day != str(day).strip().lower():
        return False

    onepage_flag = str(location.get("onepage", "")).strip().lower()
    return onepage_flag == "y"


def _render_onepager_html(
    location: Dict[str, Any],
    report_row: Dict[str, Any],
    output_path: Path,
    day: str = "",
    passes: Optional[List[Tuple[Dict[str, Any], Dict[str, Any]]]] = None,
    sheet_loc_ids: Optional[List[Any]] = None,
) -> None:
    """Render one-pager as HTML (Issue #735 / #810 / #871). Map tiles load in the browser."""
    loc_id = location.get("loc_id", "")
    loc_label = location.get("loc_label", "")
    if passes and len(passes) > 1:
        ids = " / ".join(str(p[0].get("loc_id")) for p in passes)
        title = f"LOCATION: {loc_label} ({ids})"
    else:
        title = f"LOCATION: {loc_id} - {loc_label}"
    loc_type = html.escape(str(location.get("loc_type", "")))
    resources = _extract_resources(location)
    lat = location.get("lat", "")
    lon = location.get("lon", "")
    gps_line = f"{lat}, {lon}"
    maps_url = _build_google_maps_url(lat, lon)
    loc_start = _format_time(report_row.get("loc_start"))
    loc_end = _format_time(report_row.get("loc_end"))
    duration = report_row.get("duration")
    duration_text = f"{duration} min" if duration not in [None, "", "NA"] else "NA"
    day_esc = html.escape(day)
    is_proxy = _is_proxy_location(location)
    events = _extract_events(location)
    notes_html = _format_bullets_html(location.get("notes", "") or "NA")
    equipment_html = _format_bullets_html(location.get("equipment", "") or "NA")
    contact_html = _format_bullets_html(location.get("contact", "") or "NA")

    map_lat = map_lon = None
    try:
        map_lat = float(lat)
        map_lon = float(lon)
        if not (math.isfinite(map_lat) and math.isfinite(map_lon)):
            map_lat = map_lon = None
    except (TypeError, ValueError):
        map_lat = map_lon = None

    if is_proxy:
        runner_timings_html = "<p>This location is near the course, but not directly on one or more events' course.</p>"
    elif passes and len(passes) > 1:
        blocks = [
            "<p>The predicted timing for the first and last runner to arrive at and depart from this location. "
            "Outbound and Return are separate passes on paired reverse legs.</p>"
        ]
        for idx, (_loc, prow) in enumerate(passes):
            role = "Outbound" if idx == 0 else "Return"
            pid = html.escape(str(_loc.get("loc_id")))
            blocks.append(f"<h3>{role} (ID {pid})</h3>")
            blocks.append(
                "<ul>"
                f"<li>First: {html.escape(_format_time(prow.get('first_runner')))}</li>"
                f"<li>Peak Start: {html.escape(_format_time(prow.get('peak_start')))}</li>"
                f"<li>Peak End: {html.escape(_format_time(prow.get('peak_end')))}</li>"
                f"<li>Last: {html.escape(_format_time(prow.get('last_runner')))}</li>"
                "</ul>"
            )
            blocks.append(_by_event_timing_html(prow))
        runner_timings_html = "\n".join(blocks)
    else:
        runner_timings_html = """
        <p>The predicted timing for the first and last runner to arrive at and depart from this location.
        The peak times are when to expect the highest number of runners.</p>
        <ul>
            <li>First: """ + html.escape(_format_time(report_row.get("first_runner"))) + """</li>
            <li>Peak Start: """ + html.escape(_format_time(report_row.get("peak_start"))) + """</li>
            <li>Peak End: """ + html.escape(_format_time(report_row.get("peak_end"))) + """</li>
            <li>Last: """ + html.escape(_format_time(report_row.get("last_runner"))) + """</li>
        </ul>""" + _by_event_timing_html(report_row)

    events_list = ", ".join(events) if events else "NA"

    tile_url = json.dumps(carto_light_tile_url())
    if map_lat is not None and map_lon is not None:
        map_block = (
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
            '<div id="loc-map" class="map" role="img" aria-label="Location map"></div>'
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            "<script>(function(){"
            f"var lat={json.dumps(map_lat)}, lon={json.dumps(map_lon)}, url={tile_url};"
            "var map=L.map('loc-map').setView([lat,lon],16);"
            "L.tileLayer(url,{attribution:'&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>, &copy; <a href=\"https://carto.com/attributions\">CARTO</a>',subdomains:'abcd',maxZoom:20}).addTo(map);"
            "L.marker([lat,lon]).addTo(map);"
            "})();</script>"
        )
    else:
        map_block = ""

    resources_html = "".join(f"<li>{html.escape(r)}</li>" for r in resources) if resources else "<li>NA</li>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 1rem 2rem; }}
        h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
        h2 {{ font-size: 1rem; margin-top: 1rem; margin-bottom: 0.25rem; }}
        h3 {{ font-size: 0.95rem; margin-top: 0.75rem; margin-bottom: 0.25rem; }}
        p, ul {{ margin: 0.25rem 0; }}
        ul {{ padding-left: 1.5rem; }}
        .map {{ width: 100%; height: 360px; margin: 0.5rem 0; border: 1px solid #ddd; }}
        a {{ color: #0066cc; }}
    </style>
</head>
<body>
    <h1>{html.escape(title)}</h1>
    <p><strong>TYPE:</strong> {loc_type}</p>
    <h2>LOCATION TIMES</h2>
    <p>Time on location across all shifts.</p>
    <p>Day: {day_esc}</p>
    <p>Times: """ + html.escape(f"{loc_start} - {loc_end} (Duration: {duration_text})") + """</p>
    <h2>RESOURCES</h2>
    <ul>
    """ + resources_html + """
    </ul>
    <h2>MAP</h2>
    """ + (map_block + "\n    " if map_block else "") + """<p>GPS: """ + html.escape(gps_line) + """</p>
    <p>View on <a href=\"""" + html.escape(maps_url) + """\" target="_blank" rel="noopener">Google Maps</a></p>
    <h2>RUNNER TIMINGS</h2>
    """ + runner_timings_html + """
    <h2>EVENTS</h2>
    <p>""" + (html.escape("Runners from the following events will be at this location during the times above: " + events_list) if not is_proxy else html.escape("This location is near the course, but not directly on one or more events' course.")) + """</p>
    <h2>NOTES</h2>
    """ + notes_html + """
    <h2>EQUIPMENT PROVIDED</h2>
    """ + equipment_html + """
    <h2>CONTACT</h2>
    """ + contact_html + """
    <h2>WEATHER</h2>
    <p>Dress for the weather conditions for the duration of your shift.</p>
    <h2>FOOTWEAR</h2>
    <p>Wear comfortable shoes as you will be standing for most of your shift. You are welcome to bring a lawn chair to wait outside of peak hours.</p>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")


def _format_bullets_html(text: str) -> str:
    """Format text as HTML bullet list (Issue #735)."""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "<p>- NA</p>"
    return "<ul>" + "".join(f"<li>{html.escape(line)}</li>" for line in lines) + "</ul>"


def _extract_events(location: Dict[str, Any]) -> List[str]:
    from app.core.event_discovery import active_events

    return active_events(location)


def _is_proxy_location(location: Dict[str, Any]) -> bool:
    proxy_loc_id = location.get("proxy_loc_id")
    return proxy_loc_id not in [None, "", "nan"] and not pd.isna(proxy_loc_id)


def _extract_resources(location: Dict[str, Any]) -> List[str]:
    resources = []
    nested = location.get("resources")
    if isinstance(nested, dict):
        for code, count in nested.items():
            try:
                count_value = int(count)
            except (TypeError, ValueError):
                continue
            if count_value > 0:
                resources.append(f"{code}: {count_value}")
        if resources:
            return resources
    for key, count in location.items():
        if not str(key).endswith("_count"):
            continue
        code = str(key)[: -len("_count")]
        if count is None or (isinstance(count, float) and pd.isna(count)):
            continue
        try:
            count_value = int(count)
        except (TypeError, ValueError):
            continue
        if count_value > 0:
            resources.append(f"{code}: {count_value}")
    return resources


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


