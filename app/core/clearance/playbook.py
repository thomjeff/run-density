"""Static clearance playbook from Locations last_runner (Issue #832)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.core.clearance.model import (
    CLEAR_WHEN_LAST_RUNNER,
    empty_clearance_doc,
    subject_key,
)
from app.core.clearance.storage import try_load_config_clearance
from app.core.locations.pairing import time_to_seconds
from app.core.motion.build import resolve_motion_package_id
from app.core.v2.analysis_config import load_analysis_json
from app.core.v2.timings import _format_seconds_to_hhmmss
from app.utils.run_id import get_run_directory

logger = logging.getLogger(__name__)


def _asset_label_map(doc: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for asset in doc.get("assets") or []:
        if isinstance(asset, dict) and asset.get("asset_id"):
            out[str(asset["asset_id"])] = str(asset.get("label") or asset["asset_id"])
    return out


def load_location_last_runners(locations_csv: Path) -> Dict[str, Tuple[str, int]]:
    """Map loc_id → (last_runner HH:MM:SS, seconds)."""
    out: Dict[str, Tuple[str, int]] = {}
    if not locations_csv.is_file():
        return out
    with open(locations_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = str(row.get("loc_id") or "").strip()
            if loc_id.isdigit():
                loc_id = str(int(loc_id))
            if not loc_id:
                continue
            raw = row.get("last_runner")
            sec = time_to_seconds(raw)
            if sec is None:
                continue
            text = str(raw).strip()
            prev = out.get(loc_id)
            if prev is None or sec > prev[1]:
                out[loc_id] = (text, int(sec))
    return out


def _location_labels_from_csv(locations_csv: Path) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if not locations_csv.is_file():
        return labels
    with open(locations_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = str(row.get("loc_id") or "").strip()
            if loc_id.isdigit():
                loc_id = str(int(loc_id))
            if loc_id and loc_id not in labels:
                labels[loc_id] = str(row.get("loc_label") or "").strip()
    return labels


def resolve_run_package_id(run_id: str) -> Optional[str]:
    run_dir = get_run_directory(run_id)
    try:
        analysis = load_analysis_json(run_dir)
    except (OSError, FileNotFoundError, ValueError) as exc:
        logger.warning("Clearance: could not load analysis.json for %s: %s", run_id, exc)
        return None
    data_dir = analysis.get("data_dir")
    return resolve_motion_package_id(analysis_config=analysis, data_dir=data_dir)


def _point_clear_time(
    subject: Mapping[str, str],
    last_runners: Mapping[str, Tuple[str, int]],
) -> Tuple[Optional[str], Optional[int], str]:
    """Return (hhmmss, sec, source) for a location point. Assets have no point time."""
    if subject.get("kind") != "location":
        return None, None, "none"
    loc_id = str(subject.get("id") or "")
    hit = last_runners.get(loc_id)
    if not hit:
        return None, None, "missing_last_runner"
    return hit[0], hit[1], "last_runner"


def _until_clear_time(
    subject: Mapping[str, str],
    last_runners: Mapping[str, Tuple[str, int]],
    derived: Mapping[str, Tuple[str, int]],
) -> Tuple[Optional[str], Optional[int], str]:
    """Location until = last runner at the point. Asset until = derived reopen."""
    if subject.get("kind") == "location":
        return _point_clear_time(subject, last_runners)
    key = subject_key(dict(subject))
    hit = derived.get(key)
    if not hit:
        return None, None, "missing_derived"
    return hit[0], hit[1], "derived"


def build_clearance_playbook(
    doc: Optional[Mapping[str, Any]],
    *,
    last_runners: Optional[Mapping[str, Tuple[str, int]]] = None,
    location_labels: Optional[Mapping[str, str]] = None,
    config_id: Optional[str] = None,
    run_id: Optional[str] = None,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derive reopen times: max(clear_time(u) for u in until).

    Location clear_time = Locations.csv last_runner at the point.
    """
    payload = dict(doc or empty_clearance_doc())
    last_runners = dict(last_runners or {})
    labels = dict(location_labels or {})
    labels.update(_asset_label_map(payload))
    rules = list(payload.get("rules") or [])

    derived: Dict[str, Tuple[str, int]] = {}
    entries: List[Dict[str, Any]] = []

    # Process rules in dependency order: until subjects before blocked when possible.
    remaining = list(rules)
    guard = 0
    while remaining and guard < len(rules) + 2:
        guard += 1
        progressed = False
        still: List[Any] = []
        for rule in remaining:
            until_ready = True
            until_rows: List[Dict[str, Any]] = []
            times: List[int] = []
            missing: List[str] = []
            for until in rule["until"]:
                hhmm, sec, source = _until_clear_time(until, last_runners, derived)
                label = labels.get(until["id"]) or until["id"]
                row = {
                    "kind": until["kind"],
                    "id": until["id"],
                    "label": label,
                    "clear_time": hhmm,
                    "clear_time_sec": sec,
                    "source": source,
                }
                until_rows.append(row)
                if sec is None:
                    until_ready = False
                    missing.append(subject_key(until))
                else:
                    times.append(sec)
            if not until_ready:
                still.append(rule)
                blocked = rule["blocked"]
                entries.append(
                    _entry(
                        rule,
                        until_rows,
                        labels,
                        reopen_at=None,
                        reopen_at_sec=None,
                        missing=missing,
                    )
                )
                continue
            reopen_sec = max(times)
            reopen_at = _format_seconds_to_hhmmss(reopen_sec)
            derived[subject_key(rule["blocked"])] = (reopen_at, reopen_sec)
            entries.append(
                _entry(
                    rule,
                    until_rows,
                    labels,
                    reopen_at=reopen_at,
                    reopen_at_sec=reopen_sec,
                    missing=[],
                )
            )
            progressed = True
        remaining = still
        if not progressed:
            break

    # Drop duplicate placeholder entries from earlier passes; keep last per rule id.
    by_id: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        by_id[entry["rule_id"]] = entry
    ordered = list(by_id.values())
    ordered.sort(
        key=lambda e: (
            e["reopen_at_sec"] is None,
            e["reopen_at_sec"] if e["reopen_at_sec"] is not None else 0,
            e["rule_id"],
        )
    )

    return {
        "ok": True,
        "config_id": config_id,
        "run_id": run_id,
        "day": day,
        "clear_when": CLEAR_WHEN_LAST_RUNNER,
        "entries": ordered,
        "count": len(ordered),
    }


