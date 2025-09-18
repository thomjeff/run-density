# app/segments_from_bins.py
from __future__ import annotations
import os, json, gzip, logging
from typing import Tuple
import pandas as pd

log = logging.getLogger(__name__)

def load_bins_parquet_or_geojson(bins_path_parquet: str, bins_path_geojson_gz: str) -> pd.DataFrame:
    try:
        df = pd.read_parquet(bins_path_parquet)
        log.info("SEG_BINS_LOAD: parquet=%s rows=%d", os.path.abspath(bins_path_parquet), len(df))
        return df
    except Exception as e:
        log.warning("SEG_BINS_LOAD: parquet failed (%s), attempting geojson.gz", e)

    with gzip.open(bins_path_geojson_gz, "rt") as f:
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
    df = pd.DataFrame(rows)
    log.info("SEG_BINS_LOAD: geojson=%s rows=%d", os.path.abspath(bins_path_geojson_gz), len(df))
    return df

def bins_to_segment_windows(df_bins: pd.DataFrame) -> pd.DataFrame:
    # Types & derived fields
    df = df_bins.dropna(subset=["segment_id","start_km","end_km","t_start","t_end","density"]).copy()
    df["t_start"] = pd.to_datetime(df["t_start"], utc=True)
    df["t_end"]   = pd.to_datetime(df["t_end"],   utc=True)
    df["bin_len_m"] = (df["end_km"].astype(float) - df["start_km"].astype(float)) * 1000.0

    # length-weighted mean density per (segment, window) + peak
    def _agg(g: pd.DataFrame) -> pd.Series:
        wsum = (g["density"] * g["bin_len_m"]).sum()
        lsum = max(1e-9, g["bin_len_m"].sum())
        return pd.Series({
            "density_mean": wsum / lsum,
            "density_peak": g["density"].max(),
            "n_bins": len(g)
        })

    out = (df.groupby(["segment_id","t_start","t_end"], as_index=False)
             .apply(_agg)
             .reset_index(drop=True))
    return out

def write_segment_windows(out_dir: str, seg_df: pd.DataFrame) -> Tuple[str, int]:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "segment_windows_from_bins.parquet")
    seg_df.to_parquet(out_path, index=False)
    log.info("POST_SAVE segment_windows_from_bins=%s rows=%d", os.path.abspath(out_path), len(seg_df))
    return out_path, len(seg_df)

def create_canonical_segments_from_bins(out_dir: str, bins_parquet: str, bins_geojson_gz: str) -> str:
    df_bins = load_bins_parquet_or_geojson(bins_parquet, bins_geojson_gz)
    seg_df  = bins_to_segment_windows(df_bins)
    out, n  = write_segment_windows(out_dir, seg_df)
    return out
