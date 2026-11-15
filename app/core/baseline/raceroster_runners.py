"""
Convert Race Roster results Excel exports into analysis runner CSV files.

Chip time is required for pace and start_offset; rows without Chip Time are skipped.
Issue #957: in-app import anonymizes bibs and maps sheets to the active event catalog.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd

from app.utils.constants import ACTIVE_EVENT_IDS, EVENT_LONG_LABELS, RACE_EVENTS
from app.utils.run_id import generate_unique_runner_ids

# (Excel sheet name, event id, distance km, output filename) — legacy CLI defaults
DEFAULT_SHEET_EVENTS: Tuple[Tuple[str, str, float, str], ...] = (
    ("5K Elite", "elite", 5.0, "elite_runners.csv"),
    ("5K Open", "open", 5.0, "open_runners.csv"),
    ("10K", "10k", 10.0, "10k_runners.csv"),
    ("Half Marathon", "half", 21.1, "half_runners.csv"),
    ("Full Marathon", "full", 42.2, "full_runners.csv"),
)

REQUIRED_RESULT_COLUMNS = ("Chip Time", "Gun Time", "No.")

# Active-catalog distances in km for pace (Issue #957)
EVENT_DISTANCE_KM: Dict[str, float] = {
    "5k": 5.0,
    "10k": 10.0,
    "half": 21.1,
    "full": 42.2,
}

WorkbookSource = Union[Path, bytes, BytesIO]


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


def active_event_choices() -> List[Dict[str, Any]]:
    """Events offered in the Race Roster sheet mapper (no legacy Elite/Open)."""
    rows: List[Dict[str, Any]] = []
    for event in RACE_EVENTS:
        if event.get("legacy"):
            continue
        eid = event["id"]
        rows.append(
            {
                "id": eid,
                "label": event["label"],
                "long_label": event["long_label"],
                "distance_km": EVENT_DISTANCE_KM.get(eid),
            }
        )
    return rows


def distance_km_for_event(event_id: str) -> float:
    key = str(event_id or "").strip().lower()
    if key not in EVENT_DISTANCE_KM:
        raise ValueError(
            f"Unknown or inactive event '{event_id}'; "
            f"allowed: {', '.join(ACTIVE_EVENT_IDS)}"
        )
    return float(EVENT_DISTANCE_KM[key])


def suggest_event_for_sheet(sheet_name: str) -> Optional[str]:
    """
    Suggest an active event id from a Race Roster sheet title.

    Legacy sheet names (5K Elite / 5K Open) map to ``5k``.
    """
    text = str(sheet_name or "").strip().lower()
    if not text:
        return None
    # Exact id / label / long label
    for event in RACE_EVENTS:
        eid = event["id"]
        if event.get("legacy"):
            continue
        candidates = {
            eid.lower(),
            str(event.get("label") or "").lower(),
            str(event.get("long_label") or "").lower(),
        }
        if text in candidates:
            return eid
    # Legacy sheet titles → active 5k
    if "5k" in text or text in {"5 k", "5 kilometre", "5 kilometer"}:
        return "5k"
    if "half" in text:
        return "half"
    if "full" in text or "marathon" in text:
        # Prefer full when both "marathon" and not half
        if "half" not in text:
            return "full"
    if "10k" in text or text in {"10 k", "10 kilometre", "10 kilometer"}:
        return "10k"
    return None


def build_event_runners_from_results_df(
    df: pd.DataFrame,
    event_name: str,
    distance_km: float,
    *,
    anonymize: bool = False,
    used_runner_ids: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Build one runner CSV dataframe from a results sheet.

    Returns ``(runners_df, skipped_no_chip_count)``.
    When ``anonymize`` is True, bib numbers are replaced with random Base62 ids.
    """
    missing = [col for col in REQUIRED_RESULT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    work = df.copy()
    work["chip_seconds"] = work["Chip Time"].map(parse_time_to_seconds)
    work["gun_seconds"] = work["Gun Time"].map(parse_time_to_seconds)
    # Chip-only rule: both Gun Time and Chip Time required
    before = len(work)
    work = work.dropna(subset=["chip_seconds", "gun_seconds"])
    skipped = before - len(work)
    if work.empty:
        raise ValueError(f"No finishers with valid Gun/Chip times for {event_name}")

    work["start_offset"] = (
        (work["gun_seconds"] - work["chip_seconds"]).round().astype(int)
    )
    work["start_offset"] = work["start_offset"].clip(lower=0)
    work["pace"] = (work["chip_seconds"] / 60.0) / distance_km
    if anonymize:
        used = used_runner_ids if used_runner_ids is not None else set()
        ids = generate_unique_runner_ids(len(work), used_ids=used)
        work["runner_id"] = ids
        used.update(ids)
    else:
        work["runner_id"] = work["No."].astype(int).astype(str)
    work["event"] = event_name
    if float(distance_km).is_integer():
        work["distance"] = int(distance_km)
    else:
        work["distance"] = distance_km

    out = work[["event", "runner_id", "pace", "distance", "start_offset"]].copy()
    out = out.sort_values(["pace", "runner_id"], kind="stable").reset_index(drop=True)
    return out, int(skipped)


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


def _open_workbook(source: WorkbookSource) -> pd.ExcelFile:
    if isinstance(source, (bytes, bytearray)):
        return pd.ExcelFile(BytesIO(source))
    if isinstance(source, BytesIO):
        source.seek(0)
        return pd.ExcelFile(source)
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Workbook not found: {path}")
    return pd.ExcelFile(path)


def list_workbook_sheets(source: WorkbookSource) -> List[Dict[str, Any]]:
    """List sheet names with suggested active event ids (does not read row data)."""
    with _open_workbook(source) as book:
        sheets = list(book.sheet_names)
    return [
        {
            "sheet": name,
            "suggested_event": suggest_event_for_sheet(name),
            "long_label": EVENT_LONG_LABELS.get(
                suggest_event_for_sheet(name) or "", ""
            ),
        }
        for name in sheets
    ]


def _event_preview_stats(df: pd.DataFrame) -> Dict[str, Any]:
    from app.core.baseline.calculator import calculate_baseline_metrics

    metrics = calculate_baseline_metrics(df)
    start_offsets = df["start_offset"].astype(int)
    return {
        "participants": int(len(df)),
        "p00": float(metrics["base_p00"]),
        "p05": float(metrics["base_p05"]),
        "p25": float(metrics["base_p25"]),
        "p50": float(metrics["base_p50"]),
        "p75": float(metrics["base_p75"]),
        "p95": float(metrics["base_p95"]),
        "p100": float(metrics["base_p100"]),
        "start_offset_min": int(start_offsets.min()),
        "start_offset_max": int(start_offsets.max()),
    }


def convert_raceroster_workbook(
    source: WorkbookSource,
    sheet_event_map: Mapping[str, str],
    *,
    anonymize: bool = True,
    used_runner_ids: Optional[set[str]] = None,
    source_filenames: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Convert mapped sheets into runner frames (in memory).

    ``sheet_event_map`` maps sheet name → active event id. Sheets mapped to
    empty / skipped are ignored. Duplicate event targets raise.
    """
    if not sheet_event_map:
        raise ValueError("sheet_event_map is required")

    used = used_runner_ids if used_runner_ids is not None else set()
    frames: Dict[str, pd.DataFrame] = {}
    skipped_by_event: Dict[str, int] = {}
    sheet_map_used: Dict[str, str] = {}

    with _open_workbook(source) as book:
        available = set(book.sheet_names)
        mapped_missing = [
            name
            for name, event_raw in sheet_event_map.items()
            if str(event_raw or "").strip() and name not in available
        ]
        # Allow multi-workbook imports: only require sheets that exist here.
        # If none of the mapped sheets are present, raise.
        present_mapped = [
            name
            for name, event_raw in sheet_event_map.items()
            if str(event_raw or "").strip() and name in available
        ]
        # Multi-workbook imports may pass a combined map; skip books with no
        # overlapping sheets. Callers raise if nothing is produced overall.
        if not present_mapped:
            if mapped_missing and not any(
                str(event_raw or "").strip() and name in available
                for name, event_raw in sheet_event_map.items()
            ):
                # Helpful error when every mapped sheet is absent from this book
                # and this looks like a single-workbook call (all maps missing).
                nonempty = [
                    name
                    for name, event_raw in sheet_event_map.items()
                    if str(event_raw or "").strip()
                ]
                if nonempty and set(nonempty) <= set(mapped_missing):
                    raise ValueError(
                        f"Sheet not found in workbook: {mapped_missing[0]!r}"
                    )
            return {
                "frames": {},
                "uploads": [],
                "preview": {},
                "provenance": {
                    "source": "raceroster",
                    "anonymized": bool(anonymize),
                    "source_filenames": [str(n) for n in (source_filenames or []) if n],
                    "sheet_event_map": {},
                    "skipped_by_event": {},
                },
                "events": [],
            }
        for sheet_name in present_mapped:
            event_id = str(sheet_event_map[sheet_name] or "").strip().lower()
            if event_id not in ACTIVE_EVENT_IDS:
                raise ValueError(
                    f"Event '{event_id}' is not in the active catalog "
                    f"({', '.join(ACTIVE_EVENT_IDS)})"
                )
            if event_id in frames:
                raise ValueError(
                    f"Event '{event_id}' is mapped more than once "
                    f"(already from sheet {sheet_map_used.get(event_id)!r})"
                )
            distance_km = distance_km_for_event(event_id)
            raw = pd.read_excel(book, sheet_name=sheet_name)
            runners, skipped = build_event_runners_from_results_df(
                raw,
                event_id,
                distance_km,
                anonymize=anonymize,
                used_runner_ids=used,
            )
            frames[event_id] = runners
            skipped_by_event[event_id] = skipped
            sheet_map_used[sheet_name] = event_id

    if not frames:
        raise ValueError("No sheets mapped to events")

    previews: Dict[str, Any] = {}
    for event_id, df in frames.items():
        previews[event_id] = {
            **_event_preview_stats(df),
            "skipped_no_chip": skipped_by_event.get(event_id, 0),
            "sheet": next(
                (s for s, e in sheet_map_used.items() if e == event_id), None
            ),
        }

    uploads: List[Tuple[str, bytes]] = []
    for event_id, df in frames.items():
        filename = f"{event_id}_runners.csv"
        uploads.append((filename, df.to_csv(index=False).encode("utf-8")))

    provenance = {
        "source": "raceroster",
        "anonymized": bool(anonymize),
        "source_filenames": [str(n) for n in (source_filenames or []) if n],
        "sheet_event_map": dict(sheet_map_used),
        "skipped_by_event": dict(skipped_by_event),
    }
    return {
        "frames": frames,
        "uploads": uploads,
        "preview": previews,
        "provenance": provenance,
        "events": list(frames.keys()),
    }


def export_raceroster_runner_csvs(
    xlsx_path: Path,
    out_dir: Path,
    *,
    event_ids: Optional[Sequence[str]] = None,
    sheet_events: Sequence[Tuple[str, str, float, str]] = DEFAULT_SHEET_EVENTS,
    anonymize: bool = False,
    used_runner_ids: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Read a Race Roster workbook and write ``{event}_runners.csv`` files.

    Returns summary rows: sheet, event, filename, runner_count, skipped_no_chip.
    Pass ``anonymize=True`` (or CLI ``--anonymize``) to replace bibs with random ids.
    """
    xlsx_path = Path(xlsx_path)
    out_dir = Path(out_dir)
    if not xlsx_path.is_file():
        raise FileNotFoundError(f"Workbook not found: {xlsx_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = filter_sheet_events(event_ids, sheet_events)
    summaries: List[Dict[str, Any]] = []
    used = used_runner_ids if used_runner_ids is not None else set()

    for sheet_name, event_name, distance_km, filename in specs:
        raw = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        runners, skipped = build_event_runners_from_results_df(
            raw,
            event_name,
            distance_km,
            anonymize=anonymize,
            used_runner_ids=used,
        )
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
                "anonymized": bool(anonymize),
            }
        )
    return summaries
