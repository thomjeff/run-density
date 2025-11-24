"""
Smoke Testing Module

Provides lightweight testing for quick validation during development.
This is Tier 1 testing - fast, basic functionality validation.

Usage:
    python3 -m app.smoke_testing
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


class SmokeTester:
    """Lightweight smoke testing for quick validation."""
    
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
    
    def test_health_endpoint(self) -> bool:
        """Test health endpoint."""
        response = self.client.get("/health")
        return response.status_code == 200 and response.json().get("status") == "healthy"
    
    def test_ready_endpoint(self) -> bool:
        """Test ready endpoint."""
        response = self.client.get("/ready")
        data = response.json()
        return response.status_code == 200 and data.get("ok") == True
    
    def test_density_endpoint_basic(self) -> bool:
        """Test density endpoint with minimal data."""
        response = self.client.post("/api/density-report", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "densityCsv": "data/segments.csv",  # Required field
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "stepKm": 0.1,
            "timeWindow": 60  # Reduced for speed
        })
        return response.status_code == 200 and response.json().get("ok") == True
    
    def test_flow_endpoint_basic(self) -> bool:
        """Test flow endpoint with minimal data."""
        response = self.client.post("/api/temporal-flow", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "minOverlapDuration": 10,
            "conflictLengthM": 100
        })
        return response.status_code == 200 and response.json().get("ok") == True
    
    def test_report_generation(self) -> bool:
        """Test that reports are generated."""
        # Run a quick density analysis
        response = self.client.post("/api/density-report", json={
            "paceCsv": "data/runners.csv",
            "segmentsCsv": "data/segments.csv",
            "densityCsv": "data/segments.csv",  # Required field
            "startTimes": {"Full": 420, "10K": 440, "Half": 460},
            "stepKm": 0.1,
            "timeWindow": 60
        })
        
        if response.status_code != 200:
            return False
        
        # Check if report content is in response
        data = response.json()
        return "markdown_content" in data and len(data["markdown_content"]) > 100
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run all smoke tests."""
        print("=== SMOKE TESTING (Tier 1) ===")
        print("Quick validation for basic functionality")
        print()
        
        start_time = time.time()
        
        # Core API tests
        self.run_test("Health Endpoint", self.test_health_endpoint)
        self.run_test("Ready Endpoint", self.test_ready_endpoint)
        self.run_test("Density Endpoint (Basic)", self.test_density_endpoint_basic)
        self.run_test("Flow Endpoint (Basic)", self.test_flow_endpoint_basic)
        self.run_test("Report Generation", self.test_report_generation)
        
        self.results["duration"] = time.time() - start_time
        
        # Print summary
        print()
        print("=== SMOKE TEST SUMMARY ===")
        print(f"Total Tests: {self.results['total']}")
        print(f"Passed: {self.results['passed']} ✅")
        print(f"Failed: {self.results['failed']} ❌")
        print(f"Duration: {self.results['duration']:.2f}s")
        print(f"Success Rate: {(self.results['passed']/self.results['total']*100):.1f}%")
        
        if self.results['failed'] == 0:
            print("🎉 ALL SMOKE TESTS PASSED!")
            return True
        else:
            print("⚠️  Some smoke tests failed")
            return False


def main():
    """Main smoke testing entry point."""
    tester = SmokeTester()
    success = tester.run_smoke_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