def _entry(
    rule: Mapping[str, Any],
    until_rows: List[Dict[str, Any]],
    labels: Mapping[str, str],
    *,
    reopen_at: Optional[str],
    reopen_at_sec: Optional[int],
    missing: List[str],
) -> Dict[str, Any]:
    blocked = rule["blocked"]
    label = labels.get(blocked["id"]) or blocked["id"]
    note = str(rule.get("note") or "").strip()
    explanation = _explain(blocked, label, until_rows, reopen_at, missing)
    return {
        "rule_id": rule["id"],
        "blocked": {
            "kind": blocked["kind"],
            "id": blocked["id"],
            "label": label,
        },
        "until": until_rows,
        "reopen_at": reopen_at,
        "reopen_at_sec": reopen_at_sec,
        "missing": missing,
        "note": note,
        "explanation": explanation,
    }


def _explain(
    blocked: Mapping[str, str],
    blocked_label: str,
    until_rows: List[Dict[str, Any]],
    reopen_at: Optional[str],
    missing: List[str],
) -> str:
    who = f"{blocked_label} ({blocked['kind']} {blocked['id']})"
    parts = []
    for row in until_rows:
        clock = row["clear_time"] or "no last-runner time"
        src = "last runner at point" if row["source"] == "last_runner" else (
            "derived reopen" if row["source"] == "derived" else "timing unavailable"
        )
        parts.append(f"{row['label']} ({row['kind']} {row['id']}: {clock}, {src})")
    joined = " AND ".join(parts) if parts else "(none)"
    if missing:
        return (
            f"{who} stays closed until {joined}. "
            "Reopen time unknown until missing timings exist."
        )
    return f"{who} may reopen at {reopen_at} once {joined} are clear."


def playbook_for_run(
    run_id: str,
    *,
    day: str,
    locations_csv: Path,
    config_id: Optional[str] = None,
) -> Dict[str, Any]:
    cid = config_id or resolve_run_package_id(run_id)
    doc = try_load_config_clearance(cid)
    last_runners = load_location_last_runners(locations_csv)
    labels = _location_labels_from_csv(locations_csv)
    if doc is None:
        return build_clearance_playbook(
            empty_clearance_doc(),
            last_runners=last_runners,
            location_labels=labels,
            config_id=cid,
            run_id=run_id,
            day=day,
        )
    return build_clearance_playbook(
        doc,
        last_runners=last_runners,
        location_labels=labels,
        config_id=cid,
        run_id=run_id,
        day=day,
    )


def attach_clearance_to_locations(
    locations: List[Dict[str, Any]],
    playbook: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Add ``clearance`` on location rows that are blocked subjects."""
    by_loc: Dict[str, Dict[str, Any]] = {}
    for entry in playbook.get("entries") or []:
        blocked = entry.get("blocked") or {}
        if blocked.get("kind") != "location":
            continue
        by_loc[str(blocked.get("id"))] = entry
    for row in locations:
        loc_id = str(row.get("loc_id") or "").strip()
        if loc_id.isdigit():
            loc_id = str(int(loc_id))
        entry = by_loc.get(loc_id)
        if not entry:
            row["clearance"] = None
            continue
        row["clearance"] = {
            "blocked": True,
            "rule_id": entry.get("rule_id"),
            "until": entry.get("until"),
            "reopen_at": entry.get("reopen_at"),
            "note": entry.get("note"),
            "explanation": entry.get("explanation"),
            "missing": entry.get("missing") or [],
        }
    return locations
