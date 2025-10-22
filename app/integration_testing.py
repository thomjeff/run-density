"""
Integration Testing Module

Provides comprehensive testing for API endpoints and report generation.
This is Tier 2 testing - thorough validation without heavy computation.

Usage:
    python3 -m app.integration_testing
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import requests
from fastapi.testclient import TestClient

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app


class IntegrationTester:
    """Integration testing for API endpoints and report generation."""
    
    def __init__(self):
        self.client = TestClient(app)
        self.results = {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "duration": 0,
            "tests": []
        }
    
    def run_test(self, test_name: str, test_func) -> bool:
        """Run a single test and record results."""
        self.results["total"] += 1
        start_time = time.time()
        
        try:
            result = test_func()
            duration = time.time() - start_time
            
            if result:
                self.results["passed"] += 1
                self.results["tests"].append({
                    "name": test_name,
                    "status": "✅ PASS",
                    "duration": f"{duration:.2f}s"
                })
                print(f"✅ {test_name} - {duration:.2f}s")
                return True
            else:
                self.results["failed"] += 1
                self.results["tests"].append({
                    "name": test_name,
                    "status": "❌ FAIL",
                    "duration": f"{duration:.2f}s"
                })
                print(f"❌ {test_name} - {duration:.2f}s")
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.results["failed"] += 1
            self.results["tests"].append({
                "name": test_name,
                "status": f"❌ ERROR: {str(e)}",
                "duration": f"{duration:.2f}s"
            })
            print(f"❌ {test_name} - ERROR: {str(e)} - {duration:.2f}s")
            return False
    
    def test_all_endpoints(self) -> bool:
        """Test all API endpoints."""
        endpoints = [
            ("/health", "GET", None),
            ("/ready", "GET", None),
            ("/api/density-report", "POST", {
                "paceCsv": "data/runners.csv",
                "segmentsCsv": "data/segments.csv",
                "startTimes": {"Full": 420, "10K": 440, "Half": 460},
                "stepKm": 0.1,
                "timeWindow": 120
            }),
            ("/api/temporal-flow-report", "POST", {
                "paceCsv": "data/runners.csv",
                "segmentsCsv": "data/segments.csv",
                "startTimes": {"Full": 420, "10K": 440, "Half": 460},
                "minOverlapDuration": 10,
                "conflictLengthM": 100
            }),
            ("/api/temporal-flow", "POST", {
                "paceCsv": "data/runners.csv",
                "segmentsCsv": "data/segments.csv",
                "startTimes": {"Full": 420, "10K": 440, "Half": 460},
                "minOverlapDuration": 10,
                "conflictLengthM": 100
            }),
            ("/api/flow-density-correlation", "POST", {
                "paceCsv": "data/runners.csv",
                "segmentsCsv": "data/segments.csv",
                "startTimes": {"Full": 420, "10K": 440, "Half": 460},
                "minOverlapDuration": 10,
                "conflictLengthM": 100,
                "stepKm": 0.1,
                "timeWindow": 120
            })
        ]
        
        for endpoint, method, data in endpoints:
            if method == "GET":
                response = self.client.get(endpoint)
            else:
                response = self.client.post(endpoint, json=data)
            
            if response.status_code != 200:
                print(f"  ❌ {endpoint} returned {response.status_code}")
                return False
        
        return True
    
    def test_report_content_quality(self) -> bool:
        """Test report content quality."""
        # Test density report
        response = self.client.post("/api/density-report", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "stepKm": 0.1,
            "timeWindow": 120
        })
        
        if response.status_code != 200:
            return False
        
        data = response.json()
        if "markdown_content" not in data:
            return False
        
        content = data["markdown_content"]
        
        # Check for essential content
        required_sections = [
            "# Density Analysis Report",
            "## Summary",
            "## Segment Analysis",
            "Total Segments:"
        ]
        
        for section in required_sections:
            if section not in content:
                print(f"  ❌ Missing section: {section}")
                return False
        
        return True
    
    def test_flow_report_content_quality(self) -> bool:
        """Test flow report content quality."""
        # Test flow report
        response = self.client.post("/api/temporal-flow-report", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "minOverlapDuration": 10,
            "conflictLengthM": 100
        })
        
        if response.status_code != 200:
            return False
        
        data = response.json()
        if "markdown_content" not in data or "csv_content" not in data:
            return False
        
        markdown_content = data["markdown_content"]
        csv_content = data["csv_content"]
        
        # Check for essential content
        required_sections = [
            "# Temporal Flow Analysis Report",
            "## Summary",
            "## Segment Analysis",
            "Total Segments:"
        ]
        
        for section in required_sections:
            if section not in markdown_content:
                print(f"  ❌ Missing section: {section}")
                return False
        
        # Check CSV content
        if len(csv_content) < 100:  # Should have substantial content
            print("  ❌ CSV content too short")
            return False
        
        return True
    
    def test_correlation_endpoint(self) -> bool:
        """Test flow-density correlation endpoint."""
        response = self.client.post("/api/flow-density-correlation", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "minOverlapDuration": 10,
            "conflictLengthM": 100,
            "stepKm": 0.1,
            "timeWindow": 120
        })
        
        if response.status_code != 200:
            return False
        
        data = response.json()
        required_fields = [
            "ok", "engine", "timestamp", "flow_summary", 
            "density_summary", "correlations", "total_correlations"
        ]
        
        for field in required_fields:
            if field not in data:
                print(f"  ❌ Missing field: {field}")
                return False
        
        return True
    
    def test_error_handling(self) -> bool:
        """Test error handling with invalid data."""
        # Test with invalid CSV path
        response = self.client.post("/api/density-report", json={
            "paceCsv": "data/nonexistent.csv",
            "segmentsCsv": "data/segments.csv",
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "stepKm": 0.1,
            "timeWindow": 120
        })
        
        # Should return an error status
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                print("  ❌ Should have failed with invalid CSV")
                return False
        
        return True
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        print("=== INTEGRATION TESTING (Tier 2) ===")
        print("Comprehensive API and report validation")
        print()
        
        start_time = time.time()
        
        # API endpoint tests
        self.run_test("All API Endpoints", self.test_all_endpoints)
        self.run_test("Density Report Content Quality", self.test_report_content_quality)
        self.run_test("Flow Report Content Quality", self.test_flow_report_content_quality)
        self.run_test("Flow-Density Correlation", self.test_correlation_endpoint)
        self.run_test("Error Handling", self.test_error_handling)
        
        self.results["duration"] = time.time() - start_time
        
        # Print summary
        print()
        print("=== INTEGRATION TEST SUMMARY ===")
        print(f"Total Tests: {self.results['total']}")
        print(f"Passed: {self.results['passed']} ✅")
        print(f"Failed: {self.results['failed']} ❌")
        print(f"Duration: {self.results['duration']:.2f}s")
        print(f"Success Rate: {(self.results['passed']/self.results['total']*100):.1f}%")
        
        if self.results['failed'] == 0:
            print("🎉 ALL INTEGRATION TESTS PASSED!")
            return True
        else:
            print("⚠️  Some integration tests failed")
            return False


def main():
    """Main integration testing entry point."""
    tester = IntegrationTester()
    success = tester.run_integration_tests()
    sys.exit(0 if success else 1)


# ----------------------------------------------------------------------
# QA Validation Test for Issue #304
# Ensures overtaking and co-presence metrics are exported correctly
# ----------------------------------------------------------------------

def test_overtaking_and_copresence_metrics_exist_and_are_int():
    """
    Validates that overtaking_segments and co_presence_segments
    exist in the exported summary JSON and contain integer values.
    This test enforces regression protection for Issue #304.
    """
    import os
    import json
    
    # Determine artifact directory (supports Local + Cloud)
    artifact_dir = os.environ.get("RUNFLOW_ARTIFACT_DIR", "./artifacts")
    summary_path = os.path.join(artifact_dir, "latest.json")

    # Ensure file exists
    assert os.path.exists(summary_path), f"Summary file not found at {summary_path}"

    # Load summary JSON
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # --- Required keys must exist ---
    assert "overtaking_segments" in summary, "Missing 'overtaking_segments' key in summary export"
    assert "co_presence_segments" in summary, "Missing 'co_presence_segments' key in summary export"

    # --- Values must be integers ---
    overtaking_val = summary["overtaking_segments"]
    copresence_val = summary["co_presence_segments"]

    assert isinstance(overtaking_val, int), f"Expected int for overtaking_segments, got {type(overtaking_val)}"
    assert isinstance(copresence_val, int), f"Expected int for co_presence_segments, got {type(copresence_val)}"

    # --- Values should be non-negative ---
    assert overtaking_val >= 0, "overtaking_segments should be >= 0"
    assert copresence_val >= 0, "co_presence_segments should be >= 0"

    # Optional sanity log
    print(f"[QA] overtaking_segments={overtaking_val}, co_presence_segments={copresence_val}")


if __name__ == "__main__":
    main()
