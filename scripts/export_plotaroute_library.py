#!/usr/bin/env python3
"""Export segments.csv + flow.csv (+ per-event GPX) from cursor/plotaroute manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.course.segment_library import export_library_to_course, write_package_exports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("cursor/plotaroute"),
        help="Directory with chunk GPX files and manifest.yaml",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Config package directory to write CSV/GPX (optional)",
    )
    args = parser.parse_args()
    lib = args.library.resolve()
    manifest = lib / "manifest.yaml"
    if not manifest.is_file():
        print(f"Missing {manifest}", file=sys.stderr)
        return 1

    bundle = export_library_to_course(lib, manifest)
    print("Recipe lengths (km):", bundle["recipe_lengths_km"])
    if bundle["stitch_warnings"]:
        print("Stitch warnings:")
        for w in bundle["stitch_warnings"]:
            print(" ", w)
    print("Segments:", len(bundle["segments"]))
    print("Flow CSV lines:", bundle["flow_csv"].count("\n"))

    if args.out:
        write_package_exports(args.out.resolve(), lib, manifest)
        print("Wrote:", args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
