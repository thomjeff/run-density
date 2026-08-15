"""
Build Loc Sheets index entries for a day (Issue #735 / #740 / #810).

Uses locations_results.json only: ``onepage`` must be ``y`` (see locations.csv / pipeline).
Fallback: if none match, include locations that have a generated HTML one-pager on disk.

Issue #810: paired reverse-leg locations (shared ``location_key``) appear once in the
index, using the outbound (lowest) ``loc_id`` as the sheet link target. HTML is also
written under each pair member's loc_id for direct URL compatibility.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from app.core.locations.pairing import effective_location_key

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
    seen_keys: Set[str] = set()

    # Prefer grouping: any onepage=y member of a key emits one index row (min loc_id)
    onepage_by_key: Dict[str, List[Dict[str, Any]]] = {}
    onepage_solo: List[Dict[str, Any]] = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if not _day_matches(loc, selected_day):
            continue
        if not _is_onepage_y(loc):
            continue
        key = effective_location_key(loc)
        if key:
            onepage_by_key.setdefault(key, []).append(loc)
        else:
            onepage_solo.append(loc)

    for key, members in onepage_by_key.items():
        # Include all day-matching members of this key for label/id (even if only one is onepage)
        all_members = [
            loc
            for loc in locations
            if isinstance(loc, dict)
            and _day_matches(loc, selected_day)
            and effective_location_key(loc) == key
        ]
        pool = all_members or members

        def _lid(loc: Dict[str, Any]) -> int:
            try:
                return int(loc.get("loc_id"))
            except (TypeError, ValueError):
                return 10**9

        primary = min(pool, key=_lid)
        sheets.append(
            {
                "loc_id": primary.get("loc_id"),
                "label": primary.get("loc_label", ""),
                "location_key": key,
                "loc_ids": sorted({_lid(m) for m in pool if _lid(m) < 10**9}),
            }
        )
        seen_keys.add(key)

    for loc in onepage_solo:
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
        key = effective_location_key(loc)
        if key and key in seen_keys:
            continue
        lid = loc.get("loc_id")
        if lid is None or str(lid).strip() == "":
            continue
        lid_str = str(lid).strip()
        if html_dir.exists() and (html_dir / f"{lid_str}.html").is_file():
            if key:
                seen_keys.add(key)
            sheets.append({"loc_id": lid_str, "label": loc.get("loc_label", "")})

    sheets.sort(key=lambda x: (x["loc_id"] is None, x["loc_id"]))
    return sheets


def loc_sheets_html_dir(run_dir: Path, selected_day: str) -> Path:
    return Path(run_dir) / selected_day / "reports" / "loc_sheets" / "html"


def zip_loc_sheet_html(run_dir: Path, selected_day: str) -> bytes:
    """Pack already-written loc sheet HTML. Does not regenerate sheets (#871)."""
    import io
    import zipfile

    html_dir = loc_sheets_html_dir(run_dir, selected_day)
    if not html_dir.is_dir():
        raise FileNotFoundError(f"No location sheets for day {selected_day}")
    files = sorted(p for p in html_dir.glob("*.html") if p.is_file())
    if not files:
        raise FileNotFoundError(f"No location sheets for day {selected_day}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    return buf.getvalue()
