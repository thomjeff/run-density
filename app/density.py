from __future__ import annotations
import math
import time
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np

# --------- Helpers ---------

def _load_pace_csv(url_or_path: str) -> pd.DataFrame:
    df = pd.read_csv(url_or_path)
    expected = {"event","runner_id","pace","distance"}
    missing = expected - set(df.columns.str.lower())
    # Normalize column case
    df.columns = [c.lower() for c in df.columns]
    exp2 = {"event","runner_id","pace","distance"}
    if not exp2.issubset(set(df.columns)):
        raise ValueError(f"your_pace_data.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    # Coerce
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"].astype(str)
    df["pace"] = df["pace"].astype(float)  # minutes per km
    df["distance"] = df["distance"].astype(float)
    return df

def _arrival_time_sec(start_min: float, km: float, pace_min_per_km: float) -> float:
    return start_min * 60.0 + pace_min_per_km * 60.0 * km

def _map_km_for_event(km_physical: float, event: str) -> float:
    """
    Hook for course-specific mapping.
    By default, identity mapping (same physical km for both events).
    If you have a mapping (e.g., Half_km = km_physical - 3.10), implement here.
    """
    return km_physical

def _count_present(df_event: pd.DataFrame, km_physical: float, t_center: float, window_s: float) -> int:
    # arrival time at this physical km for each runner (constant pace model)
    km_for_event = _map_km_for_event(km_physical, df_event.name if hasattr(df_event, "name") else "")
    t_arr = df_event["start_sec"] + df_event["pace_sec_per_km"] * km_for_event
    return int(((t_arr >= (t_center - window_s/2)) & (t_arr <= (t_center + window_s/2))).sum())

def _linear_density(runners_per_window: int, width_m: float) -> float:
    # Convert to linear density approximation (runners per metre along length)
    # We assume 1 metre length slice representative of the 60s window steady state.
    # Later callers may convert to areal density by dividing by width.
    # Here we just return runners per metre as proxy (will be normalized by caller).
    # Using 1m length equivalent is simplistic but consistent.
    return runners_per_window / 1.0

# --------- Public API ---------

def run_density(
    pace_csv: str,
    start_times: Dict[str, float],
    segments: List[Dict[str, any]],
    step_km: float,
    time_window_s: float,
) -> Dict[str, Any]:
    """Compute density-oriented metrics per requested segment.

    Returns a dict with:
      - segments: list of results per segment
        each item has keys:
          segment: {eventA,eventB,from,to,width,direction}
          steps: list of {km, A_runners, B_runners, combined_runners, areal_density, zone}
          peak: {km, A, B, combined, areal_density, zone}
          time_in_zones: {green_s, amber_s, red_s, darkred_s}
    """
    t0 = time.perf_counter()
    df = _load_pace_csv(pace_csv)
    # Pre-compute start and pace in seconds
    df = df.copy()
    df["start_sec"] = df["event"].map({k: float(v)*60.0 for k,v in start_times.items()}).astype(float)
    df["pace_sec_per_km"] = df["pace"].astype(float) * 60.0

    results = []
    for seg in segments:
        eventA = seg["eventA"]
        eventB = seg.get("eventB")
        km_from = float(seg["from"])
        km_to = float(seg["to"])
        width_m = float(seg.get("width", 3.0))
        direction = str(seg.get("direction","uni")).lower()
        # Effective width (bi-direction halves width for each direction)
        eff_width = width_m if direction == "uni" else max(width_m / 2.0, 0.1)

        dfA = df[df["event"] == eventA].copy()
        dfA.name = eventA
        if dfA.empty:
            raise ValueError(f"No runners for eventA={eventA}")
        dfB = None
        if eventB:
            dfB = df[df["event"] == eventB].copy()
            dfB.name = eventB
            if dfB.empty:
                raise ValueError(f"No runners for eventB={eventB}")

        steps = []
        km_vals = np.round(np.arange(km_from, km_to + 1e-9, step_km), 2)
        for km in km_vals:
            # Center timestamp uses event A median arrival as reference
            t_center_A = (dfA["start_sec"] + dfA["pace_sec_per_km"] * _map_km_for_event(km, eventA)).median()
            countA = _count_present(dfA, km, t_center_A, time_window_s)
            countB = 0
            if dfB is not None:
                # Use event B median at mapped position as its own center to avoid bias
                t_center_B = (dfB["start_sec"] + dfB["pace_sec_per_km"] * _map_km_for_event(km, eventB)).median()
                countB = _count_present(dfB, km, t_center_B, time_window_s)
            combined = countA + countB
            # Areal density (/m^2): linear density (~runners/m) divided by width
            linear = _linear_density(combined, eff_width)
            areal = linear / eff_width  # runners per square metre
            # Zone thresholds (tune as needed)
            if areal < 1.0:
                zone = "green"
            elif areal < 1.5:
                zone = "amber"
            elif areal < 2.0:
                zone = "red"
            else:
                zone = "dark-red"
            steps.append({
                "km": float(km),
                f"{eventA}_runners": int(countA),
                f"{eventB}_runners": int(countB) if dfB is not None else None,
                "combined_runners": int(combined),
                "areal_density": round(float(areal), 3),
                "zone": zone,
            })

        # Peak by combined runners
        peak = max(steps, key=lambda x: x["combined_runners"])
        # Time-in-zones proxy: convert step count to time by window overlap (best-effort)
        zone_counts = {"green":0, "amber":0, "red":0, "dark-red":0}
        for s in steps:
            zone_counts[s["zone"]] += 1
        seconds_per_step = time_window_s  # proxy; overlaps between steps ignored
        time_in_zones = {k: v * seconds_per_step for k,v in zone_counts.items()}

        results.append({
            "segment": {
                "eventA": eventA, "eventB": eventB,
                "from": km_from, "to": km_to,
                "width": width_m, "direction": direction
            },
            "steps": steps,
            "peak": {
                "km": peak["km"],
                "A": peak.get(f"{eventA}_runners", 0),
                "B": peak.get(f"{eventB}_runners", 0) if eventB else None,
                "combined": peak["combined_runners"],
                "areal_density": peak["areal_density"],
                "zone": peak["zone"],
            },
            "time_in_zones": time_in_zones,
        })

    return {
        "ok": True,
        "engine": "density",
        "segments": results,
    }