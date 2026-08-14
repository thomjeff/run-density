"""Compare two Locations.csv reports for trajectory-layer cutover (#860).

Timing columns must match within ``tolerance_sec`` (0 = exact HH:MM:SS strings).
Identity is ``(day, loc_id, pass_id)`` when those columns exist, else row index.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

TIMING_COLUMNS = (
    "first_runner",
    "last_runner",
    "peak_start",
    "peak_end",
    "loc_start",
    "loc_end",
)


def _row_key(row: pd.Series, index: int) -> Tuple[Any, ...]:
    parts: List[Any] = []
    for col in ("day", "loc_id", "pass_id"):
        if col in row.index and pd.notna(row.get(col)):
            parts.append(str(row[col]).strip())
        else:
            parts.append("")
    if not any(parts):
        return (index,)
    return tuple(parts)


def _hhmmss_to_sec(value: object) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    bits = text.split(":")
    if len(bits) != 3:
        raise ValueError(f"Not HH:MM:SS: {value!r}")
    h, m, s = (int(bits[0]), int(bits[1]), int(bits[2]))
    return h * 3600 + m * 60 + s


def compare_locations_frames(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    timing_columns: Sequence[str] = TIMING_COLUMNS,
    tolerance_sec: float = 0.0,
) -> List[Dict[str, Any]]:
    """Return a list of mismatch dicts. Empty list means parity."""
    diffs: List[Dict[str, Any]] = []
    base_map = {_row_key(row, i): row for i, row in baseline.iterrows()}
    cand_map = {_row_key(row, i): row for i, row in candidate.iterrows()}

    missing = sorted(set(base_map) - set(cand_map), key=str)
    extra = sorted(set(cand_map) - set(base_map), key=str)
    for key in missing:
        diffs.append({"kind": "missing_row", "key": key})
    for key in extra:
        diffs.append({"kind": "extra_row", "key": key})

    cols = [c for c in timing_columns if c in baseline.columns and c in candidate.columns]
    for key in sorted(set(base_map) & set(cand_map), key=str):
        left = base_map[key]
        right = cand_map[key]
        for col in cols:
            lv = left.get(col)
            rv = right.get(col)
            if tolerance_sec <= 0:
                ls = "" if pd.isna(lv) else str(lv).strip()
                rs = "" if pd.isna(rv) else str(rv).strip()
                if ls != rs:
                    diffs.append(
                        {
                            "kind": "timing",
                            "key": key,
                            "column": col,
                            "baseline": ls,
                            "candidate": rs,
                        }
                    )
                continue
            ls = _hhmmss_to_sec(lv)
            rs = _hhmmss_to_sec(rv)
            if ls is None and rs is None:
                continue
            if ls is None or rs is None or abs(ls - rs) > tolerance_sec:
                diffs.append(
                    {
                        "kind": "timing",
                        "key": key,
                        "column": col,
                        "baseline": lv,
                        "candidate": rv,
                    }
                )
    return diffs


def compare_locations_csv(
    baseline_path: Path,
    candidate_path: Path,
    *,
    tolerance_sec: float = 0.0,
) -> List[Dict[str, Any]]:
    baseline = pd.read_csv(baseline_path)
    candidate = pd.read_csv(candidate_path)
    return compare_locations_frames(
        baseline, candidate, tolerance_sec=tolerance_sec
    )
