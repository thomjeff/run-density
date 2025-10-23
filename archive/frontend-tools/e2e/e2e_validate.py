"""
Runflow E2E Parity Validation

Validates parity between canonical hash computation and meta.json run_hash.
Ensures consistency across local and cloud builds.

Author: AI Assistant (Cursor)
Issue: #274 - Phase 5: Validation & Deployment
Architecture Guidance: ChatGPT
"""

from pathlib import Path
import json
import hashlib
import sys
from datetime import datetime
from collections import Counter

# Canonical JSON formatting (must match Phase 1 validator)
CANON = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}

# Required files for validation
FILES = [
    "data/segments.geojson",
    "data/segment_metrics.json",
    "data/flags.json",
    "data/meta.json"
]


def _canon_bytes(p: Path) -> bytes:
    """
    Convert file to canonical bytes for hashing.
    
    JSON/GeoJSON files are parsed and re-serialized in canonical form.
    Other files are hashed as-is.
    """
    if p.suffix.lower() in {".json", ".geojson"}:
        obj = json.loads(p.read_text())
        return json.dumps(obj, **CANON).encode("utf-8")
    return p.read_bytes()


def sha256(paths: list) -> str:
    """
    Compute canonical SHA256 hash across multiple files.
    
    Args:
        paths: List of file paths to hash
        
    Returns:
        str: SHA256 hash (lowercase hex)
    """
    h = hashlib.sha256()
    for p in map(Path, sorted(paths)):
        h.update(_canon_bytes(p))
    return h.hexdigest()


def metrics_summary() -> dict:
    """
    Generate summary statistics from segment_metrics.json.
    
    Returns:
        dict: Summary with segment count and LOS distribution
    """
    metrics = json.loads(Path("data/segment_metrics.json").read_text())["items"]
    
    # Count LOS distribution
    los_counts = {k: 0 for k in list("ABCDEF")}
    los_counts.update(Counter(m.get("worst_los", "") for m in metrics))
    
    return {
        "segments": len(metrics),
        "los_counts": los_counts
    }


def main():
    """
    Run E2E parity validation.
    
    Validates:
    1. All required files exist
    2. Canonical hash matches meta.run_hash
    3. Metrics summary is computed
    
    Exit codes:
        0: Success (parity confirmed)
        2: Failure (missing files or hash mismatch)
    """
    print("[E2E Validate] Starting parity validation...")
    
    # Check for missing files
    missing = [f for f in FILES if not Path(f).exists()]
    if missing:
        report = {
            "status": "Failed",
            "errors": [f"Missing files: {missing}"]
        }
        print(json.dumps(report, indent=2))
        sys.exit(2)
    
    # Compute canonical hash (exclude meta.json as it may change after write)
    data_files = [f for f in FILES if not f.endswith("meta.json")]
    run_hash_canonical = sha256(data_files)
    
    # Load meta.json
    meta = json.loads(Path("data/meta.json").read_text())
    
    # Generate metrics summary
    summary = metrics_summary()
    
    # Build validation report
    report = {
        "status": "Validated",
        "run_hash_canonical": run_hash_canonical,
        "meta_run_hash": meta.get("run_hash"),
        "env": meta.get("environment"),
        "summary": summary,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Write validation report
    output_dir = Path("frontend/validation/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    validation_report_path = output_dir / "validation_report.json"
    validation_report_path.write_text(json.dumps(report, indent=2))
    
    # Check parity
    parity_ok = (report["run_hash_canonical"] == report["meta_run_hash"])
    
    if parity_ok:
        print(f"[E2E Validate] ✅ PASS - Hash parity confirmed")
        print(f"[E2E Validate]    Canonical: {run_hash_canonical[:16]}...")
        print(f"[E2E Validate]    Meta:      {report['meta_run_hash'][:16]}...")
        print(f"[E2E Validate]    Segments:  {summary['segments']}")
        print(f"[E2E Validate]    LOS dist:  {summary['los_counts']}")
    else:
        print(f"[E2E Validate] ❌ FAIL - Hash mismatch")
        print(f"[E2E Validate]    Canonical: {run_hash_canonical}")
        print(f"[E2E Validate]    Meta:      {report['meta_run_hash']}")
    
    # Print full report
    print("\n" + json.dumps(report, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if parity_ok else 2)


if __name__ == "__main__":
    main()

