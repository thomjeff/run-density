#!/usr/bin/env python3
"""
Junction Flow prototype CLI (#818) — thin wrapper over core compute.

Prefer a full analysis run (Phase 4.3) for SSOT artifacts. This script is for
ad-hoc recompute against an existing package + runners without re-running the
pipeline.

Usage:
  .venv/bin/python scripts/prototype_junction_flow.py \\
    --package-id bGNTx9388Ah9LpXarPuLak \\
    --run-id ek6eu8XUDy5pRUembPYTQr \\
    --junction-label "Trail at George"
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.core.junction_flow.compute import (
    NODE_DWELL_SEC,
    MERGE_PARTNER_EVENTS,
    _load_runners,
    analyze_junction,
)

DEFAULT_RUNFLOW = Path("/Users/jthompson/Documents/runflow")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--junction-label", default=None)
    parser.add_argument("--runflow-root", type=Path, default=DEFAULT_RUNFLOW)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    package_dir = args.runflow_root / "config" / args.package_id
    run_dir = args.runflow_root / "analysis" / args.run_id
    analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    day = (analysis.get("event_days") or ["sun"])[0]
    gun_by_event = {
        str(e["name"]).lower(): float(e["start_time"])
        for e in analysis.get("events") or []
    }

    junctions_doc = json.loads((package_dir / "junctions.json").read_text(encoding="utf-8"))
    junctions = list(junctions_doc.get("junctions") or [])
    if args.junction_label:
        junctions = [j for j in junctions if str(j.get("label") or "") == args.junction_label]
        if not junctions:
            raise SystemExit(f"Junction not found: {args.junction_label}")

    events_needed = set()
    for junction in junctions:
        for ix in junction.get("interactions") or []:
            events_needed.update(str(e).lower() for e in (ix.get("events") or []))
    runners_by_event = {e: _load_runners(package_dir, e) for e in sorted(events_needed)}

    out_dir = args.out_dir or (run_dir / day / "reports" / "junctions_prototype")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": args.run_id,
        "package_id": args.package_id,
        "method": {
            "participation": "dwell_copresence_at_node",
            "node_dwell_sec": NODE_DWELL_SEC,
            "merge_partner_events": list(MERGE_PARTNER_EVENTS),
        },
        "junctions": [],
    }

    for junction in junctions:
        analyzed = analyze_junction(junction, runners_by_event, gun_by_event)
        summary["junctions"].append(
            {
                "junction_id": analyzed.get("junction_id"),
                "junction_label": analyzed.get("junction_label"),
                "interactions": [
                    {
                        "id": ix["id"],
                        "type": ix["type"],
                        "side": ix["side"],
                        "label": ix["label"],
                        "events": ix["events"],
                        "window_start": ix["window_start"],
                        "window_end": ix["window_end"],
                        "window_minutes": ix["window_minutes"],
                        "unique_by_role_event": ix["unique_by_role_event"],
                        "peak_concurrent": ix["peak_concurrent"],
                        "field_crosstab_top": (ix.get("field_crosstab") or [])[:15],
                        "notes": ix.get("notes") or [],
                    }
                    for ix in analyzed.get("interactions") or []
                ],
            }
        )
        for ix in analyzed.get("interactions") or []:
            if ix.get("minute_rows"):
                name = f"{ix['id']}_{ix['type']}_per_minute.csv"
                with (out_dir / name).open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(ix["minute_rows"][0].keys()))
                    writer.writeheader()
                    writer.writerows(ix["minute_rows"])
            if ix.get("field_crosstab"):
                name = f"{ix['id']}_{ix['type']}_field_crosstab.csv"
                with (out_dir / name).open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(ix["field_crosstab"][0].keys()))
                    writer.writeheader()
                    writer.writerows(ix["field_crosstab"])

    summary_path = out_dir / "junction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
