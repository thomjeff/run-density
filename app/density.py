# app/density.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field

print("run_density: single-loop v1.3.4 marker", flush=True)

# -----------------------------
# Constants
# -----------------------------

# Default zone thresholds
DEFAULT_AREAL_CUTS = [7.5, 15.0, 30.0, 50.0]
DEFAULT_CROWD_CUTS = [1.0, 2.0, 4.0, 8.0]

# Validation limits
MIN_TIME_WINDOW = 5
MAX_TIME_WINDOW = 600
MIN_STEP_KM = 0.0
MAX_STEP_KM = 1.0
EPSILON = 1e-9

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
    def has(self, event: str) -> bool:
        # Check raw fields without applying the 0 default
        if event == "Full":
            return self.Full is not None
        if event == "Half":
            return self.Half is not None
        if event == "10K":
            return self.TenK is not None
        return False

class ZoneConfig(BaseModel):
    # five bands => 4 cuts, in strictly increasing order
    areal: Optional[List[float]] = None    # e.g. [7.5, 15, 30, 50]
    crowd: Optional[List[float]] = None    # e.g. [1.0, 2.0, 4.0, 8.0]

class DensityPayload(BaseModel):
    # External CSVs (raw GitHub URLs etc.)
    paceCsv: Optional[str] = None
    overlapsCsv: Optional[str] = None

    # Or inline segments (alternative to overlapsCsv)
    segments: Optional[List[Dict]] = None

    startTimes: StartTimes

    # Validation tightened (must be >0 and ≤1; timeWindow >0; depth >0)
    stepKm: float = Field(0.03, gt=MIN_STEP_KM, le=MAX_STEP_KM)
    timeWindow: int = Field(60, gt=MIN_TIME_WINDOW, le=MAX_TIME_WINDOW)
    depth_m: float = Field(3.0, gt=0.0)

    # Existing optional zone configuration (we kept the name ZoneConfig per your preference)
    zones: Optional[ZoneConfig] = None

    # NEW: choose which metric to color zones by ("areal" or "crowd")
    zoneMetric: Optional[str] = Field("areal", pattern="^(areal|crowd)$")


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


def preview_segments(payload: "DensityPayload") -> List[Dict]:
    """
    Return validated overlaps as plain dicts for QA/inspection, including length_km.
    Does not run density math.
    """
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)
    out: List[Dict] = []
    for s in overlaps:
        lengthA = max(0.0, float(s.to_km_A - s.from_km_A))
        lengthB = max(0.0, float(s.to_km_B - s.from_km_B))
        out.append({
            "seg_id": s.seg_id,
            "segment_label": s.segment_label,
            "direction": s.direction,
            "width_m": float(s.width_m),
            "eventA": s.eventA,
            "from_km_A": float(s.from_km_A),
            "to_km_A": float(s.to_km_A),
            "eventB": s.eventB,
            "from_km_B": float(s.from_km_B),
            "to_km_B": float(s.to_km_B),
            "length_km": max(lengthA, lengthB),
        })
    return out

# -----------------------------
# Maths & utilities
# -----------------------------

def _zone_from_cuts(value: float, cuts: List[float]) -> str:
    """
    cuts: 4 ascending thresholds [g→y, y→o, o→r, r→dr]
    """
    g_y, y_o, o_r, r_dr = cuts
    if value >= r_dr:
        return "dark-red"
    if value >= o_r:
        return "red"
    if value >= y_o:
        return "orange"
    if value >= g_y:
        return "yellow"
    return "green"

# Alias for generic metric zoning (areal or crowd) using provided cuts.
def _zone_from_metric(value: float, cuts: Optional[List[float]] = None) -> str:
    # If cuts is None or invalid, use standard areal thresholds.
    if not cuts or len(cuts) != 4 or cuts != sorted(cuts):
        cuts = DEFAULT_AREAL_CUTS
    return _zone_from_cuts(value, cuts)

