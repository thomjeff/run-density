"""
Shared runner CSV filename and uniqueness helpers.

Issue #879 / #852: one-CSV-per-event files named ``{event}_runners.csv``.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd

from app.core.baseline.validation import validate_runner_csv_bytes
from app.core.v2.validation import ValidationError, assert_unique_runner_ids
from app.utils.constants import COURSE_EVENT_IDS

RUNNERS_FILENAME_SUFFIX = "_runners.csv"


def event_id_from_runners_filename(filename: str) -> str:
    """Parse ``{event}_runners.csv`` into a known event id."""
    name = Path(str(filename or "")).name
    if not name:
        raise ValueError("Runner filename is required")
    lower = name.lower()
    if not lower.endswith(RUNNERS_FILENAME_SUFFIX):
        raise ValueError(
            f"Runner file must be named {{event}}{RUNNERS_FILENAME_SUFFIX} (got {name})"
        )
    event = lower[: -len(RUNNERS_FILENAME_SUFFIX)]
    allowed = {e.lower() for e in COURSE_EVENT_IDS}
    if event not in allowed:
        raise ValueError(
            f"Unknown event '{event}' in {name}; allowed: {', '.join(sorted(allowed))}"
        )
    return event


def _raise_uniqueness(exc: ValidationError) -> None:
    raise ValueError(exc.message) from exc


def validate_runner_csv_set(
    uploads: Sequence[Tuple[str, bytes]],
) -> Tuple[Dict[str, bytes], List[Tuple[str, pd.DataFrame]], Dict[str, str]]:
    """
    Validate each CSV and cross-file ``runner_id`` uniqueness.

    Returns (event -> csv bytes, event frames, event -> filename).
    Does not write files. A duplicate ``runner_id`` across events fails.
    """
    if not uploads:
        raise ValueError("At least one runner CSV is required")

    by_event: Dict[str, bytes] = {}
    frames: List[Tuple[str, pd.DataFrame]] = []
    file_names: Dict[str, str] = {}

    for raw_name, data in uploads:
        filename = Path(str(raw_name or "")).name
        event = event_id_from_runners_filename(filename)
        if event in by_event:
            raise ValueError(f"Duplicate runner file for event '{event}'")
        validate_runner_csv_bytes(data, filename)
        df = pd.read_csv(BytesIO(data), dtype={"runner_id": "string"})
        events_in_file = {
            str(v).strip().lower()
            for v in df["event"].dropna().unique()
            if str(v).strip()
        }
        if not events_in_file:
            raise ValueError(f"{filename}: event column is empty")
        unexpected = events_in_file - {event}
        if unexpected:
            raise ValueError(
                f"{filename}: event column must be '{event}' "
                f"(found {', '.join(sorted(unexpected))})"
            )
        by_event[event] = data
        frames.append((event, df))
        file_names[event] = filename

    try:
        assert_unique_runner_ids(frames, file_names=file_names)
    except ValidationError as exc:
        _raise_uniqueness(exc)

    return by_event, frames, file_names


def ordered_dataset_events(events: Sequence[str]) -> List[str]:
    """Stable event order from COURSE_EVENT_IDS, then any extras."""
    found = {str(e).strip().lower() for e in events if str(e).strip()}
    ordered = [e for e in COURSE_EVENT_IDS if e in found]
    extras = sorted(found - set(ordered))
    return ordered + extras


def dataset_files_map(events: Sequence[str]) -> Dict[str, str]:
    return {event: f"{event}{RUNNERS_FILENAME_SUFFIX}" for event in events}


def _quantile_float(value: Any) -> float:
    return round(float(value), 2)


def summarize_runner_frames(
    frames: Sequence[Tuple[str, pd.DataFrame]],
) -> Dict[str, Any]:
    """Participant counts and pace percentiles (min/km) per event."""
    from app.core.baseline.calculator import calculate_baseline_metrics

    summary: Dict[str, Any] = {}
    for event, df in frames:
        entry: Dict[str, Any] = {"participants": int(len(df))}
        try:
            metrics = calculate_baseline_metrics(df)
            entry["p00"] = _quantile_float(metrics["base_p00"])
            entry["p05"] = _quantile_float(metrics["base_p05"])
            entry["p25"] = _quantile_float(metrics["base_p25"])
            entry["p50"] = _quantile_float(metrics["base_p50"])
            entry["p75"] = _quantile_float(metrics["base_p75"])
            entry["p95"] = _quantile_float(metrics["base_p95"])
            entry["p100"] = _quantile_float(metrics["base_p100"])
        except (ValueError, KeyError, TypeError):
            pass
        summary[event] = entry
    return summary
