"""
Computed locations report JSON (Issues #894 / #895).

Plan Locations and Execute read this artifact via GET /api/locations.
CSV reports remain exports only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

LOCATIONS_REPORT_FILENAME = "locations_report.json"


def locations_report_relpath(day: str) -> str:
    return f"{day}/computation/{LOCATIONS_REPORT_FILENAME}"


def parse_optional_id(value: Any) -> Optional[int]:
    """Parse a pass_id / loc_id; empty, NaN, and non-numeric become None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null", "na"):
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def authored_proxy_pass_id(row: Mapping[str, Any]) -> Optional[int]:
    """
    Timing-source pass instance from Build/package fields.

    Package ``proxy_loc_id`` is a legacy alias of ``proxy_pass_id`` (pass instance),
    not the human Location id. Computed JSON resolves the human id separately.
    """
    for field in ("proxy_pass_id", "proxy_loc_id"):
        parsed = parse_optional_id(row.get(field))
        if parsed is not None:
            return parsed
    timing = row.get("timing_source")
    if isinstance(timing, str) and timing.startswith("proxy:"):
        return parse_optional_id(timing.split(":", 1)[1])
    return None


def pass_id_to_loc_id_map(
    pass_rows: Sequence[Mapping[str, Any]],
) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for row in pass_rows:
        pid = parse_optional_id(row.get("pass_id") or row.get("id"))
        lid = parse_optional_id(row.get("loc_id"))
        if pid is not None and lid is not None:
            out[pid] = lid
    return out


def resolve_proxy_ids(
    raw_proxy_pass_id: Optional[int],
    pass_to_loc: Mapping[int, int],
) -> Tuple[Optional[int], Optional[int]]:
    """
    Return ``(proxy_pass_id, proxy_loc_id)``.

    ``proxy_loc_id`` is the human Location number of the timing-source pass.
    If the authored value is already a human loc_id (not a pass_id), keep it
    as ``proxy_loc_id`` and pick a matching pass when unique.
    """
    if raw_proxy_pass_id is None:
        return None, None
    if raw_proxy_pass_id in pass_to_loc:
        return raw_proxy_pass_id, pass_to_loc[raw_proxy_pass_id]
    loc_ids = {lid for lid in pass_to_loc.values()}
    if raw_proxy_pass_id in loc_ids:
        matches = [pid for pid, lid in pass_to_loc.items() if lid == raw_proxy_pass_id]
        proxy_pass = matches[0] if len(matches) == 1 else (matches[0] if matches else None)
        return proxy_pass, raw_proxy_pass_id
    return raw_proxy_pass_id, None


def attach_resolved_proxies(pass_rows: Sequence[MutableMapping[str, Any]]) -> None:
    """Stamp resolved ``proxy_pass_id`` / ``proxy_loc_id`` on pass-level rows in place."""
    pass_to_loc = pass_id_to_loc_id_map(pass_rows)
    for row in pass_rows:
        raw = authored_proxy_pass_id(row)
        proxy_pass, proxy_loc = resolve_proxy_ids(raw, pass_to_loc)
        row["proxy_pass_id"] = proxy_pass
        row["proxy_loc_id"] = proxy_loc


def proxy_from_passes(
    passes: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[int], Optional[int]]:
    """First authored/resolved proxy on member passes (off-course is typically one pass)."""
    for row in passes:
        pp = parse_optional_id(row.get("proxy_pass_id"))
        pl = parse_optional_id(row.get("proxy_loc_id"))
        if pp is None:
            pp = authored_proxy_pass_id(row)
        if pp is not None or pl is not None:
            return pp, pl
    return None, None


def locations_proxied_to(
    locations: Iterable[Mapping[str, Any]], loc_id: Any
) -> List[Mapping[str, Any]]:
    """Reverse index: rows whose ``proxy_loc_id`` equals the given human Location id."""
    target = parse_optional_id(loc_id)
    if target is None:
        return []
    out: List[Mapping[str, Any]] = []
    for row in locations:
        if parse_optional_id(row.get("proxy_loc_id")) == target:
            out.append(row)
    return out


def json_ready(value: Any) -> Any:
    """JSON-serializable form: NaN/Inf → None, numpy scalars → Python."""
    if value is None:
        return None
    typ_name = type(value).__name__
    if typ_name in ("NAType", "NaTType"):
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if hasattr(value, "item") and callable(value.item) and not isinstance(value, (bytes, bytearray)):
        try:
            return json_ready(value.item())
        except (ValueError, AttributeError):
            pass
    return value


def resources_available_from_rows(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    codes = set()
    for row in rows:
        for key, raw in row.items():
            if not str(key).endswith("_count"):
                continue
            try:
                if float(raw or 0) > 0:
                    codes.add(str(key)[:-6])
            except (TypeError, ValueError):
                continue
    return sorted(codes)


def build_locations_report_document(
    *,
    run_id: Optional[str],
    day: Optional[str],
    locations: Sequence[Mapping[str, Any]],
    resources_available: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    loc_list = [json_ready(dict(row)) for row in locations]
    resources = list(resources_available) if resources_available is not None else resources_available_from_rows(loc_list)
    return {
        "run_id": run_id or "",
        "day": (day or "").strip().lower(),
        "count": len(loc_list),
        "resources_available": resources,
        "locations": loc_list,
    }


def write_locations_report_json(path: Path, document: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_ready(dict(document)), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return path


def computation_dir_for_report(
    *,
    run_id: Optional[str],
    day: Optional[str],
    output_dir: Optional[str] = None,
) -> Optional[Path]:
    """Prefer runflow/analysis/{run_id}/{day}/computation; else sibling of reports/."""
    if run_id and day:
        from app.utils.run_id import get_run_directory

        return get_run_directory(run_id) / str(day).strip().lower() / "computation"
    if output_dir:
        out = Path(output_dir)
        if out.name == "reports":
            return out.parent / "computation"
    return None
