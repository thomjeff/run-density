"""Compare two analysis runs' key artifacts (#862 parity)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


FLOW_METRIC_COLS = [
    "overtaking_a",
    "overtaking_b",
    "pct_a",
    "pct_b",
    "copresence_a",
    "copresence_b",
    "unique_encounters",
    "participants_involved",
]


def _day_dir(run_root: Path) -> Path:
    for name in ("sun", "sat", "fri", "mon"):
        d = run_root / name
        if d.is_dir():
            return d
    raise FileNotFoundError(f"No day directory under {run_root}")


def _numeric_max_abs_diff(a: pd.DataFrame, b: pd.DataFrame, cols: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for col in cols:
        if col not in a.columns or col not in b.columns:
            continue
        x = pd.to_numeric(a[col], errors="coerce").fillna(0)
        y = pd.to_numeric(b[col], errors="coerce").fillna(0)
        n = min(len(x), len(y))
        if n == 0:
            out[col] = 0.0
            continue
        out[col] = float((x.iloc[:n] - y.iloc[:n]).abs().max())
    return out


def compare_runs(baseline_id: str, candidate_id: str, analysis_root: Path) -> Dict[str, Any]:
    base = _day_dir(analysis_root / baseline_id)
    cand = _day_dir(analysis_root / candidate_id)
    report: Dict[str, Any] = {
        "baseline": baseline_id,
        "candidate": candidate_id,
        "day_baseline": base.name,
        "day_candidate": cand.name,
    }

    loc_b = pd.read_csv(base / "reports" / "Locations.csv")
    loc_c = pd.read_csv(cand / "reports" / "Locations.csv")
    timing_cols = [c for c in ("first_runner", "last_runner", "peak_start", "peak_end") if c in loc_b.columns]
    report["locations_rows"] = {"baseline": len(loc_b), "candidate": len(loc_c)}
    report["locations_timing_max_abs"] = _numeric_max_abs_diff(loc_b, loc_c, timing_cols)

    flow_b = pd.read_csv(base / "reports" / "Flow.csv")
    flow_c = pd.read_csv(cand / "reports" / "Flow.csv")
    report["flow_rows"] = {"baseline": len(flow_b), "candidate": len(flow_c)}
    report["flow_csv_equal"] = bool(flow_b.equals(flow_c))
    if not report["flow_csv_equal"]:
        key = [c for c in ("seg_id", "event_a", "event_b", "zone_index", "zone_start_km_a") if c in flow_b.columns]
        report["flow_metric_max_abs"] = _numeric_max_abs_diff(flow_b, flow_c, FLOW_METRIC_COLS)
    else:
        report["flow_metric_max_abs"] = {col: 0.0 for col in FLOW_METRIC_COLS}

    dens_b = json.loads((base / "computation" / "density_results.json").read_text(encoding="utf-8"))
    dens_c = json.loads((cand / "computation" / "density_results.json").read_text(encoding="utf-8"))
    segs_b = dens_b.get("segments") or {}
    segs_c = dens_c.get("segments") or {}
    report["density_segment_counts"] = {"baseline": len(segs_b), "candidate": len(segs_c)}
    peak_deltas = []
    for sid, payload in segs_b.items():
        other = segs_c.get(sid) or {}
        pb = (payload.get("summary") or {}).get("active_peak_concurrency")
        pc = (other.get("summary") or {}).get("active_peak_concurrency")
        if pb is None or pc is None:
            continue
        peak_deltas.append(abs(float(pb) - float(pc)))
    report["density_peak_concurrency_max_abs"] = max(peak_deltas) if peak_deltas else None

    bins_b = pd.read_parquet(base / "bins" / "bins.parquet")
    bins_c = pd.read_parquet(cand / "bins" / "bins.parquet")
    report["bins_rows"] = {"baseline": len(bins_b), "candidate": len(bins_c)}
    dens_col = next((c for c in ("density", "areal_density", "crowd_density", "n_runners") if c in bins_b.columns), None)
    if dens_col and len(bins_b) == len(bins_c):
        d = (bins_b[dens_col].astype(float) - bins_c[dens_col].astype(float)).abs()
        report["bins_metric"] = dens_col
        report["bins_metric_max_abs"] = float(d.max())
        report["bins_metric_mean_abs"] = float(d.mean())
        report["bins_density_corr"] = float(bins_b[dens_col].astype(float).corr(bins_c[dens_col].astype(float)))

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Runflow analysis runs")
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--analysis-root", default="/app/runflow/analysis")
    args = parser.parse_args()
    report = compare_runs(args.baseline, args.candidate, Path(args.analysis_root))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
