#!/usr/bin/env python3
"""Export segments.csv + flow.csv (+ per-event GPX) from a reference leg library manifest."""

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
        default=Path("cursor/reference-legs"),
        help="Directory with leg GPX files and manifest.yaml",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Config package directory to write CSV/GPX (optional)",
    )
    args = parser.parse_args()
    lib = args.library.resolve()
    if not (lib / "manifest.yaml").is_file():
        print(f"manifest.yaml not found under {lib}", file=sys.stderr)
        return 1
    bundle = export_library_to_course(lib, lib / "manifest.yaml")
    print(f"Segments: {len(bundle['segments'])}")
    print(f"Stitch warnings: {len(bundle['stitch_warnings'])}")
    if bundle["stitch_warnings"]:
        for w in bundle["stitch_warnings"]:
            print(f"  - {w}")
    if args.out:
        write_package_exports(args.out.resolve(), lib)
        print(f"Wrote exports to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
