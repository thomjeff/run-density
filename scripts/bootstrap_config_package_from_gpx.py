#!/usr/bin/env python3
"""Create a config package with course geometry loaded from a GPX track."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Repo root on sys.path when run as scripts/bootstrap_*.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config_package.storage import (
    create_config_package,
    load_config_course,
    save_config_course,
)
from app.core.gpx.processor import parse_gpx_file


def gpx_to_coordinates(gpx_path: Path) -> tuple[list[list[float]], str, float]:
    gpx = parse_gpx_file(str(gpx_path))
    coords: list[list[float]] = []
    for p in gpx.points:
        c = [round(p.lon, 6), round(p.lat, 6)]
        if not coords or c[0] != coords[-1][0] or c[1] != coords[-1][1]:
            coords.append(c)
    return coords, gpx.name, gpx.total_distance_km


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gpx", type=Path, help="Source GPX file")
    parser.add_argument("--label", required=True, help="Package label")
    parser.add_argument("--description", default="", help="Package description")
    parser.add_argument(
        "--copy-gpx",
        action="store_true",
        help="Copy GPX into package folder as full.gpx",
    )
    args = parser.parse_args()
    if not args.gpx.is_file():
        print(f"GPX not found: {args.gpx}", file=sys.stderr)
        return 1

    coords, track_name, km = gpx_to_coordinates(args.gpx)
    print(f"Track: {track_name!r}, {len(coords)} vertices, {km:.2f} km")

    result = create_config_package(args.label, args.description)
    config_id = result["config_id"]
    package_path = Path(result["path"])

    course = load_config_course(config_id)
    course["geometry"] = {"type": "LineString", "coordinates": coords}
    course["segment_breaks"] = []
    course["segment_break_labels"] = {}
    course["segment_break_descriptions"] = {}
    course["segment_break_ids"] = {}
    course["segments"] = []
    course["waypoints"] = []
    course["segment_defs"] = []
    course["flow_control_points"] = []
    course["turnaround_indices"] = []
    course["start_description"] = "Start"
    course["end_description"] = "Finish"

    save_config_course(config_id, course)
    if args.copy_gpx:
        shutil.copy2(args.gpx, package_path / "full.gpx")

    print(f"config_id: {config_id}")
    print(f"path: {package_path}")
    print("Open Race Configuration and select this package to add segment pins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
