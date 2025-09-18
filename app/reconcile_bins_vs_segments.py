#!/usr/bin/env python3
"""
Reconcile bin-level density vs. segment density (±2% target).

Usage:
  python reconcile_bins_vs_segments.py \
      --bins path/to/bins.parquet \
      --segments-json path/to/map_data_YYYY-MM-DD-HHMM.json \
      [--tolerance 0.02]

It expects the map_data JSON schema like:
{
  "segments": [
    {
      "seg_id": "A1",
      "windows": [
        {"t_start": "2025-09-18T07:00:00Z", "t_end": "...", "density": 0.00123},
        ...
      ]
    }, ...
  ]
}

Bins parquet schema (typical):
  bin_id, segment_id, start_km, end_km, t_start, t_end, density, flow, los_class, bin_size_km
"""

import argparse, os, sys, json, math, gzip
import pandas as pd

def load_bins(path: str) -> pd.DataFrame:
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

    # basic cleaning
    df = df.dropna(subset=["segment_id","start_km","end_km","t_start","t_end","density"])
    # compute bin length (km) and meters for weighting
    df["bin_len_km"] = (df["end_km"] - df["start_km"]).astype(float)
    df["bin_len_m"]  = df["bin_len_km"] * 1000.0
    return df

def load_segment_windows_from_map(map_json_path: str) -> pd.DataFrame:
    with open(map_json_path, "r") as f:
        data = json.load(f)
    segs = data.get("segments", [])
    rows = []
    for s in segs:
        sid = s.get("seg_id") or s.get("segment_id")
        for w in s.get("windows", []):
            rows.append({
                "segment_id": sid,
                "t_start": w.get("t_start"),
                "t_end": w.get("t_end"),
                "seg_density": w.get("density"),
            })
    df = pd.DataFrame(rows)
    # drop empty rows
    df = df.dropna(subset=["segment_id","t_start","t_end","seg_density"])
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bins", required=True, help="bins.parquet or bins.geojson.gz")
    ap.add_argument("--segments-json", required=True, help="map_data_*.json with segment windows")
    ap.add_argument("--tolerance", type=float, default=0.02, help="relative tolerance (default 0.02 = 2%)")
    args = ap.parse_args()

    # Load
    bins = load_bins(args.bins)
    segw = load_segment_windows_from_map(args.segments_json)

    # Normalize time strings for join
    # (Assumes exact string match; if needed, convert to pandas timestamps and round to minute)
    for df in (bins, segw):
        df["t_start"] = pd.to_datetime(df["t_start"], utc=True)
        df["t_end"]   = pd.to_datetime(df["t_end"], utc=True)

    # Join by (segment_id, t_start, t_end)
    merged = pd.merge(
        bins,
        segw,
        on=["segment_id","t_start","t_end"],
        how="inner",
        validate="many_to_one"  # many bins per one segment window
    )

    if merged.empty:
        print("ERROR: No overlap between bins and segment windows. Check you used artifacts from the SAME RUN.", file=sys.stderr)
        return 2

    # For each (segment_id, window), compute length-weighted mean bin density
    grp = merged.groupby(["segment_id","t_start","t_end"], as_index=False).apply(
        lambda g: pd.Series({
            "bin_len_m_sum": g["bin_len_m"].sum(),
            "bin_density_len_mean": (g["density"] * g["bin_len_m"]).sum() / max(1e-9, g["bin_len_m"].sum()),
            "seg_density": g["seg_density"].iloc[0],
            "n_bins": len(g),
        })
    ).reset_index(drop=True)

    # Relative error
    grp["rel_err"] = (grp["bin_density_len_mean"] - grp["seg_density"]) / grp["seg_density"].replace(0, pd.NA)
    # Treat segments with seg_density==0: require bin_density_len_mean also ~0
    zero_mask = grp["seg_density"] == 0
    grp.loc[zero_mask, "rel_err"] = (grp.loc[zero_mask, "bin_density_len_mean"].abs() <= 1e-9).map(lambda ok: 0.0 if ok else float("inf"))

    # Flag failures
    tol = args.tolerance
    grp["pass"] = grp["rel_err"].abs() <= tol
    failed = grp[~grp["pass"]]

    # Summaries
    total_windows = len(grp)
    failed_count  = len(failed)
    max_abs_err   = grp["rel_err"].abs().replace([pd.NA, pd.NaT], 0).max()

    print(f"Windows compared: {total_windows}, failures: {failed_count}, tol={tol*100:.1f}%")
    print(f"Max |relative error|: {max_abs_err:.4f}")
    print()
    print("Per-segment summary:")
    segsum = grp.groupby("segment_id").agg(
        windows=("segment_id","count"),
        failures=("pass", lambda s: int((~s).sum())),
        mean_abs_rel_err=("rel_err", lambda x: float(x.abs().replace([pd.NA], 0).mean())),
        p95_abs_rel_err=("rel_err", lambda x: float(x.abs().quantile(0.95))),
    ).reset_index().sort_values("p95_abs_rel_err", ascending=False)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 120):
        print(segsum.to_string(index=False))

    # Fail the run if any window outside tolerance
    if failed_count > 0:
        print("\nFAILED windows (sample up to 20):")
        print(failed.head(20)[["segment_id","t_start","t_end","seg_density","bin_density_len_mean","rel_err","n_bins"]])
        return 1

    print("\nOK: All windows within tolerance.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
