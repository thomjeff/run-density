"""
UI Artifacts Quality Control Tests

Validates critical schema and data consistency requirements per ChatGPT QA review.
Enforces:
1. ISO-8601 provenance timestamp in meta.json
2. flags.json is an array (correct shape)
3. flow.json aggregation matches sum-per-segment from Flow CSV

Author: ChatGPT QA Specification
Epic: RF-FE-002 | Issue: #279 | Step: 7 QA
"""

import json
import re
import math
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# ---------- Helpers ----------
ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
REP = ROOT / "reports"

def load_latest():
    """Load the latest run_id from artifacts/latest.json."""
    latest_path = ART / "latest.json"
    assert latest_path.exists(), f"artifacts/latest.json not found at {latest_path}"
    
    latest = json.loads(latest_path.read_text())
    run_id = latest.get("run_id")
    assert run_id, "artifacts/latest.json must include run_id"
    return run_id

def load_ui(run_id):
    """Load all UI artifacts for a given run_id."""
    ui_dir = ART / run_id / "ui"
    meta = json.loads((ui_dir / "meta.json").read_text())
    metrics = json.loads((ui_dir / "segment_metrics.json").read_text())
    flags = json.loads((ui_dir / "flags.json").read_text())
    flow_json = json.loads((ui_dir / "flow.json").read_text())
    segments_geo = json.loads((ui_dir / "segments.geojson").read_text())
    return meta, metrics, flags, flow_json, segments_geo

def find_flow_csv(run_id):
    """Find the latest Flow.csv file for a given run_id."""
    d = REP / run_id
    cands = sorted(d.glob("*-Flow.csv"), reverse=True)
    assert cands, f"No Flow CSV found in reports/{run_id}"
    return cands[0]

def parse_iso8601(ts: str) -> datetime:
    """
    Parse ISO-8601 timestamp. Accept Z or offset. Fail fast if invalid.
    
    Examples:
    - Good: 2025-10-19T16:55:00Z
    - Good: 2025-10-19T16:55:00+00:00
    - Bad:  2025-10-19T::00Z
    """
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

# ---------- Tests ----------

def test_meta_timestamp_is_iso8601_utc():
    """
    Test 1: meta.json must have valid ISO-8601 UTC timestamp.
    
    Required format: YYYY-MM-DDTHH:MM:SSZ
    Example: 2025-10-19T16:55:00Z
    """
    run_id = load_latest()
    meta, *_ = load_ui(run_id)
    assert "run_timestamp" in meta, "meta.run_timestamp missing"
    ts = meta["run_timestamp"]
    try:
        dt = parse_iso8601(ts)
    except Exception as e:
        raise AssertionError(f"meta.run_timestamp not ISO-8601: {ts!r}") from e
    assert dt.tzinfo is not None, "meta.run_timestamp must be timezone-aware (UTC/Z)"
    print(f"✅ meta.run_timestamp is valid ISO-8601: {ts}")

def test_flags_json_is_array():
    """
    Test 2: flags.json must be a JSON array of flag objects.
    
    Required format: [{seg_id, type, severity, ...}, ...]
    NOT: {flagged_segments: [...]}
    """
    run_id = load_latest()
    _, _, flags, _, _ = load_ui(run_id)
    assert isinstance(flags, list), f"flags.json must be a JSON array [], got {type(flags).__name__}"
    
    # Optional: basic shape check if non-empty
    if flags:
        f0 = flags[0]
        assert isinstance(f0, dict), f"flags[] entries must be objects, got {type(f0).__name__}"
        assert "seg_id" in f0, "flags[] must include seg_id"
        print(f"✅ flags.json is an array with {len(flags)} items")
    else:
        print("✅ flags.json is an empty array (no flags)")

