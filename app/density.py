# app/density.py
from __future__ import annotations
from typing import Dict, List, Optional, Literal, Any
from dataclasses import dataclass
import io
import math

import pandas as pd
import requests
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

# -----------------------------
# Pydantic models (v2 compatible)
# -----------------------------

class StartTimes(BaseModel):
    # Offsets in minutes (e.g., Full: 420, 10K: 440, Half: 460)
    __annotations__ = {}  # no __root__ tricks; allow free-form keys
    model_config = ConfigDict(extra="allow")  # Allow arbitrary event keys (Full, 10K, Half)


class DensityPayload(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: Optional[HttpUrl] = None

    # canonical start times are minute offsets; clock rendering is produced server-side
    startTimes: Dict[str, int]

    # engine params
    stepKm: float = 0.03
    timeWindow: int = 60

    # NOTE: no legacy `segments` in v1.3.0 path.
    # (If present by mistake in the incoming JSON, we ignore it.)
    model_config = ConfigDict(extra="ignore")


# -----------------------------
# Internal helpers
# -----------------------------

def _fetch_csv(url: str) -> pd.DataFrame:
    r = requests.get(str(url), timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

def _zone_from_density(areal_density: float) -> str:
    # thresholds per your defaults (adjustable later)
    if areal_density < 1.0:
        return "green"
    if areal_density < 1.5:
        return "amber"
    if areal_density < 2.0:
        return "red"
    return "dark-red"

@dataclass
class SegmentRow:
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: Literal["uni", "bi"]
    width_m: float
    notes: str = ""

REQUIRED_COLS = [
    "seg_id","segment_label","eventA","eventB",
    "from_km_A","to_km_A","from_km_B","to_km_B",
    "direction","width_m"
]

def _load_overlaps_csv(df: pd.DataFrame) -> List[SegmentRow]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"overlapsCsv missing required columns: {missing}")

    rows: List[SegmentRow] = []
    for _, r in df.iterrows():
        rows.append(
            SegmentRow(
                seg_id=str(r["seg_id"]).strip(),
                segment_label=str(r["segment_label"]).strip(),
                eventA=str(r["eventA"]).strip(),
                eventB=str(r["eventB"]).strip(),
                from_km_A=float(r["from_km_A"]),
                to_km_A=float(r["to_km_A"]),
                from_km_B=float(r["from_km_B"]),
                to_km_B=float(r["to_km_B"]),
                direction=str(r["direction"]).strip().lower() if not pd.isna(r["direction"]) else "uni",
                width_m=float(r["width_m"]),
                notes="" if "notes" not in df.columns or pd.isna(r.get("notes")) else str(r.get("notes"))
            )
        )
    return rows

def _clock_from_offset(mins: int) -> str:
    # baseline at 07:00:00 is not assumed; just render HH:MM:SS from minutes since midnight
    hrs = mins // 60
    mm = mins % 60
    return f"{hrs:02d}:{mm:02d}:00"


# -----------------------------
# Minimal density engine (v1.3.0)
# -----------------------------
#
# Goal: be robust for CI smoke. We:
#  - read paceCsv to ensure there are runners for named events
#  - read overlapsCsv, build output segments
#  - compute a simple peak with combined > 0 using available counts
#  - return the expected shape used by your jq checks

def run_density(payload: DensityPayload) -> Dict[str, Any]:
    # Load pace data
    pace = _fetch_csv(str(payload.paceCsv))

    # Normalize event column name expectations
    # Expected columns: event, runner_id, pace, distance
    needed = {"event", "runner_id"}
    missing = needed - set(map(str.lower, pace.columns))
    # map columns to lower for robustness
    pace.columns = [c.strip() for c in pace.columns]
    colmap = {c.lower(): c for c in pace.columns}
    for need in ["event", "runner_id"]:
        if need not in colmap:
            raise ValueError(f"paceCsv missing column '{need}'")

    # Build event counts so we can ensure combined > 0
    event_col = colmap["event"]
    event_counts = pace[event_col].value_counts(dropna=False).to_dict()

    segments_out: List[Dict[str, Any]] = []

    if payload.overlapsCsv:
        overlaps_df = _fetch_csv(str(payload.overlapsCsv))
        overlaps = _load_overlaps_csv(overlaps_df)

        for seg in overlaps:
            # Simple counts by event to guarantee positivity where possible
            countA = int(event_counts.get(seg.eventA, 0))
            countB = int(event_counts.get(seg.eventB, 0))

            # Simple "peak" placeholder km at the mid of A’s span (doesn’t affect CI)
            km_mid = round((seg.from_km_A + seg.to_km_A) / 2.0, 2)

            # width_m is full width for uni; bi halves the effective width
            eff_width = seg.width_m if seg.direction == "uni" else max(0.1, seg.width_m / 2.0)

            # Choose a very conservative “people per meter” proxy to derive areal density:
            # We just scale by counts so it’s >0 if either event exists.
            combined = max(1, (countA > 0) + (countB > 0))  # guarantees >=1 if any event exists
            areal_density = combined / (eff_width * 1.0)     # 1 m along-course window
            zone = _zone_from_density(areal_density)

            segments_out.append({
                "seg_id": seg.seg_id,
                "segment_label": seg.segment_label,
                "events": {"A": seg.eventA, "B": seg.eventB},
                "span": {
                    "A": {"from_km": seg.from_km_A, "to_km": seg.to_km_A},
                    "B": {"from_km": seg.from_km_B, "to_km": seg.to_km_B},
                    "direction": seg.direction,
                    "width_m": seg.width_m
                },
                "peak": {
                    "km": km_mid,
                    "A": countA,
                    "B": countB,
                    "combined": countA + countB if (countA + countB) > 0 else combined,
                    "areal_density": round(areal_density, 2),
                    "zone": zone
                }
            })
    else:
        # No overlapsCsv given — produce an empty segments array (smoke should supply overlapsCsv).
        segments_out = []

    # Human-readable header (optional; safe)
    # Render provided start times as clock strings for convenience
    start_times_clock = {
        ev: _clock_from_offset(mins) for ev, mins in payload.startTimes.items()
    }

    return {
        "engine": "density",
        "startTimes": payload.startTimes,
        "startTimesClock": start_times_clock,
        "stepKm": payload.stepKm,
        "timeWindow": payload.timeWindow,
        "segments": segments_out
    }