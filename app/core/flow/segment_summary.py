"""
Segment-first Flow summary (#845–#848).

Groups existing pair artifacts by seg_id. No subset-proportional compute.
Parent KPIs (unique overtakers) ship only when fz_runners rows carry pair keys
and the same-pass × cross-event filter is applied.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.core.course.flow_csv import default_flow_id
from app.utils.constants import (
    FLOW_SEGMENT_SUMMARY_FILENAME,
    FLOW_SEGMENT_SUMMARY_SCHEMA,
    REPORTS_OVERLAPS_DIRNAME,
    REPORTS_OVERLAPS_SUMMARY_FILENAME,
)

logger = logging.getLogger(__name__)

PAIR_KIND_SAME_PASS = "same_pass"
PAIR_KIND_CORRIDOR = "corridor"
PAIR_KIND_SAME_EVENT = "same_event"

PACE_MIXING_READY = "ready"
PACE_MIXING_UNAVAILABLE = "unavailable_needs_pair_keyed_fz_runners"

_SEG_TOKEN_RE = re.compile(r"^[A-Za-z]+\d+[A-Za-z0-9]*$")
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _norm_event(value: Any) -> str:
    return str(value or "").strip().lower()


def _looks_like_seg_id(token: str) -> bool:
    return bool(_SEG_TOKEN_RE.match(str(token or "").strip()))


def classify_pair_kind(
    flow_id: str,
    event_a: str,
    event_b: str,
    seg_id: str = "",
) -> str:
    """Classify a pair atom for parent vs typed-child treatment."""
    ea = _norm_event(event_a)
    eb = _norm_event(event_b)
    if ea and eb and ea == eb:
        return PAIR_KIND_SAME_EVENT

    fid = str(flow_id or "").strip()
    sid = str(seg_id or "").strip()
    if fid and sid and fid == default_flow_id(sid, ea, eb):
        return PAIR_KIND_SAME_PASS

    if fid and sid and fid.startswith(f"{sid}_"):
        remainder = fid[len(sid) + 1 :]
        first = remainder.split("_", 1)[0]
        if first not in {ea, eb} and _looks_like_seg_id(first):
            return PAIR_KIND_CORRIDOR

    if ea and eb:
        return PAIR_KIND_SAME_PASS if ea != eb else PAIR_KIND_SAME_EVENT
    if fid and sid and fid.startswith(f"{sid}_"):
        remainder = fid[len(sid) + 1 :]
        first = remainder.split("_", 1)[0]
        if _looks_like_seg_id(first):
            return PAIR_KIND_CORRIDOR
        return PAIR_KIND_SAME_PASS
    return PAIR_KIND_SAME_PASS


def hhmm_to_minutes(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    match = _HHMM_RE.match(text)
    if not match:
        return None
    hours = int(match.group(1))
    mins = int(match.group(2))
    if mins > 59:
        return None
    return hours * 60 + mins


def pair_temporal_state(
    cursor_hhmm: str,
    pair_start_hhmm: str,
    pair_end_hhmm: str,
) -> str:
    cursor = hhmm_to_minutes(cursor_hhmm)
    start = hhmm_to_minutes(pair_start_hhmm)
    end = hhmm_to_minutes(pair_end_hhmm)
    if cursor is None or start is None or end is None:
        return "unknown"
    if cursor < start:
        return "not_yet_active"
    if cursor > end:
        return "inactive"
    return "active"


def unique_role_unions(
    runner_rows: Sequence[Mapping[str, Any]],
    *,
    role: str,
    allowed_flow_ids: Iterable[str],
) -> Dict[str, int]:
    allowed = {str(fid) for fid in allowed_flow_ids}
    by_event: Dict[str, set] = defaultdict(set)
    for row in runner_rows:
        if str(row.get("role") or "") != role:
            continue
        flow_id = str(row.get("flow_id") or "").strip()
        if flow_id not in allowed:
            continue
        event = _norm_event(row.get("event"))
        runner_id = row.get("runner_id")
        if not event or runner_id is None or runner_id == "":
            continue
        by_event[event].add(str(runner_id))
    return {event: len(ids) for event, ids in sorted(by_event.items())}


def _pct(count: int, field_size: int) -> Optional[float]:
    if field_size <= 0:
        return None
    return round(100.0 * count / field_size, 1)


def _field_sizes_from_pairs(pair_entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    for pair in pair_entries:
        ea = _norm_event(pair.get("event_a"))
        eb = _norm_event(pair.get("event_b"))
        total_a = pair.get("total_a")
        total_b = pair.get("total_b")
        if ea and isinstance(total_a, (int, float)) and total_a:
            sizes[ea] = max(sizes.get(ea, 0), int(total_a))
        if eb and isinstance(total_b, (int, float)) and total_b:
            sizes[eb] = max(sizes.get(eb, 0), int(total_b))
    return sizes


def _worst_pair_attribution(same_pass_pairs: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_score = -1
    for pair in same_pass_pairs:
        worst = pair.get("worst_zone") or {}
        score = int(worst.get("overtaking_a") or 0) + int(worst.get("overtaking_b") or 0)
        score = max(score, int(worst.get("unique_encounters") or 0))
        if score > best_score:
            best_score = score
            best = {
                "flow_id": pair.get("flow_id"),
                "event_a": pair.get("event_a"),
                "event_b": pair.get("event_b"),
                "zone_index": worst.get("zone_index"),
                "severity_metric": "overtaking_a_plus_b_or_unique_encounters",
                "severity_value": score,
                "overlap_start": pair.get("overlap_start"),
                "overlap_end": pair.get("overlap_end"),
            }
    return best


def merge_occupancy_series(
    per_minute_tables: Sequence[Tuple[Sequence[str], Sequence[Mapping[str, Any]]]],
) -> List[Dict[str, Any]]:
    """Merge same-pass per-minute CSVs into event occupancy context.

    For each minute × event, take the max count across pair tables. Same-segment
    concurrent headcount should agree; max is conservative if one series is sparse.
    """
    by_minute: Dict[str, Dict[str, int]] = defaultdict(dict)
    for events, rows in per_minute_tables:
        for row in rows:
            minute = str(row.get("minute_start") or "").strip()
            if not minute:
                continue
            for event in events:
                col = f"{event}_count"
                if col not in row:
                    continue
                try:
                    count = int(row.get(col) or 0)
                except (TypeError, ValueError):
                    continue
                prev = by_minute[minute].get(event)
                by_minute[minute][event] = count if prev is None else max(prev, count)

    series = []
    for minute in sorted(by_minute, key=lambda m: hhmm_to_minutes(m) or 0):
        point = {"minute": minute}
        point.update(by_minute[minute])
        series.append(point)
    return series


def build_segment_flow_summary(
    *,
    flow_segments: Mapping[str, Any],
    overlaps_summary: Mapping[str, Any],
    runner_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    occupancy_tables: Optional[Sequence[Tuple[str, Sequence[str], Sequence[Mapping[str, Any]]]]] = None,
    cursor_hhmm: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the durable per-seg_id Flow summary from existing pair artifacts."""
    overlap_by_flow_id = {}
    for item in overlaps_summary.get("segments") or []:
        if isinstance(item, dict) and item.get("flow_id"):
            overlap_by_flow_id[str(item["flow_id"])] = item

    fs_by_key: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    fs_by_pair: Dict[Tuple[str, str, str], List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
    for composite_key, raw in (flow_segments or {}).items():
        if not isinstance(raw, dict):
            continue
        seg_id = str(raw.get("seg_id") or "").strip()
        if not seg_id:
            continue
        event_a = _norm_event(raw.get("event_a"))
        event_b = _norm_event(raw.get("event_b"))
        explicit_id = str(raw.get("flow_id") or "").strip()
        fs_by_key[composite_key] = (composite_key, raw)
        if explicit_id:
            fs_by_key[explicit_id] = (composite_key, raw)
        fs_by_pair[(seg_id, event_a, event_b)].append((composite_key, raw))

    def _lookup_flow_segment(flow_id: str, seg_id: str, event_a: str, event_b: str):
        if flow_id in fs_by_key:
            return fs_by_key[flow_id]
        matches = fs_by_pair.get((seg_id, event_a, event_b)) or []
        return matches[0] if matches else (None, {})

    grouped: Dict[str, Dict[str, Any]] = {}
    consumed_composites = set()
    consumed_pair_keys = set()

    def _append_pair(seg_id: str, pair: Dict[str, Any]) -> None:
        bucket = grouped.setdefault(
            seg_id,
            {"seg_id": seg_id, "segment_label": pair.get("segment_label") or "", "pairs": []},
        )
        label = pair.get("segment_label") or ""
        if label and " / " not in label:
            bucket["segment_label"] = label
        elif not bucket["segment_label"]:
            bucket["segment_label"] = label
        bucket["pairs"].append(pair)

    for overlap in overlaps_summary.get("segments") or []:
        if not isinstance(overlap, dict):
            continue
        flow_id = str(overlap.get("flow_id") or "").strip()
        seg_id = str(overlap.get("seg_id") or "").strip()
        event_a = _norm_event(overlap.get("event_a"))
        event_b = _norm_event(overlap.get("event_b"))
        if not flow_id or not seg_id:
            continue
        composite_key, raw = _lookup_flow_segment(flow_id, seg_id, event_a, event_b)
        kind = classify_pair_kind(flow_id, event_a, event_b, seg_id)
        pair = {
            "flow_id": flow_id,
            "composite_key": composite_key,
            "kind": kind,
            "event_a": event_a,
            "event_b": event_b,
            "segment_label": (raw or {}).get("segment_label") or overlap.get("seg_label") or "",
            "flow_type": (raw or {}).get("flow_type"),
            "total_a": int((raw or {}).get("total_a") or 0),
            "total_b": int((raw or {}).get("total_b") or 0),
            "overlap_start": overlap.get("overlap_start"),
            "overlap_end": overlap.get("overlap_end"),
            "peak_concurrent_a": overlap.get("peak_concurrent_a"),
            "peak_concurrent_b": overlap.get("peak_concurrent_b"),
            "csv_filename": overlap.get("csv_filename"),
            "worst_zone": (raw or {}).get("worst_zone"),
            "zone_count": len((raw or {}).get("zones") or []),
        }
        if cursor_hhmm:
            pair["state"] = pair_temporal_state(
                cursor_hhmm,
                pair.get("overlap_start") or "",
                pair.get("overlap_end") or "",
            )
        _append_pair(seg_id, pair)
        if composite_key:
            consumed_composites.add(composite_key)
        consumed_pair_keys.add((seg_id, event_a, event_b))

    for composite_key, raw in (flow_segments or {}).items():
        if not isinstance(raw, dict) or composite_key in consumed_composites:
            continue
        seg_id = str(raw.get("seg_id") or "").strip()
        event_a = _norm_event(raw.get("event_a"))
        event_b = _norm_event(raw.get("event_b"))
        if not seg_id or (seg_id, event_a, event_b) in consumed_pair_keys:
            continue
        flow_id = str(raw.get("flow_id") or composite_key or default_flow_id(seg_id, event_a, event_b)).strip()
        kind = classify_pair_kind(flow_id, event_a, event_b, seg_id)
        pair = {
            "flow_id": flow_id,
            "composite_key": composite_key,
            "kind": kind,
            "event_a": event_a,
            "event_b": event_b,
            "segment_label": raw.get("segment_label") or "",
            "flow_type": raw.get("flow_type"),
            "total_a": int(raw.get("total_a") or 0),
            "total_b": int(raw.get("total_b") or 0),
            "overlap_start": None,
            "overlap_end": None,
            "peak_concurrent_a": None,
            "peak_concurrent_b": None,
            "csv_filename": None,
            "worst_zone": raw.get("worst_zone"),
            "zone_count": len(raw.get("zones") or []),
        }
        _append_pair(seg_id, pair)

    parents = []
    for seg_id, bucket in sorted(grouped.items(), key=lambda item: item[0]):
        pairs = bucket["pairs"]
        same_pass = [p for p in pairs if p["kind"] == PAIR_KIND_SAME_PASS]
        corridor = [p for p in pairs if p["kind"] == PAIR_KIND_CORRIDOR]
        same_event = [p for p in pairs if p["kind"] == PAIR_KIND_SAME_EVENT]

        events = []
        for pair in same_pass:
            for event in (pair["event_a"], pair["event_b"]):
                if event and event not in events:
                    events.append(event)

        starts = [hhmm_to_minutes(p.get("overlap_start")) for p in same_pass]
        ends = [hhmm_to_minutes(p.get("overlap_end")) for p in same_pass]
        valid_starts = [m for m in starts if m is not None]
        valid_ends = [m for m in ends if m is not None]
        t0 = (
            f"{min(valid_starts) // 60:02d}:{min(valid_starts) % 60:02d}"
            if valid_starts
            else None
        )
        t1 = (
            f"{max(valid_ends) // 60:02d}:{max(valid_ends) % 60:02d}"
            if valid_ends
            else None
        )

        field_sizes = _field_sizes_from_pairs(same_pass)
        allowed_ids = [p["flow_id"] for p in same_pass]
        runner_keyed = bool(runner_rows) and any(str(r.get("flow_id") or "") for r in runner_rows or [])
        if runner_keyed and same_pass:
            overtakers = unique_role_unions(
                runner_rows or [], role="overtaking", allowed_flow_ids=allowed_ids
            )
            overtaken = unique_role_unions(
                runner_rows or [], role="overtaken", allowed_flow_ids=allowed_ids
            )
            status = PACE_MIXING_READY
        else:
            overtakers = {}
            overtaken = {}
            status = PACE_MIXING_UNAVAILABLE

        occupancy = []
        if occupancy_tables:
            tables = []
            allowed = set(allowed_ids)
            for flow_id, events_in_table, rows in occupancy_tables:
                if flow_id in allowed:
                    tables.append((events_in_table, rows))
            occupancy = merge_occupancy_series(tables)

        parents.append(
            {
                "seg_id": seg_id,
                "segment_label": bucket["segment_label"],
                "events": events,
                "t0": t0,
                "t1": t1,
                "field_denominator": "starters_in_analysis_run",
                "field_sizes": field_sizes,
                "pace_mixing_status": status,
                "unique_overtakers": {
                    event: overtakers.get(event, 0) for event in events
                },
                "unique_overtaken": {
                    event: overtaken.get(event, 0) for event in events
                },
                "share_of_starters_overtaking": {
                    event: _pct(overtakers.get(event, 0), field_sizes.get(event, 0))
                    for event in events
                },
                "highest_severity_pair": _worst_pair_attribution(same_pass),
                "occupancy_source": "same_pass_overlap_per_minute_max",
                "occupancy": occupancy,
                "pairs": {
                    "same_pass": same_pass,
                    "corridor": corridor,
                    "same_event": same_event,
                },
            }
        )

    return {
        "schema_version": FLOW_SEGMENT_SUMMARY_SCHEMA,
        "epic": "#845",
        "kpis_ship_gate": "same_pass_cross_event_filter",
        "narrative": None,
        "segments": parents,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_runner_rows(reports_dir: Path, day: str) -> List[Dict[str, Any]]:
    candidates = [
        reports_dir / f"{day}_fz_runners.parquet",
        reports_dir / "fz_runners.parquet",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            import pandas as pd

            frame = pd.read_parquet(path)
        except Exception as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return []
        if "flow_id" not in frame.columns:
            return []
        return frame.to_dict(orient="records")
    return []


def _load_occupancy_tables(
    overlaps_dir: Path,
    overlaps_summary: Mapping[str, Any],
) -> List[Tuple[str, Sequence[str], Sequence[Mapping[str, Any]]]]:
    tables: List[Tuple[str, Sequence[str], Sequence[Mapping[str, Any]]]] = []
    for item in overlaps_summary.get("segments") or []:
        if not isinstance(item, dict):
            continue
        flow_id = str(item.get("flow_id") or "").strip()
        filename = str(item.get("csv_filename") or "").strip()
        if not flow_id or not filename:
            continue
        path = overlaps_dir / filename
        if not path.is_file():
            continue
        kind = classify_pair_kind(
            flow_id,
            item.get("event_a"),
            item.get("event_b"),
            str(item.get("seg_id") or ""),
        )
        if kind != PAIR_KIND_SAME_PASS:
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        events = [
            event
            for event in (_norm_event(item.get("event_a")), _norm_event(item.get("event_b")))
            if event
        ]
        tables.append((flow_id, events, rows))
    return tables


def build_segment_flow_summary_from_day_dir(day_dir: Path, day: str) -> Dict[str, Any]:
    """Read existing day artifacts and build the segment summary (O(pairs))."""
    metrics_path = day_dir / "ui" / "metrics" / "flow_segments.json"
    overlaps_dir = day_dir / "reports" / REPORTS_OVERLAPS_DIRNAME
    overlaps_path = overlaps_dir / REPORTS_OVERLAPS_SUMMARY_FILENAME
    flow_segments = _load_json(metrics_path) if metrics_path.is_file() else {}
    overlaps_summary = _load_json(overlaps_path) if overlaps_path.is_file() else {}
    runner_rows = _load_runner_rows(day_dir / "reports", day)
    occupancy_tables = _load_occupancy_tables(overlaps_dir, overlaps_summary)
    return build_segment_flow_summary(
        flow_segments=flow_segments,
        overlaps_summary=overlaps_summary,
        runner_rows=runner_rows,
        occupancy_tables=occupancy_tables,
    )


def write_segment_flow_summary(day_dir: Path, day: str) -> Optional[Path]:
    summary = build_segment_flow_summary_from_day_dir(day_dir, day)
    out_dir = day_dir / "ui" / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / FLOW_SEGMENT_SUMMARY_FILENAME
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out_path
