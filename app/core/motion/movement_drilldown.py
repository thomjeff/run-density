"""Motion Stream Passage movement drill-down (#856).

Motion-only: explains concurrent visit streams in a reporting window.
Not a Junctions replacement. Counts are same-window concurrent stream
volume unless a tighter overlap is added later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.core.junction_flow.compute import prepare_runners_by_event

COUNT_SEMANTICS = "same_window_concurrent_stream_volume"
COUNT_SEMANTICS_NOTE = (
    "Volumes are same-window concurrent stream presence in the reporting "
    "bucket — not proof that two runners met or physically crossed."
)
MATRIX_SEMANTICS = "nearest_same_window_partner"
MATRIX_SEMANTICS_NOTE = (
    "Each unique enter on the row stream is paired with the nearest enter on "
    "the column stream in the same reporting window (within partner dwell). "
    "Cells count unique row-stream runners by (row quintile × partner quintile)."
)

# Match authored visit_km labels to clustered visit medians.
DEFAULT_VISIT_KM_TOLERANCE = 0.15


def stream_key(event: str, visit_km: float) -> str:
    return f"{str(event).lower()}@{float(visit_km):.2f}"


def _sec_to_clock(sec: int) -> str:
    """Format midnight-aligned seconds as HH:MM (seconds omitted for UI density)."""
    t = max(0, int(sec))
    h = t // 3600
    m = (t % 3600) // 60
    return f"{h:02d}:{m:02d}"


def load_authored_movements(
    data_dir: Optional[Path],
    loc_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Load optional package authored movements for a loc_id.

    Looks for ``motion_movements.json`` under the analysis data_dir:
    { "locations": { "<loc_id>": { "movements": [ ... ] } } }
    """
    if data_dir is None or loc_id is None:
        return []
    path = Path(data_dir) / "motion_movements.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    locations = payload.get("locations") or {}
    entry = locations.get(str(loc_id))
    if entry is None and str(loc_id).isdigit():
        entry = locations.get(int(loc_id))
    if not isinstance(entry, dict):
        return []
    movements = entry.get("movements") or []
    out: List[Dict[str, Any]] = []
    for raw in movements:
        if not isinstance(raw, dict):
            continue
        a = raw.get("stream_a") or {}
        b = raw.get("stream_b") or {}
        if not a.get("event") or a.get("visit_km") is None:
            continue
        if not b.get("event") or b.get("visit_km") is None:
            continue
        out.append(
            {
                "name": raw.get("name") or None,
                "type": (str(raw.get("type")).lower() if raw.get("type") else None),
                "stream_a": {
                    "event": str(a["event"]).lower(),
                    "visit_km": float(a["visit_km"]),
                },
                "stream_b": {
                    "event": str(b["event"]).lower(),
                    "visit_km": float(b["visit_km"]),
                },
            }
        )
    return out


def build_runner_quintile_lookup(
    runners_df: Optional[pd.DataFrame],
) -> Dict[Tuple[str, str], int]:
    """Map (event, runner_id) → pace quintile (Q1 lead … Q5 rear)."""
    if runners_df is None or runners_df.empty:
        return {}
    by_event = prepare_runners_by_event(runners_df)
    out: Dict[Tuple[str, str], int] = {}
    for event, part in by_event.items():
        for _, row in part.iterrows():
            out[(str(event).lower(), str(row["runner_id"]))] = int(row["quintile"])
    return out


def quintile_profile_for_runners(
    runner_ids: Sequence[str],
    event: str,
    lookup: Mapping[Tuple[str, str], int],
) -> Dict[str, int]:
    counts = {str(q): 0 for q in range(1, 6)}
    ev = str(event).lower()
    for rid in runner_ids:
        q = lookup.get((ev, str(rid)))
        if q is None:
            continue
        counts[str(int(q))] = counts.get(str(int(q)), 0) + 1
    return counts


def _streams_match(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    *,
    km_tol: float,
) -> bool:
    if str(a.get("event", "")).lower() != str(b.get("event", "")).lower():
        return False
    try:
        return abs(float(a["visit_km"]) - float(b["visit_km"])) <= float(km_tol)
    except (TypeError, ValueError, KeyError):
        return False


