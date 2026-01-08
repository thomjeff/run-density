#!/usr/bin/env python3
"""
Validate LOS alignment across bins.parquet, segment_metrics.json, Density.md, and UI endpoint.

Usage:
    python3 scripts/validate_los_alignment.py --run-id <run_id> --day <day>

Optional args:
    --runflow-root <path>    Root directory containing runflow data (default: env RUNFLOW_ROOT or /app/runflow)
    --api-base-url <url>     Base URL for UI API (default: http://localhost:8000)
    --segment-id <seg_id>    Segment ID to validate (default: A1)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests


SUMMARY_FIELDS = {
    "peak_density",
    "peak_rate",
    "segments_with_flags",
    "flagged_bins",
    "overtaking_segments",
    "co_presence_segments",
}


class ValidationError(Exception):
    """Error raised when validation checks fail."""


def _resolve_runflow_root(explicit_root: Optional[str]) -> Path:
    if explicit_root:
        return Path(explicit_root)
    env_root = os.getenv("RUNFLOW_ROOT")
    if env_root:
        return Path(env_root)
    return Path("/app/runflow")


def _load_bins(parquet_path: Path) -> pd.DataFrame:
    if not parquet_path.exists():
        raise ValidationError(f"bins.parquet not found at {parquet_path}")
    return pd.read_parquet(parquet_path)


def _find_worst_bin_los(df: pd.DataFrame, segment_id: str) -> str:
    group_col = "segment_id" if "segment_id" in df.columns else "seg_id"
    if group_col not in df.columns:
        raise ValidationError("bins.parquet missing segment_id/seg_id column")

    if segment_id not in set(df[group_col]):
        raise ValidationError(f"Segment {segment_id} not found in bins.parquet")

    segment_bins = df[df[group_col] == segment_id]
    density_col = None
    for candidate in ("density", "density_peak", "density_mean"):
        if candidate in segment_bins.columns:
            density_col = candidate
            break
    if density_col is None:
        raise ValidationError("bins.parquet missing density columns")

    worst_bin_idx = segment_bins[density_col].idxmax()
    worst_bin = segment_bins.loc[worst_bin_idx]

    if "los_class" not in worst_bin:
        raise ValidationError("bins.parquet worst bin missing los_class")

    worst_los = str(worst_bin["los_class"]).strip()
    if not worst_los:
        raise ValidationError("bins.parquet worst bin los_class is empty")
    return worst_los


def _load_segment_metrics(metrics_path: Path) -> Dict[str, Dict[str, str]]:
    if not metrics_path.exists():
        raise ValidationError(f"segment_metrics.json not found at {metrics_path}")
    raw_data = json.loads(metrics_path.read_text())
    if not isinstance(raw_data, dict):
        raise ValidationError("segment_metrics.json is not a dict")
    return {k: v for k, v in raw_data.items() if k not in SUMMARY_FIELDS and isinstance(v, dict)}


def _parse_density_report_los(density_md_path: Path, segment_id: str) -> str:
    if not density_md_path.exists():
        raise ValidationError(f"Density.md not found at {density_md_path}")

    lines = density_md_path.read_text().splitlines()
    table_start = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Flagged Segments":
            table_start = idx
            break
    if table_start is None:
        raise ValidationError("Density.md missing 'Flagged Segments' section")

    header_idx = None
    for idx in range(table_start, len(lines)):
        if lines[idx].strip().startswith("| Segment "):
            header_idx = idx
            break
        if lines[idx].strip().startswith("## "):
            break
    if header_idx is None:
        raise ValidationError("Density.md flagged segments table header not found")

    headers = [h.strip() for h in lines[header_idx].strip().strip("|").split("|")]
    if "Segment" not in headers or "LOS" not in headers:
        raise ValidationError("Density.md flagged segments table missing Segment/LOS columns")

    segment_idx = headers.index("Segment")
    los_idx = headers.index("LOS")
    row_start = header_idx + 2

    for row in lines[row_start:]:
        if not row.strip().startswith("|"):
            if row.strip().startswith("## "):
                break
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) <= max(segment_idx, los_idx):
            continue
        if cells[segment_idx] == segment_id:
            los_value = cells[los_idx].strip()
            if not los_value:
                raise ValidationError(f"Density.md LOS empty for segment {segment_id}")
            return los_value

    raise ValidationError(f"Density.md missing segment row for {segment_id}")


def _fetch_ui_segment_los(api_base_url: str, run_id: str, day: str, segment_id: str) -> str:
    url = f"{api_base_url.rstrip('/')}/api/density/segments"
    response = requests.get(url, params={"run_id": run_id, "day": day}, timeout=30)
    if response.status_code != 200:
        raise ValidationError(f"UI endpoint {url} failed: {response.status_code} {response.text}")
    payload = response.json()
    segments = payload.get("segments", [])
    for segment in segments:
        if segment.get("seg_id") == segment_id:
            los_value = segment.get("worst_los")
            if not los_value:
                raise ValidationError(f"UI endpoint missing worst_los for {segment_id}")
            return str(los_value).strip()
    raise ValidationError(f"UI endpoint missing segment {segment_id}")


def _compare_values(label: str, expected: str, actual: str, errors: List[str]) -> None:
    if expected != actual:
        errors.append(f"LOS mismatch ({label}): expected {expected}, got {actual}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LOS alignment across artifacts and UI.")
    parser.add_argument("--run-id", required=True, help="Run ID to validate")
    parser.add_argument("--day", required=True, help="Day code (fri|sat|sun|mon)")
    parser.add_argument("--runflow-root", help="Root directory containing runflow data")
    parser.add_argument("--api-base-url", default="http://localhost:8000", help="UI API base URL")
    parser.add_argument("--segment-id", default="A1", help="Segment ID to validate")
    args = parser.parse_args()

    runflow_root = _resolve_runflow_root(args.runflow_root)
    run_path = runflow_root / args.run_id / args.day

    bins_path = run_path / "bins" / "bins.parquet"
    metrics_path = run_path / "ui" / "metrics" / "segment_metrics.json"
    density_md_path = run_path / "reports" / "Density.md"

    errors: List[str] = []

    bins_df = _load_bins(bins_path)
    bins_los = _find_worst_bin_los(bins_df, args.segment_id)

    segment_metrics = _load_segment_metrics(metrics_path)
    metrics_los = segment_metrics.get(args.segment_id, {}).get("worst_los")
    if not metrics_los:
        raise ValidationError(f"segment_metrics.json missing worst_los for {args.segment_id}")
    metrics_los = str(metrics_los).strip()

    report_los = _parse_density_report_los(density_md_path, args.segment_id)
    report_los = str(report_los).strip()

    ui_los = _fetch_ui_segment_los(args.api_base_url, args.run_id, args.day, args.segment_id)

    _compare_values("segment_metrics.json vs bins.parquet", bins_los, metrics_los, errors)
    _compare_values("Density.md vs segment_metrics.json", metrics_los, report_los, errors)
    _compare_values("UI endpoint vs segment_metrics.json", metrics_los, ui_los, errors)

    if errors:
        error_text = "\n".join(f"- {err}" for err in errors)
        raise ValidationError(f"LOS validation failed:\n{error_text}")

    print("✅ LOS validation passed")
    print(f"   Segment: {args.segment_id}")
    print(f"   bins.parquet worst_los: {bins_los}")
    print(f"   segment_metrics.json worst_los: {metrics_los}")
    print(f"   Density.md worst_los: {report_los}")
    print(f"   UI endpoint worst_los: {ui_los}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValidationError as exc:
        print(f"❌ {exc}")
        sys.exit(1)
