#!/usr/bin/env python3
"""
Pipeline Run Comparison Script

Compares a test run against a reference run to validate pipeline implementation.
Used to ensure Issue #574 implementation produces identical results.

Issue #579: Create pipeline validation script for Issue #574

Usage:
    python3 scripts/compare_pipeline_runs.py <test_run_id> [--reference-run-id YREtByZhLnG6GjCmUxMSkd]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Default reference run
DEFAULT_REFERENCE_RUN = "YREtByZhLnG6GjCmUxMSkd"
RUNFLOW_ROOT = Path("/Users/jthompson/Documents/runflow")

# Expected values from reference run YREtByZhLnG6GjCmUxMSkd (extracted once, never changes)
EXPECTED_VALUES = {
    "sat": {
        "peak_density": 0.692,
        "peak_rate": 0.0,
        "segments_with_flags": 6,
        "flagged_bins": 210,
        "res_scores": {
            "sat-elite": 5.0,
            "sat-open": 5.0
        },
        "overtaking": 10,
        "co_presence": 10,
        "locations_count": 16,
        "heatmap_count": 6
    },
    "sun": {
        "peak_density": 0.755,
        "peak_rate": 0.0,
        "segments_with_flags": 17,
        "flagged_bins": 1875,
        "res_scores": {
            "sun-all": 5.0
        },
        "overtaking": 29,
        "co_presence": 29,
        "locations_count": 96,
        "heatmap_count": 17
    }
}


class ComparisonResult:
    """Result of a single comparison check."""
    def __init__(self, name: str, passed: bool, details: List[str] = None):
        self.name = name
        self.passed = passed
        self.details = details or []


def parse_density_executive_summary(density_md_path: Path, day: str) -> Dict[str, Any]:
    """Parse Density.md Executive Summary section."""
    if not density_md_path.exists():
        return {}
    
    import re
    content = density_md_path.read_text()
    
    # Extract metrics from Executive Summary
    metrics = {}
    
    # Peak Density
    peak_density_match = re.search(r'\*\*Peak Density:\*\* ([\d.]+) p/m²', content)
    if peak_density_match:
        metrics['peak_density'] = float(peak_density_match.group(1))
    
    # Peak Rate
    peak_rate_match = re.search(r'\*\*Peak Rate:\*\* ([\d.]+) p/s', content)
    if peak_rate_match:
        metrics['peak_rate'] = float(peak_rate_match.group(1))
    
    # Segments with Flags (format: "X / Y")
    segments_flags_match = re.search(r'\*\*Segments with Flags:\*\* (\d+) / (\d+)', content)
    if segments_flags_match:
        metrics['segments_with_flags'] = int(segments_flags_match.group(1))
    
    # Flagged Bins (format: "X / Y")
    flagged_bins_match = re.search(r'\*\*Flagged Bins:\*\* (\d+) / ([\d,]+)', content)
    if flagged_bins_match:
        metrics['flagged_bins'] = int(flagged_bins_match.group(1))
    
    # RES scores (per event group)
    res_scores = {}
    res_section_match = re.search(r'\*\*Runner Experience Scores \(RES\):\*\*(.*?)(?=\n>|\n---|\Z)', content, re.DOTALL)
    if res_section_match:
        res_lines = res_section_match.group(1)
        for line in res_lines.split('\n'):
            res_match = re.search(r'- (\S+): ([\d.]+)', line)
            if res_match:
                group_id = res_match.group(1)
                res_value = float(res_match.group(2))
                res_scores[group_id] = res_value
    metrics['res_scores'] = res_scores
    
    return metrics


def count_locations(locations_csv_path: Path) -> int:
    """Count locations from Locations.csv (excluding header)."""
    if not locations_csv_path.exists():
        return 0
    
    lines = locations_csv_path.read_text().strip().split('\n')
    # Subtract 1 for header
    return max(0, len(lines) - 1)


def count_heatmaps(heatmaps_dir: Path) -> int:
    """Count PNG heatmap files."""
    if not heatmaps_dir.exists():
        return 0
    
    return len(list(heatmaps_dir.glob("*.png")))


def check_file_structure(run_path: Path, day: str) -> Dict[str, bool]:
    """Check if expected file structure exists."""
    day_path = run_path / day
    
    checks = {
        'computation_density': (day_path / "computation" / "density_results.json").exists(),
        'computation_flow': (day_path / "computation" / "flow_results.json").exists(),
        'computation_locations': (day_path / "computation" / "locations_results.json").exists(),
        'ui_metadata_dir': (day_path / "ui" / "metadata").exists(),
        'ui_metrics_dir': (day_path / "ui" / "metrics").exists(),
        'ui_geospatial_dir': (day_path / "ui" / "geospatial").exists(),
        'ui_visualizations_dir': (day_path / "ui" / "visualizations").exists(),
    }
    
    return checks


def validate_json_artifacts(run_path: Path, day: str) -> Tuple[bool, List[str]]:
    """Validate JSON artifacts are parseable and have expected structure."""
    day_path = run_path / day
    computation_dir = day_path / "computation"
    
    errors = []
    
    # Check density_results.json
    density_path = computation_dir / "density_results.json"
    if density_path.exists():
        try:
            data = json.loads(density_path.read_text())
            if 'day' not in data or 'segments' not in data:
                errors.append(f"density_results.json missing required keys")
        except json.JSONDecodeError as e:
            errors.append(f"density_results.json invalid JSON: {e}")
    else:
        errors.append("density_results.json not found")
    
    # Check flow_results.json
    flow_path = computation_dir / "flow_results.json"
    if flow_path.exists():
        try:
            data = json.loads(flow_path.read_text())
            if 'day' not in data or 'segments' not in data:
                errors.append(f"flow_results.json missing required keys")
        except json.JSONDecodeError as e:
            errors.append(f"flow_results.json invalid JSON: {e}")
    else:
        errors.append("flow_results.json not found")
    
    # Check locations_results.json
    locations_path = computation_dir / "locations_results.json"
    if locations_path.exists():
        try:
            data = json.loads(locations_path.read_text())
            if 'day' not in data:
                errors.append(f"locations_results.json missing required keys")
        except json.JSONDecodeError as e:
            errors.append(f"locations_results.json invalid JSON: {e}")
    else:
        errors.append("locations_results.json not found")
    
    return len(errors) == 0, errors


def compare_density_metrics(test_run: Path, day: str, expected: Dict[str, Any]) -> ComparisonResult:
    """Compare density metrics against expected values."""
    test_density = test_run / day / "reports" / "Density.md"
    
    if not test_density.exists():
        return ComparisonResult(
            f"Density.md Executive Summary ({day})",
            False,
            [f"Test Density.md not found for {day}"]
        )
    
    test_metrics = parse_density_executive_summary(test_density, day)
    
    if not test_metrics:
        return ComparisonResult(
            f"Density.md Executive Summary ({day})",
            False,
            [f"Could not parse test Density.md for {day}"]
        )
    
    details = []
    all_match = True
    
    # Compare peak density
    test_peak = test_metrics.get('peak_density', 0)
    expected_peak = expected.get('peak_density', 0)
    match = abs(test_peak - expected_peak) < 0.0001
    details.append(f"Peak density: {test_peak:.4f} {'(match)' if match else f'(expected {expected_peak:.4f})'}")
    if not match:
        all_match = False
    
    # Compare peak rate
    test_rate = test_metrics.get('peak_rate', 0)
    expected_rate = expected.get('peak_rate', 0)
    match = abs(test_rate - expected_rate) < 0.01
    details.append(f"Peak rate: {test_rate:.2f} {'(match)' if match else f'(expected {expected_rate:.2f})'}")
    if not match:
        all_match = False
    
    # Compare segments with flags
    test_seg_flags = test_metrics.get('segments_with_flags', 0)
    expected_seg_flags = expected.get('segments_with_flags', 0)
    match = test_seg_flags == expected_seg_flags
    details.append(f"Segments with flags: {test_seg_flags} {'(match)' if match else f'(expected {expected_seg_flags})'}")
    if not match:
        all_match = False
    
    # Compare flagged bins
    test_bins = test_metrics.get('flagged_bins', 0)
    expected_bins = expected.get('flagged_bins', 0)
    match = test_bins == expected_bins
    details.append(f"Flagged bins: {test_bins} {'(match)' if match else f'(expected {expected_bins})'}")
    if not match:
        all_match = False
    
    # Compare RES scores
    test_res = test_metrics.get('res_scores', {})
    expected_res = expected.get('res_scores', {})
    for group_id, expected_value in expected_res.items():
        test_value = test_res.get(group_id, 0)
        match = abs(test_value - expected_value) < 0.01
        details.append(f"RES {group_id}: {test_value:.2f} {'(match)' if match else f'(expected {expected_value:.2f})'}")
        if not match:
            all_match = False
    
    return ComparisonResult(f"Density.md Executive Summary ({day})", all_match, details)


def compare_flow_metrics(test_run: Path, day: str, expected: Dict[str, Any]) -> ComparisonResult:
    """Compare flow metrics against expected values."""
    test_metadata = test_run / day / "metadata.json"
    
    if not test_metadata.exists():
        return ComparisonResult(
            f"Flow Metrics ({day})",
            False,
            [f"Test metadata.json not found for {day}"]
        )
    
    test_data = json.loads(test_metadata.read_text())
    test_flow = test_data.get('flow', {})
    
    details = []
    all_match = True
    
    # Compare segments with convergence (overtaking segments)
    test_overtaking = test_flow.get('segments_with_convergence', 0)
    expected_overtaking = expected.get('overtaking', 0)
    match = test_overtaking == expected_overtaking
    details.append(f"Overtaking: {test_overtaking} {'(match)' if match else f'(expected {expected_overtaking})'}")
    if not match:
        all_match = False
    
    # Co-presence is the same as segments with convergence
    test_co_presence = test_flow.get('segments_with_convergence', 0)
    expected_co_presence = expected.get('co_presence', 0)
    match = test_co_presence == expected_co_presence
    details.append(f"Co-presence: {test_co_presence} {'(match)' if match else f'(expected {expected_co_presence})'}")
    if not match:
        all_match = False
    
    return ComparisonResult(f"Flow Metrics ({day})", all_match, details)


def compare_locations_count(test_run: Path, day: str, expected: Dict[str, Any]) -> ComparisonResult:
    """Compare locations count against expected value."""
    test_locations = test_run / day / "reports" / "Locations.csv"
    
    test_count = count_locations(test_locations)
    expected_count = expected.get('locations_count', 0)
    
    match = test_count == expected_count
    details = [f"{day}: {test_count} locations {'(match)' if match else f'(expected {expected_count})'}"]
    
    return ComparisonResult(f"Locations Count ({day})", match, details)


def compare_heatmap_count(test_run: Path, day: str, expected: Dict[str, Any]) -> ComparisonResult:
    """Compare heatmap count against expected value."""
    test_heatmaps = test_run / day / "ui" / "heatmaps"
    
    test_count = count_heatmaps(test_heatmaps)
    expected_count = expected.get('heatmap_count', 0)
    
    match = test_count == expected_count
    details = [f"{day}: {test_count} heatmaps {'(match)' if match else f'(expected {expected_count})'}"]
    
    return ComparisonResult(f"Heatmap Count ({day})", match, details)


def compare_file_structure(test_run: Path, day: str) -> ComparisonResult:
    """Check if expected file structure exists."""
    test_checks = check_file_structure(test_run, day)
    
    details = []
    all_pass = True
    
    for check_name, exists in test_checks.items():
        status = "exists" if exists else "missing"
        details.append(f"{check_name}: {status}")
        if not exists:
            all_pass = False
    
    return ComparisonResult(f"File Structure ({day})", all_pass, details)


def compare_json_artifacts(test_run: Path, day: str) -> ComparisonResult:
    """Validate JSON artifacts structure."""
    is_valid, errors = validate_json_artifacts(test_run, day)
    
    details = errors if errors else ["All JSON files valid and parseable"]
    
    return ComparisonResult(f"JSON Artifact Structure ({day})", is_valid, details)


def get_days_from_analysis_json(run_path: Path) -> List[str]:
    """Get list of days from analysis.json."""
    analysis_path = run_path / "analysis.json"
    if not analysis_path.exists():
        return []
    
    analysis = json.loads(analysis_path.read_text())
    return analysis.get('event_days', [])


def main():
    parser = argparse.ArgumentParser(
        description="Compare pipeline runs to validate Issue #574 implementation"
    )
    parser.add_argument(
        'test_run_id',
        help='Test run ID to compare'
    )
    parser.add_argument(
        '--reference-run-id',
        default=DEFAULT_REFERENCE_RUN,
        help=f'Reference run ID (default: {DEFAULT_REFERENCE_RUN})'
    )
    
    args = parser.parse_args()
    
    test_run_path = RUNFLOW_ROOT / args.test_run_id
    
    if not test_run_path.exists():
        print(f"❌ Test run not found: {test_run_path}", file=sys.stderr)
        sys.exit(1)
    
    # Get days from test run analysis.json
    days = get_days_from_analysis_json(test_run_path)
    if not days:
        print(f"⚠️  Could not determine days from analysis.json, using sat/sun", file=sys.stderr)
        days = ['sat', 'sun']
    
    print(f"Comparing test run {args.test_run_id} against reference {args.reference_run_id}")
    print()
    
    results = []
    
    # Compare for each day
    for day in days:
        if day not in EXPECTED_VALUES:
            print(f"⚠️  No expected values for day {day}, skipping", file=sys.stderr)
            continue
        
        expected = EXPECTED_VALUES[day]
        
        # Density metrics
        results.append(compare_density_metrics(test_run_path, day, expected))
        
        # Flow metrics
        results.append(compare_flow_metrics(test_run_path, day, expected))
        
        # Locations count
        results.append(compare_locations_count(test_run_path, day, expected))
        
        # Heatmap count
        results.append(compare_heatmap_count(test_run_path, day, expected))
        
        # File structure (only check test run - reference doesn't have new structure)
        results.append(compare_file_structure(test_run_path, day))
        
        # JSON artifacts (only validate test run)
        results.append(compare_json_artifacts(test_run_path, day))
    
    # Print results
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"{status} {result.name} - {'PASS' if result.passed else 'FAIL'}")
        for detail in result.details:
            print(f"   {detail}")
        print()
    
    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"Summary: {passed}/{total} checks passed")
    
    # Exit code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
