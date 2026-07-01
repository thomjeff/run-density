#!/usr/bin/env python3
"""Build analysis runner CSVs from a Race Roster results Excel export."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root on sys.path when run as scripts/build_*.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.baseline.raceroster_runners import (  # noqa: E402
    DEFAULT_SHEET_EVENTS,
    export_raceroster_runner_csvs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx",
        type=Path,
        help="Race Roster results workbook (.xlsx)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for *_runners.csv output (default: current directory)",
    )
    parser.add_argument(
        "--events",
        default="",
        help="Comma-separated event ids to export (default: all FM sheets). "
        "Example: 10k,half,full",
    )
    parser.add_argument(
        "--list-sheets",
        action="store_true",
        help="List default sheet → event mappings and exit",
    )
    args = parser.parse_args()

    if args.list_sheets:
        print("Default sheet mappings:")
        for sheet, event, distance, filename in DEFAULT_SHEET_EVENTS:
            print(f"  {sheet!r} → {event} ({distance} km) → {filename}")
        return 0

    if not args.xlsx:
        parser.error("--xlsx is required unless --list-sheets is used")

    event_ids = [part.strip() for part in args.events.split(",") if part.strip()] or None
    try:
        summaries = export_raceroster_runner_csvs(
            args.xlsx,
            args.out_dir,
            event_ids=event_ids,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for row in summaries:
        skipped = row["skipped_no_chip"]
        skip_note = f", {skipped} skipped (no chip)" if skipped else ""
        print(
            f"{row['filename']}: {row['runner_count']} runners"
            f"{skip_note} ← sheet {row['sheet']!r}"
        )
    print(f"Wrote {len(summaries)} file(s) to {args.out_dir.resolve()}")
    print("Upload via Race Configuration → Runners → Install runner files → Upload CSV files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
