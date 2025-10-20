#!/usr/bin/env python3
"""
test_schema_contract.py

CI validation script for Issue #285 - Density schema contract validation.
Validates that schema_density.json is present and has the correct structure.

Exit codes:
  0 = OK
  1 = Validation failure
  2 = Usage / path errors

Usage:
  python tests/test_schema_contract.py [--artifacts-dir /path/to/artifacts]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set


def err(msg: str) -> None:
    """Print error message to stderr."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def info(msg: str) -> None:
    """Print info message to stdout."""
    print(f"[INFO] {msg}")


def validate_schema_density_json(schema_path: Path) -> bool:
    """
    Validate schema_density.json structure and content.
    
    Args:
        schema_path: Path to schema_density.json
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
    except Exception as e:
        err(f"Could not read schema_density.json: {e}")
        return False
    
    # Check required top-level keys
    required_keys = {"schema_version", "units", "fields"}
    missing_keys = required_keys - set(schema_data.keys())
    if missing_keys:
        err(f"schema_density.json missing required keys: {missing_keys}")
        return False
    
    # Validate schema_version format (semver)
    schema_version = schema_data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.replace(".", "").replace("-", "").isdigit():
        err(f"schema_version must be semver format, got: {schema_version}")
        return False
    
    # Validate units
    units = schema_data.get("units", {})
    required_units = {
        "density": "persons_per_m2",
        "rate": "persons_per_second",
        "los": "A-F",
        "severity": "NONE|WATCH|ALERT|CRITICAL",
        "time": "ISO8601"
    }
    
    for unit_key, expected_value in required_units.items():
        if unit_key not in units:
            err(f"Missing required unit: {unit_key}")
            return False
        if units[unit_key] != expected_value:
            err(f"Invalid unit for {unit_key}: expected '{expected_value}', got '{units[unit_key]}'")
            return False
    
    # Validate fields
    fields = schema_data.get("fields", [])
    if not isinstance(fields, list):
        err("fields must be a list")
        return False
    
    # Check required field names
    required_fields = {"segment_id", "t_start", "t_end", "density", "rate", "los"}
    field_names = {f.get("name") for f in fields if isinstance(f, dict)}
    missing_fields = required_fields - field_names
    if missing_fields:
        err(f"Missing required fields: {missing_fields}")
        return False
    
    # Validate field structure
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            err(f"Field {i} must be a dict")
            return False
        
        required_field_keys = {"name", "type", "required", "description"}
        missing_field_keys = required_field_keys - set(field.keys())
        if missing_field_keys:
            err(f"Field {i} missing required keys: {missing_field_keys}")
            return False
        
        # Validate field type
        field_type = field.get("type")
        valid_types = {"string", "number", "timestamp"}
        if field_type not in valid_types:
            err(f"Field {i} has invalid type '{field_type}', must be one of: {valid_types}")
            return False
    
    # Validate aliases (if present)
    aliases = schema_data.get("aliases", {})
    if aliases:
        if not isinstance(aliases, dict):
            err("aliases must be a dict")
            return False
        
        # Check for alias conflicts with canonical field names
        canonical_names = {f.get("name") for f in fields if isinstance(f, dict)}
        for alias_key, alias_values in aliases.items():
            if alias_key in canonical_names:
                err(f"Alias key '{alias_key}' conflicts with canonical field name")
                return False
            
            if not isinstance(alias_values, list):
                err(f"Alias '{alias_key}' values must be a list")
                return False
    
    info(f"✅ schema_density.json validation passed")
    info(f"   Schema version: {schema_version}")
    info(f"   Fields: {len(fields)}")
    info(f"   Required fields present: {len(required_fields & field_names)}/{len(required_fields)}")
    
    return True


def find_latest_artifacts_dir(artifacts_root: Path) -> Path:
    """
    Find the latest artifacts directory.
    
    Args:
        artifacts_root: Root artifacts directory
        
    Returns:
        Path to latest artifacts directory
    """
    if not artifacts_root.exists():
        raise FileNotFoundError(f"Artifacts root not found: {artifacts_root}")
    
    # Look for date-based directories (YYYY-MM-DD format)
    date_dirs = []
    for item in artifacts_root.iterdir():
        if item.is_dir() and len(item.name) == 10 and item.name.replace("-", "").isdigit():
            date_dirs.append(item)
    
    if not date_dirs:
        raise FileNotFoundError("No date-based artifact directories found")
    
    # Return the most recent directory
    latest_dir = max(date_dirs, key=lambda d: d.name)
    return latest_dir


def main(argv: List[str]) -> int:
    """Main validation function."""
    ap = argparse.ArgumentParser(description="Validate schema_density.json contract")
    ap.add_argument("--artifacts-dir", default="artifacts", 
                   help="Root artifacts directory (default: artifacts)")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args(argv)
    
    artifacts_root = Path(args.artifacts_dir)
    
    try:
        # Find latest artifacts directory
        latest_dir = find_latest_artifacts_dir(artifacts_root)
        info(f"Using artifacts directory: {latest_dir}")
        
        # Look for schema_density.json in ui subdirectory
        schema_path = latest_dir / "ui" / "schema_density.json"
        if not schema_path.exists():
            err(f"schema_density.json not found at: {schema_path}")
            return 1
        
        # Validate the schema
        if not validate_schema_density_json(schema_path):
            return 1
        
        # Validate segment_metrics.json has schema field
        print("\n🔍 Validating segment_metrics.json schema field...")
        segment_metrics_path = latest_dir / "ui" / "segment_metrics.json"
        if segment_metrics_path.exists():
            with open(segment_metrics_path, 'r', encoding='utf-8') as f:
                segment_metrics = json.load(f)
            
            # Handle both dict and list formats
            if isinstance(segment_metrics, dict):
                rows = list(segment_metrics.values())
            else:
                rows = segment_metrics
            
            if not isinstance(rows, list) or not rows:
                err("segment_metrics.json must be a non-empty array")
                return 1
            
            # Check for schema field in each segment
            missing_schema = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if not row.get("schema"):
                    missing_schema.append(row.get("segment_id", "unknown"))
            
            if missing_schema:
                err(f"schema missing for segments: {missing_schema[:10]}")
                return 1
            
            info(f"✅ segment_metrics.json schema field validation passed")
            info(f"   Segments with schema: {len(rows)}")
        else:
            err("segment_metrics.json not found")
            return 1
            
    except Exception as e:
        err(f"Failed to validate segment_metrics.json: {e}")
        return 1

        info("🎉 All schema contract validations passed!")
        return 0
        
    except Exception as e:
        err(f"Validation failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
