import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import pytest
from fastapi.testclient import TestClient
import yaml

from app.main import app  # FastAPI app

TOL = 1e-3  # Allow for rounding differences in API responses

def load_latest_run_id():
    latest_path = Path("artifacts/latest.json")
    with latest_path.open("r", encoding="utf-8") as f:
        return json.load(f)["run_id"]

def load_rulebook_thresholds():
    with open("config/density_rulebook.yml", "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    # Expect: y["globals"]["los_thresholds"] with keys "A".."F", each with min/max
    return y["globals"]["los_thresholds"]

def los_from_density(density, thresholds):
    # thresholds: {"A":{"min":0.0,"max":0.36}, ...}
    # Choose the band where min <= density < max, last band inclusive on max
    for band in ["A","B","C","D","E"]:
        rng = thresholds[band]
        if rng["min"] <= density < rng["max"]:
            return band
    # If none matched, it's F
    return "F"

def fmt_hhmm(ts):
    # ts: pandas Timestamp or datetime
    if pd.isna(ts):
        return None
    if isinstance(ts, pd.Timestamp):
        ts = ts.to_pydatetime()
    return ts.strftime("%H:%M")

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

def test_segments_api_matches_bins_parquet(client):
    run_id = load_latest_run_id()

    # Load raw sources
    bins_path = Path(f"reports/{run_id}/bins.parquet")
    assert bins_path.exists(), f"Missing {bins_path}"

    bins = pd.read_parquet(bins_path)

    # Expected columns in bins:
    # segment_id, start_km, end_km, t_start, t_end, density, rate, ...
    required = {"segment_id", "t_start", "t_end", "density", "rate"}
    missing = required - set(bins.columns)
    assert not missing, f"bins.parquet missing columns: {missing}"

    # Normalize time columns to datetime (if not already)
    # Expect ISO strings or pandas timestamps; coerce_any
    for col in ["t_start", "t_end"]:
        if not pd.api.types.is_datetime64_any_dtype(bins[col]):
            bins[col] = pd.to_datetime(bins[col], utc=True, errors="coerce")

    # Compute expected per-segment metrics from raw bins
    grp = bins.groupby("segment_id", dropna=False)

    expected_peak_density = grp["density"].max().to_dict()
    expected_peak_rate    = grp["rate"].max().to_dict()

    # Active window: min t_start to max t_end where there is activity
    min_start = grp["t_start"].min().to_dict()
    max_end   = grp["t_end"].max().to_dict()

    thresholds = load_rulebook_thresholds()
    expected_worst_los = {
        seg: los_from_density(dval if pd.notna(dval) else 0.0, thresholds)
        for seg, dval in expected_peak_density.items()
    }

    # Call the API
    resp = client.get("/api/segments/geojson")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("type") == "FeatureCollection"
    feats = payload.get("features", [])

    # Build actuals from API
    actual_by_seg = {}
    for f in feats:
        p = f.get("properties", {})
        seg = p.get("seg_id")
        if not seg:
            continue
        actual_by_seg[seg] = {
            "peak_density": p.get("peak_density"),
            "peak_rate": p.get("peak_rate"),
            "worst_los": p.get("worst_los"),
            "active_window": p.get("active_window"),  # expected "HH:MM–HH:MM"
        }

    # Compare for every seg present in API payload
    for seg, actual in actual_by_seg.items():
        # Peak density
        exp_pd = float(expected_peak_density.get(seg, 0.0) or 0.0)
        act_pd = float(actual.get("peak_density") or 0.0)
        assert abs(exp_pd - act_pd) <= TOL, f"[{seg}] peak_density exp={exp_pd} got={act_pd}"

        # Peak rate
        exp_pr = float(expected_peak_rate.get(seg, 0.0) or 0.0)
        act_pr = float(actual.get("peak_rate") or 0.0)
        assert abs(exp_pr - act_pr) <= TOL, f"[{seg}] peak_rate exp={exp_pr} got={act_pr}"

        # Worst LOS (derived from peak density)
        exp_los = expected_worst_los.get(seg, "A")
        act_los = actual.get("worst_los") or "A"
        assert exp_los == act_los, f"[{seg}] worst_los exp={exp_los} got={act_los}"

        # Active window
        exp_start = fmt_hhmm(min_start.get(seg))
        exp_end   = fmt_hhmm(max_end.get(seg))
        exp_window = f"{exp_start}–{exp_end}" if exp_start and exp_end else None

        act_window = actual.get("active_window")
        # Only enforce when both exist
        if exp_window and act_window:
            assert exp_window == act_window, f"[{seg}] active_window exp={exp_window} got={act_window}"
