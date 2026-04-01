#!/usr/bin/env python3
"""
Write minimal runflow/analysis/index.json for cloud-release (Issue #740).

Single-run entry so GET /api/runs/list resolves in the Cloud Run image.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: write_cloud_index_json.py <run_id> <output_analysis_dir>", file=sys.stderr)
        sys.exit(1)
    run_id = sys.argv[1]
    out_dir = Path(sys.argv[2])
    run_dir = out_dir / run_id
    entry: dict = {
        "run_id": run_id,
        "created_at": None,
        "description": None,
        "status": "complete",
        "event_summary": {},
    }
    analysis_path = run_dir / "analysis.json"
    if analysis_path.exists():
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        entry["description"] = data.get("description")
        entry["event_summary"] = data.get("event_summary") or {}
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        entry["created_at"] = meta.get("created_at")
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    index_path.write_text(json.dumps([entry], indent=2), encoding="utf-8")
    print(f"Wrote {index_path}")


if __name__ == "__main__":
    main()
