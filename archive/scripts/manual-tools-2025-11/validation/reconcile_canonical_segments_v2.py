#!/usr/bin/env python3
"""
Reconcile canonical segments with a fresh aggregation from canonical bins.

Inputs (default to today's reports folder):
  --reports-dir /path/to/reports/YYYY-MM-DD
  --bins-parquet <override>                    (default: reports-dir/bins.parquet)
  --segments-parquet <override>                (default: reports-dir/segment_windows_from_bins.parquet)
  --out-csv <path>                             (default: reports-dir/reconciliation_canonical_vs_fresh.csv)

Env vars (optional):
  REL_ERR_TOL=0.02        # ±2% per-window tolerance
  P95_ERR_TOL=0.02        # p95 absolute relative error tolerance
  MIN_DENOM=1e-9          # numeric stability floor

Exit codes:
  0 = pass
  2 = fail (thresholds exceeded or required files missing or empty)

Usage:
  python reconcile_canonical_segments_v2.py --reports-dir ./reports/2025-09-19
"""

import argparse
import os
import sys
import json
import math
import gzip
from datetime import datetime, timezone

import pandas as pd

def _abs_path(p): return os.path.abspath(p)

def _env_float(key, default):
    try:
        return float(os.getenv(key, default))
    except Exception:
        return default

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", required=True, help="Path to daily reports folder (e.g., ./reports/2025-09-19)")
    ap.add_argument("--bins-parquet", default=None, help="Override path to bins.parquet")
    ap.add_argument("--segments-parquet", default=None, help="Override path to segment_windows_from_bins.parquet")
    ap.add_argument("--out-csv", default=None, help="Path to write reconciliation CSV (default: reports-dir/reconciliation_canonical_vs_fresh.csv)")
    return ap.parse_args()

def load_bins_parquet(path_parquet, path_geojson_gz=None):
    """
    Load bins from parquet (preferred). If parquet missing and geojson.gz present, fall back.
    Returns DataFrame with at least: segment_id, start_km, end_km, t_start, t_end, density
    """
    if path_parquet and os.path.exists(path_parquet):
        df = pd.read_parquet(path_parquet)
        return df

    if path_geojson_gz and os.path.exists(path_geojson_gz):
        with gzip.open(path_geojson_gz, "rt") as f:
            gj = json.load(f)
        rows = []
        for ft in gj.get("features", []):
            p = ft.get("properties", {})
            rows.append({
                "segment_id": p.get("segment_id"),
                "start_km": p.get("start_km"),
                "end_km": p.get("end_km"),
                "t_start": p.get("t_start"),
                "t_end": p.get("t_end"),
                "density": p.get("density"),
            })
        return pd.DataFrame(rows)

    raise FileNotFoundError(f"Neither parquet nor geojson bins found at: {path_parquet} / {path_geojson_gz}")

def normalize_bins(df_bins, min_denom):
    """Ensure correct dtypes and compute bin_len_m."""
    need_cols = ["segment_id","start_km","end_km","t_start","t_end","density"]
    missing = [c for c in need_cols if c not in df_bins.columns]
    if missing:
        raise ValueError(f"Bins dataframe missing required columns: {missing}")

    df = df_bins.dropna(subset=["segment_id","start_km","end_km","t_start","t_end","density"]).copy()

    # Coerce types
    df["segment_id"] = df["segment_id"].astype(str)
    df["start_km"] = pd.to_numeric(df["start_km"], errors="coerce")
    df["end_km"] = pd.to_numeric(df["end_km"], errors="coerce")
    df["density"] = pd.to_numeric(df["density"], errors="coerce")
    df = df.dropna(subset=["start_km","end_km","density"])

    # Parse timestamps as utc
    df["t_start"] = pd.to_datetime(df["t_start"], utc=True, errors="coerce")
    df["t_end"]   = pd.to_datetime(df["t_end"],   utc=True, errors="coerce")
    df = df.dropna(subset=["t_start","t_end"])

    # Compute bin length in meters
    df["bin_len_m"] = (df["end_km"] - df["start_km"]) * 1000.0

    return df

def aggregate_bins_to_segments(df_bins):
    """
    Fresh aggregation: bins -> segments using length-weighted mean density.
    Returns DataFrame with: segment_id, t_start, t_end, density_mean_fresh, density_peak_fresh, n_bins
    """
    def _agg_func(group):
        # Length-weighted mean density
        weights = group["bin_len_m"]
        densities = group["density"]
        
        total_weight = weights.sum()
        if total_weight <= 0:
            density_mean = 0.0
        else:
            density_mean = (densities * weights).sum() / total_weight
        
        return pd.Series({
            "density_mean_fresh": density_mean,
            "density_peak_fresh": densities.max(),
            "n_bins": len(group)
        })

    # Group by segment and time window
    result = df_bins.groupby(["segment_id", "t_start", "t_end"], group_keys=False).apply(_agg_func, include_groups=False).reset_index()
    
    return result

