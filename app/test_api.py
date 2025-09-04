#!/usr/bin/env python3
"""
Test API Endpoints
==================

FastAPI endpoints for running tests and retrieving test results.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from tests.test_runner import TestRunner, TestResult

# Create router
test_router = APIRouter(prefix="/api/tests", tags=["tests"])

# Global test runner instance
test_runner = TestRunner()

class TestRequest(BaseModel):
    test_id: str
    save_report: bool = False

class TestResponse(BaseModel):
    test_id: str
    status: str
    message: str
    details: Dict[str, Any]
    execution_time: float
    timestamp: str

class TestListResponse(BaseModel):
    available_tests: List[str]
    total_tests: int

class TestReportResponse(BaseModel):
    summary: Dict[str, Any]
    results: List[Dict[str, Any]]

@test_router.get("/list", response_model=TestListResponse)
async def list_tests():
    """List all available test IDs"""
    try:
        available_tests = test_runner.list_tests()
        return TestListResponse(
            available_tests=available_tests,
            total_tests=len(available_tests)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tests: {str(e)}")

@test_router.post("/run", response_model=TestResponse)
async def run_test(request: TestRequest, background_tasks: BackgroundTasks):
    """Run a specific test by ID"""
    try:
        result = test_runner.run_test(request.test_id)
        
        # Save report in background if requested
        if request.save_report:
            background_tasks.add_task(save_test_report, result)
        
        return TestResponse(**result.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run test: {str(e)}")

@test_router.post("/run-all", response_model=TestReportResponse)
async def run_all_tests(background_tasks: BackgroundTasks, save_report: bool = False):
    """Run all available tests"""
    try:
        results = test_runner.run_all_tests()
        report = test_runner.generate_report(results)
        
        # Save report in background if requested
        if save_report:
            background_tasks.add_task(save_test_report, report)
        
        return TestReportResponse(**report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run all tests: {str(e)}")

@test_router.get("/health")
async def test_health():
    """Health check for test API"""
    try:
        available_tests = test_runner.list_tests()
        return {
            "status": "healthy",
            "available_tests": len(available_tests),
            "test_runner_initialized": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test API health check failed: {str(e)}")

@test_router.get("/status/{test_id}")
async def get_test_status(test_id: str):
    """Get the status of a specific test (if it was recently run)"""
    try:
        # Check if test exists
        if test_id not in test_runner.list_tests():
            raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")
        
        # For now, just return that the test exists
        # In a more sophisticated implementation, we could track test history
        return {
            "test_id": test_id,
            "status": "available",
            "message": "Test is available for execution"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get test status: {str(e)}")

def save_test_report(result_or_report: Any) -> None:
    """Background task to save test report"""
    try:
        if isinstance(result_or_report, TestResult):
            # Single test result
            report = test_runner.generate_report([result_or_report])
        else:
            # Full report
            report = result_or_report
        
        test_runner.save_report(report)
    except Exception as e:
        print(f"Failed to save test report: {e}")

# Additional utility endpoints

@test_router.get("/temporal-flow/quick-check")
async def temporal_flow_quick_check():
    """Quick check of temporal flow functionality"""
    try:
        result = test_runner.run_test("temporal_flow_smoke")
        return {
            "test_id": "temporal_flow_smoke",
            "status": result.status,
            "message": result.message,
            "execution_time": result.execution_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal flow quick check failed: {str(e)}")

@test_router.get("/density/quick-check")
async def density_quick_check():
    """Quick check of density functionality"""
    try:
        result = test_runner.run_test("density_smoke")
        return {
            "test_id": "density_smoke",
            "status": result.status,
            "message": result.message,
            "execution_time": result.execution_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Density quick check failed: {str(e)}")

@test_router.get("/comprehensive/validation")
async def comprehensive_validation():
    """Run comprehensive validation of both temporal flow and density"""
    try:
        # Run both comprehensive tests
        flow_result = test_runner.run_test("temporal_flow_comprehensive")
        density_result = test_runner.run_test("density_comprehensive")
        
        # Determine overall status
        overall_status = "PASS" if flow_result.status == "PASS" and density_result.status == "PASS" else "FAIL"
        
        return {
            "overall_status": overall_status,
            "temporal_flow": {
                "status": flow_result.status,
                "message": flow_result.message,
                "execution_time": flow_result.execution_time
            },
            "density": {
                "status": density_result.status,
                "message": density_result.message,
                "execution_time": density_result.execution_time
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comprehensive validation failed: {str(e)}")
