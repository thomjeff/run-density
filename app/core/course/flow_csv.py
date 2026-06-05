"""
Flow.csv authoring, conservative export, and validation.

Issue #759: Generate a conservative first draft (cross-event pairs only) with
unique flow_id per row. Same-event and out-and-back rows come from overrides
or future pass metadata — not Cartesian auto-generation.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.utils.constants import COURSE_EVENT_IDS

FLOW_CSV_COLUMNS = [
    "flow_id",
    "seg_id",
    "seg_label",
    "event_a",
    "event_b",
    "from_km_a",
    "to_km_a",
    "from_km_b",
    "to_km_b",
    "flow_type",
    "direction",
    "notes",
]

VALID_FLOW_TYPES = frozenset({"overtake", "merge", "counterflow", "none"})
VALID_DIRECTIONS = frozenset({"uni", "bi"})
_KM_TOL = 1e-6
_FLOW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class FlowValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _norm_event(value: Any) -> str:
    return str(value or "").strip().lower()


def _km_ranges_identical(
    from_a: float, to_a: float, from_b: float, to_b: float, *, tol: float = _KM_TOL
) -> bool:
    return abs(from_a - from_b) <= tol and abs(to_a - to_b) <= tol


def default_flow_id(seg_id: str, event_a: str, event_b: str) -> str:
    """Stable default flow_id for cross-event auto-generated rows."""
    return f"{seg_id}_{event_a}_{event_b}"


def flow_output_id(row: Dict[str, Any]) -> str:
    """Per-minute CSV basename identity (without _per_minute.csv suffix)."""
    fid = str(row.get("flow_id") or "").strip()
    if fid:
        return fid
    return str(row.get("seg_id") or "").strip()


def _sanitize_flow_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not _FLOW_ID_RE.match(text):
        raise ValueError(f"Invalid flow_id: {value!r}")
    return text


def _segment_active_events(seg: Dict[str, Any], event_ids: Sequence[str]) -> List[str]:
    active: List[str] = []
    events_list = seg.get("events") or []
    for eid in event_ids:
        eid = eid.lower()
        if eid in events_list:
            active.append(eid)
        elif str(seg.get(eid, "n")).lower() == "y":
            active.append(eid)
    return active


def _segment_km_window(seg: Dict[str, Any], event_id: str) -> Tuple[float, float]:
    from_km = float(seg.get(f"{event_id}_from_km") or 0)
    to_km = float(seg.get(f"{event_id}_to_km") or 0)
    return from_km, to_km


def _normalize_override(override: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(override, dict):
        return None
    seg_id = str(override.get("seg_id") or "").strip()
    event_a = _norm_event(override.get("event_a"))
    event_b = _norm_event(override.get("event_b"))
    if not seg_id or not event_a or not event_b:
        return None
    return {
        "seg_id": seg_id,
        "event_a": event_a,
        "event_b": event_b,
        "from_km_a": override.get("from_km_a"),
        "to_km_a": override.get("to_km_a"),
        "from_km_b": override.get("from_km_b"),
        "to_km_b": override.get("to_km_b"),
        "flow_type": override.get("flow_type"),
        "direction": override.get("direction"),
        "notes": override.get("notes"),
        "flow_id": override.get("flow_id"),
        "seg_label": override.get("seg_label"),
        "auto_generated": False,
    }


def build_flow_csv_from_segments(
    segments: Sequence[Dict[str, Any]],
    event_ids: Optional[Sequence[str]] = None,
    *,
    overrides: Optional[Sequence[Dict[str, Any]]] = None,
    include_same_event_pairs: bool = False,
) -> str:
    """
    Generate a conservative flow.csv from combined-course segment rows.

    Default: cross-event pairs only (full/half, full/10k, half/10k).
    Same-event rows are omitted unless ``include_same_event_pairs`` is True
    (legacy) or supplied via ``overrides`` with distinct km windows.
    """
    event_ids = [e.lower() for e in (event_ids or COURSE_EVENT_IDS)]
    segment_by_id = {
        str(seg.get("seg_id", "")).strip(): seg
        for seg in segments
        if str(seg.get("seg_id", "")).strip()
    }

    emitted_keys: set = set()
    rows: List[Dict[str, Any]] = []

    def append_row(row: Dict[str, Any]) -> None:
        key = (
            str(row.get("flow_id") or ""),
            str(row.get("seg_id") or ""),
            _norm_event(row.get("event_a")),
            _norm_event(row.get("event_b")),
        )
        if key in emitted_keys:
            return
        emitted_keys.add(key)
        rows.append(row)

    for raw_ov in overrides or []:
        ov = _normalize_override(raw_ov)
        if not ov:
            continue
        seg = segment_by_id.get(ov["seg_id"])
        if not seg:
            continue
        from_a, to_a = (
            (float(ov["from_km_a"]), float(ov["to_km_a"]))
            if ov["from_km_a"] is not None and ov["to_km_a"] is not None
            else _segment_km_window(seg, ov["event_a"])
        )
        from_b, to_b = (
            (float(ov["from_km_b"]), float(ov["to_km_b"]))
            if ov["from_km_b"] is not None and ov["to_km_b"] is not None
            else _segment_km_window(seg, ov["event_b"])
        )
        if to_a <= from_a and to_b <= from_b:
            continue
        if (
            ov["event_a"] == ov["event_b"]
            and _km_ranges_identical(from_a, to_a, from_b, to_b)
        ):
            continue
        flow_id = str(ov.get("flow_id") or "").strip() or default_flow_id(
            ov["seg_id"], ov["event_a"], ov["event_b"]
        )
        append_row(
            {
                "flow_id": flow_id,
                "seg_id": ov["seg_id"],
                "seg_label": str(ov.get("seg_label") or seg.get("seg_label") or "").strip(),
                "event_a": ov["event_a"],
                "event_b": ov["event_b"],
                "from_km_a": from_a,
                "to_km_a": to_a,
                "from_km_b": from_b,
                "to_km_b": to_b,
                "flow_type": str(
                    ov.get("flow_type") or seg.get("flow_type") or "overtake"
                ).strip().lower(),
                "direction": str(
                    ov.get("direction") or seg.get("direction") or "uni"
                ).strip().lower(),
                "notes": str(ov.get("notes") or "").strip()
                or str(seg.get("description") or "").strip()
                or str(seg.get("flow_notes") or "").strip(),
                "auto_generated": False,
            }
        )

    override_pair_keys = {
        (r["seg_id"], r["event_a"], r["event_b"]) for r in rows
    }

    for seg in segments:
        seg_id = str(seg.get("seg_id", "")).strip()
        if not seg_id:
            continue
        seg_label = str(seg.get("seg_label", "")).strip()
        direction = str(seg.get("direction") or "uni").strip().lower()
        active = _segment_active_events(seg, event_ids)
        if len(active) < 2 and not include_same_event_pairs:
            continue

        pair_list: List[Tuple[str, str]] = []
        if include_same_event_pairs:
            pair_list = [(a, b) for a, b in combinations(active, 2)]
            for e in active:
                pair_list.append((e, e))
        else:
            pair_list = [(a, b) for a, b in combinations(active, 2)]

        for event_a, event_b in pair_list:
            if (seg_id, event_a, event_b) in override_pair_keys:
                continue
            from_a, to_a = _segment_km_window(seg, event_a)
            from_b, to_b = _segment_km_window(seg, event_b)
            if to_a <= from_a and to_b <= from_b:
                continue
            if event_a == event_b:
                if not include_same_event_pairs:
                    continue
                if _km_ranges_identical(from_a, to_a, from_b, to_b):
                    continue
            append_row(
                {
                    "flow_id": default_flow_id(seg_id, event_a, event_b),
                    "seg_id": seg_id,
                    "seg_label": seg_label,
                    "event_a": event_a,
                    "event_b": event_b,
                    "from_km_a": from_a,
                    "to_km_a": to_a,
                    "from_km_b": from_b,
                    "to_km_b": to_b,
                    "flow_type": str(seg.get("flow_type") or "overtake").strip().lower(),
                    "direction": direction,
                    "notes": str(seg.get("description") or "").strip()
                    or str(seg.get("flow_notes") or "").strip(),
                    "auto_generated": True,
                }
            )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(FLOW_CSV_COLUMNS)
    for row in rows:
        writer.writerow([row.get(col, "") for col in FLOW_CSV_COLUMNS])
    return out.getvalue()


def validate_flow_csv(
    rows: Sequence[Dict[str, Any]],
    *,
    strict_auto_same_event: bool = True,
) -> FlowValidationResult:
    """
    Validate flow.csv rows.

    Hard errors block export/analysis prep; warnings flag authoring gaps.
    """
    result = FlowValidationResult()
    seen_flow_ids: Dict[str, int] = {}
    bi_output_ids: Dict[str, List[int]] = {}

    for idx, raw in enumerate(rows):
        row_num = idx + 2  # header + 1-based
        if not isinstance(raw, dict):
            result.errors.append(f"Row {row_num}: must be an object")
            continue

        seg_id = str(raw.get("seg_id") or "").strip()
        event_a = _norm_event(raw.get("event_a"))
        event_b = _norm_event(raw.get("event_b"))
        flow_id = str(raw.get("flow_id") or "").strip() or (
            default_flow_id(seg_id, event_a, event_b) if seg_id else ""
        )
        flow_type = str(raw.get("flow_type") or "").strip().lower()
        direction = str(raw.get("direction") or "").strip().lower()
        auto_generated = bool(raw.get("auto_generated"))

        if not seg_id:
            result.errors.append(f"Row {row_num}: seg_id is required")
        if not event_a or not event_b:
            result.errors.append(f"Row {row_num}: event_a and event_b are required")
        if flow_type not in VALID_FLOW_TYPES:
            result.errors.append(
                f"Row {row_num}: flow_type must be one of {sorted(VALID_FLOW_TYPES)}"
            )
        if direction not in VALID_DIRECTIONS:
            result.errors.append(
                f"Row {row_num}: direction must be one of {sorted(VALID_DIRECTIONS)}"
            )
        if flow_id:
            if not _FLOW_ID_RE.match(flow_id):
                result.errors.append(f"Row {row_num}: invalid flow_id {flow_id!r}")
            seen_flow_ids[flow_id] = seen_flow_ids.get(flow_id, 0) + 1

        try:
            from_a = float(raw.get("from_km_a"))
            to_a = float(raw.get("to_km_a"))
            from_b = float(raw.get("from_km_b"))
            to_b = float(raw.get("to_km_b"))
        except (TypeError, ValueError):
            result.errors.append(f"Row {row_num}: km columns must be numeric")
            continue

        same_event = event_a == event_b
        identical_km = _km_ranges_identical(from_a, to_a, from_b, to_b)
        notes = str(raw.get("notes") or "").strip()

        if (
            strict_auto_same_event
            and auto_generated
            and same_event
            and identical_km
        ):
            result.errors.append(
                f"Row {row_num} ({flow_id}): auto-generated same-event row with "
                "identical A/B km windows is not allowed"
            )
        elif same_event and identical_km and not notes:
            result.warnings.append(
                f"Row {row_num} ({flow_id}): same-event row with identical km "
                "windows should include notes explaining the interaction or be removed"
            )

        if direction == "bi" and identical_km:
            result.warnings.append(
                f"Row {row_num} ({flow_id}): direction=bi but A/B km windows are "
                "identical — confirm outbound/return split or override km ranges"
            )

        if same_event and direction == "bi" and identical_km:
            result.warnings.append(
                f"Row {row_num} ({flow_id}): same-event bidirectional segment "
                "without distinct outbound/return km windows"
            )

        if flow_type == "counterflow" and direction == "uni":
            result.warnings.append(
                f"Row {row_num} ({flow_id}): flow_type=counterflow with direction=uni "
                "(allowed, but verify intent)"
            )

        if same_event and not notes:
            result.warnings.append(
                f"Row {row_num} ({flow_id}): same-event row has blank notes"
            )

        if direction == "bi":
            bi_output_ids.setdefault(flow_output_id(raw), []).append(row_num)

    for fid, count in seen_flow_ids.items():
        if count > 1:
            result.errors.append(f"Duplicate flow_id: {fid} ({count} rows)")

    for output_id, row_nums in bi_output_ids.items():
        if len(row_nums) > 1:
            result.errors.append(
                f"Multiple direction=bi rows share output id {output_id!r} "
                f"(rows {row_nums}); use unique flow_id values"
            )

    return result


def parse_flow_csv_text(csv_text: str) -> List[Dict[str, Any]]:
    """Parse flow.csv text into row dicts (all string values preserved)."""
    reader = csv.DictReader(io.StringIO(csv_text))
    return [dict(row) for row in reader]


def validate_flow_csv_text(csv_text: str, **kwargs: Any) -> FlowValidationResult:
    return validate_flow_csv(parse_flow_csv_text(csv_text), **kwargs)