def match_authored_movement(
    stream_a: Mapping[str, Any],
    stream_b: Mapping[str, Any],
    authored: Sequence[Mapping[str, Any]],
    *,
    km_tol: float = DEFAULT_VISIT_KM_TOLERANCE,
) -> Optional[Dict[str, Any]]:
    """Match an unordered visit pair to an authored movement, if any."""
    for m in authored:
        a = m.get("stream_a") or {}
        b = m.get("stream_b") or {}
        if (
            _streams_match(stream_a, a, km_tol=km_tol)
            and _streams_match(stream_b, b, km_tol=km_tol)
        ) or (
            _streams_match(stream_a, b, km_tol=km_tol)
            and _streams_match(stream_b, a, km_tol=km_tol)
        ):
            return {
                "name": m.get("name"),
                "type": m.get("type"),
            }
    return None


def nearest_partner_quintile_matrix(
    stream_a: Sequence[Mapping[str, Any]],
    stream_b: Sequence[Mapping[str, Any]],
    *,
    dwell_sec: float,
) -> Dict[str, Any]:
    """
    Junctions-style nearest-partner Q×Q within a reporting window.

    Each entry needs ``runner_id``, ``t``, and ``quintile``. Unique A runners
    are paired at most once (first occurrence kept) with the nearest B enter
    within ``dwell_sec``.
    """
    dwell = float(dwell_sec)
    a_rows: List[Tuple[str, float, int]] = []
    seen_a: set = set()
    for raw in stream_a:
        rid = str(raw.get("runner_id") or "")
        q = raw.get("quintile")
        t = raw.get("t")
        if not rid or q is None or t is None or rid in seen_a:
            continue
        seen_a.add(rid)
        a_rows.append((rid, float(t), int(q)))

    b_rows: List[Tuple[str, float, int]] = []
    for raw in stream_b:
        rid = str(raw.get("runner_id") or "")
        q = raw.get("quintile")
        t = raw.get("t")
        if not rid or q is None or t is None:
            continue
        b_rows.append((rid, float(t), int(q)))
    b_rows.sort(key=lambda r: r[1])

    counts: Dict[Tuple[int, int], set] = {}
    matched_a = 0
    if a_rows and b_rows:
        b_ts = [r[1] for r in b_rows]
        for rid, at, aq in a_rows:
            # Binary search for nearest B enter time
            lo, hi = 0, len(b_ts)
            while lo < hi:
                mid = (lo + hi) // 2
                if b_ts[mid] < at:
                    lo = mid + 1
                else:
                    hi = mid
            candidates = []
            if lo < len(b_ts):
                candidates.append(lo)
            if lo > 0:
                candidates.append(lo - 1)
            best_j = None
            best_dt = None
            for j in candidates:
                dt = abs(b_ts[j] - at)
                if best_dt is None or dt < best_dt:
                    best_dt = dt
                    best_j = j
            if best_j is None or best_dt is None or best_dt > dwell:
                continue
            matched_a += 1
            qb = b_rows[best_j][2]
            counts.setdefault((aq, qb), set()).add(rid)

    cells = [
        {
            "qa": int(qa),
            "qb": int(qb),
            "n": int(len(ids)),
        }
        for (qa, qb), ids in sorted(counts.items())
    ]
    return {
        "semantics": MATRIX_SEMANTICS,
        "dwell_sec": dwell,
        "matched_a": int(matched_a),
        "stream_a_with_q": int(len(a_rows)),
        "stream_b_with_q": int(len(b_rows)),
        "cells": cells,
    }


def attach_quintile_matrices(
    pairs: Sequence[Mapping[str, Any]],
    visit_enters: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    dwell_sec: float,
) -> List[Dict[str, Any]]:
    """Attach nearest-partner Q×Q matrix to each concurrent pair."""
    out: List[Dict[str, Any]] = []
    for p in pairs:
        row = dict(p)
        ka = stream_key(p["stream_a"]["event"], p["stream_a"]["visit_km"])
        kb = stream_key(p["stream_b"]["event"], p["stream_b"]["visit_km"])
        row["quintile_matrix"] = nearest_partner_quintile_matrix(
            visit_enters.get(ka) or [],
            visit_enters.get(kb) or [],
            dwell_sec=dwell_sec,
        )
        out.append(row)
    return out


