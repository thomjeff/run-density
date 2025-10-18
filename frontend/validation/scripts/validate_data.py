from pathlib import Path
import json, sys, os

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from frontend.validation.data_contracts.schemas import (
    GeoJSONFeatureCollection, SegmentMetricsFile, FlagsFile, Meta
)
from frontend.validation.scripts.compute_hash import compute_run_hash
from datetime import datetime, timezone

DATA = {
    "segments": "data/segments.geojson",
    "metrics": "data/segment_metrics.json",
    "flags":   "data/flags.json",
    "meta":    "data/meta.json",
}

def load_json(path: str):
    return json.loads(Path(path).read_text())

def main():
    Path("frontend/validation/output").mkdir(parents=True, exist_ok=True)

    required = list(DATA.values())
    missing = [p for p in required if not Path(p).exists()]
    if missing:
        print(json.dumps({"status":"Failed","errors":[f"Missing files: {missing}"]}, indent=2))
        sys.exit(2)

    errors = []

    # Load
    try:
        segments_raw = load_json(DATA["segments"])
        metrics_raw  = load_json(DATA["metrics"])
        flags_raw    = load_json(DATA["flags"])
        meta_raw     = load_json(DATA["meta"])
    except Exception as e:
        print(f"[load] {e}")
        sys.exit(1)

    # Schema validation
    try:
        segments = GeoJSONFeatureCollection(**segments_raw)
        metrics  = SegmentMetricsFile(**metrics_raw)
        flags    = FlagsFile(**flags_raw)
        meta     = Meta(**meta_raw)
    except Exception as e:
        errors.append(f"Schema validation failed: {e}")

    # Referential integrity
    try:
        seg_ids = {f.properties.segment_id for f in segments.features}
        metrics_ids = {m.segment_id for m in metrics.items}
        flags_ids   = {f.segment_id for f in flags.items}
        missing_in_segments = (metrics_ids | flags_ids) - seg_ids
        if missing_in_segments:
            errors.append(f"IDs present in metrics/flags but not segments: {sorted(missing_in_segments)[:10]}")
    except Exception as e:
        errors.append(f"Integrity check failed: {e}")

    # Compute run hash
    try:
        run_hash = compute_run_hash([
            DATA["segments"],
            DATA["metrics"],
            DATA["flags"],
        ])
    except Exception as e:
        errors.append(f"Hash failed: {e}")
        run_hash = None

    # Update meta
    try:
        meta_out = dict(meta_raw)
        meta_out["run_hash"]   = run_hash
        meta_out["validated"]  = len(errors) == 0
        meta_out.setdefault("run_timestamp", datetime.now(timezone.utc).isoformat())
        meta_out["environment"] = os.getenv("RUNFLOW_ENV", meta_out.get("environment","local"))
        Path(DATA["meta"]).write_text(json.dumps(meta_out, indent=2))
    except Exception as e:
        errors.append(f"meta.json write failed: {e}")

    # Badge
    try:
        from frontend.validation.scripts.write_provenance_badge import write_badge
        write_badge(DATA["meta"], "frontend/validation/output/provenance_snippet.html")
    except Exception as e:
        errors.append(f"Badge write failed: {e}")

    # Report
    report = {
        "status": "Validated" if not errors else "Failed",
        "errors": errors,
        "run_hash": run_hash,
        "files": DATA,
    }
    Path("frontend/validation/output/validation_report.json").write_text(json.dumps(report, indent=2))

    if errors:
        print(json.dumps(report, indent=2))
        sys.exit(2)
    print(json.dumps(report, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
