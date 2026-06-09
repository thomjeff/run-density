#!/usr/bin/env python3
"""
Copy leg-scoped locations (and resources) from a legacy package segment_library
into org legs used by an org-primary config package.

Matches legs by explicit map and/or nearest GPX geometry. Run inside Docker:

  python scripts/migrate_leg_locations.py \\
    --source K6F4cn3dM4TCzNQEDxJBeD \\
    --target QhVdbSZKvjQ4cEGvPDddtb \\
    --apply
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.core.config_package.org_leg_library import (
    load_org_leg_manifest,
    save_org_leg_manifest,
)
from app.core.config_package.segment_recipes import apply_package_recipes
from app.core.config_package.storage import (
    get_config_root,
    load_config_course,
    load_config_manifest,
    resolve_config_package_path,
    save_config_course,
    save_config_manifest,
)
from app.core.locations.schema import count_column, ensure_manifest_resources, normalize_location_record
from app.utils.constants import COURSE_EVENT_IDS
from app.core.course.segment_library import manifest_legs, parse_leg_gpx, set_manifest_legs
from app.core.config_package.legs import _normalize_locations
from app.utils.run_id import get_runflow_root

# High-confidence K6 leg id -> org leg id (length/label verified manually).
EXPLICIT_K6_TO_ORG: Dict[str, str] = {
    "01": "12",  # Start to Friel
    "02": "05",  # Friel to 10k Turn
    "05": "06",  # Friel to Station At Barker
    "06": "13",  # Station to Gibson Trail (short)
    "08": "09",  # Gibson Trail to Bridge at Mill
    "14": "03",  # Bridge Mill to Half Turn
    "15": "10",  # Half Turn to Bridge at Mill
    "13": "11",  # Half Turn to Full Turn (chase)
}

_LOC_FIELDS = (
    "loc_label",
    "loc_type",
    "lat",
    "lon",
    "placement",
    "location_key",
    "notes",
    "buffer",
    "interval",
    "zone",
    "equipment",
    "contact",
    "proxy_loc_id",
    "day",
    "onepage",
    "resources",
)

_COURSE_MERGE_FIELDS = _LOC_FIELDS + tuple(COURSE_EVENT_IDS)


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_to_route_m(lon: float, lat: float, coords: List[List[float]]) -> float:
    if not coords:
        return float("inf")
    best = float("inf")
    for lon2, lat2 in coords:
        best = min(best, _haversine_m(lon, lat, lon2, lat2))
    for i in range(len(coords) - 1):
        lon_a, lat_a = coords[i]
        lon_b, lat_b = coords[i + 1]
        for t in (0.25, 0.5, 0.75):
            lon_m = lon_a + (lon_b - lon_a) * t
            lat_m = lat_a + (lat_b - lat_a) * t
            best = min(best, _haversine_m(lon, lat, lon_m, lat_m))
    return best


def _load_source_legs(source_id: str) -> List[Dict[str, Any]]:
    lib = get_config_root() / source_id / "segment_library"
    manifest = yaml.safe_load((lib / "manifest.yaml").read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = []
    for entry in manifest_legs(manifest):
        gpx = lib / str(entry["file"])
        parsed = parse_leg_gpx(gpx) if gpx.is_file() else {}
        rows.append(
            {
                "id": str(entry["id"]).strip(),
                "seg_label": str(entry.get("seg_label") or "").strip(),
                "locations": copy.deepcopy(entry.get("locations") or []),
                "coords": parsed.get("coordinates") or [],
            }
        )
    return rows


def _load_org_legs() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    org_dir = get_runflow_root() / "org" / "legs"
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = []
    for entry in manifest_legs(manifest):
        gpx = org_dir / str(entry["file"])
        parsed = parse_leg_gpx(gpx) if gpx.is_file() else {}
        legs.append(
            {
                "entry": copy.deepcopy(entry),
                "id": str(entry["id"]).strip(),
                "coords": parsed.get("coordinates") or [],
            }
        )
    return manifest, legs


def _loc_key(loc: Dict[str, Any]) -> Tuple:
    return (
        round(float(loc.get("lat") or 0), 5),
        round(float(loc.get("lon") or 0), 5),
        str(loc.get("loc_label") or "").strip().lower(),
    )


def _trim_loc(loc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: copy.deepcopy(loc[k]) for k in _LOC_FIELDS if k in loc}
    return out


def _enrich_loc_from_course(
    loc: Dict[str, Any],
    course_by_key: Dict[Tuple, Dict[str, Any]],
    resource_codes: List[str],
) -> Dict[str, Any]:
    """Overlay ops metadata from source course.json (resource counts live there, not in leg manifest)."""
    src = course_by_key.get(_loc_key(loc))
    if not src:
        return loc
    out = copy.deepcopy(loc)
    for field in _COURSE_MERGE_FIELDS:
        if field in src and src[field] not in (None, ""):
            out[field] = copy.deepcopy(src[field])
    for code in resource_codes:
        col = count_column(code)
        if col in src and src[col] not in (None, ""):
            out[col] = src[col]
    if isinstance(src.get("resources"), dict):
        out["resources"] = copy.deepcopy(src["resources"])
    normalize_location_record(out, resource_codes, index=0)
    return out


def merge_course_location_metadata(source_id: str, target_id: str) -> Dict[str, Any]:
    """Copy resource counts and ops fields from source course.json onto target course locations."""
    src_course = load_config_course(source_id)
    tgt_course = load_config_course(target_id)
    tgt_manifest = load_config_manifest(target_id)
    resource_codes = [r["code"] for r in ensure_manifest_resources(tgt_manifest)]

    src_by_key = {
        _loc_key(loc): loc
        for loc in (src_course.get("locations") or [])
        if isinstance(loc, dict)
    }

    merged = 0
    unmatched: List[str] = []
    for loc in tgt_course.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        src = src_by_key.get(_loc_key(loc))
        if not src:
            unmatched.append(str(loc.get("loc_label") or ""))
            continue
        for field in _COURSE_MERGE_FIELDS:
            if field in src and src[field] not in (None, ""):
                loc[field] = copy.deepcopy(src[field])
        for code in resource_codes:
            col = count_column(code)
            if col in src and src[col] not in (None, ""):
                loc[col] = src[col]
        if isinstance(src.get("resources"), dict):
            loc["resources"] = copy.deepcopy(src["resources"])
        idx = max(0, int(loc.get("id", 1)) - 1)
        normalize_location_record(loc, resource_codes, index=idx)
        merged += 1

    save_config_course(target_id, tgt_course)
    return {
        "course_locations_merged": merged,
        "course_unmatched": len(unmatched),
        "unmatched_labels": unmatched[:10],
    }


def _nearest_org_leg(
    loc: Dict[str, Any],
    org_legs: List[Dict[str, Any]],
) -> Tuple[Optional[str], float]:
    lat = float(loc.get("lat") or 0)
    lon = float(loc.get("lon") or 0)
    placement = str(loc.get("placement") or "along").strip().lower()
    limit_m = 900.0 if placement == "off" or loc.get("loc_type") == "traffic" else 350.0
    best_id: Optional[str] = None
    best_d = float("inf")
    for leg in org_legs:
        d = _point_to_route_m(lon, lat, leg["coords"])
        if d < best_d:
            best_d = d
            best_id = leg["id"]
    if best_d > limit_m:
        return None, best_d
    return best_id, best_d


def migrate(
    source_id: str,
    target_id: str,
    *,
    apply: bool = False,
    dry_run: bool = False,
    course_only: bool = False,
) -> Dict[str, Any]:
    if course_only:
        course_result = merge_course_location_metadata(source_id, target_id)
        if apply:
            from app.core.config_package.legs import sync_leg_location_metadata_from_course

            sync_leg_location_metadata_from_course(target_id)
            course_result["synced_org_legs"] = True
        return course_result

    source_legs = _load_source_legs(source_id)
    src_course = load_config_course(source_id)
    src_manifest = load_config_manifest(source_id)
    resource_codes = [r["code"] for r in ensure_manifest_resources(src_manifest)]
    course_by_key = {
        _loc_key(loc): loc
        for loc in (src_course.get("locations") or [])
        if isinstance(loc, dict)
    }
    org_manifest, org_legs = _load_org_legs()
    org_by_id = {leg["id"]: leg for leg in org_legs}

    assigned: Dict[str, List[Dict[str, Any]]] = {leg["id"]: [] for leg in org_legs}
    seen: Dict[str, set] = {leg["id"]: set() for leg in org_legs}
    report: Dict[str, Any] = {
        "explicit": [],
        "geometry": [],
        "skipped": [],
        "unmapped_source_legs": [],
    }

    for src in source_legs:
        src_id = src["id"]
        locs = src["locations"]
        if not locs:
            continue
        org_id = EXPLICIT_K6_TO_ORG.get(src_id)
        mode = "explicit"
        for loc in locs:
            trimmed = _trim_loc(loc)
            if not trimmed:
                continue
            target_org = org_id
            dist_m = 0.0
            if not target_org:
                mode = "geometry"
                target_org, dist_m = _nearest_org_leg(trimmed, org_legs)
            if not target_org:
                report["skipped"].append(
                    {
                        "source_leg": src_id,
                        "label": trimmed.get("loc_label"),
                        "reason": f"no org leg within tolerance ({dist_m:.0f}m)",
                    }
                )
                continue
            enriched = _enrich_loc_from_course(trimmed, course_by_key, resource_codes)
            key = _loc_key(enriched)
            if key in seen[target_org]:
                continue
            seen[target_org].add(key)
            assigned[target_org].append(enriched)
            bucket = report["explicit"] if mode == "explicit" else report["geometry"]
            bucket.append(
                {
                    "source_leg": src_id,
                    "org_leg": target_org,
                    "label": trimmed.get("loc_label"),
                    "dist_m": round(dist_m, 1),
                }
            )
        if not org_id and locs:
            report["unmapped_source_legs"].append(
                {"source_leg": src_id, "seg_label": src["seg_label"], "loc_count": len(locs)}
            )

    if dry_run:
        counts = {oid: len(locs) for oid, locs in assigned.items() if locs}
        report["org_location_counts"] = counts
        report["total"] = sum(counts.values())
        return report

    for leg in org_legs:
        oid = leg["id"]
        new_locs = assigned.get(oid) or []
        if not new_locs:
            continue
        entry = leg["entry"]
        entry["locations"] = _normalize_locations(new_locs)
        org_by_id[oid]["entry"] = entry

    updated_entries = [org_by_id[leg["id"]]["entry"] for leg in org_legs]
    set_manifest_legs(org_manifest, updated_entries)
    save_org_leg_manifest(org_manifest)

    # Copy resource registry from source package to target.
    src_manifest = load_config_manifest(source_id)
    tgt_path = resolve_config_package_path(target_id)
    tgt_manifest = load_config_manifest(target_id)
    tgt_manifest["resources"] = copy.deepcopy(src_manifest.get("resources") or [])
    save_config_manifest(tgt_path, tgt_manifest)

    result = {
        "org_legs_updated": [oid for oid, locs in assigned.items() if locs],
        "location_counts": {oid: len(locs) for oid, locs in assigned.items() if locs},
        "total_locations": sum(len(locs) for locs in assigned.values()),
        "resources_copied": len(tgt_manifest.get("resources") or []),
        "report": report,
    }

    course_result = merge_course_location_metadata(source_id, target_id)
    result["course_merge"] = course_result

    if apply:
        from app.core.config_package.legs import sync_leg_location_metadata_from_course

        sync_leg_location_metadata_from_course(target_id)
        apply_package_recipes(target_id, export_csv=True)
        result["applied"] = True
        result["synced_org_legs"] = True

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate leg locations to org library")
    parser.add_argument("--source", required=True, help="Source config_id (legacy package legs)")
    parser.add_argument("--target", required=True, help="Target config_id (org-primary package)")
    parser.add_argument("--apply", action="store_true", help="Apply recipes after migration")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    parser.add_argument(
        "--course-only",
        action="store_true",
        help="Merge course.json metadata only (skip org leg reassignment)",
    )
    args = parser.parse_args()
    out = migrate(
        args.source,
        args.target,
        apply=args.apply,
        dry_run=args.dry_run,
        course_only=args.course_only,
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
