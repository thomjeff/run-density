#!/usr/bin/env python3
"""
Simple Bin vs Segment Reconciliation (Peak Density Comparison)

Compares bin-level density aggregates to segment peak densities from map data.
This is a simplified version that works with available map_data.json format.

Usage:
  python reconcile_bins_simple.py \
      --bins path/to/bins.parquet \
      --map-data path/to/map_data_YYYY-MM-DD-HHMM.json \
      [--tolerance 0.10]
"""

import argparse, os, sys, json, gzip
import pandas as pd

def load_bins(path: str) -> pd.DataFrame:
    """Load bin dataset from parquet or geojson.gz"""
    if path.endswith(".parquet"):
        import pyarrow.parquet as pq
        df = pq.read_table(path).to_pandas()
    elif path.endswith(".geojson.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            gj = json.load(f)
        feats = gj.get("features", [])
        rows = []
        for ft in feats:
            p = ft.get("properties", {})
            rows.append({
                "segment_id": p.get("segment_id"),
                "start_km": p.get("start_km"),
                "end_km": p.get("end_km"),
                "t_start": p.get("t_start"),
                "t_end": p.get("t_end"),
                "density": p.get("density"),
                "flow": p.get("flow"),
                "bin_size_km": p.get("bin_size_km"),
            })
        df = pd.DataFrame(rows)
    else:
        raise ValueError(f"Unsupported bins format: {path}")

    # Basic cleaning
    df = df.dropna(subset=["segment_id","density"])
    df["bin_len_km"] = (df["end_km"] - df["start_km"]).astype(float)
    df["bin_len_m"] = df["bin_len_km"] * 1000.0
    return df

def load_segment_peaks(map_data_path: str) -> pd.DataFrame:
    """Load segment peak densities from map_data.json"""
    with open(map_data_path, "r") as f:
        data = json.load(f)
    
    segments = data.get("segments", {})
    rows = []
    for seg_id, seg_data in segments.items():
        rows.append({
            "segment_id": seg_id,
            "peak_areal_density": seg_data.get("peak_areal_density", 0.0),
            "segment_label": seg_data.get("segment_label", seg_id)
        })
    
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bins", required=True, help="bins.parquet or bins.geojson.gz")
    ap.add_argument("--map-data", required=True, help="map_data_*.json with segment peaks")
    ap.add_argument("--tolerance", type=float, default=0.10, help="relative tolerance (default 0.10 = 10%)")
    args = ap.parse_args()

    # Load data
    bins = load_bins(args.bins)
    segments = load_segment_peaks(args.map_data)

    # Aggregate bins by segment (length-weighted mean density)
    bin_agg = bins.groupby("segment_id").apply(
        lambda g: pd.Series({
            "bin_count": len(g),
            "occupied_bins": (g["density"] > 0).sum(),
            "bin_peak_density": g["density"].max(),
            "bin_mean_density": (g["density"] * g["bin_len_m"]).sum() / max(1e-9, g["bin_len_m"].sum()),
            "total_bin_length_m": g["bin_len_m"].sum()
        })
    ).reset_index()

    # Merge with segment data
    comparison = pd.merge(bin_agg, segments, on="segment_id", how="inner")
    
    if comparison.empty:
        print("ERROR: No matching segments between bins and map data", file=sys.stderr)
        return 2

    # Calculate relative error (bin peak vs segment peak)
    comparison["rel_err"] = (comparison["bin_peak_density"] - comparison["peak_areal_density"]) / comparison["peak_areal_density"].replace(0, pd.NA)
    
    # Handle zero density segments
    zero_mask = comparison["peak_areal_density"] == 0
    comparison.loc[zero_mask, "rel_err"] = (comparison.loc[zero_mask, "bin_peak_density"].abs() <= 1e-9).map(lambda ok: 0.0 if ok else float("inf"))

    # Flag failures
    tol = args.tolerance
    comparison["pass"] = comparison["rel_err"].abs() <= tol
    failed = comparison[~comparison["pass"]]

    # Summary statistics
    total_segments = len(comparison)
    failed_count = len(failed)
    max_abs_err = comparison["rel_err"].abs().replace([pd.NA], 0).max()

    print(f"Bin vs Segment Peak Density Reconciliation")
    print(f"==========================================")
    print(f"Segments compared: {total_segments}")
    print(f"Failures (>{tol*100:.1f}%): {failed_count}")
    print(f"Max |relative error|: {max_abs_err:.4f} ({max_abs_err*100:.1f}%)")
    print()

    # Detailed comparison table
    print("Per-segment comparison:")
    display_cols = ["segment_id", "segment_label", "bin_peak_density", "peak_areal_density", "rel_err", "occupied_bins", "pass"]
    comparison_display = comparison[display_cols].copy()
    comparison_display["rel_err"] = comparison_display["rel_err"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
    comparison_display["bin_peak_density"] = comparison_display["bin_peak_density"].apply(lambda x: f"{x:.6f}")
    comparison_display["peak_areal_density"] = comparison_display["peak_areal_density"].apply(lambda x: f"{x:.6f}")
    
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 150):
        print(comparison_display.to_string(index=False))

    # Show failures if any
    if failed_count > 0:
        print(f"\nFAILED segments (>{tol*100:.1f}% tolerance):")
        failed_display = failed[display_cols].copy()
        failed_display["rel_err"] = failed_display["rel_err"].apply(lambda x: f"{x:.4f}")
        print(failed_display.to_string(index=False))
        return 1

    print(f"\n✅ SUCCESS: All segments within ±{tol*100:.1f}% tolerance")
    return 0

if __name__ == "__main__":
    sys.exit(main())
