#!/usr/bin/env python3
"""
Test script for density report validation

This script creates test reports to verify the validation script works correctly.
"""

import tempfile
from pathlib import Path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from validate_density_refactoring import DensityReportComparator


def create_test_reports():
    """Create test reports for validation testing."""
    
    # Test report content
    baseline_content = """# Density Analysis Report

## Executive Summary
- Peak Density: 0.755 p/m²
- Peak Rate: 11.31 p/s
- Segments with Flags: 17 / 28
- Flagged Bins: 1,875
- Total Participants: 1,898

## Start Times
- Full Marathon: 07:00 (368 participants)
- Half Marathon: 07:40 (912 participants)
- 10K: 07:20 (618 participants)

## Methodology
- Window size: 2.0 minutes
- Bin size: 0.2 km
- Total Segments Analyzed: 28

### Segment A1: Start to Queen/Regent
- Peak Density: 0.755 p/m²
- Level of Service: D
- Peak Rate: 11.31 p/s
- Flagged: Yes

### Segment A2: Queen/Regent to WSB mid-point
- Peak Density: 0.469 p/m²
- Level of Service: B
- Peak Rate: 6.61 p/s
- Flagged: Yes
"""

    # Identical content (should pass validation)
    identical_content = baseline_content
    
    # Different content (should fail validation)
    different_content = baseline_content.replace("0.755", "0.756").replace("11.31", "11.32")
    
    return baseline_content, identical_content, different_content


def test_validation_script():
    """Test the validation script with sample data."""
    
    print("🧪 Testing density report validation script...")
    
    # Create test reports
    baseline_content, identical_content, different_content = create_test_reports()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Identical reports (should pass)
        print("\n📋 Test 1: Identical reports (should PASS)")
        baseline_file = temp_path / "baseline.md"
        identical_file = temp_path / "identical.md"
        
        baseline_file.write_text(baseline_content)
        identical_file.write_text(identical_content)
        
        comparator = DensityReportComparator(str(baseline_file), str(identical_file))
        success = comparator.run_comparison()
        
        if success:
            print("✅ Test 1 PASSED: Identical reports validated correctly")
        else:
            print("❌ Test 1 FAILED: Identical reports should have passed")
        
        # Test 2: Different reports (should fail)
        print("\n📋 Test 2: Different reports (should FAIL)")
        different_file = temp_path / "different.md"
        different_file.write_text(different_content)
        
        comparator = DensityReportComparator(str(baseline_file), str(different_file))
        success = comparator.run_comparison()
        
        if not success:
            print("✅ Test 2 PASSED: Different reports correctly identified as different")
        else:
            print("❌ Test 2 FAILED: Different reports should have failed validation")
    
    print("\n🎉 Validation script testing complete!")


if __name__ == "__main__":
    test_validation_script()
