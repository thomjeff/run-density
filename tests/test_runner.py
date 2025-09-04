#!/usr/bin/env python3
"""
Test Runner Framework for Run-Density Analysis
==============================================

A comprehensive test framework that provides:
- Test ID-based execution
- API integration
- Reusable test cases
- Structured reporting
- Frontend UI integration

Usage:
    python tests/test_runner.py --test-id temporal_flow_convergence
    python tests/test_runner.py --test-id density_comprehensive
    python tests/test_runner.py --list-tests
    python tests/test_runner.py --run-all
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

class TestResult:
    """Test result data structure"""
    def __init__(self, test_id: str, status: str, message: str = "", 
                 details: Dict[str, Any] = None, execution_time: float = 0.0):
        self.test_id = test_id
        self.status = status  # "PASS", "FAIL", "ERROR"
        self.message = message
        self.details = details or {}
        self.execution_time = execution_time
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp
        }

class TestRunner:
    """Main test runner class"""
    
    def __init__(self):
        self.test_registry: Dict[str, callable] = {}
        self.results: List[TestResult] = []
        self.register_tests()
    
    def register_tests(self):
        """Register all available tests"""
        # Import test modules
        from tests.temporal_flow_tests import TemporalFlowTests
        from tests.density_tests import DensityTests
        
        # Register test suites
        temporal_flow_tests = TemporalFlowTests()
        density_tests = DensityTests()
        
        # Register individual tests
        self.test_registry.update({
            "temporal_flow_convergence": temporal_flow_tests.test_convergence_segments,
            "temporal_flow_comprehensive": temporal_flow_tests.test_comprehensive_validation,
            "temporal_flow_comparison_csv": temporal_flow_tests.test_comprehensive_comparison_csv,
            "temporal_flow_smoke": temporal_flow_tests.test_smoke,
            "density_comprehensive": density_tests.test_comprehensive_density,
            "density_validation": density_tests.test_density_validation,
            "density_smoke": density_tests.test_smoke,
        })
    
    def list_tests(self) -> List[str]:
        """List all available test IDs"""
        return list(self.test_registry.keys())
    
    def run_test(self, test_id: str) -> TestResult:
        """Run a specific test by ID"""
        if test_id not in self.test_registry:
            return TestResult(
                test_id=test_id,
                status="ERROR",
                message=f"Test '{test_id}' not found. Available tests: {', '.join(self.list_tests())}"
            )
        
        print(f"🧪 Running test: {test_id}")
        start_time = time.time()
        
        try:
            # Run the test
            test_func = self.test_registry[test_id]
            result = test_func()
            
            execution_time = time.time() - start_time
            
            # Convert to TestResult if needed
            if isinstance(result, TestResult):
                result.execution_time = execution_time
                return result
            elif isinstance(result, dict):
                return TestResult(
                    test_id=test_id,
                    status=result.get("status", "PASS"),
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                    execution_time=execution_time
                )
            else:
                return TestResult(
                    test_id=test_id,
                    status="PASS" if result else "FAIL",
                    message="Test completed",
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return TestResult(
                test_id=test_id,
                status="ERROR",
                message=f"Test execution failed: {str(e)}",
                details={"error": str(e), "traceback": str(e)},
                execution_time=execution_time
            )
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all registered tests"""
        print("🚀 Running all tests...")
        results = []
        
        for test_id in self.list_tests():
            result = self.run_test(test_id)
            results.append(result)
            self.results.append(result)
            
            # Print result
            status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}
            emoji = status_emoji.get(result.status, "❓")
            print(f"  {emoji} {test_id}: {result.status} ({result.execution_time:.2f}s)")
            if result.message:
                print(f"     {result.message}")
        
        return results
    
    def generate_report(self, results: List[TestResult] = None) -> Dict[str, Any]:
        """Generate a comprehensive test report"""
        if results is None:
            results = self.results
        
        total_tests = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errors = sum(1 for r in results if r.status == "ERROR")
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "success_rate": (passed / total_tests * 100) if total_tests > 0 else 0,
                "timestamp": datetime.now().isoformat()
            },
            "results": [r.to_dict() for r in results]
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save test report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_report_{timestamp}.json"
        
        # Ensure results directory exists
        results_dir = Path("results/test_runs")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = results_dir / filename
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Test report saved to: {filepath}")
        return filepath

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Run-Density Test Runner")
    parser.add_argument("--test-id", help="Run specific test by ID")
    parser.add_argument("--list-tests", action="store_true", help="List all available tests")
    parser.add_argument("--run-all", action="store_true", help="Run all tests")
    parser.add_argument("--save-report", action="store_true", help="Save test report to file")
    parser.add_argument("--output", help="Output file for report")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.list_tests:
        print("📋 Available tests:")
        for test_id in runner.list_tests():
            print(f"  - {test_id}")
        return
    
    if args.run_all:
        results = runner.run_all_tests()
        report = runner.generate_report(results)
        
        print(f"\n📊 Test Summary:")
        print(f"  Total: {report['summary']['total_tests']}")
        print(f"  Passed: {report['summary']['passed']}")
        print(f"  Failed: {report['summary']['failed']}")
        print(f"  Errors: {report['summary']['errors']}")
        print(f"  Success Rate: {report['summary']['success_rate']:.1f}%")
        
        if args.save_report:
            runner.save_report(report, args.output)
    
    elif args.test_id:
        result = runner.run_test(args.test_id)
        print(f"\n📊 Test Result:")
        print(f"  Status: {result.status}")
        print(f"  Message: {result.message}")
        print(f"  Execution Time: {result.execution_time:.2f}s")
        
        if result.details:
            print(f"  Details: {json.dumps(result.details, indent=2)}")
        
        if args.save_report:
            report = runner.generate_report([result])
            runner.save_report(report, args.output)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