def _zone_for_density(
    areal_density: float,
    crowd_density: float,
    payload: DensityPayload,
) -> str:
    """
    Decide the zone using either 'areal' (default) or 'crowd' metric.
    Thresholds come from payload.zones if provided; otherwise defaults are used.
    """
    # defaults match your historical behaviour
    default_areal = DEFAULT_AREAL_CUTS
    default_crowd = DEFAULT_CROWD_CUTS

    # pick metric
    metric = (payload.zoneMetric or "areal").lower()

    # choose thresholds (validate increasing, else fall back)
    if metric == "crowd":
        cuts = getattr(getattr(payload, "zones", None), "crowd", None)
        if not (isinstance(cuts, list) and len(cuts) == 4 and cuts == sorted(cuts)):
            cuts = default_crowd
        return _zone_from_cuts(crowd_density, cuts)

    # default: areal
    cuts = getattr(getattr(payload, "zones", None), "areal", None)
    if not (isinstance(cuts, list) and len(cuts) == 4 and cuts == sorted(cuts)):
        cuts = default_areal
    return _zone_from_cuts(areal_density, cuts)


def _arrival_clock_seconds(event: str, start_times: StartTimes) -> int:
    return int(start_times.get(event) * 60)


def _first_arrival_time_at_km(df_event: pd.DataFrame, event: str, km_val: float, start_times: StartTimes) -> Optional[float]:
    """Earliest race-clock time a runner from `event` reaches `km_val`."""
    if df_event.empty:
        return None
    elig = df_event[df_event["distance"] >= (km_val - EPSILON)]
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
    elig = df_event[df_event["distance"] >= (km_val - EPSILON)]
    if elig.empty:
        return 0
    t0 = _arrival_clock_seconds(event, start_times)
    arrivals = t0 + elig["start_offset"].values + km_val * elig["pace"].values * 60.0
    t_max = t_ref + float(time_window_s) - EPSILON
    return int(((arrivals >= t_ref) & (arrivals <= t_max)).sum())

# --- helper: km positions with at least one sample, even if (to - from) < step ---
def _km_positions(from_km: float, to_km: float, step_km: float) -> List[float]:
    if to_km < from_km:
        from_km, to_km = to_km, from_km  # safety
    if step_km <= 0:
        step_km = 0.03  # fallback
    n_steps = max(0, int((to_km - from_km) / max(step_km, EPSILON)))
    pos = [from_km + i * step_km for i in range(n_steps + 1)]
    # ensure we include end if close and not already there
    if pos and pos[-1] + EPSILON < to_km:
        pos.append(to_km)
    if not pos:
        # extremely short segment: still return at least the start
        pos = [from_km]
    return pos

