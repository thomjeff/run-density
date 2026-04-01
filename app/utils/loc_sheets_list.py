"""
Build Loc Sheets index entries for a day (Issue #735 / #740).

Uses locations_results.json only: ``onepage`` must be ``y`` (see locations.csv / pipeline).
Fallback: if none match, include locations that have a generated HTML one-pager on disk.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _day_matches(loc: Dict[str, Any], selected_day: str) -> bool:
    loc_day = str(loc.get("day", "")).strip().lower()
    return not loc_day or loc_day == selected_day


def _is_onepage_y(loc: Dict[str, Any]) -> bool:
    return str(loc.get("onepage", "")).strip().lower() == "y"


def build_loc_sheet_entries(run_dir: Path, selected_day: str) -> List[Dict[str, Any]]:
    """
    Return sorted list of {loc_id, label} for the Loc Sheets index page.
    """
    comp_path = run_dir / selected_day / "computation" / "locations_results.json"
    if not comp_path.exists():
        return []

    try:
        data = json.loads(comp_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not read locations_results.json at %s: %s", comp_path, e)
        return []

    locations = data.get("locations") or []
    sheets: List[Dict[str, Any]] = []

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if not _day_matches(loc, selected_day):
            continue
        if not _is_onepage_y(loc):
            continue
        sheets.append({"loc_id": loc.get("loc_id"), "label": loc.get("loc_label", "")})

    if sheets:
        sheets.sort(key=lambda x: (x["loc_id"] is None, x["loc_id"]))
        return sheets

    html_dir = run_dir / selected_day / "reports" / "loc_sheets" / "html"
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if not _day_matches(loc, selected_day):
            continue
        lid = loc.get("loc_id")
        if lid is None or str(lid).strip() == "":
            continue
        lid_str = str(lid).strip()
        if html_dir.exists() and (html_dir / f"{lid_str}.html").is_file():
            sheets.append({"loc_id": lid_str, "label": loc.get("loc_label", "")})

    sheets.sort(key=lambda x: (x["loc_id"] is None, x["loc_id"]))
    return sheets
