#!/usr/bin/env python3
"""
Test script for Flow Report Validation Utility

This script tests the validate_flow_refactoring.py utility by creating
dummy Flow reports and verifying the comparison logic works correctly.
"""

import sys
import os
import tempfile
import pandas as pd
from pathlib import Path

# Add scripts directory to path
sys.path.append(str(Path(__file__).parent))

from validate_flow_refactoring import FlowReportValidator

def create_dummy_flow_md(content_type: str = "baseline") -> str:
    """Create a dummy Flow markdown report for testing."""
    if content_type == "baseline":
        content = """# Temporal Flow Analysis Report

**Generated:** 2025-10-28 15:40:00
**Analysis Engine:** temporal_flow
**Version:** v1.6.45
**Environment:** http://localhost:8080 (Local Development)

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Segments | 22 |
| Segments with Convergence | 8 |
| Convergence Rate | 36.4% |

### Flow Type Breakdown

| Flow Type | Count |
|-----------|-------|
| overtake | 5 |
| merge | 2 |
| diverge | 1 |
"""
    else:  # refactored
        content = """# Temporal Flow Analysis Report

**Generated:** 2025-10-28 15:45:00
**Analysis Engine:** temporal_flow
**Version:** v1.6.45
**Environment:** http://localhost:8080 (Local Development)

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Segments | 22 |
| Segments with Convergence | 8 |
| Convergence Rate | 36.4% |

### Flow Type Breakdown

| Flow Type | Count |
|-----------|-------|
| overtake | 5 |
| merge | 2 |
| diverge | 1 |
"""
    
    return content

def create_dummy_flow_csv(content_type: str = "baseline") -> pd.DataFrame:
    """Create a dummy Flow CSV report for testing."""
    if content_type == "baseline":
        data = {
            'seg_id': ['A1', 'A2', 'A3', 'B1', 'B2'],
            'flow_type': ['overtake', 'merge', 'diverge', 'overtake', 'merge'],
            'has_convergence': [True, True, False, True, True],
            'total_a': [100, 150, 200, 120, 180],
            'total_b': [80, 120, 150, 100, 160],
            'overtaking_a': [20, 30, 0, 25, 35],
            'overtaking_b': [15, 25, 0, 20, 30]
        }
    else:  # refactored - different data
        data = {
            'seg_id': ['A1', 'A2', 'A3', 'B1', 'B2'],
            'flow_type': ['overtake', 'merge', 'diverge', 'overtake', 'merge'],
            'has_convergence': [True, True, False, True, True],
            'total_a': [105, 155, 205, 125, 185],  # Different values
            'total_b': [85, 125, 155, 105, 165],   # Different values
            'overtaking_a': [25, 35, 0, 30, 40],  # Different values
            'overtaking_b': [20, 30, 0, 25, 35]  # Different values
        }
    
    return pd.DataFrame(data)

def test_identical_reports():
    """Test validation with identical reports (should pass)."""
    print("🧪 Testing identical reports...")
    
    # Create identical dummy reports
    baseline_md = create_dummy_flow_md("baseline")
    refactored_md = create_dummy_flow_md("baseline")  # Same content
    
    baseline_csv = create_dummy_flow_csv("baseline")
    refactored_csv = create_dummy_flow_csv("baseline")  # Same data
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(baseline_md)
        baseline_md_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(refactored_md)
        refactored_md_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        baseline_csv.to_csv(f.name, index=False)
        baseline_csv_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        refactored_csv.to_csv(f.name, index=False)
        refactored_csv_path = f.name
    
    try:
        # Test validation
        validator = FlowReportValidator()
        
        markdown_result = validator.validate_markdown_reports(baseline_md_path, refactored_md_path)
        csv_result = validator.validate_csv_reports(baseline_csv_path, refactored_csv_path)
        
        # Check results
        if markdown_result.get('files_match', False) and csv_result.get('files_match', False):
            print("✅ Identical reports test PASSED")
            return True
        else:
            print("❌ Identical reports test FAILED")
            print(f"Markdown match: {markdown_result.get('files_match', False)}")
            print(f"CSV match: {csv_result.get('files_match', False)}")
            return False
            
    finally:
        # Cleanup
        for path in [baseline_md_path, refactored_md_path, baseline_csv_path, refactored_csv_path]:
            os.unlink(path)

def test_different_reports():
    """Test validation with different reports (should fail)."""
    print("🧪 Testing different reports...")
    
    # Create different dummy reports
    baseline_md = create_dummy_flow_md("baseline")
    refactored_md = create_dummy_flow_md("refactored")
    
    baseline_csv = create_dummy_flow_csv("baseline")
    refactored_csv = create_dummy_flow_csv("refactored")
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(baseline_md)
        baseline_md_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(refactored_md)
        refactored_md_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        baseline_csv.to_csv(f.name, index=False)
        baseline_csv_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        refactored_csv.to_csv(f.name, index=False)
        refactored_csv_path = f.name
    
    try:
        # Test validation
        validator = FlowReportValidator()
        
        markdown_result = validator.validate_markdown_reports(baseline_md_path, refactored_md_path)
        csv_result = validator.validate_csv_reports(baseline_csv_path, refactored_csv_path)
        
        # Check results
        if not markdown_result.get('files_match', True) and not csv_result.get('files_match', True):
            print("✅ Different reports test PASSED")
            return True
        else:
            print("❌ Different reports test FAILED")
            print(f"Markdown match: {markdown_result.get('files_match', False)}")
            print(f"CSV match: {csv_result.get('files_match', False)}")
            return False
            
    finally:
        # Cleanup
        for path in [baseline_md_path, refactored_md_path, baseline_csv_path, refactored_csv_path]:
            os.unlink(path)

def main():
    """Run all tests."""
    print("🚀 Starting Flow Report Validation Utility Tests\n")
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Identical reports
    if test_identical_reports():
        tests_passed += 1
    
    print()
    
    # Test 2: Different reports
    if test_different_reports():
        tests_passed += 1
    
    print(f"\n📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Flow validation utility is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the validation utility.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
