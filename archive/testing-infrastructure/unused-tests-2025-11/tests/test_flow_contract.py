#!/usr/bin/env python3
"""
CI validation for flow.json contract (Issue #287)

Validates that flow.json:
- Exists and is non-empty
- Has correct schema_version and units
- Contains expected minimum segment coverage
- Has consistent structure (rows and summaries)

Run with: python tests/test_flow_contract.py
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


def err(msg: str) -> None:
    """Print error message to stderr."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def info(msg: str) -> None:
    """Print info message."""
    print(f"[INFO] {msg}")


def validate_flow_json(artifacts_root: Path) -> int:
    """
    Validate flow.json contract.
    
    Returns:
        0 if validation passes, 1 if it fails
    """
    # Find latest artifacts directory
    if not artifacts_root.exists():
        err(f"Artifacts root not found: {artifacts_root}")
        return 1
    
    date_dirs = [d for d in artifacts_root.iterdir() if d.is_dir() and d.name.startswith('20')]
    if not date_dirs:
        err("No date-based artifact directories found")
        return 1
    
    latest_dir = max(date_dirs, key=lambda d: d.name)
    flow_path = latest_dir / "ui" / "flow.json"
    
    info(f"Using artifacts directory: {latest_dir}")
    
    # Check presence
    if not flow_path.exists():
        err("flow.json not found")
        return 1
    
    # Load and validate
    try:
        with open(flow_path, 'r', encoding='utf-8') as f:
            flow_data = json.load(f)
    except Exception as e:
        err(f"Failed to parse flow.json: {e}")
        return 1
    
    # Validate schema version
    schema_version = flow_data.get("schema_version")
    if not schema_version:
        err("schema_version missing from flow.json")
        return 1
    info(f"✅ schema_version: {schema_version}")
    
    # Validate units
    units = flow_data.get("units", {})
    if units.get("rate") != "persons_per_second":
        err(f"units.rate must be 'persons_per_second', got: {units.get('rate')}")
        return 1
    info(f"✅ units.rate: {units.get('rate')}")
    
    # Validate rows
    rows = flow_data.get("rows", [])
    if not isinstance(rows, list):
        err("rows must be a list")
        return 1
    
    if len(rows) == 0:
        err("rows is empty - no flow data")
        return 1
    
    info(f"✅ rows: {len(rows)} bin-level records")
    
    # Validate row structure (spot check first few)
    required_row_fields = ["segment_id", "t_start", "t_end", "rate"]
    for i, row in enumerate(rows[:10]):
        if not isinstance(row, dict):
            err(f"rows[{i}] is not a dict")
            return 1
        for field in required_row_fields:
            if field not in row:
                err(f"rows[{i}] missing required field: {field}")
                return 1
    
    # Validate summaries
    summaries = flow_data.get("summaries", [])
    if not isinstance(summaries, list):
        err("summaries must be a list")
        return 1
    
    if len(summaries) == 0:
        err("summaries is empty - no segment aggregates")
        return 1
    
    info(f"✅ summaries: {len(summaries)} segments")
    
    # Validate summary structure
    required_summary_fields = ["segment_id", "bins", "peak_rate", "avg_rate", "active_start", "active_end"]
    for i, summary in enumerate(summaries):
        if not isinstance(summary, dict):
            err(f"summaries[{i}] is not a dict")
            return 1
        for field in required_summary_fields:
            if field not in summary:
                err(f"summaries[{i}] missing required field: {field}")
                return 1
    
    # Validate coverage: expect at least 20 segments for this dataset
    # (Configurable threshold - adjust based on your dataset)
    # Note: Current dataset has 22 segments; threshold set conservatively to 20
    MIN_SEGMENTS = 20
    if len(summaries) < MIN_SEGMENTS:
        err(f"Unexpected low segment coverage: {len(summaries)} < {MIN_SEGMENTS}")
        return 1
    
    # Optional: Check consistency between rows and summaries
    segment_ids_from_rows = set(row["segment_id"] for row in rows)
    segment_ids_from_summaries = set(summary["segment_id"] for summary in summaries)
    
    if segment_ids_from_summaries != segment_ids_from_rows:
        missing_in_summaries = segment_ids_from_rows - segment_ids_from_summaries
        missing_in_rows = segment_ids_from_summaries - segment_ids_from_rows
        if missing_in_summaries:
            err(f"Segments in rows but not in summaries: {missing_in_summaries}")
        if missing_in_rows:
            err(f"Segments in summaries but not in rows: {missing_in_rows}")
        return 1
    
    info(f"✅ Segment consistency: {len(segment_ids_from_summaries)} unique segments in both rows and summaries")
    
    print("\n✅ flow.json validation passed!")
    return 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        artifacts_root = Path(sys.argv[1])
    else:
        artifacts_root = Path("artifacts")
    
    exit_code = validate_flow_json(artifacts_root)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

