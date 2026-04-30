"""
Runflow v2 Timings Module

Computes predicted timings (first/last finishers, durations) from runner data.
Uses vectorized pandas operations for efficient computation across thousands of runners.

Issue #638: Correct implementation of predicted_timings using runner finish times
instead of bin window timestamps.

Issue #743: Finish-time waves CSV aggregates runner finish_time_sec into 20-minute blocks.

Core Principles:
- Compute finish times directly from runner data (pace, distance, start_offset)
- Use vectorized operations (NO loops over runners)
- Use Event.start_time as primary source, analysis_config for fallback durations
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import csv
import math
import pandas as pd
import logging

from app.core.v2.models import Event

logger = logging.getLogger(__name__)

_FINISH_BUCKET_SECONDS = 20 * 60


def finish_bucket_start_sec(finish_time_sec: float) -> int:
    """
    Map finish time (seconds since naive midnight) to the start of its 20-minute clock bucket.

    Buckets align within each hour: [0,19:59], [20:00,39:59], [40:00,59:59].
    Boundary rule (half-open): finish at exactly HH:20:00 belongs to the second block.
    """
    s = max(0, int(math.floor(float(finish_time_sec))))
    hour_start = (s // 3600) * 3600
    offset_in_hour = s % 3600
    slot = offset_in_hour // _FINISH_BUCKET_SECONDS  # 0, 1, or 2
    return hour_start + slot * _FINISH_BUCKET_SECONDS


def _format_seconds_to_hhmmss(seconds_from_midnight: float) -> str:
    """Format seconds from midnight to HH:MM:SS (supports hour >= 24 if needed)."""
    try:
        total_seconds = max(0, int(float(seconds_from_midnight)))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "00:00:00"


def build_runner_finish_times_df(
    *,
    events: List[Event],
    analysis_config: Dict[str, Any],
    runners_df: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """
    One row per runner with predicted finish_time_sec (seconds since naive midnight).

    Issue #743: Same formula as compute_predicted_timings — gun/start + offset + pace * distance.
    Events with no runner rows do not appear in the frame (handled upstream for aggregates).

    Returns:
        DataFrame with columns runner_id, event (lowercase), finish_time_sec; or None if unusable input.
        Empty DataFrame if no runners could be scored (caller may treat like no data).
    """
    required_columns = ["runner_id", "event", "pace", "distance"]
    optional_warn = ["start_offset"]
    missing_required = [col for col in required_columns if col not in runners_df.columns]
    missing_optional = [col for col in optional_warn if col not in runners_df.columns]
    if missing_required:
        logger.warning(
            "Issue #743: Missing columns for finish times: %s (have %s)",
            missing_required,
            list(runners_df.columns),
        )
        if runners_df.empty or "pace" not in runners_df.columns or "distance" not in runners_df.columns:
            return None
    elif missing_optional:
        logger.debug(
            "Issue #743: Optional columns missing for finish times: %s",
            missing_optional,
        )

    work = runners_df.copy()
    if "event" in work.columns:
        work["event"] = work["event"].astype(str).str.lower()

    frames: List[pd.DataFrame] = []
    for event in events:
        event_name = event.name.lower()
        event_start_min = event.start_time
        event_runners = work[work["event"] == event_name].copy()
        if event_runners.empty:
            continue
        if "pace" not in event_runners.columns or "distance" not in event_runners.columns:
            logger.warning("Issue #743: Missing pace or distance for event %s", event_name)
            continue

        event_runners["pace_sec_per_km"] = event_runners["pace"] * 60.0
        if "start_offset" in event_runners.columns:
            event_runners["start_offset_sec"] = event_runners["start_offset"].fillna(0).astype(float)
        else:
            event_runners["start_offset_sec"] = 0.0
        event_runners["runner_start_sec"] = (event_start_min * 60.0) + event_runners["start_offset_sec"]
        event_runners["finish_time_sec"] = (
            event_runners["runner_start_sec"]
            + (event_runners["pace_sec_per_km"] * event_runners["distance"])
        )
        frames.append(event_runners[["runner_id", "event", "finish_time_sec"]])

    if not frames:
        return pd.DataFrame(columns=["runner_id", "event", "finish_time_sec"])
    return pd.concat(frames, ignore_index=True)


def write_finish_times_csv(output_path: Path, day_code: str, finish_df: pd.DataFrame) -> bool:
    """
    Issue #743: Aggregate predicted finishes into 20-minute waves; non-zero rows only plus ``all``.

    Inserts a blank line between consecutive buckets when the clock hour changes (Excel-friendly).

    Returns:
        True if file was written with at least one data row; False if nothing to emit.
    """
    if finish_df is None or finish_df.empty:
        return False

    bucket_col = finish_df["finish_time_sec"].map(finish_bucket_start_sec)
    tmp = finish_df.assign(_bucket=bucket_col)

    grouped = tmp.groupby(["_bucket", "event"], observed=False).size().reset_index(name="count")
    grouped = grouped[grouped["count"] > 0].sort_values(["_bucket", "event"])

    if grouped.empty:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    prev_hour: Optional[int] = None
    rows_written = 0
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["day", "time_window_start", "time_window_end", "event", "count"])

        for bucket_start in sorted(grouped["_bucket"].unique()):
            chunk = grouped[grouped["_bucket"] == bucket_start]
            hour = bucket_start // 3600
            if prev_hour is not None and hour != prev_hour:
                writer.writerow([])
            prev_hour = hour

            window_start_str = _format_seconds_to_hhmmss(bucket_start)
            window_end_str = _format_seconds_to_hhmmss(bucket_start + _FINISH_BUCKET_SECONDS - 1)

            total = int(chunk["count"].sum())
            for _, row in chunk.sort_values("event").iterrows():
                writer.writerow([day_code, window_start_str, window_end_str, row["event"], int(row["count"])])
                rows_written += 1
            writer.writerow([day_code, window_start_str, window_end_str, "all", total])
            rows_written += 1

    logger.info(
        "Issue #743: Wrote finish_times.csv (%s rows incl. all): %s",
        rows_written,
        output_path,
    )
    return True


def _format_seconds_to_hhmm(seconds_from_midnight: float) -> str:
    """
    Format seconds from midnight to HH:MM string.
    
    Args:
        seconds_from_midnight: Seconds elapsed since midnight (0-86400)
        
    Returns:
        Time string in HH:MM format (e.g., "07:30")
    """
    try:
        total_seconds = int(float(seconds_from_midnight))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to format seconds {seconds_from_midnight} to HH:MM: {e}")
        return "00:00"


def compute_predicted_timings(
    *,
    events: List[Event],
    analysis_config: Dict[str, Any],
    runners_df: pd.DataFrame
) -> Optional[Dict[str, Any]]:
    """
    Compute predicted_timings dict from runner data using vectorized operations.
    
    Issue #638: Correct implementation using runner finish times instead of bin windows.
    
    Args:
        events: List of Event objects for the day
        analysis_config: Analysis configuration dict (for event_duration_minutes fallback)
        runners_df: DataFrame with columns: runner_id, event, pace, distance, start_offset
        
    Returns:
        Dictionary with predicted_timings structure, or None if computation fails
        Structure:
        {
            "day_start": "HH:MM",
            "event_first_finisher": {"event_name": "HH:MM", ...},
            "day_first_finisher": "HH:MM",
            "event_last_finisher": {"event_name": "HH:MM", ...},
            "day_last_finisher": "HH:MM",
            "day_end": "HH:MM",
            "actual_event_duration": {"event_name": "HH:MM", ...},  # last_finisher − event start (gun)
            "day_duration": "HH:MM"
        }
    """
    try:
        # Build lookup from Event objects (primary source for start times)
        event_start_times = {event.name.lower(): event.start_time for event in events}

        # Build lookup from analysis_config for fallback durations
        event_durations = {}
        if analysis_config and "events" in analysis_config:
            for event_data in analysis_config["events"]:
                if isinstance(event_data, dict):
                    event_name = event_data.get("name", "").lower()
                    if event_name and "event_duration_minutes" in event_data:
                        event_durations[event_name] = event_data["event_duration_minutes"]

        finish_df = build_runner_finish_times_df(
            events=events,
            analysis_config=analysis_config,
            runners_df=runners_df,
        )
        if finish_df is None:
            return None

        event_first_finisher = {}
        event_last_finisher = {}
        actual_event_duration = {}

        for event in events:
            event_name = event.name.lower()
            event_start_min = event.start_time  # minutes after midnight

            sub = finish_df[finish_df["event"] == event_name] if not finish_df.empty else pd.DataFrame()

            if sub.empty:
                if event_name in event_durations:
                    duration_minutes = event_durations[event_name]
                    event_last_min = event_start_min + duration_minutes
                    event_last_finisher[event_name] = _format_seconds_to_hhmm(event_last_min * 60)
                    actual_event_duration[event_name] = _format_seconds_to_hhmm(duration_minutes * 60)
                    logger.debug(
                        "Issue #638: No runners for event %s, using fallback duration",
                        event_name,
                    )
                else:
                    logger.debug(
                        "Issue #638: No runners and no duration fallback for event %s",
                        event_name,
                    )
                continue

            event_first_sec = sub["finish_time_sec"].min()
            event_last_sec = sub["finish_time_sec"].max()

            event_first_finisher[event_name] = _format_seconds_to_hhmm(event_first_sec)
            event_last_finisher[event_name] = _format_seconds_to_hhmm(event_last_sec)

            event_start_sec = float(event_start_min) * 60.0
            duration_sec = float(event_last_sec) - event_start_sec
            if duration_sec < 0:
                logger.warning(
                    "Issue #638: Negative event duration for %s (last before start); clamping to 0",
                    event_name,
                )
                duration_sec = 0.0
            actual_event_duration[event_name] = _format_seconds_to_hhmm(duration_sec)

            logger.debug(
                "Issue #638: Computed timings for event %s: first=%s, last=%s, duration(last-start)=%s",
                event_name,
                event_first_finisher[event_name],
                event_last_finisher[event_name],
                actual_event_duration[event_name],
            )
        
        # Day-level aggregation
        # day_start = min(event start times)
        day_start_min = min(event_start_times.values()) if event_start_times else None
        if day_start_min is None:
            logger.warning("Issue #638: No event start times available, cannot compute day_start")
            return None
        
        day_start_str = _format_seconds_to_hhmm(day_start_min * 60)
        
        # day_first_finisher = min(all event_first values that exist)
        # day_last_finisher = max(all event_last values that exist)
        if event_first_finisher:
            # Convert HH:MM strings back to seconds for comparison
            def hhmm_to_seconds(hhmm_str: str) -> float:
                try:
                    parts = hhmm_str.split(':')
                    return int(parts[0]) * 3600 + int(parts[1]) * 60
                except (ValueError, IndexError):
                    return 0.0
            
            day_first_sec = min(hhmm_to_seconds(v) for v in event_first_finisher.values())
            day_last_sec = max(hhmm_to_seconds(v) for v in event_last_finisher.values())
            
            day_first_finisher_str = _format_seconds_to_hhmm(day_first_sec)
            day_last_finisher_str = _format_seconds_to_hhmm(day_last_sec)
        else:
            # Fallback: use event durations if no runners
            if event_durations and event_start_times:
                # Compute day_last from start_time + duration for each event
                day_last_min = max(
                    event_start_times.get(event_name, 0) + event_durations.get(event_name, 0)
                    for event_name in event_start_times.keys()
                    if event_name in event_durations
                )
                day_last_finisher_str = _format_seconds_to_hhmm(day_last_min * 60)
                # Set day_first to day_start as fallback
                day_first_finisher_str = day_start_str
            else:
                logger.warning("Issue #638: No event finishers and no duration fallback available")
                return None
        
        day_end_str = day_last_finisher_str  # day_end = day_last_finisher
        
        # day_duration = day_end - day_start
        def hhmm_to_seconds(hhmm_str: str) -> float:
            try:
                parts = hhmm_str.split(':')
                return int(parts[0]) * 3600 + int(parts[1]) * 60
            except (ValueError, IndexError):
                return 0.0
        
        day_duration_sec = hhmm_to_seconds(day_end_str) - hhmm_to_seconds(day_start_str)
        day_duration_str = _format_seconds_to_hhmm(day_duration_sec)
        
        # Build predicted_timings structure
        predicted_timings = {
            "day_start": day_start_str,
            "event_first_finisher": event_first_finisher,
            "day_first_finisher": day_first_finisher_str,
            "event_last_finisher": event_last_finisher,
            "day_last_finisher": day_last_finisher_str,
            "day_end": day_end_str,
            "actual_event_duration": actual_event_duration,
            "day_duration": day_duration_str
        }
        
        logger.info(
            f"Issue #638: Computed predicted_timings: "
            f"day_start={day_start_str}, day_first={day_first_finisher_str}, "
            f"day_last={day_last_finisher_str}, day_duration={day_duration_str}"
        )
        
        return predicted_timings
        
    except Exception as e:
        logger.error(f"Issue #638: Failed to compute predicted_timings: {e}", exc_info=True)
        return None
