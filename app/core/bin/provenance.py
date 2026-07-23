"""
Resolve density-report bin/window metadata from analysis artifacts (Issue #798 Phase 5).

Never invent silent defaults such as window_s=30 / bin_km=0.2 for live reports.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import pandas as pd


class BinProvenanceError(ValueError):
    """Bins artifacts do not contain enough information for report metadata."""


def resolve_bin_report_params(bins_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Derive report methodology params from ``bins.parquet`` columns.

    Returns:
        Dict with:
          - ``bin_km`` / ``step_km``: spatial bin size (km)
          - ``window_s`` / ``window_seconds``: temporal window (seconds)
    """
    if bins_df is None or bins_df.empty:
        raise BinProvenanceError("bins DataFrame is empty; cannot resolve bin/window provenance")

    bin_km = _resolve_bin_km(bins_df)
    window_seconds = _resolve_window_seconds(bins_df)
    return {
        "bin_km": bin_km,
        "step_km": bin_km,
        "window_s": window_seconds,
        "window_seconds": window_seconds,
    }


def _resolve_bin_km(bins_df: pd.DataFrame) -> float:
    if "bin_size_km" not in bins_df.columns:
        raise BinProvenanceError(
            "bins.parquet missing 'bin_size_km'; cannot set report bin size without inventing a value"
        )
    series = pd.to_numeric(bins_df["bin_size_km"], errors="coerce").dropna()
    if series.empty:
        raise BinProvenanceError("bins.parquet has no usable bin_size_km values")
    unique = sorted({round(float(v), 6) for v in series.unique()})
    if len(unique) == 1:
        return float(unique[0])
    # Prefer modal value when coarsening left mixed sizes; still artifact-backed.
    mode_vals = series.mode()
    if mode_vals.empty:
        raise BinProvenanceError(f"ambiguous bin_size_km values: {unique}")
    return float(round(float(mode_vals.iloc[0]), 6))


def _resolve_window_seconds(bins_df: pd.DataFrame) -> int:
    if "t_start" not in bins_df.columns or "t_end" not in bins_df.columns:
        raise BinProvenanceError(
            "bins.parquet missing t_start/t_end; cannot set report window without inventing a value"
        )
    starts = pd.to_datetime(bins_df["t_start"], utc=True, errors="coerce")
    ends = pd.to_datetime(bins_df["t_end"], utc=True, errors="coerce")
    deltas = (ends - starts).dt.total_seconds().dropna()
    deltas = deltas[deltas > 0]
    if deltas.empty:
        raise BinProvenanceError("bins.parquet has no positive (t_end - t_start) windows")
    # Median is robust if a few irregular rows exist
    seconds = int(round(float(deltas.median())))
    if seconds <= 0:
        raise BinProvenanceError(f"resolved non-positive window_seconds={seconds}")
    return seconds
