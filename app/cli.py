"""Runflow CLI (#860).

Usage:
    python -m app.cli analyze --run-id <id> --through trajectory
    python -m app.cli analyze --run-id <id> --through locations
    python -m app.cli analyze --run-id <id> --through full
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.v2.models import Day, Event
from app.core.v2.pipeline import create_full_analysis_pipeline
from app.core.v2.through import THROUGH_VALUES, normalize_through
from app.utils.run_id import get_run_directory


def _events_from_analysis(analysis: dict) -> list[Event]:
    events: list[Event] = []
    for raw in analysis.get("events") or []:
        events.append(
            Event(
                name=str(raw["name"]),
                day=Day(str(raw["day"]).lower()),
                start_time=int(raw["start_time"]),
                gpx_file=str(raw.get("gpx_file") or ""),
                runners_file=str(raw.get("runners_file") or ""),
            )
        )
    if not events:
        raise SystemExit("analysis.json has no events")
    return events


def cmd_analyze(args: argparse.Namespace) -> int:
    through = normalize_through(args.through)
    run_path = get_run_directory(args.run_id)
    analysis_path = run_path / "analysis.json"
    if not analysis_path.is_file():
        raise SystemExit(f"analysis.json not found at {analysis_path}")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    analysis["through"] = through
    analysis_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    events = _events_from_analysis(analysis)
    data_dir = analysis.get("data_dir")
    if not data_dir:
        raise SystemExit("analysis.json missing data_dir")

    result = create_full_analysis_pipeline(
        events=events,
        segments_file=analysis.get("segments_file") or "segments.csv",
        locations_file=analysis.get("locations_file"),
        flow_file=analysis.get("flow_file") or "flow.csv",
        data_dir=str(data_dir),
        run_id=args.run_id,
        request_payload=analysis,
        through=through,
    )
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "through": result.get("through"),
                "days": result.get("days"),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Runflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser(
        "analyze",
        help="Re-run an existing analysis.json with an optional staged stop-point",
    )
    analyze.add_argument("--run-id", required=True, help="Existing run directory id")
    analyze.add_argument(
        "--through",
        default="full",
        choices=sorted(THROUGH_VALUES),
        help="Stop after this stage (default: full)",
    )
    analyze.set_defaults(func=cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
