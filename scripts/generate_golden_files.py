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


def validate_scenario_match(run_id: str, scenario: str, run_dir: Path) -> bool:
    """
    Validate that the run_id matches the scenario.
    
    Args:
        run_id: Run ID to validate
        scenario: Scenario name (saturday_only, sunday_only, mixed_day)
        run_dir: Path to run directory
        
    Returns:
        True if scenario matches run_id, False otherwise
    """
    sat_dir = run_dir / "sat"
    sun_dir = run_dir / "sun"
    
    sat_exists = sat_dir.exists() and (sat_dir / "reports").exists()
    sun_exists = sun_dir.exists() and (sun_dir / "reports").exists()
    
    if scenario == "saturday_only":
        if sun_exists:
            print(f"❌ ERROR: Scenario 'saturday_only' but run_id {run_id} contains 'sun' directory")
            print(f"   This run appears to be a mixed-day or sunday-only run.")
            print(f"   Use a run_id from a Saturday-only test.")
            return False
        if not sat_exists:
            print(f"❌ ERROR: Scenario 'saturday_only' but run_id {run_id} has no 'sat' directory")
            return False
    
    elif scenario == "sunday_only":
        if sat_exists:
            print(f"❌ ERROR: Scenario 'sunday_only' but run_id {run_id} contains 'sat' directory")
            print(f"   This run appears to be a mixed-day or saturday-only run.")
            print(f"   Use a run_id from a Sunday-only test.")
            return False
        if not sun_exists:
            print(f"❌ ERROR: Scenario 'sunday_only' but run_id {run_id} has no 'sun' directory")
            return False
    
    elif scenario == "mixed_day":
        if not sat_exists or not sun_exists:
            print(f"❌ ERROR: Scenario 'mixed_day' but run_id {run_id} is missing 'sat' or 'sun' directory")
            print(f"   Expected both 'sat' and 'sun' directories for mixed-day scenario.")
            return False
    
    return True


def generate_golden_files(run_id: str, scenario: str = "mixed_day", skip_validation: bool = False):
    """
    Generate golden files from a successful test run.
    
    Args:
        run_id: Run ID from successful test (e.g., n8U9eoqPBkEtpwwJ8rBt9F)
        scenario: Scenario name (saturday_only, sunday_only, mixed_day)
        skip_validation: Skip scenario validation (use with caution)
    """
    runflow_root = get_runflow_root()
    run_dir = runflow_root / run_id
    
    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        sys.exit(1)
    
    # Validate scenario matches run_id
    if not skip_validation:
        if not validate_scenario_match(run_id, scenario, run_dir):
            print(f"\n💡 Tip: Use --skip-validation to override this check (not recommended)")
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
    
    # Determine which days to copy based on scenario
    days_to_copy = []
    if scenario == "saturday_only":
        days_to_copy = ["sat"]
    elif scenario == "sunday_only":
        days_to_copy = ["sun"]
    else:  # mixed_day
        days_to_copy = ["sat", "sun"]
    
    # Copy files for each day
    for day in days_to_copy:
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
        description="Generate golden files from successful test run",
        epilog="""
Examples:
  # Generate golden files for mixed-day scenario (validates both sat and sun exist)
  python scripts/generate_golden_files.py <run_id> --scenario mixed_day
  
  # Generate golden files for Saturday-only scenario (validates only sat exists, no sun)
  python scripts/generate_golden_files.py <run_id> --scenario saturday_only
  
  # Generate golden files for Sunday-only scenario (validates only sun exists, no sat)
  python scripts/generate_golden_files.py <run_id> --scenario sunday_only
  
  # Skip validation (use with caution - may generate incorrect golden files)
  python scripts/generate_golden_files.py <run_id> --scenario saturday_only --skip-validation
        """
    )
    parser.add_argument("run_id", help="Run ID from successful test")
    parser.add_argument(
        "--scenario",
        default="mixed_day",
        choices=["saturday_only", "sunday_only", "mixed_day"],
        help="Scenario name for golden files"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip scenario validation (not recommended)"
    )
    
    args = parser.parse_args()
    generate_golden_files(args.run_id, args.scenario, skip_validation=args.skip_validation)


if __name__ == "__main__":
    main()