def build_concurrent_pairs(
    enters_by_visit: Sequence[Mapping[str, Any]],
    *,
    authored_movements: Optional[Sequence[Mapping[str, Any]]] = None,
    km_tol: float = DEFAULT_VISIT_KM_TOLERANCE,
) -> List[Dict[str, Any]]:
    """
    All unordered visit-stream pairs in a window with concurrent volumes.

    volume_a / volume_b are the enter uniques for each stream in that window.
    """
    streams = [
        {
            "event": str(v["event"]).lower(),
            "visit_km": float(v["visit_km"]),
            "enters": int(v["enters"]),
            "key": stream_key(v["event"], v["visit_km"]),
        }
        for v in enters_by_visit
        if v.get("enters")
    ]
    streams.sort(key=lambda s: (s["event"], s["visit_km"]))
    authored = list(authored_movements or [])
    pairs: List[Dict[str, Any]] = []
    for i in range(len(streams)):
        for j in range(i + 1, len(streams)):
            a = streams[i]
            b = streams[j]
            matched = match_authored_movement(a, b, authored, km_tol=km_tol)
            pairs.append(
                {
                    "stream_a": {
                        "event": a["event"],
                        "visit_km": a["visit_km"],
                        "key": a["key"],
                    },
                    "stream_b": {
                        "event": b["event"],
                        "visit_km": b["visit_km"],
                        "key": b["key"],
                    },
                    "volume_a": a["enters"],
                    "volume_b": b["enters"],
                    "movement_type": matched.get("type") if matched else None,
                    "movement_name": matched.get("name") if matched else None,
                    "label": (
                        matched.get("type")
                        if matched and matched.get("type")
                        else "concurrent_streams"
                    ),
                }
            )
    return pairs


def build_movement_spans(
    rows: Sequence[Mapping[str, Any]],
    *,
    window_sec: int,
    authored_movements: Optional[Sequence[Mapping[str, Any]]] = None,
    km_tol: float = DEFAULT_VISIT_KM_TOLERANCE,
) -> List[Dict[str, Any]]:
    """
    Day-level first / peak / last windows for each visit-stream pair.

    Peak uses max(volume_a + volume_b) among windows where both streams appear.
    """
    authored = list(authored_movements or [])
    # pair_key -> list of (t0, vol_a, vol_b, label meta)
    accum: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for row in rows:
        visits = row.get("enters_by_visit") or []
        if len(visits) < 2:
            continue
        t0 = int(row["t0"])
        pairs = build_concurrent_pairs(
            visits, authored_movements=authored, km_tol=km_tol
        )
        for p in pairs:
            ka = p["stream_a"]["key"]
            kb = p["stream_b"]["key"]
            key = (ka, kb) if ka <= kb else (kb, ka)
            # normalize volumes to key order
            if key[0] == ka:
                va, vb = p["volume_a"], p["volume_b"]
                sa, sb = p["stream_a"], p["stream_b"]
            else:
                va, vb = p["volume_b"], p["volume_a"]
                sa, sb = p["stream_b"], p["stream_a"]
            accum.setdefault(key, []).append(
                {
                    "t0": t0,
                    "volume_a": va,
                    "volume_b": vb,
                    "stream_a": sa,
                    "stream_b": sb,
                    "movement_type": p.get("movement_type"),
                    "movement_name": p.get("movement_name"),
                    "label": p.get("label"),
                }
            )

    window = max(1, int(window_sec))
    out: List[Dict[str, Any]] = []
    for _key, hits in accum.items():
        hits_sorted = sorted(hits, key=lambda h: h["t0"])
        peak = max(hits_sorted, key=lambda h: h["volume_a"] + h["volume_b"])
        first = hits_sorted[0]
        last = hits_sorted[-1]
        out.append(
            {
                "stream_a": first["stream_a"],
                "stream_b": first["stream_b"],
                "movement_type": first.get("movement_type"),
                "movement_name": first.get("movement_name"),
                "label": first.get("label") or "concurrent_streams",
                "first_t0": int(first["t0"]),
                "peak_t0": int(peak["t0"]),
                "last_t0": int(last["t0"]),
                "first_window": (
                    f"{_sec_to_clock(first['t0'])}–{_sec_to_clock(first['t0'] + window)}"
                ),
                "peak_window": (
                    f"{_sec_to_clock(peak['t0'])}–{_sec_to_clock(peak['t0'] + window)}"
                ),
                "last_window": (
                    f"{_sec_to_clock(last['t0'])}–{_sec_to_clock(last['t0'] + window)}"
                ),
                "peak_volume_a": int(peak["volume_a"]),
                "peak_volume_b": int(peak["volume_b"]),
                "windows_present": int(len(hits_sorted)),
            }
        )

    out.sort(
        key=lambda m: (
            m.get("movement_type") or "zzz",
            m["stream_a"]["event"],
            m["stream_a"]["visit_km"],
            m["stream_b"]["event"],
            m["stream_b"]["visit_km"],
        )
    )
    return out
