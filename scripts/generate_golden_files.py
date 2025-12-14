#!/usr/bin/env python3
"""
Generate Golden Files from Successful Test Run

Issue #502: Generate golden files for regression testing.

Usage:
    python scripts/generate_golden_files.py <run_id> [--scenario mixed_day]
"""

import argparse
import shutil
from pathlib import Path
import sys
import os


def get_runflow_root():
    """Get runflow root directory."""
    # Check container path first
    container_path = Path("/app/runflow")
    if container_path.exists():
        return container_path
    
    # Fall back to local path
    local_path = Path(os.path.expanduser("~/Documents/runflow"))
    if local_path.exists():
        return local_path
    
    # Default to ./runflow
    return Path("runflow")


def generate_golden_files(run_id: str, scenario: str = "mixed_day"):
    """
    Generate golden files from a successful test run.
    
    Args:
        run_id: Run ID from successful test (e.g., n8U9eoqPBkEtpwwJ8rBt9F)
        scenario: Scenario name (saturday_only, sunday_only, mixed_day)
    """
    runflow_root = get_runflow_root()
    run_dir = runflow_root / run_id
    
    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        sys.exit(1)
    
    # Golden files directory
    golden_base = Path(__file__).parent.parent / "tests" / "v2" / "golden"
    golden_base.mkdir(parents=True, exist_ok=True)
    
    scenario_dir = golden_base / scenario
    scenario_dir.mkdir(exist_ok=True)
    
    # Files to copy per day
    files_to_copy = {
        "reports": ["Density.md", "Flow.csv", "Flow.md", "Locations.csv"],
    }
    
    # Copy files for each day
    for day in ["sat", "sun"]:
        day_dir = run_dir / day
        if not day_dir.exists():
            print(f"⚠️  Day directory not found: {day_dir}")
            continue
        
        golden_day_dir = scenario_dir / day
        golden_day_dir.mkdir(exist_ok=True)
        
        # Copy report files
        reports_dir = day_dir / "reports"
        if reports_dir.exists():
            for filename in files_to_copy["reports"]:
                source = reports_dir / filename
                if source.exists():
                    dest = golden_day_dir / filename
                    shutil.copy2(source, dest)
                    print(f"✅ Copied {day}/{filename}")
                else:
                    print(f"⚠️  File not found: {source}")
    
    print(f"\n✅ Golden files generated for scenario '{scenario}'")
    print(f"📁 Location: {scenario_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate golden files from successful test run"
    )
    parser.add_argument("run_id", help="Run ID from successful test")
    parser.add_argument(
        "--scenario",
        default="mixed_day",
        choices=["saturday_only", "sunday_only", "mixed_day"],
        help="Scenario name for golden files"
    )
    
    args = parser.parse_args()
    generate_golden_files(args.run_id, args.scenario)


if __name__ == "__main__":
    main()

