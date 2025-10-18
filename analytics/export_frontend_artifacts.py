"""
Runflow Frontend Artifact Exporter

Converts analytics pipeline outputs into canonical JSON files for front-end consumption.
Pure functions with no side effects beyond file writes.

Author: AI Assistant (Cursor)
Issue: #274 - Phase 5: Validation & Deployment
Architecture Guidance: ChatGPT
"""

from pathlib import Path
import json
import yaml
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Canonical JSON formatting for deterministic hashing
CANON = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}


def _sha256_bytes(b: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def rulebook_hash(path: str = "config/density_rulebook.yml") -> str:
    """
    Compute canonical SHA256 hash of the density rulebook YAML.
    
    Args:
        path: Path to density_rulebook.yml
        
    Returns:
        str: SHA256 hash (lowercase hex)
    """
    obj = yaml.safe_load(Path(path).read_text())
    # Convert to canonical JSON for deterministic hashing
    b = json.dumps(obj, **CANON).encode("utf-8")
    return _sha256_bytes(b)


def get_dataset_version() -> str:
    """
    Get dataset version from git or fallback to timestamp.
    
    Returns:
        str: Git SHA (short) or YYYYMMDD.HHMM timestamp
    """
    try:
        # Try git rev-parse --short HEAD
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Fallback to timestamp
    return datetime.now(timezone.utc).strftime("%Y%m%d.%H%M")


def write_segments_geojson(geojson_obj: dict, out: str = "data/segments.geojson") -> None:
    """
    Write segments GeoJSON in canonical format.
    
    Args:
        geojson_obj: GeoJSON FeatureCollection dict
        out: Output path (default: data/segments.geojson)
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(geojson_obj, **CANON))
    print(f"[Export] ✅ Wrote {out}")


def write_segment_metrics_json(items: List[Dict], out: str = "data/segment_metrics.json") -> None:
    """
    Write segment metrics JSON in canonical format.
    
    Args:
        items: List of segment metric dicts
        out: Output path (default: data/segment_metrics.json)
        
    Expected shape per item:
        {
            "segment_id": "S001",
            "worst_los": "C",
            "peak_density_window": "08:05–08:20",
            "co_presence_pct": 35.0,
            "overtaking_pct": 12.0,
            "utilization_pct": 60.0
        }
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"items": items}, **CANON))
    print(f"[Export] ✅ Wrote {out} ({len(items)} segments)")


def write_flags_json(items: List[Dict], out: str = "data/flags.json") -> None:
    """
    Write flags JSON in canonical format.
    
    Args:
        items: List of flag dicts
        out: Output path (default: data/flags.json)
        
    Expected shape per item:
        {
            "segment_id": "S001",
            "flag_type": "co_presence",  # or "overtaking"
            "severity": "warn",           # "info", "warn", "critical"
            "window": "08:05–08:20",
            "note": "Optional description"
        }
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"items": items}, **CANON))
    print(f"[Export] ✅ Wrote {out} ({len(items)} flags)")


def write_meta_json(
    env: Optional[str] = None,
    dataset_ver: Optional[str] = None,
    out: str = "data/meta.json"
) -> None:
    """
    Write meta.json with run metadata.
    
    Phase 1 validator will later add 'run_hash' and 'validated' fields.
    
    Args:
        env: Environment ("local" or "cloud"), defaults to RUNFLOW_ENV or "local"
        dataset_ver: Dataset version string, defaults to git SHA or timestamp
        out: Output path (default: data/meta.json)
    """
    import os
    
    if env is None:
        env = os.getenv("RUNFLOW_ENV", "local")
    
    if dataset_ver is None:
        dataset_ver = get_dataset_version()
    
    meta = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env,
        "rulebook_hash": rulebook_hash(),
        "dataset_version": dataset_ver,
        "run_hash": None,     # Will be set by Phase 1 validator
        "validated": None     # Will be set by Phase 1 validator
    }
    
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(meta, indent=2))
    print(f"[Export] ✅ Wrote {out} (env={env}, version={dataset_ver})")


def write_participants_json(
    total: int,
    full: int,
    half: int,
    tenk: int,
    out: str = "data/participants.json"
) -> None:
    """
    Write participants.json (optional).
    
    Args:
        total: Total participants across all events
        full: Full marathon participants
        half: Half marathon participants
        tenk: 10K participants
        out: Output path (default: data/participants.json)
    """
    participants = {
        "total": total,
        "full": full,
        "half": half,
        "tenk": tenk
    }
    
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(participants, indent=2))
    print(f"[Export] ✅ Wrote {out} (total={total})")


def write_segment_series_json(
    series_data: Dict[str, Dict],
    out: str = "data/segment_series.json"
) -> None:
    """
    Write segment_series.json for sparklines (optional).
    
    Args:
        series_data: Dict mapping segment_id to {"density": [values...]}
        out: Output path (default: data/segment_series.json)
        
    Example:
        {
            "S001": {"density": [0.22, 0.35, 0.41, 0.38, 0.29]},
            "S002": {"density": [0.15, 0.18, 0.21, 0.19, 0.16]}
        }
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(series_data, **CANON))
    print(f"[Export] ✅ Wrote {out} ({len(series_data)} segments)")

