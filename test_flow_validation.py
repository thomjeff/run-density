#!/usr/bin/env python3
"""
Test script for the flow validation framework
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.flow import analyze_temporal_flow_segments
from app.flow_validation import validate_flow_analysis_results
import json

def test_validation_framework():
    """Test the flow validation framework with current analysis results."""
    
    print("=== TESTING FLOW VALIDATION FRAMEWORK ===")
    
    # Run temporal flow analysis
    print("Running temporal flow analysis...")
    results = analyze_temporal_flow_segments(
        'data/runners.csv', 
        'data/segments_new.csv', 
        {'Full': 420, 'Half': 440, '10K': 460}
    )
    
    segments = results.get('segments', [])
    print(f"Analyzed {len(segments)} segments")
    
    # Run validation
    print("\nRunning validation framework...")
    validation_summary = validate_flow_analysis_results(
        segments=segments,
        baseline_segments=None,  # No baseline for this test
        export_path="reports/validation/flow_validation_report.json"
    )
    
    # Print summary
    print(f"\n=== VALIDATION SUMMARY ===")
    print(f"Total checks: {validation_summary['total_checks']}")
    print(f"Passed: {validation_summary['passed_checks']}")
    print(f"Failed: {validation_summary['failed_checks']}")
    print(f"Success rate: {validation_summary['success_rate']:.1f}%")
    
    # Show failed checks if any
    if validation_summary['failed_checks'] > 0:
        print(f"\n=== FAILED CHECKS ===")
        for result in validation_summary['validation_results']:
            if not result['passed']:
                print(f"❌ {result['check_name']}: {result['message']}")
                if result['details']:
                    print(f"   Details: {result['details']}")
    
    # Show passed checks
    print(f"\n=== PASSED CHECKS ===")
    for result in validation_summary['validation_results']:
        if result['passed']:
            print(f"✅ {result['check_name']}: {result['message']}")
    
    return validation_summary

def create_baseline_comparison():
    """Create a baseline for future comparisons."""
    
    print("\n=== CREATING BASELINE ===")
    
    # Run analysis to create baseline
    results = analyze_temporal_flow_segments(
        'data/runners.csv', 
        'data/segments_new.csv', 
        {'Full': 420, 'Half': 440, '10K': 460}
    )
    
    # Export baseline
    os.makedirs("reports/baseline", exist_ok=True)
    baseline_path = "reports/baseline/flow_analysis_baseline.json"
    
    with open(baseline_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"📊 Baseline saved to: {baseline_path}")
    
    return baseline_path

if __name__ == "__main__":
    # Run validation test
    validation_summary = test_validation_framework()
    
    # Create baseline for future comparisons
    baseline_path = create_baseline_comparison()
    
    print(f"\n=== VALIDATION FRAMEWORK TEST COMPLETE ===")
    print(f"Validation framework is {'✅ WORKING' if validation_summary['failed_checks'] == 0 else '❌ NEEDS ATTENTION'}")
    print(f"Baseline created for future regression testing")
