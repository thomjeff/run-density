# app/density.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field

# -----------------------------
# Models
# -----------------------------

class StartTimes(BaseModel):
    # minutes after "race clock 0"
    Full: Optional[int] = None
    Half: Optional[int] = None
    TenK: Optional[int] = Field(default=None, alias="10K")

    def get(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self.TenK is not None:
            return self.TenK
        return 0  # default so we don't crash


class DensityPayload(BaseModel):
    # External CSVs (raw GitHub URLs etc.)
    paceCsv: Optional[str] = None
    overlapsCsv: Optional[str] = None

    # Or inline segments (alternative to overlapsCsv)
    segments: Optional[List[Dict]] = None

    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds

    # Depth (metres along the course) for pax/m^2 crowd density
    depth_m: float = 3.0


@dataclass
class OverlapSegment:
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str  # "uni" | "bi"
    width_m: float
    notes: str = ""


# -----------------------------
# Helpers: I/O
# -----------------------------

def _fetch_csv(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch CSV: {url} ({e})")


def _load_pace_df(paceCsv: Optional[str]) -> pd.DataFrame:
    if not paceCsv:
        raise HTTPException(status_code=422, detail="paceCsv is required")

    df = _fetch_csv(paceCsv)

    # Required columns
    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"paceCsv missing columns: {sorted(missing)}")

    # Optional start_offset (seconds) — default 0
    if "start_offset" not in df.columns:
        df["start_offset"] = 0

    # Normalize types
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"].astype(str)
    df["pace"] = df["pace"].astype(float)       # minutes per km
    df["distance"] = df["distance"].astype(float)
    df["start_offset"] = df["start_offset"].fillna(0).astype(int)

    return df


def _load_overlaps(overlapsCsv: Optional[str], inline_segments: Optional[List[Dict]]) -> List[OverlapSegment]:
    rows: List[Dict] = []

    if overlapsCsv:
        df = _fetch_csv(overlapsCsv)
        required = [
            "seg_id", "segment_label",
            "eventA", "eventB",
            "from_km_A", "to_km_A",
            "from_km_B", "to_km_B",
            "direction", "width_m",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise HTTPException(status_code=422, detail=f"overlapsCsv missing columns: {missing}")

        df = df.fillna({"notes": ""})
        for _, r in df.iterrows():
            rows.append({
                "seg_id": str(r["seg_id"]),
                "segment_label": str(r["segment_label"]),
                "eventA": str(r["eventA"]),
                "eventB": str(r["eventB"]),
                "from_km_A": float(r["from_km_A"]),
                "to_km_A": float(r["to_km_A"]),
                "from_km_B": float(r["from_km_B"]),
                "to_km_B": float(r["to_km_B"]),
                "direction": str(r["direction"]),
                "width_m": float(r["width_m"]),
                "notes": str(r.get("notes", "")),
            })

    if inline_segments:
        for raw in inline_segments:
            seg_id = str(raw.get("seg_id") or "").strip()
            if not seg_id:
                raise HTTPException(status_code=422, detail="Inline segment missing seg_id")

            rows.append({
                "seg_id": seg_id,
                "segment_label": str(raw.get("segment_label") or seg_id),
                "eventA": str(raw.get("eventA")),
                "eventB": str(raw.get("eventB")),
                "from_km_A": float(raw.get("from_km_A")),
                "to_km_A": float(raw.get("to_km_A")),
                "from_km_B": float(raw.get("from_km_B")),
                "to_km_B": float(raw.get("to_km_B")),
                "direction": str(raw.get("direction")),
                "width_m": float(raw.get("width_m")),
                "notes": str(raw.get("notes") or ""),
            })

    if not rows:
        return []

    out: List[OverlapSegment] = []
    for r in rows:
        out.append(OverlapSegment(
            seg_id=r["seg_id"],
            segment_label=r["segment_label"],
            eventA=r["eventA"],
            eventB=r["eventB"],
            from_km_A=r["from_km_A"],
            to_km_A=r["to_km_A"],
            from_km_B=r["from_km_B"],
            to_km_B=r["to_km_B"],
            direction=r["direction"],
            width_m=r["width_m"],
            notes=r.get("notes", ""),
        ))
    return out


# -----------------------------
# Maths & utilities
# -----------------------------

def _zone_for_areal(areal_density: float) -> str:
    if areal_density >= 50:
        return "dark-red"
    if areal_density >= 30:
        return "red"
    if areal_density >= 15:
        return "orange"
    if areal_density >= 7.5:
        return "yellow"
    return "green"


def _arrival_clock_seconds(event: str, start_times: StartTimes) -> int:
    return int(start_times.get(event) * 60)


def _first_arrival_time_at_km(df_event: pd.DataFrame, event: str, km_val: float, start_times: StartTimes) -> Optional[float]:
    """Earliest race-clock time a runner from `event` reaches `km_val`."""
    if df_event.empty:
        return None
    elig = df_event[df_event["distance"] >= (km_val - 1e-9)]
    if elig.empty:
        return None
    t0 = _arrival_clock_seconds(event, start_times)
    arrivals = t0 + elig["start_offset"].values + km_val * elig["pace"].values * 60.0
    return float(arrivals.min())


def _count_in_window_at_km(
    df_event: pd.DataFrame,
    event: str,
    km_val: float,
    start_times: StartTimes,
    t_ref: float,
    time_window_s: int,
) -> int:
    """Count runners at km within [t_ref, t_ref + window)."""
    elig = df_event[df_event["distance"] >= (km_val - 1e-9)]
    if elig.empty:
        return 0
    t0 = _arrival_clock_seconds(event, start_times)
    arrivals = t0 + elig["start_offset"].values + km_val * elig["pace"].values * 60.0
    t_max = t_ref + float(time_window_s) - 1e-9
    return int(((arrivals >= t_ref) & (arrivals <= t_max)).sum())


def _trace_segment(
    seg: OverlapSegment,
    df: pd.DataFrame,
    start_times: StartTimes,
    step_km: float,
    time_window_s: int,
    debug: bool,
) -> Tuple[List[Dict], Dict]:
    """Trace along A’s span, always using a **shared** time window for A & B."""
    dfA = df[df["event"] == seg.eventA]
    dfB = df[df["event"] == seg.eventB]

    rng_start = min(seg.from_km_A, seg.to_km_A)
    rng_end   = max(seg.from_km_A, seg.to_km_A)

    k = rng_start
    trace: List[Dict] = []
    while k <= rng_end + 1e-9:
        # Map A’s km to B’s km (proportional)
        if abs(seg.to_km_A - seg.from_km_A) < 1e-9:
            kmB = seg.from_km_B
        else:
            ratio = (k - seg.from_km_A) / (seg.to_km_A - seg.from_km_A)
            kmB = seg.from_km_B + ratio * (seg.to_km_B - seg.from_km_B)

        # First arrival per event
        tA_min = _first_arrival_time_at_km(dfA, seg.eventA, k,   start_times)
        tB_min = _first_arrival_time_at_km(dfB, seg.eventB, kmB, start_times)

        # Shared window anchor
        t_ref: Optional[float]
        if (tA_min is None) and (tB_min is None):
            t_ref = None
        elif tA_min is None:
            t_ref = tB_min
        elif tB_min is None:
            t_ref = tA_min
        else:
            t_ref = min(tA_min, tB_min)

        if t_ref is None:
            a = b = 0
        else:
            a = _count_in_window_at_km(dfA, seg.eventA, k,   start_times, t_ref, time_window_s)
            b = _count_in_window_at_km(dfB, seg.eventB, kmB, start_times, t_ref, time_window_s)

        combined = a + b
        trace.append({"km": round(k, 2), "A": int(a), "B": int(b), "combined": int(combined)})
        k += step_km

    # First-overlap clock at A-start (min of A/B earliest there)
    startA = seg.from_km_A
    if abs(seg.to_km_A - seg.from_km_A) < 1e-9:
        kmB_at_Astart = seg.from_km_B
    else:
        kmB_at_Astart = seg.from_km_B  # ratio 0 at A start

    tA0 = _first_arrival_time_at_km(dfA, seg.eventA, startA,      start_times)
    tB0 = _first_arrival_time_at_km(dfB, seg.eventB, kmB_at_Astart, start_times)

    t_first = None
    if (tA0 is not None) and (tB0 is not None):
        t_first = min(tA0, tB0)
    elif tA0 is not None:
        t_first = tA0
    elif tB0 is not None:
        t_first = tB0

    first_overlap = None
    if t_first is not None:
        hh = int(t_first // 3600)
        mm = int((t_first % 3600) // 60)
        ss = int(t_first % 60)
        first_overlap = {"clock": f"{hh:02d}:{mm:02d}:{ss:02d}", "km": round(startA, 2)}

    return trace, (first_overlap or {"clock": None, "km": round(startA, 2)})


# -----------------------------
# Public entry
# -----------------------------

def run_density(payload: DensityPayload, seg_id_filter: Optional[str] = None, debug: bool = False):
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)
    if seg_id_filter:
        overlaps = [o for o in overlaps if o.seg_id == seg_id_filter]

    pace_df = _load_pace_df(payload.paceCsv)

    results: List[Dict] = []
    for seg in overlaps:
        trace, first_overlap_obj = _trace_segment(
            seg=seg,
            df=pace_df,
            start_times=payload.startTimes,
            step_km=payload.stepKm,
            time_window_s=payload.timeWindow,
            debug=debug,
        )

        # Peak combined (simultaneous window by construction)
        if trace:
            peak_row = max(trace, key=lambda r: r["combined"])
            peak_km = peak_row["km"]
            peak_A = peak_row["A"]
            peak_B = peak_row["B"]
            peak_combined = peak_row["combined"]
        else:
            peak_km = seg.from_km_A
            peak_A = peak_B = peak_combined = 0

        # Effective width (halve for bi-direction segments)
        effective_width = seg.width_m
        if seg.direction.strip().lower() == "bi":
            effective_width = max(effective_width / 2.0, 1e-9)

        # Areal density (pax per metre of width)
        areal_density = peak_combined / max(effective_width, 1e-9)

        # Crowd density (pax per m^2), using depth_m
        crowd_density = peak_combined / max(effective_width * payload.depth_m, 1e-9)

        # Zone by areal density (keep your existing thresholds)
        if areal_density >= 50:
            zone = "dark-red"
        elif areal_density >= 30:
            zone = "red"
        elif areal_density >= 15:
            zone = "orange"
        elif areal_density >= 7.5:
            zone = "yellow"
        else:
            zone = "green"

        results.append({
            "seg_id": seg.seg_id,
            "segment_label": seg.segment_label,
            "direction": seg.direction,
            "width_m": seg.width_m,
            "first_overlap": first_overlap_obj,
            "peak": {
                "km": peak_km,
                "A": int(peak_A),
                "B": int(peak_B),
                "combined": int(peak_combined),
                "areal_density": areal_density,
                "crowd_density": crowd_density,
                "zone": zone,
            },
            "trace": trace if debug else None,
        })

    return {"engine": "density", "segments": results}