def load_canonical_segments(segments_parquet):
    """
    Load canonical segments from segment_windows_from_bins.parquet.
    Returns DataFrame with: segment_id, t_start, t_end, density_mean, density_peak, n_bins
    """
    if not os.path.exists(segments_parquet):
        raise FileNotFoundError(f"Canonical segments not found: {segments_parquet}")
    
    df = pd.read_parquet(segments_parquet)
    
    # Ensure required columns
    need_cols = ["segment_id", "t_start", "t_end", "density_mean", "density_peak"]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Canonical segments missing required columns: {missing}")
    
    # Parse timestamps as UTC
    df["t_start"] = pd.to_datetime(df["t_start"], utc=True, errors="coerce")
    df["t_end"] = pd.to_datetime(df["t_end"], utc=True, errors="coerce")
    df = df.dropna(subset=["t_start", "t_end"])
    
    return df

def main():
    args = parse_args()
    
    reports_dir = _abs_path(args.reports_dir)
    if not os.path.isdir(reports_dir):
        print(f"ERR: Reports directory not found: {reports_dir}", file=sys.stderr)
        sys.exit(2)

    bins_parquet = args.bins_parquet or os.path.join(reports_dir, "bins.parquet")
    bins_geojson_gz = os.path.join(reports_dir, "bins.geojson.gz")
    segments_parquet = args.segments_parquet or os.path.join(reports_dir, "segment_windows_from_bins.parquet")
    out_csv = args.out_csv or os.path.join(reports_dir, "reconciliation_canonical_vs_fresh.csv")

    rel_tol = _env_float("REL_ERR_TOL", 0.02)
    p95_tol = _env_float("P95_ERR_TOL", 0.02)
    min_denom = _env_float("MIN_DENOM", 1e-9)

    # Load bins
    try:
        df_bins_raw = load_bins_parquet(bins_parquet, bins_geojson_gz)
    except Exception as e:
        print(f"ERR: load_bins failed: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        df_bins = normalize_bins(df_bins_raw, min_denom)
    except Exception as e:
        print(f"ERR: normalize_bins failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Fresh aggregation
    try:
        df_fresh = aggregate_bins_to_segments(df_bins)
    except Exception as e:
        print(f"ERR: aggregate bins->segments failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Load canonical segments
    try:
        df_canon = load_canonical_segments(segments_parquet)
    except Exception as e:
        print(f"ERR: load_canonical_segments failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Join on keys
    keys = ["segment_id","t_start","t_end"]
    m = df_canon.merge(df_fresh, on=keys, how="inner")

    if m.empty:
        print("ERR: No overlapping windows between canonical segments and fresh aggregation.", file=sys.stderr)
        sys.exit(2)

    # Compute absolute relative error vs canonical
    m["abs_rel_err"] = (m["density_mean"] - m["density_mean_fresh"]).abs() / m["density_mean"].clip(lower=min_denom)

    # Save per-window comparison
    available_cols = keys + ["density_mean","density_mean_fresh","density_peak_fresh","abs_rel_err"]
    # Add n_bins if available
    if "n_bins" in m.columns:
        available_cols.append("n_bins")
    m[available_cols].to_csv(out_csv, index=False)

    # Summaries
    by_seg = m.groupby("segment_id")["abs_rel_err"]
    seg_p95 = by_seg.quantile(0.95).sort_values(ascending=False)

    overall_p95 = m["abs_rel_err"].quantile(0.95)
    overall_mean = m["abs_rel_err"].mean()
    overall_max = m["abs_rel_err"].max()
    
    # Count failures
    failures = (m["abs_rel_err"] > rel_tol).sum()
    
    # Print summary
    print("=== CANONICAL RECONCILIATION (bins -> fresh vs saved) ===")
    print(f"Rows compared:      {len(m)}")
    print(f"Mean |rel err|:     {overall_mean:.6f}")
    print(f"P95  |rel err|:     {overall_p95:.6f}  (tolerance {p95_tol:.4f})")
    print(f"Max  |rel err|:     {overall_max:.6f}")
    print(f"Windows > {rel_tol:.4f}:   {failures}")
    print()
    
    if len(seg_p95) > 0:
        print("Top segments by P95 |rel err|:")
        for seg_id, p95_err in seg_p95.head(10).items():
            print(f"   {seg_id}  p95_abs={p95_err:.6f}")
        print()
    
    # Determine pass/fail
    if failures > 0 or overall_p95 > p95_tol:
        print("RESULT: FAIL")
        print(f"Reconciliation CSV written to: {out_csv}")
        sys.exit(2)
    else:
        print("RESULT: PASS")
        print(f"Reconciliation CSV written to: {out_csv}")
        sys.exit(0)

if __name__ == "__main__":
    main()
