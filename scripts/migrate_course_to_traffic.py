#!/usr/bin/env python3
"""
Issue #948: rewrite location type ``course`` as on-course ``traffic``.

Covers authoring data only: the org leg library, saved courses, and config
packages. Analysis runs and imported Day Plans keep ``course``; their readers
treat it as on-course traffic.

Dry run (default) reports counts. ``--apply`` first writes a backup tarball
under ``{runflow}/backups/`` and then rewrites the files. Run inside Docker:

  python scripts/migrate_course_to_traffic.py
  python scripts/migrate_course_to_traffic.py --apply
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.utils.run_id import get_runflow_root

ON_COURSE_PLACEMENTS = ("along", "start", "end")
CSV_NAMES = ("passes.csv", "locations.csv")
YAML_PARTS = ("leg_library", "segment_library", "race_leg_library")


def _convert_location(loc: Dict[str, Any]) -> bool:
    if str(loc.get("loc_type") or "").strip().lower() != "course":
        return False
    loc["loc_type"] = "traffic"
    if str(loc.get("placement") or "").strip().lower() not in ON_COURSE_PLACEMENTS:
        loc["placement"] = "along"
    return True


def _walk(node: Any) -> int:
    changed = 0
    if isinstance(node, dict):
        if "loc_type" in node and ("loc_label" in node or "lat" in node):
            changed += int(_convert_location(node))
        for value in node.values():
            changed += _walk(value)
    elif isinstance(node, list):
        for item in node:
            changed += _walk(item)
    return changed


def _yaml_text(path: Path) -> tuple[int, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    changed = _walk(data)
    return changed, yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _json_text(path: Path) -> tuple[int, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = _walk(data)
    return changed, json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _csv_text(path: Path) -> tuple[int, str]:
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    if "loc_type" not in fields:
        return 0, text
    rows = list(reader)
    changed = 0
    for row in rows:
        if str(row.get("loc_type") or "").strip().lower() == "course":
            row["loc_type"] = "traffic"
            changed += 1
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return changed, out.getvalue()


def candidate_files(root: Path) -> List[Path]:
    files: List[Path] = []
    org_legs = root / "org" / "legs" / "manifest.yaml"
    if org_legs.is_file():
        files.append(org_legs)
    homes = sorted(p for p in (root / "org" / "courses").glob("*") if p.is_dir())
    homes += sorted(
        p
        for p in (root / "config").glob("*")
        if p.is_dir() and (p / "course.json").is_file()
    )
    for home in homes:
        for part in YAML_PARTS:
            manifest = home / part / "manifest.yaml"
            if manifest.is_file():
                files.append(manifest)
        for name in ("course.json", *CSV_NAMES):
            path = home / name
            if path.is_file():
                files.append(path)
    return files


def plan_changes(root: Path) -> Dict[Path, tuple[int, str]]:
    changes: Dict[Path, tuple[int, str]] = {}
    for path in candidate_files(root):
        if path.suffix == ".yaml":
            result = _yaml_text(path)
        elif path.suffix == ".json":
            result = _json_text(path)
        else:
            result = _csv_text(path)
        if result[0]:
            changes[path] = result
    return changes


def backup(root: Path, paths: List[Path]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = root / "backups" / f"pre948-{stamp}.tar.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        for path in paths:
            tar.add(path, arcname=str(path.relative_to(root)))
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument("--root", type=Path, default=None, help="Runflow root")
    args = parser.parse_args()
    root = args.root or get_runflow_root()
    changes = plan_changes(root)
    report = {
        "root": str(root),
        "files": {str(p.relative_to(root)): n for p, (n, _) in changes.items()},
        "locations": sum(n for n, _ in changes.values()),
        "applied": False,
    }
    if args.apply and changes:
        report["backup"] = str(backup(root, list(changes)))
        for path, (_, text) in changes.items():
            path.write_text(text, encoding="utf-8")
        report["applied"] = True
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
