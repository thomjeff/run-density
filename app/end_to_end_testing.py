"""
End-to-End Testing Module

Comprehensive testing module for running full end-to-end tests through the API.
This module provides reusable functions for testing all API endpoints and report generation.

Usage:
    from app.end_to_end_testing import run_comprehensive_tests, test_api_endpoints, test_report_generation
    
    # Run all tests
    results = run_comprehensive_tests()
    
    # Run specific tests
    api_results = test_api_endpoints()
    report_results = test_report_generation()
"""

import os
import glob
from typing import Dict, List, Tuple, Any
from fastapi.testclient import TestClient
from app.main import app


def test_api_endpoints(start_times: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Test all API endpoints through main.py.
    
    Args:
        start_times: Event start times in minutes from midnight
                    Default: {'Full': 420, '10K': 440, 'Half': 460}
    
    Returns:
        Dictionary with test results for each endpoint
    """
    if start_times is None:
        start_times = {'Full': 420, '10K': 440, 'Half': 460}
    
    print("=== API ENDPOINT TESTING ===")
    print()
    
    client = TestClient(app)
    results = {}
    
    # Test health and ready endpoints
    print("1. Testing Health and Ready Endpoints...")
    health_response = client.get('/health')
    ready_response = client.get('/ready')
    
    results['health'] = {
        'status_code': health_response.status_code,
        'success': health_response.status_code == 200,
        'response': health_response.json() if health_response.status_code == 200 else None
    }
    
    results['ready'] = {
        'status_code': ready_response.status_code,
        'success': ready_response.status_code == 200,
        'response': ready_response.json() if ready_response.status_code == 200 else None
    }
    
    print(f"   /health: {health_response.status_code} {'✅' if health_response.status_code == 200 else '❌'}")
    print(f"   /ready: {ready_response.status_code} {'✅' if ready_response.status_code == 200 else '❌'}")
    print()
    
    # Test report generation endpoints
    print("2. Testing Report Generation Endpoints...")
    
    # Test density report endpoint
    density_response = client.post('/api/density-report', json={
        'paceCsv': 'data/runners.csv',
        'densityCsv': 'data/segments_new.csv',
        'startTimes': start_times
    })
    
    results['density_report'] = {
        'status_code': density_response.status_code,
        'success': density_response.status_code == 200,
        'response': density_response.json() if density_response.status_code == 200 else None
    }
    
    # Test temporal flow report endpoint
    temporal_report_response = client.post('/api/temporal-flow-report', json={
        'paceCsv': 'data/runners.csv',
        'segmentsCsv': 'data/segments_new.csv',
        'startTimes': start_times
    })
    
    results['temporal_flow_report'] = {
        'status_code': temporal_report_response.status_code,
        'success': temporal_report_response.status_code == 200,
        'response': temporal_report_response.json() if temporal_report_response.status_code == 200 else None
    }
    
    # Test temporal flow analysis endpoint
    temporal_flow_response = client.post('/api/temporal-flow', json={
        'paceCsv': 'data/runners.csv',
        'segmentsCsv': 'data/segments_new.csv',
        'startTimes': start_times
    })
    
    results['temporal_flow'] = {
        'status_code': temporal_flow_response.status_code,
        'success': temporal_flow_response.status_code == 200,
        'response': temporal_flow_response.json() if temporal_flow_response.status_code == 200 else None
    }
    
    print(f"   /api/density-report: {density_response.status_code} {'✅' if density_response.status_code == 200 else '❌'}")
    print(f"   /api/temporal-flow-report: {temporal_report_response.status_code} {'✅' if temporal_report_response.status_code == 200 else '❌'}")
    print(f"   /api/temporal-flow: {temporal_flow_response.status_code} {'✅' if temporal_flow_response.status_code == 200 else '❌'}")
    print()
    
    # Summary
    all_success = all(result['success'] for result in results.values())
    print(f"API Endpoint Testing: {'✅ ALL PASSED' if all_success else '❌ SOME FAILED'}")
    print()
    
    return results


def test_report_generation(start_times: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Test report generation by calling the modules directly.
    
    Args:
        start_times: Event start times in minutes from midnight
                    Default: {'Full': 420, '10K': 440, 'Half': 460}
    
    Returns:
        Dictionary with test results for report generation
    """
    if start_times is None:
        start_times = {'Full': 420, '10K': 440, 'Half': 460}
    
    print("=== REPORT GENERATION TESTING ===")
    print()
    
    results = {}
    
    try:
        # Test temporal flow report generation
        print("1. Testing Temporal Flow Report Generation...")
        from app.temporal_flow_report import generate_temporal_flow_report
        
        temporal_result = generate_temporal_flow_report(
            pace_csv='data/runners.csv',
            segments_csv='data/segments_new.csv',
            start_times=start_times
        )
        
        results['temporal_flow_report'] = {
            'success': temporal_result.get('ok', False),
            'result': temporal_result
        }
        
        print(f"   Temporal Flow Report: {'✅' if temporal_result.get('ok', False) else '❌'}")
        if temporal_result.get('ok', False):
            print(f"   Report Path: {temporal_result.get('report_path', 'N/A')}")
        
    except Exception as e:
        results['temporal_flow_report'] = {
            'success': False,
            'error': str(e)
        }
        print(f"   Temporal Flow Report: ❌ Error: {str(e)}")
    
    print()
    
    try:
        # Test density report generation
        print("2. Testing Density Report Generation...")
        from app.density_report import generate_density_report
        
        density_result = generate_density_report(
            pace_csv='data/runners.csv',
            density_csv='data/segments_new.csv',
            start_times=start_times
        )
        
        results['density_report'] = {
            'success': density_result.get('ok', False),
            'result': density_result
        }
        
        print(f"   Density Report: {'✅' if density_result.get('ok', False) else '❌'}")
        if density_result.get('ok', False):
            print(f"   Report Path: {density_result.get('report_path', 'N/A')}")
        
    except Exception as e:
        results['density_report'] = {
            'success': False,
            'error': str(e)
        }
        print(f"   Density Report: ❌ Error: {str(e)}")
    
    print()
    
    # Summary
    all_success = all(result['success'] for result in results.values())
    print(f"Report Generation Testing: {'✅ ALL PASSED' if all_success else '❌ SOME FAILED'}")
    print()
    
    return results


def test_report_files() -> Dict[str, Any]:
    """
    Test that report files are generated and accessible.
    
    Returns:
        Dictionary with test results for file generation
    """
    print("=== REPORT FILE TESTING ===")
    print()
    
    results = {}
    
    # Check for temporal flow markdown files
    temporal_md_files = glob.glob('reports/analysis/*_Temporal_Flow_Report.md')
    results['temporal_flow_md'] = {
        'count': len(temporal_md_files),
        'files': temporal_md_files,
        'success': len(temporal_md_files) > 0
    }
    
    # Check for temporal flow CSV files
    temporal_csv_files = glob.glob('reports/analysis/temporal_flow_analysis_*.csv')
    results['temporal_flow_csv'] = {
        'count': len(temporal_csv_files),
        'files': temporal_csv_files,
        'success': len(temporal_csv_files) > 0
    }
    
    # Check for density markdown files
    density_md_files = glob.glob('reports/analysis/*_Density_Analysis_Report.md')
    results['density_md'] = {
        'count': len(density_md_files),
        'files': density_md_files,
        'success': len(density_md_files) > 0
    }
    
    print(f"1. Temporal Flow MD files: {len(temporal_md_files)} {'✅' if len(temporal_md_files) > 0 else '❌'}")
    print(f"2. Temporal Flow CSV files: {len(temporal_csv_files)} {'✅' if len(temporal_csv_files) > 0 else '❌'}")
    print(f"3. Density Analysis MD files: {len(density_md_files)} {'✅' if len(density_md_files) > 0 else '❌'}")
    print()
    
    # Summary
    all_success = all(result['success'] for result in results.values())
    print(f"Report File Testing: {'✅ ALL PASSED' if all_success else '❌ SOME FAILED'}")
    print()
    
    return results


def test_report_content_quality() -> Dict[str, Any]:
    """
    Test the quality and content of generated reports.
    
    Returns:
        Dictionary with test results for report content quality
    """
    print("=== REPORT CONTENT QUALITY TESTING ===")
    print()
    
    results = {}
    
    # Find latest report files
    temporal_md_files = glob.glob('reports/analysis/*_Temporal_Flow_Report.md')
    density_md_files = glob.glob('reports/analysis/*_Density_Analysis_Report.md')
    
    if not temporal_md_files or not density_md_files:
        print("❌ Cannot test content quality - report files not found")
        return {'error': 'Report files not found'}
    
    latest_temporal_md = max(temporal_md_files, key=os.path.getctime)
    latest_density_md = max(density_md_files, key=os.path.getctime)
    
    # Test temporal flow report content
    print("1. Testing Temporal Flow Report Content...")
    try:
        with open(latest_temporal_md, 'r') as f:
            temporal_content = f.read()
        
        temporal_checks = {
            'Proper event names (10K Range, Half Range)': '10K Range' in temporal_content and 'Half Range' in temporal_content,
            'No generic names (Event A Range)': 'Event A Range' not in temporal_content and 'Event B Range' not in temporal_content,
            'No NaN values': 'nan =' not in temporal_content
        }
        
        results['temporal_flow'] = temporal_checks
        
        for check, result in temporal_checks.items():
            print(f"   {check}: {'✅' if result else '❌'}")
        
    except Exception as e:
        results['temporal_flow'] = {'error': str(e)}
        print(f"   ❌ Error reading temporal flow report: {str(e)}")
    
    print()
    
    # Test density report content
    print("2. Testing Density Analysis Report Content...")
    try:
        with open(latest_density_md, 'r') as f:
            density_content = f.read()
        
        density_checks = {
            'Proper segment names (A1a: Start to Queen/Regent)': 'A1a: Start to Queen/Regent' in density_content,
            'No unknown segments': 'Unknown:' not in density_content,
            'Proper counts (Total Segments: 20)': '**Total Segments:** 20' in density_content and '**Processed Segments:** 20' in density_content
        }
        
        results['density'] = density_checks
        
        for check, result in density_checks.items():
            print(f"   {check}: {'✅' if result else '❌'}")
        
    except Exception as e:
        results['density'] = {'error': str(e)}
        print(f"   ❌ Error reading density report: {str(e)}")
    
    print()
    
    # Overall quality assessment
    all_checks = []
    for category in results.values():
        if isinstance(category, dict) and 'error' not in category:
            all_checks.extend(category.values())
    
    overall_quality = all(all_checks) if all_checks else False
    print(f"Overall Report Quality: {'✅ EXCELLENT' if overall_quality else '❌ ISSUES FOUND'}")
    print()
    
    return results


def run_comprehensive_tests(start_times: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Run comprehensive end-to-end tests including API endpoints, report generation, and content quality.
    
    Args:
        start_times: Event start times in minutes from midnight
                    Default: {'Full': 420, '10K': 440, 'Half': 460}
    
    Returns:
        Dictionary with all test results
    """
    if start_times is None:
        start_times = {'Full': 420, '10K': 440, 'Half': 460}
    
    print("=== COMPREHENSIVE END-TO-END TESTING ===")
    print("Testing all API endpoints and report generation")
    print()
    
    # Run all test categories
    api_results = test_api_endpoints(start_times)
    report_generation_results = test_report_generation(start_times)
    report_file_results = test_report_files()
    content_quality_results = test_report_content_quality()
    
    # Combine all results
    all_results = {
        'api_endpoints': api_results,
        'report_generation': report_generation_results,
        'report_files': report_file_results,
        'content_quality': content_quality_results
    }
    
    # Overall success assessment
    api_success = all(result['success'] for result in api_results.values())
    report_gen_success = all(result['success'] for result in report_generation_results.values())
    report_file_success = all(result['success'] for result in report_file_results.values())
    
    # Content quality success (check if any checks exist and all pass)
    content_checks = []
    for category in content_quality_results.values():
        if isinstance(category, dict) and 'error' not in category:
            content_checks.extend(category.values())
    content_quality_success = all(content_checks) if content_checks else False
    
    overall_success = api_success and report_gen_success and report_file_success and content_quality_success
    
    print("=== FINAL SUMMARY ===")
    print(f"API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"Report Generation: {'✅ PASSED' if report_gen_success else '❌ FAILED'}")
    print(f"Report Files: {'✅ PASSED' if report_file_success else '❌ FAILED'}")
    print(f"Content Quality: {'✅ PASSED' if content_quality_success else '❌ FAILED'}")
    print()
    
    if overall_success:
        print("🎉 ALL TESTS PASSED! System is ready for production!")
    else:
        print("⚠️  Some tests failed - review before production deployment")
    
    print()
    print("=== END-TO-END TESTING COMPLETE ===")
    
    return all_results


if __name__ == "__main__":
    # Run comprehensive tests when module is executed directly
    results = run_comprehensive_tests()
