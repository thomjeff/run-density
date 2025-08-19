from __future__ import annotations
import time
from typing import Dict, Optional, Any, List
import pandas as pd
import numpy as np

def _load_pace_csv(url_or_path: str) -> pd.DataFrame:
    df = pd.read_csv(url_or_path)
    df.columns = [c.lower() for c in df.columns]
    expected = {"event","runner_id","pace","distance"}
    if not expected.issubset(df.columns):
        raise ValueError(f"your_pace_data.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"].astype(str)
    df["pace"] = df["pace"].astype(float)      # minutes per km
    df["distance"] = df["distance"].astype(float)
    return df

def _arrival_time_sec(start_min: float, km: float, pace_min_per_km: float) -> float:
    return start_min * 60.0 + pace_min_per_km * 60.0 * km

def analyze_overlaps(
    pace_csv: str,
    overlaps_csv: Optional[str],
    start_times: Dict[str, float],
    step_km: float,
    time_window_s: float,
    eventA: str,
    eventB: Optional[str],
    from_km: float,
    to_km: float,
) -> Dict[str, Any]:
    """Per-step split counts using constant-pace model & staggered starts.

    Returns:
      {
        ok: True,
        engine: "overlap",
        steps: [ {km, <A>_runners, <B>_runners, combined_runners}, ... ],
        peak: {km, A, B, combined}
      }
    """
    t0 = time.perf_counter()
    df = _load_pace_csv(pace_csv).copy()
    df["start_sec"] = df["event"].map({k: float(v)*60.0 for k,v in start_times.items()}).astype(float)
    df["pace_sec_per_km"] = df["pace"] * 60.0

    dfA = df[df["event"] == eventA].copy()
    if dfA.empty:
        raise ValueError(f"No runners for eventA={eventA}")
    dfA.name = eventA
    dfB = None
    if eventB:
        dfB = df[df["event"] == eventB].copy()
        if dfB.empty:
            raise ValueError(f"No runners for eventB={eventB}")
        dfB.name = eventB

    def count_at_km(df_event: pd.DataFrame, km: float, t_center: float) -> int:
        t_arr = df_event["start_sec"] + df_event["pace_sec_per_km"] * km
        return int(((t_arr >= (t_center - time_window_s/2)) & (t_arr <= (t_center + time_window_s/2))).sum())

    steps: List[Dict[str, Any]] = []
    kms = np.round(np.arange(from_km, to_km + 1e-9, step_km), 2)
    for km in kms:
        # Reference timestamps per event (median) to reduce bias
        tA = (dfA["start_sec"] + dfA["pace_sec_per_km"] * km).median()
        cA = count_at_km(dfA, km, tA)
        cB = 0
        if dfB is not None:
            tB = (dfB["start_sec"] + dfB["pace_sec_per_km"] * km).median()
            cB = count_at_km(dfB, km, tB)
        steps.append({
            "km": float(km),
            f"{eventA}_runners": int(cA),
            f"{eventB}_runners": int(cB) if dfB is not None else None,
            "combined_runners": int(cA + cB),
        })

    peak = max(steps, key=lambda s: s["combined_runners"]) if steps else {"km": None, "combined_runners": 0}
    peak_out = {
        "km": peak["km"],
        "A": peak.get(f"{eventA}_runners", 0),
        "B": peak.get(f"{eventB}_runners", 0) if eventB else None,
        "combined": peak["combined_runners"],
    }
    return {
        "ok": True,
        "engine": "overlap",
        "steps": steps,
        "peak": peak_out,
    }