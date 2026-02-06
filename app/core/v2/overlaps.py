"""
Bidirectional overlap reports for Flow UI (Issue #720).

Generates per-minute counts, entries, and exits for event pairs marked
as bidirectional in flow.csv, and writes CSVs + summary metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import csv
import logging
import math

import numpy as np
import pandas as pd

from app.core.v2.models import Day, Event
from app.utils.constants import (
    REPORTS_OVERLAPS_DIRNAME,
    REPORTS_OVERLAPS_SUMMARY_FILENAME,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverlapSummary:
    seg_id: str
    seg_label: str
    event_a: str
    event_b: str
    event_a_label: str
    event_b_label: str
    from_km_a: float
    to_km_a: float
    from_km_b: float
    to_km_b: float
    overlap_start: str
    overlap_end: str
    overlap_duration_minutes: float
    peak_concurrent_a: int
    peak_concurrent_b: int
    csv_filename: str


def _require_columns(df: pd.DataFrame, columns: List[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(missing)}")


def _normalize_event_name(value: Any) -> str:
    return str(value).strip().lower()


def _format_hhmm_from_seconds(seconds_since_midnight: float) -> str:
    minutes = int(max(0, seconds_since_midnight) // 60)
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _compute_entry_exit_seconds(
    runners_df: pd.DataFrame,
    start_time_minutes: float,
    from_km: float,
    to_km: float,
) -> Tuple[np.ndarray, np.ndarray]:
    _require_columns(runners_df, ["pace", "start_offset"], "runners data")
    pace_values = pd.to_numeric(runners_df["pace"], errors="coerce")
    if pace_values.isna().any() or (pace_values <= 0).any():
        raise ValueError("runners data missing valid pace values for overlap report generation.")
    pace_sec_per_km = pace_values.to_numpy() * 60.0
    start_offset_sec = pd.to_numeric(runners_df["start_offset"], errors="coerce").fillna(0).to_numpy()
    start_time_sec = float(start_time_minutes) * 60.0
    entry_times = start_time_sec + start_offset_sec + pace_sec_per_km * float(from_km)
    exit_times = start_time_sec + start_offset_sec + pace_sec_per_km * float(to_km)
    return entry_times, exit_times


def _minute_series(
    entry_times: np.ndarray,
    exit_times: np.ndarray,
    start_sec: float,
    end_sec: float,
) -> Tuple[List[float], List[Dict[str, int]]]:
    if entry_times.size == 0 or exit_times.size == 0:
        return [], []

    entry_sorted = np.sort(entry_times)
    exit_sorted = np.sort(exit_times)

    start_floor = int(math.floor(start_sec / 60.0) * 60)
    end_ceil = int(math.ceil(end_sec / 60.0) * 60)
    if end_ceil <= start_floor:
        return [], []

    minute_starts = list(range(start_floor, end_ceil, 60))
    metrics: List[Dict[str, int]] = []

    for minute_start in minute_starts:
        minute_end = minute_start + 60
        entries = int(np.searchsorted(entry_sorted, minute_end, side="left") - np.searchsorted(entry_sorted, minute_start, side="left"))
        exits = int(np.searchsorted(exit_sorted, minute_end, side="left") - np.searchsorted(exit_sorted, minute_start, side="left"))
        concurrent = int(np.searchsorted(entry_sorted, minute_end, side="left") - np.searchsorted(exit_sorted, minute_start, side="left"))
        metrics.append({"concurrent": concurrent, "entries": entries, "exits": exits})

    return [float(s) for s in minute_starts], metrics


def _write_overlap_csv(
    output_dir: Path,
    seg_id: str,
    event_a: str,
    event_b: str,
    event_a_label: str,
    event_b_label: str,
    minute_starts: List[float],
    metrics_a: List[Dict[str, int]],
    metrics_b: List[Dict[str, int]],
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_filename = f"{seg_id}_per_minute.csv"
    csv_path = output_dir / csv_filename

    headers = [
        "minute_start",
        "minute_end",
        f"{event_a_label}_count",
        f"{event_a_label}_entries",
        f"{event_a_label}_exits",
        f"{event_b_label}_count",
        f"{event_b_label}_entries",
        f"{event_b_label}_exits",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for idx, minute_start in enumerate(minute_starts):
            minute_end = minute_start + 60
            row = [
                _format_hhmm_from_seconds(minute_start),
                _format_hhmm_from_seconds(minute_end),
                metrics_a[idx]["concurrent"],
                metrics_a[idx]["entries"],
                metrics_a[idx]["exits"],
                metrics_b[idx]["concurrent"],
                metrics_b[idx]["entries"],
                metrics_b[idx]["exits"],
            ]
            writer.writerow(row)

    return csv_filename


def generate_bidirectional_overlap_reports(
    *,
    run_id: str,
    day: Day,
    day_events: List[Event],
    analysis_context: Any,
    all_runners_df: pd.DataFrame,
    reports_dir: Path,
    segments_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Generate per-minute overlap CSVs and a summary JSON for bidirectional segments.
    """
    if analysis_context is None:
        raise ValueError("analysis_context is required for overlap report generation.")

    flow_df = analysis_context.get_flow_df()
    _require_columns(
        flow_df,
        ["seg_id", "event_a", "event_b", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "direction"],
        "flow.csv",
    )
    _require_columns(all_runners_df, ["event", "pace", "start_offset"], "runners data")

    day_event_names = {event.name.lower() for event in day_events}
    flow_df = flow_df.copy()
    flow_df["event_a_norm"] = flow_df["event_a"].map(_normalize_event_name)
    flow_df["event_b_norm"] = flow_df["event_b"].map(_normalize_event_name)
    flow_df["direction_norm"] = flow_df["direction"].astype(str).str.strip().str.lower()

    eligible = flow_df[
        flow_df["event_a_norm"].isin(day_event_names)
        & flow_df["event_b_norm"].isin(day_event_names)
        & (flow_df["direction_norm"] == "bi")
    ].copy()

    analyzed_count = int(len(eligible))
    overlap_count = 0
    summaries: List[OverlapSummary] = []

    start_times = {event.name.lower(): float(event.start_time) for event in day_events}
    overlaps_dir = reports_dir / REPORTS_OVERLAPS_DIRNAME

    for _, row in eligible.iterrows():
        seg_id = str(row["seg_id"])
        event_a = str(row["event_a_norm"])
        event_b = str(row["event_b_norm"])
        event_a_label = event_a
        event_b_label = event_b
        if event_a == event_b:
            event_a_label = f"{event_a}_a"
            event_b_label = f"{event_b}_b"

        if event_a not in start_times or event_b not in start_times:
            raise ValueError(f"Missing start_time for event pair {event_a}/{event_b} in day {day.value}.")

        runners_a = all_runners_df[all_runners_df["event"].astype(str).str.lower() == event_a]
        runners_b = all_runners_df[all_runners_df["event"].astype(str).str.lower() == event_b]
        if runners_a.empty or runners_b.empty:
            continue

        from_km_a = float(row["from_km_a"])
        to_km_a = float(row["to_km_a"])
        from_km_b = float(row["from_km_b"])
        to_km_b = float(row["to_km_b"])

        entry_a, exit_a = _compute_entry_exit_seconds(runners_a, start_times[event_a], from_km_a, to_km_a)
        entry_b, exit_b = _compute_entry_exit_seconds(runners_b, start_times[event_b], from_km_b, to_km_b)
        if entry_a.size == 0 or entry_b.size == 0:
            continue

        overlap_start = max(float(entry_a.min()), float(entry_b.min()))
        overlap_end = min(float(exit_a.max()), float(exit_b.max()))
        if overlap_end <= overlap_start:
            continue

        overlap_count += 1

        time_start = min(float(entry_a.min()), float(entry_b.min()))
        time_end = max(float(exit_a.max()), float(exit_b.max()))
        minute_starts, metrics_a = _minute_series(entry_a, exit_a, time_start, time_end)
        _, metrics_b = _minute_series(entry_b, exit_b, time_start, time_end)

        csv_filename = _write_overlap_csv(
            overlaps_dir,
            seg_id,
            event_a,
            event_b,
            event_a_label,
            event_b_label,
            minute_starts,
            metrics_a,
            metrics_b,
        )

        seg_label = str(row.get("seg_label") or "")
        if not seg_label and segments_df is not None and "seg_label" in segments_df.columns:
            seg_match = segments_df[segments_df["seg_id"] == seg_id]
            if not seg_match.empty:
                seg_label = str(seg_match.iloc[0].get("seg_label", ""))

        summaries.append(
            OverlapSummary(
                seg_id=seg_id,
                seg_label=seg_label,
                event_a=event_a,
                event_b=event_b,
                event_a_label=event_a_label,
                event_b_label=event_b_label,
                from_km_a=from_km_a,
                to_km_a=to_km_a,
                from_km_b=from_km_b,
                to_km_b=to_km_b,
                overlap_start=_format_hhmm_from_seconds(overlap_start),
                overlap_end=_format_hhmm_from_seconds(overlap_end),
                overlap_duration_minutes=round((overlap_end - overlap_start) / 60.0, 2),
                peak_concurrent_a=max(m["concurrent"] for m in metrics_a) if metrics_a else 0,
                peak_concurrent_b=max(m["concurrent"] for m in metrics_b) if metrics_b else 0,
                csv_filename=csv_filename,
            )
        )

    summary_payload = {
        "run_id": run_id,
        "day": day.value,
        "analyzed_count": analyzed_count,
        "overlap_count": overlap_count,
        "segments": [summary.__dict__ for summary in summaries],
    }

    overlaps_dir.mkdir(parents=True, exist_ok=True)
    summary_path = overlaps_dir / REPORTS_OVERLAPS_SUMMARY_FILENAME
    summary_path.write_text(
        json_dumps(summary_payload),
        encoding="utf-8",
    )

    logger.info(
        f"✅ Bidirectional overlap reports generated for day {day.value}: "
        f"{overlap_count}/{analyzed_count} segments with overlap"
    )
    return summary_payload


def json_dumps(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2)
