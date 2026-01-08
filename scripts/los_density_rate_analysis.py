#!/usr/bin/env python3
"""Analyze correlation between density and rate, plus divergence windows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def _safe_corr(series_a: pd.Series, series_b: pd.Series) -> float | None:
    valid = series_a.notna() & series_b.notna()
    if valid.sum() < 2:
        return None
    return float(series_a[valid].corr(series_b[valid]))


def _segment_correlations(df: pd.DataFrame) -> list[dict[str, object]]:
    results = []
    for segment_id, segment_df in df.groupby("segment_id"):
        corr = _safe_corr(segment_df["density"], segment_df["rate"])
        results.append(
            {
                "segment_id": segment_id,
                "count": int(segment_df.shape[0]),
                "corr_density_rate": corr,
            }
        )
    return sorted(results, key=lambda item: (item["segment_id"] or ""))


def _window_correlations(df: pd.DataFrame) -> list[dict[str, object]]:
    results = []
    for window_idx, window_df in df.groupby("window_idx"):
        corr = _safe_corr(window_df["density"], window_df["rate"])
        t_start = window_df["t_start"].iloc[0] if "t_start" in window_df else None
        t_end = window_df["t_end"].iloc[0] if "t_end" in window_df else None
        results.append(
            {
                "window_idx": int(window_idx),
                "t_start": t_start,
                "t_end": t_end,
                "count": int(window_df.shape[0]),
                "corr_density_rate": corr,
            }
        )
    return sorted(results, key=lambda item: item["window_idx"])


def _divergence_windows(df: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    window_stats = (
        df.groupby("window_idx")
        .agg(
            t_start=("t_start", "first"),
            t_end=("t_end", "first"),
            mean_density=("density", "mean"),
            mean_rate=("rate", "mean"),
            count=("density", "size"),
        )
        .reset_index()
    )

    density_hi = window_stats["mean_density"].quantile(0.8)
    density_mid_low = window_stats["mean_density"].quantile(0.4)
    density_mid_high = window_stats["mean_density"].quantile(0.6)
    rate_hi = window_stats["mean_rate"].quantile(0.8)
    rate_low = window_stats["mean_rate"].quantile(0.2)

    high_density_low_rate = window_stats[
        (window_stats["mean_density"] >= density_hi)
        & (window_stats["mean_rate"] <= rate_low)
    ]
    high_rate_moderate_density = window_stats[
        (window_stats["mean_rate"] >= rate_hi)
        & (window_stats["mean_density"] >= density_mid_low)
        & (window_stats["mean_density"] <= density_mid_high)
    ]

    def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
        return [
            {
                "window_idx": int(row.window_idx),
                "t_start": row.t_start,
                "t_end": row.t_end,
                "mean_density": float(row.mean_density),
                "mean_rate": float(row.mean_rate),
                "count": int(row.count),
            }
            for row in frame.itertuples(index=False)
        ]

    return {
        "high_density_low_rate": _records(high_density_low_rate),
        "high_rate_moderate_density": _records(high_rate_moderate_density),
    }


def _a1_breakdown(df: pd.DataFrame) -> dict[str, object]:
    a1_df = df[df["segment_id"].str.startswith("A1", na=False)]
    if a1_df.empty:
        return {"present": False, "segments": []}

    segments = _segment_correlations(a1_df)
    has_subsegments = any(
        segment["segment_id"] != "A1" for segment in segments
    )
    return {
        "present": True,
        "has_subsegments": has_subsegments,
        "segments": segments,
    }


def build_report(df: pd.DataFrame, bins_path: Path) -> dict[str, object]:
    segment_correlations = _segment_correlations(df)
    window_correlations = _window_correlations(df)
    divergence_windows = _divergence_windows(df)
    a1 = _a1_breakdown(df)
    report = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "bins_path": str(bins_path),
        "row_count": int(df.shape[0]),
        "segment_correlations": segment_correlations,
        "window_correlations": window_correlations,
        "divergence_windows": divergence_windows,
        "a1_summary": a1,
    }
    return report


def validate_report(report: dict[str, object]) -> None:
    required_keys = {
        "generated_at",
        "bins_path",
        "segment_correlations",
        "window_correlations",
        "divergence_windows",
    }
    missing = required_keys - report.keys()
    if missing:
        raise ValueError(f"Report missing required keys: {missing}")
    if not report["segment_correlations"]:
        raise ValueError("Segment correlations are empty.")
    if not report["window_correlations"]:
        raise ValueError("Window correlations are empty.")


def write_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segments = report["segment_correlations"]
    windows = report["window_correlations"]
    divergence = report["divergence_windows"]
    a1 = report.get("a1_summary", {})

    lines = [
        "# LOS Density vs Rate Analysis",
        "",
        f"Generated: {report['generated_at']}",
        f"Bins source: `{report['bins_path']}`",
        "",
        "## Segment Correlations",
        "",
        "| Segment | Count | Corr (density, rate) |",
        "| --- | --- | --- |",
    ]
    for entry in segments:
        corr = entry["corr_density_rate"]
        corr_display = f"{corr:.4f}" if corr is not None else "n/a"
        lines.append(
            f"| {entry['segment_id']} | {entry['count']} | {corr_display} |"
        )

    lines.extend(
        [
            "",
            "## Window Correlations",
            "",
            "| Window | Start | End | Count | Corr (density, rate) |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for entry in windows:
        corr = entry["corr_density_rate"]
        corr_display = f"{corr:.4f}" if corr is not None else "n/a"
        lines.append(
            "| {window_idx} | {t_start} | {t_end} | {count} | {corr} |".format(
                window_idx=entry["window_idx"],
                t_start=entry["t_start"],
                t_end=entry["t_end"],
                count=entry["count"],
                corr=corr_display,
            )
        )

    lines.extend(
        [
            "",
            "## Divergence Windows",
            "",
            "### High density + low rate",
        ]
    )
    if divergence["high_density_low_rate"]:
        for entry in divergence["high_density_low_rate"]:
            lines.append(
                "- Window {window_idx} ({t_start}–{t_end}): mean density {mean_density:.4f}, "
                "mean rate {mean_rate:.4f} ({count} bins)".format(**entry)
            )
    else:
        lines.append("- None detected.")

    lines.extend(["", "### High rate + moderate density"])
    if divergence["high_rate_moderate_density"]:
        for entry in divergence["high_rate_moderate_density"]:
            lines.append(
                "- Window {window_idx} ({t_start}–{t_end}): mean density {mean_density:.4f}, "
                "mean rate {mean_rate:.4f} ({count} bins)".format(**entry)
            )
    else:
        lines.append("- None detected.")

    lines.extend(["", "## A1 Coverage"])
    if not a1.get("present"):
        lines.append("- A1 not present in bins.")
    else:
        lines.append(
            f"- A1 segments detected (subsegments present: {a1.get('has_subsegments')})."
        )
        for entry in a1.get("segments", []):
            corr = entry["corr_density_rate"]
            corr_display = f"{corr:.4f}" if corr is not None else "n/a"
            lines.append(
                f"  - {entry['segment_id']}: corr {corr_display} (n={entry['count']})"
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze density vs rate correlations from bins.parquet."
    )
    parser.add_argument(
        "--bins",
        type=Path,
        default=Path(
            "codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/bins/bins.parquet"
        ),
        help="Path to bins.parquet",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("codex/Issue 640 LOS/los_density_rate_analysis.json"),
        help="Output JSON report path",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("codex/Issue 640 LOS/los_density_rate_analysis.md"),
        help="Output Markdown report path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.bins)
    report = build_report(df, args.bins)
    validate_report(report)
    write_report(report, args.output)
    write_markdown(report, args.output_md)


if __name__ == "__main__":
    main()