def test_flow_json_matches_csv_sum_within_tolerance():
    """
    Test 3: flow.json values must match CSV sums per segment.
    
    Canonical rule (for UI): flow.json values are SUMS per segment derived from Flow CSV.
    The CSV has multiple rows per segment (one per event pair), so we sum them.
    
    Tolerance: absolute diff <= 1e-6 to catch gross mismatches.
    """
    run_id = load_latest()
    _, _, _, flow_json, _ = load_ui(run_id)

    # Load and aggregate Flow.csv
    csv_path = find_flow_csv(run_id)
    df = pd.read_csv(csv_path)
    
    # Group by seg_id and sum
    group_col = 'seg_id' if 'seg_id' in df.columns else 'segment_id'
    csv_sums = df.groupby(group_col)[['overtaking_a', 'overtaking_b', 'copresence_a', 'copresence_b']].sum()
    
    # Compare to flow.json per segment
    tol = 1e-6
    mismatches = []
    
    for seg_id in csv_sums.index:
        seg_id_str = str(seg_id)
        
        if seg_id_str not in flow_json:
            mismatches.append((seg_id_str, "missing_in_flow_json"))
            continue
        
        json_vals = flow_json[seg_id_str]
        csv_vals = csv_sums.loc[seg_id]
        
        for metric in ['overtaking_a', 'overtaking_b', 'copresence_a', 'copresence_b']:
            jv = float(json_vals.get(metric, 0.0))
            cv = float(csv_vals[metric])
            
            if not math.isclose(jv, cv, rel_tol=0.0, abs_tol=tol):
                mismatches.append((seg_id_str, metric, jv, cv, abs(jv - cv)))

    if mismatches:
        lines = ["Flow JSON ≠ CSV sums (tolerance 1e-6):"]
        for m in mismatches[:40]:
            lines.append(f"  {m}")
        raise AssertionError("\n".join(lines))
    
    print(f"✅ flow.json matches CSV sums for all {len(csv_sums)} segments")


def test_segment_metrics_has_core_fields():
    """
    Test 4: segment_metrics.json must have required fields.
    
    Each segment must include:
    - peak_density (numeric)
    - worst_los (A-F)
    - peak_rate (numeric)
    - active_window (string)
    """
    run_id = load_latest()
    _, metrics, *_ = load_ui(run_id)
    
    assert isinstance(metrics, dict), f"segment_metrics.json must be a dict, got {type(metrics).__name__}"
    assert len(metrics) > 0, "segment_metrics.json must have at least one segment"
    
    # Validate required fields on all segments
    required_fields = ["peak_density", "worst_los", "peak_rate", "active_window"]
    valid_los = ["A", "B", "C", "D", "E", "F"]
    
    for seg_id, seg_metrics in metrics.items():
        for field in required_fields:
            assert field in seg_metrics, f"segment_metrics[{seg_id}] missing field: {field}"
        
        # Validate LOS grade
        worst_los = seg_metrics["worst_los"]
        assert worst_los in valid_los, f"segment_metrics[{seg_id}] invalid worst_los: {worst_los}"
        
        # Validate numeric fields
        assert isinstance(seg_metrics["peak_density"], (int, float)), \
            f"segment_metrics[{seg_id}] peak_density must be numeric"
        assert isinstance(seg_metrics["peak_rate"], (int, float)), \
            f"segment_metrics[{seg_id}] peak_rate must be numeric"
    
    print(f"✅ segment_metrics.json has core fields for all {len(metrics)} segments")


if __name__ == "__main__":
    """Run all QC tests for manual verification."""
    print("🧪 UI Artifacts QC - ChatGPT Quality Gates")
    print("=" * 60)
    
    try:
        test_meta_timestamp_is_iso8601_utc()
        test_flags_json_is_array()
        test_flow_json_matches_csv_sum_within_tolerance()
        test_segment_metrics_has_core_fields()
        
        print("\n" + "=" * 60)
        print("🎉 All QC tests passed!")
        print("=" * 60)
        print("\n✅ Backend artifacts are 'known-good' and ready for UI binding")
        
    except AssertionError as e:
        print(f"\n❌ QC test failed:\n{e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error:\n{e}")
        exit(1)

