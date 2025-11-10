#!/usr/bin/env python3
"""
Test contract validation for health.json artifact.

Issue #288: Validates that health.json follows the expected schema
and contains all required system health information.

Author: Cursor AI Assistant
Epic: RF-FE-002 | Issue: #288 | Health Check page fix
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


def validate_health_json(artifacts_root: Path) -> bool:
    """
    Validate health.json contract.
    
    Args:
        artifacts_root: Path to artifacts directory
        
    Returns:
        True if validation passes, False otherwise
    """
    try:
        # Find the latest health.json
        health_path = None
        run_dirs = [d for d in artifacts_root.iterdir() if d.is_dir() and d.name not in ["latest.json", "ui"]]
        
        if not run_dirs:
            print("❌ No artifact runs found")
            return False
        
        latest_run = max(run_dirs, key=lambda d: d.name)
        health_path = latest_run / "ui" / "health.json"
        
        if not health_path.exists():
            print(f"❌ health.json not found in {latest_run.name}")
            return False
        
        # Load and validate health data
        with open(health_path, 'r') as f:
            health_data = json.load(f)
        
        # Validate schema version
        if health_data.get("schema_version") != "1.0.0":
            print(f"❌ Invalid schema_version: {health_data.get('schema_version')}")
            return False
        
        # Validate environment section
        env = health_data.get("environment", {})
        if not env.get("platform"):
            print("❌ Missing environment.platform")
            return False
        
        if not env.get("version"):
            print("❌ Missing environment.version")
            return False
        
        if not env.get("data_root"):
            print("❌ Missing environment.data_root")
            return False
        
        if not env.get("last_updated"):
            print("❌ Missing environment.last_updated")
            return False
        
        # Validate files section
        files = health_data.get("files", [])
        if not isinstance(files, list) or len(files) < 3:
            print(f"❌ Invalid files section: expected list with >= 3 items, got {len(files)}")
            return False
        
        # Check for required files
        required_files = ["segments.geojson", "segment_metrics.json", "flags.json", "meta.json"]
        file_names = [f["name"] for f in files]
        
        for required_file in required_files:
            if required_file not in file_names:
                print(f"❌ Missing required file: {required_file}")
                return False
        
        # Validate file structure
        for file_info in files:
            if "name" not in file_info or "present" not in file_info:
                print(f"❌ Invalid file entry: {file_info}")
                return False
        
        # Validate hashes section
        hashes = health_data.get("hashes", {})
        if not isinstance(hashes, dict):
            print("❌ Invalid hashes section: expected dict")
            return False
        
        # Validate endpoints section
        endpoints = health_data.get("endpoints", [])
        if not isinstance(endpoints, list) or len(endpoints) < 3:
            print(f"❌ Invalid endpoints section: expected list with >= 3 items, got {len(endpoints)}")
            return False
        
        # Validate endpoint structure
        for endpoint in endpoints:
            if "path" not in endpoint or "status" not in endpoint:
                print(f"❌ Invalid endpoint entry: {endpoint}")
                return False
            
            if endpoint["status"] not in ["up", "down", "unknown"]:
                print(f"❌ Invalid endpoint status: {endpoint['status']}")
                return False
        
        print(f"✅ health.json contract validation passed")
        print(f"   Platform: {env['platform']}")
        print(f"   Version: {env['version']}")
        print(f"   Files: {len(files)} checked")
        print(f"   Endpoints: {len(endpoints)} checked")
        
        return True
        
    except Exception as e:
        print(f"❌ Error validating health.json: {e}")
        return False


def main():
    """Main entry point for health.json contract validation."""
    if len(sys.argv) != 2:
        print("Usage: python test_health_contract.py <artifacts_root>")
        sys.exit(1)
    
    artifacts_root = Path(sys.argv[1])
    if not artifacts_root.exists():
        print(f"❌ Artifacts root does not exist: {artifacts_root}")
        sys.exit(1)
    
    success = validate_health_json(artifacts_root)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
