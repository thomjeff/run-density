"""
UI Artifacts Schema Validation Tests

Enforces critical schema requirements identified in ChatGPT's QA review:
1. meta.json must have valid ISO-8601 timestamp
2. flags.json must be a dict with flagged_segments as an array

Run: python test_artifacts_schema.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def test_meta_json_schema(meta_path: Path) -> bool:
    """
    Validate meta.json schema and ISO-8601 timestamp.
    
    Required fields:
    - run_id (string)
    - run_timestamp (string, valid ISO-8601)
    - environment (string)
    - dataset_version (string)
    - rulebook_hash (string)
    """
    print("=" * 60)
    print("Testing meta.json Schema")
    print("=" * 60)
    
    if not meta_path.exists():
        print(f"❌ File not found: {meta_path}")
        return False
    
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        
        # Check required fields
        required_fields = ["run_id", "run_timestamp", "environment", "dataset_version", "rulebook_hash"]
        for field in required_fields:
            if field not in meta:
                print(f"❌ Missing required field: {field}")
                return False
            print(f"  ✅ {field}: {meta[field]}")
        
        # Validate ISO-8601 timestamp
        timestamp = meta["run_timestamp"]
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            print(f"\n  ✅ Valid ISO-8601 timestamp: {timestamp}")
            print(f"     Parsed as: {dt}")
        except Exception as e:
            print(f"\n  ❌ Invalid ISO-8601 timestamp: {timestamp}")
            print(f"     Error: {e}")
            return False
        
        # Validate environment value
        if meta["environment"] not in ["local", "cloud"]:
            print(f"\n  ⚠️  Unexpected environment: {meta['environment']} (expected 'local' or 'cloud')")
        
        print("\n✅ meta.json schema valid!")
        return True
        
    except Exception as e:
        print(f"❌ Error validating meta.json: {e}")
        return False


def test_flags_json_schema(flags_path: Path) -> bool:
    """
    Validate flags.json schema and type.
    
    Required structure (per ChatGPT QA):
    [
      {seg_id, type, severity, ...},
      ...
    ]
    """
    print("\n" + "=" * 60)
    print("Testing flags.json Schema")
    print("=" * 60)
    
    if not flags_path.exists():
        print(f"❌ File not found: {flags_path}")
        return False
    
    try:
        with open(flags_path) as f:
            flags = json.load(f)
        
        # Check type is array (per ChatGPT QA requirement)
        if not isinstance(flags, list):
            print(f"❌ flags.json must be an array, got {type(flags).__name__}")
            return False
        print(f"  ✅ Type: array with {len(flags)} items")
        
        # Validate each flag object
        for i, flag in enumerate(flags):
            if not isinstance(flag, dict):
                print(f"❌ flags[{i}] must be a dict, got {type(flag).__name__}")
                return False
            
            required_flag_fields = ["seg_id", "type"]
            for field in required_flag_fields:
                if field not in flag:
                    print(f"❌ flags[{i}] missing required field: {field}")
                    return False
        
        if len(flags) > 0:
            print(f"     First flag: seg_id={flags[0]['seg_id']}, type={flags[0]['type']}, severity={flags[0].get('severity', 'N/A')}")
        else:
            print(f"     Empty array (no flags)")
        
        print("\n✅ flags.json schema valid!")
        return True
        
    except Exception as e:
        print(f"❌ Error validating flags.json: {e}")
        return False


def test_segment_metrics_json_schema(metrics_path: Path) -> bool:
    """
    Validate segment_metrics.json schema.
    
    Required structure:
    {
      "seg_id": {
        "worst_los": "A"-"F",
        "peak_density": float >= 0,
        "peak_rate": float >= 0,
        "active_window": "HH:MM–HH:MM"
      }
    }
    """
    print("\n" + "=" * 60)
    print("Testing segment_metrics.json Schema")
    print("=" * 60)
    
    if not metrics_path.exists():
        print(f"❌ File not found: {metrics_path}")
        return False
    
    try:
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        # Check type is dict
        if not isinstance(metrics, dict):
            print(f"❌ segment_metrics.json must be a dict, got {type(metrics).__name__}")
            return False
        
        print(f"  ✅ Type: dict with {len(metrics)} segments")
        
        # Validate each segment
        valid_los = ["A", "B", "C", "D", "E", "F"]
        errors = 0
        
        for seg_id, seg_metrics in metrics.items():
            if not isinstance(seg_metrics, dict):
                print(f"❌ metrics[{seg_id}] must be a dict")
                errors += 1
                continue
            
            # Check required fields
            required_fields = ["worst_los", "peak_density", "peak_rate", "active_window"]
            for field in required_fields:
                if field not in seg_metrics:
                    print(f"❌ metrics[{seg_id}] missing field: {field}")
                    errors += 1
            
            # Validate LOS grade
            worst_los = seg_metrics.get("worst_los")
            if worst_los not in valid_los:
                print(f"❌ metrics[{seg_id}] invalid worst_los: {worst_los}")
                errors += 1
            
            # Validate numeric fields
            if not isinstance(seg_metrics.get("peak_density"), (int, float)):
                print(f"❌ metrics[{seg_id}] peak_density must be numeric")
                errors += 1
            
            if not isinstance(seg_metrics.get("peak_rate"), (int, float)):
                print(f"❌ metrics[{seg_id}] peak_rate must be numeric")
                errors += 1
        
        if errors == 0:
            # Show sample
            first_seg = list(metrics.keys())[0]
            print(f"  ✅ Sample segment ({first_seg}):")
            print(f"     worst_los: {metrics[first_seg]['worst_los']}")
            print(f"     peak_density: {metrics[first_seg]['peak_density']}")
            print(f"     peak_rate: {metrics[first_seg]['peak_rate']}")
            print(f"     active_window: {metrics[first_seg]['active_window']}")
            print("\n✅ segment_metrics.json schema valid!")
            return True
        else:
            print(f"\n❌ {errors} schema errors found")
            return False
        
    except Exception as e:
        print(f"❌ Error validating segment_metrics.json: {e}")
        return False


def test_segments_geojson_schema(geojson_path: Path) -> bool:
    """
    Validate segments.geojson schema.
    
    Required structure:
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "geometry": {"type": "LineString", "coordinates": [...]},
          "properties": {"seg_id": "...", ...}
        }
      ]
    }
    """
    print("\n" + "=" * 60)
    print("Testing segments.geojson Schema")
    print("=" * 60)
    
    if not geojson_path.exists():
        print(f"❌ File not found: {geojson_path}")
        return False
    
    try:
        with open(geojson_path) as f:
            geojson = json.load(f)
        
        # Check type
        if geojson.get("type") != "FeatureCollection":
            print(f"❌ Must be FeatureCollection, got {geojson.get('type')}")
            return False
        print(f"  ✅ Type: FeatureCollection")
        
        # Check features array
        features = geojson.get("features", [])
        if not isinstance(features, list):
            print(f"❌ features must be an array")
            return False
        print(f"  ✅ Features: {len(features)} items")
        
        # Validate first feature
        if features:
            first = features[0]
            if first.get("type") != "Feature":
                print(f"❌ Feature type must be 'Feature'")
                return False
            
            if "geometry" not in first:
                print(f"❌ Feature missing geometry")
                return False
            
            if "properties" not in first:
                print(f"❌ Feature missing properties")
                return False
            
            if "seg_id" not in first["properties"]:
                print(f"❌ Feature properties missing seg_id")
                return False
            
            print(f"  ✅ Sample feature: {first['properties']['seg_id']}")
            print(f"     Geometry type: {first['geometry']['type']}")
            print(f"     Coordinates: {len(first['geometry'].get('coordinates', []))} points")
        
        print("\n✅ segments.geojson schema valid!")
        return True
        
    except Exception as e:
        print(f"❌ Error validating segments.geojson: {e}")
        return False


def main():
    """Run all artifact schema tests."""
    
    print("🧪 UI Artifacts Schema Validation")
    print("=" * 60)
    print("Validates critical schema requirements per ChatGPT QA review")
    print("=" * 60)
    
    # Find latest artifacts
    latest_pointer = Path("artifacts/latest.json")
    if not latest_pointer.exists():
        print("❌ artifacts/latest.json not found")
        return False
    
    with open(latest_pointer) as f:
        pointer = json.load(f)
        run_id = pointer.get("run_id")
    
    if not run_id:
        print("❌ Invalid latest.json pointer")
        return False
    
    print(f"\nTesting artifacts for run_id: {run_id}")
    print(f"Path: artifacts/{run_id}/ui/\n")
    
    artifacts_dir = Path("artifacts") / run_id / "ui"
    
    tests = [
        ("meta.json", lambda: test_meta_json_schema(artifacts_dir / "meta.json")),
        ("flags.json", lambda: test_flags_json_schema(artifacts_dir / "flags.json")),
        ("segment_metrics.json", lambda: test_segment_metrics_json_schema(artifacts_dir / "segment_metrics.json")),
        ("segments.geojson", lambda: test_segments_geojson_schema(artifacts_dir / "segments.geojson"))
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        if test_func():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Schema Validation Results: {passed}/{total} passed")
    print("=" * 60)
    
    if passed == total:
        print("🎉 All artifact schemas valid!")
        print("\n✅ Backend artifacts are 'known-good' and ready for UI binding")
        return True
    else:
        print("⚠️  Some schema validations failed - fix before proceeding")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

