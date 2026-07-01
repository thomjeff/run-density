"""
Convert Race Roster results Excel exports into analysis runner CSV files.

Chip time is required for pace and start_offset; rows without Chip Time are skipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

# (Excel sheet name, event id, distance km, output filename)
DEFAULT_SHEET_EVENTS: Tuple[Tuple[str, str, float, str], ...] = (
    ("5K Elite", "elite", 5.0, "elite_runners.csv"),
    ("5K Open", "open", 5.0, "open_runners.csv"),
    ("10K", "10k", 10.0, "10k_runners.csv"),
    ("Half Marathon", "half", 21.1, "half_runners.csv"),
    ("Full Marathon", "full", 42.2, "full_runners.csv"),
)

REQUIRED_RESULT_COLUMNS = ("Chip Time", "Gun Time", "No.")


def parse_time_to_seconds(value: Any) -> Optional[int]:
    """Parse Race Roster Gun/Chip time strings (M:SS or H:MM:SS) to seconds."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        hours, minutes, seconds = nums
        return hours * 3600 + minutes * 60 + seconds
    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds
    if len(nums) == 1:
        return nums[0]
    return None


def build_event_runners_from_results_df(
    df: pd.DataFrame,
    event_name: str,
    distance_km: float,
) -> pd.DataFrame:
    """Build one runner CSV dataframe from a results sheet."""
    missing = [col for col in REQUIRED_RESULT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    work = df.copy()
    work["chip_seconds"] = work["Chip Time"].map(parse_time_to_seconds)
    work["gun_seconds"] = work["Gun Time"].map(parse_time_to_seconds)
    work = work.dropna(subset=["chip_seconds", "gun_seconds"])
    if work.empty:
        raise ValueError(f"No finishers with valid Gun/Chip times for {event_name}")

    work["start_offset"] = (work["gun_seconds"] - work["chip_seconds"]).round().astype(int)
    work["start_offset"] = work["start_offset"].clip(lower=0)
    work["pace"] = (work["chip_seconds"] / 60.0) / distance_km
    work["runner_id"] = work["No."].astype(int).astype(str)
    work["event"] = event_name
    if float(distance_km).is_integer():
        work["distance"] = int(distance_km)
    else:
        work["distance"] = distance_km

    out = work[["event", "runner_id", "pace", "distance", "start_offset"]].copy()
    return out.sort_values(["pace", "runner_id"], kind="stable").reset_index(drop=True)


def filter_sheet_events(
    event_ids: Optional[Sequence[str]],
    sheet_events: Sequence[Tuple[str, str, float, str]] = DEFAULT_SHEET_EVENTS,
) -> List[Tuple[str, str, float, str]]:
    """Return sheet/event specs filtered by event id (e.g. 10k, half, full)."""
    if not event_ids:
        return list(sheet_events)
    wanted = {str(eid).strip().lower() for eid in event_ids if str(eid).strip()}
    selected = [row for row in sheet_events if row[1].lower() in wanted]
    if not selected:
        known = ", ".join(row[1] for row in sheet_events)
        raise ValueError(f"No matching events (known: {known})")
    return selected


def export_raceroster_runner_csvs(
    xlsx_path: Path,
    out_dir: Path,
    *,
    event_ids: Optional[Sequence[str]] = None,
    sheet_events: Sequence[Tuple[str, str, float, str]] = DEFAULT_SHEET_EVENTS,
) -> List[Dict[str, Any]]:
    """
    Read a Race Roster workbook and write ``{event}_runners.csv`` files.

    Returns summary rows: sheet, event, filename, runner_count, skipped_no_chip.
    """
    xlsx_path = Path(xlsx_path)
    out_dir = Path(out_dir)
    if not xlsx_path.is_file():
        raise FileNotFoundError(f"Workbook not found: {xlsx_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = filter_sheet_events(event_ids, sheet_events)
    summaries: List[Dict[str, Any]] = []

    for sheet_name, event_name, distance_km, filename in specs:
        raw = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        skipped = int(
            raw["Chip Time"].isna().sum()
            if "Chip Time" in raw.columns
            else len(raw)
        )
        runners = build_event_runners_from_results_df(raw, event_name, distance_km)
        target = out_dir / filename
        runners.to_csv(target, index=False)
        summaries.append(
            {
                "sheet": sheet_name,
                "event": event_name,
                "filename": filename,
                "runner_count": len(runners),
                "skipped_no_chip": skipped,
                "path": str(target),
            }
        )
    return summaries