def trace_segment(
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
    while k <= rng_end + EPSILON:
        # Map A’s km to B’s km (proportional)
        if abs(seg.to_km_A - seg.from_km_A) < EPSILON:
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
    if abs(seg.to_km_A - seg.from_km_A) < EPSILON:
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

# ---- validation helpers ------------------------------------------------------


def _fail_422(msg: str):
    raise HTTPException(status_code=422, detail=msg)


def _validate_params(step_km: float, time_window: int, depth_m: float):
    if step_km is None or step_km <= MIN_STEP_KM or step_km > MAX_STEP_KM:
        _fail_422(f"stepKm must be in ({MIN_STEP_KM}, {MAX_STEP_KM}], got {step_km}")
    if time_window is None or time_window < MIN_TIME_WINDOW or time_window > MAX_TIME_WINDOW:
        _fail_422(f"timeWindow must be between {MIN_TIME_WINDOW} and {MAX_TIME_WINDOW} seconds, got {time_window}")
    if depth_m is None or depth_m <= 0:
        _fail_422(f"depth_m must be > 0, got {depth_m}")


def _validate_overlaps(overlaps: List[OverlapSegment], start_times: StartTimes) -> None:
    """
    Validate segments + ensure startTimes has the events each segment references.
    Raises HTTP 422 with a clear message if anything is off.
    """
    def _fail_422(msg: str) -> None:
        raise HTTPException(status_code=422, detail=msg)

    for idx, s in enumerate(overlaps):
        where = f"overlaps[{idx}] (seg_id={s.seg_id})"

        # Basic numeric sanity
        if s.from_km_A > s.to_km_A:
            _fail_422(f"{where}: from_km_A ({s.from_km_A}) > to_km_A ({s.to_km_A}).")
        if s.from_km_B > s.to_km_B:
            _fail_422(f"{where}: from_km_B ({s.from_km_B}) > to_km_B ({s.to_km_B}).")
        if s.width_m is None or s.width_m <= 0:
            _fail_422(f"{where}: width_m must be > 0, got {s.width_m}.")
        dir_norm = (s.direction or "").strip().lower()
        if dir_norm not in {"uni", "bi"}:
            _fail_422(f"{where}: direction must be 'uni' or 'bi', got '{s.direction}'.")

        # Make sure the segment’s events have start times
        needed = {s.eventA, s.eventB}
        for ev in needed:
            if ev not in {"Full", "Half", "10K"}:
                _fail_422(f"{where}: unknown event '{ev}' (expected one of Full/Half/10K).")
            if not start_times.has(ev):
                _fail_422(
                    f"{where}: start time for '{ev}' is missing in startTimes. "
                    f"Provide e.g. startTimes={{\"Full\":420,\"Half\":460,\"10K\":440}}"
                )

def run_density(payload: DensityPayload, seg_id_filter: Optional[str] = None, debug: bool = False) -> Dict:
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)

    # Filter by seg_id as early as possible
    if seg_id_filter:
        overlaps = [o for o in overlaps if o.seg_id == seg_id_filter]

    # Prevent UnboundLocalError if any pre-loop path references `seg`
    seg = None  # type: ignore[assignment]

    # Validate early so the rest of the code can assume good inputs
    _validate_params(
        step_km=payload.stepKm,
        time_window=payload.timeWindow,
        depth_m=payload.depth_m,
    )
    _validate_overlaps(overlaps, payload.startTimes)

    # Load pace data once
    pace_df = _load_pace_df(payload.paceCsv)

    results: List[Dict] = []
    for s in overlaps:
        # Per-segment step fallback for very short spans (guarantee ≥ 1 bin)
        spanA = s.to_km_A - s.from_km_A
        spanB = s.to_km_B - s.from_km_B
        seg_step = payload.stepKm
        if spanA + EPSILON < seg_step or spanB + EPSILON < seg_step:
            seg_step = max(spanA, spanB)
            if seg_step <= EPSILON:
                seg_step = EPSILON  # still guarantee at least one bin

        # Build the trace at this per-segment step
        trace, first_overlap_obj = trace_segment(
            seg=s,
            df=pace_df,
            start_times=payload.startTimes,
            step_km=seg_step,                 # per-segment step
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
            peak_km = s.from_km_A
            peak_A = peak_B = peak_combined = 0

        # Effective width (halve for bi-direction segments)
        effective_width = s.width_m
        if s.direction.strip().lower() == "bi":
            effective_width = max(effective_width / 2.0, EPSILON)

        # Areal density (pax per metre of width)
        areal_density = peak_combined / max(effective_width, EPSILON)

        # Crowd density (pax per m^2), using depth_m
        crowd_density = peak_combined / max(effective_width * payload.depth_m, EPSILON)

        # Zone selection (supports areal or crowd with optional custom cuts)
        zone = _zone_for_density(
            areal_density=areal_density,
            crowd_density=crowd_density,
            payload=payload,
        )

        results.append({
            "seg_id": s.seg_id,
            "segment_label": s.segment_label,
            "direction": s.direction,
            "width_m": s.width_m,
            "first_overlap": first_overlap_obj,
            "peak": {
                "km": peak_km,
                "A": int(peak_A),
                "B": int(peak_B),
                "combined": int(peak_combined),
                "areal_density": round(areal_density, 2),
                "crowd_density": round(crowd_density, 2),
                "zone": zone,
            },
            "trace": (trace[:50] if debug and trace else None),
        })

    return {"engine": "density", "segments": results}

def export_peaks_csv(segments: List[Dict], filepath: str = "peaks.csv") -> None:
    """
    Export peak values from segments to a CSV file.
    Includes seg_id, segment_label, peak km, A, B, combined, areal_density, crowd_density, zone.
    """
    import csv
    import os
    
    if not segments:
        return
        
    fields = [
        "seg_id", "segment_label", "km", "A", "B", "combined",
        "areal_density", "crowd_density", "zone"
    ]
    
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for seg in segments:
                if "peak" not in seg:
                    continue
                peak = seg["peak"]
                writer.writerow({
                    "seg_id": seg.get("seg_id", ""),
                    "segment_label": seg.get("segment_label", ""),
                    "km": peak.get("km", ""),
                    "A": peak.get("A", 0),
                    "B": peak.get("B", 0),
                    "combined": peak.get("combined", 0),
                    "areal_density": round(peak.get("areal_density", 0.0), 2),
                    "crowd_density": round(peak.get("crowd_density", 0.0), 2),
                    "zone": peak.get("zone", ""),
                })
    except (IOError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to write CSV file: {e}")
