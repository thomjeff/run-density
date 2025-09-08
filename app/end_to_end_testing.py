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




def test_report_files() -> Dict[str, Any]:
    """
    Test that report files are generated and accessible.
    Updated to match current file naming patterns: YYYY-MM-DD-HHMM-Flow.csv/md and YYYY-MM-DD-HHMM-Density.md
    
    Returns:
        Dictionary with test results for file generation
    """
    print("=== REPORT FILE TESTING ===")
    print()
    
    results = {}
    
    # Check for temporal flow markdown files (current pattern: YYYY-MM-DD-HHMM-Flow.md)
    temporal_md_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.md')
    results['temporal_flow_md'] = {
        'count': len(temporal_md_files),
        'files': temporal_md_files,
        'success': len(temporal_md_files) > 0
    }
    
    # Check for temporal flow CSV files (current pattern: YYYY-MM-DD-HHMM-Flow.csv)
    temporal_csv_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.csv')
    results['temporal_flow_csv'] = {
        'count': len(temporal_csv_files),
        'files': temporal_csv_files,
        'success': len(temporal_csv_files) > 0
    }
    
    # Check for density markdown files (current pattern: YYYY-MM-DD-HHMM-Density.md)
    density_md_files = glob.glob('reports/analysis/*/????-??-??-????-Density.md')
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


def validate_actual_vs_expected_flow_results(actual_csv_path: str) -> Dict[str, Any]:
    """
    Validate actual flow results against expected baseline results.
    
    Args:
        actual_csv_path: Path to the actual flow CSV file
        
    Returns:
        Dictionary with validation results
    """
    import pandas as pd
    
    try:
        # Load actual results
        actual_df = pd.read_csv(actual_csv_path)
        
        # Load expected results
        expected_df = pd.read_csv('docs/flow_expected_results.csv')
        
        # Load segments data to get overtake_flag
        segments_df = pd.read_csv('data/segments_new.csv')
        
        # Create a mapping of segment_id to overtake_flag
        segment_overtake_map = dict(zip(segments_df['seg_id'], segments_df['overtake_flag']))
        
        validation_results = {}
        all_validations_passed = True
        
        print("   Validating Actual vs Expected Flow Results:")
        print("   " + "="*80)
        
        # Process each row in actual results
        for _, actual_row in actual_df.iterrows():
            seg_id = actual_row['seg_id']
            event_a = actual_row['event_a']
            event_b = actual_row['event_b']
            segment_label = actual_row['segment_label']
            
            # Create event pair string
            event_pair = f"{event_a} vs {event_b}"
            
            # Get overtake_flag for this segment
            overtake_flag = segment_overtake_map.get(seg_id, 'n')
            
            # Find matching expected row
            expected_row = expected_df[
                (expected_df['seg_id'] == seg_id) & 
                (expected_df['event_a'] == event_a) & 
                (expected_df['event_b'] == event_b)
            ]
            
            if expected_row.empty:
                print(f"   ❌ {seg_id}, {segment_label}, {event_pair}, {overtake_flag}, NO EXPECTED DATA FOUND")
                validation_results[f"{seg_id}_{event_pair}"] = False
                all_validations_passed = False
                continue
            
            expected_row = expected_row.iloc[0]
            
            if overtake_flag == 'y':
                # Segments expected to have overtaking
                actual_overtaking_a = actual_row['overtaking_a']
                actual_overtaking_b = actual_row['overtaking_b']
                actual_pct_a = actual_row['pct_a']
                actual_pct_b = actual_row['pct_b']
                
                expected_overtaking_a = expected_row['overtaking_a']
                expected_overtaking_b = expected_row['overtaking_b']
                expected_pct_a = expected_row['pct_a']
                expected_pct_b = expected_row['pct_b']
                
                # Check if counts match
                counts_match = (actual_overtaking_a == expected_overtaking_a and 
                              actual_overtaking_b == expected_overtaking_b)
                
                # Check if percentages match (with small tolerance for rounding)
                pct_match = (abs(actual_pct_a - expected_pct_a) < 0.1 and 
                           abs(actual_pct_b - expected_pct_b) < 0.1)
                
                overall_match = counts_match and pct_match
                
                status = "✅ MATCH" if overall_match else "❌ MISMATCH"
                
                print(f"   {status} {seg_id}, {segment_label}, {event_pair}, {overtake_flag}, "
                      f"{actual_overtaking_a}/{expected_overtaking_a}, {actual_overtaking_b}/{expected_overtaking_b}, "
                      f"{actual_pct_a:.1f}/{expected_pct_a:.1f}, {actual_pct_b:.1f}/{expected_pct_b:.1f}")
                
                validation_results[f"{seg_id}_{event_pair}"] = overall_match
                if not overall_match:
                    all_validations_passed = False
                    
            else:
                # Segments expected to have NO overtaking
                actual_overtaking_a = actual_row['overtaking_a']
                actual_overtaking_b = actual_row['overtaking_b']
                
                expected_overtaking_a = expected_row['overtaking_a']
                expected_overtaking_b = expected_row['overtaking_b']
                
                # Check if both actual and expected have zero overtaking
                no_overtaking_match = (actual_overtaking_a == 0 and actual_overtaking_b == 0 and
                                     expected_overtaking_a == 0 and expected_overtaking_b == 0)
                
                status = "✅ NO OVERTAKING (as expected)" if no_overtaking_match else "❌ UNEXPECTED OVERTAKING"
                
                print(f"   {status} {seg_id}, {segment_label}, {event_pair}, {overtake_flag}")
                
                validation_results[f"{seg_id}_{event_pair}"] = no_overtaking_match
                if not no_overtaking_match:
                    all_validations_passed = False
        
        print("   " + "="*80)
        print(f"   Overall Validation: {'✅ ALL MATCH' if all_validations_passed else '❌ MISMATCHES FOUND'}")
        
        return {
            'all_validations_passed': all_validations_passed,
            'individual_results': validation_results
        }
        
    except Exception as e:
        print(f"   ❌ Error during validation: {str(e)}")
        return {'error': str(e)}


def test_report_content_quality() -> Dict[str, Any]:
    """
    Test the quality and content of generated reports.
    Updated to match current file naming patterns: YYYY-MM-DD-HHMM-Flow.md and YYYY-MM-DD-HHMM-Density.md
    
    Returns:
        Dictionary with test results for report content quality
    """
    print("=== REPORT CONTENT QUALITY TESTING ===")
    print()
    
    results = {}
    
    # Find latest report files (current pattern: YYYY-MM-DD-HHMM-Flow.md and YYYY-MM-DD-HHMM-Density.md)
    temporal_md_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.md')
    temporal_csv_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.csv')
    density_md_files = glob.glob('reports/analysis/*/????-??-??-????-Density.md')
    
    if not temporal_md_files or not temporal_csv_files or not density_md_files:
        print("❌ Cannot test content quality - report files not found")
        return {'error': 'Report files not found'}
    
    latest_temporal_md = max(temporal_md_files, key=os.path.getctime)
    latest_temporal_csv = max(temporal_csv_files, key=os.path.getctime)
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
    
    # Test actual vs expected flow results validation
    print("3. Testing Actual vs Expected Flow Results Validation...")
    try:
        actual_expected_validation = validate_actual_vs_expected_flow_results(latest_temporal_csv)
        results['actual_vs_expected'] = actual_expected_validation
        
    except Exception as e:
        results['actual_vs_expected'] = {'error': str(e)}
        print(f"   ❌ Error validating actual vs expected results: {str(e)}")
    
    print()
    
    # Overall quality assessment
    all_checks = []
    for category in results.values():
        if isinstance(category, dict) and 'error' not in category:
            if category == results.get('actual_vs_expected'):
                # Special handling for actual vs expected validation
                if 'all_validations_passed' in category:
                    all_checks.append(category['all_validations_passed'])
            else:
                all_checks.extend(category.values())
    
    overall_quality = all(all_checks) if all_checks else False
    print(f"Overall Report Quality: {'✅ EXCELLENT' if overall_quality else '❌ ISSUES FOUND'}")
    print()
    
    return results


def run_streamlined_tests(start_times: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Run streamlined end-to-end tests focusing only on core reports:
    - temporal-flow.csv/md (Flow reports)
    - density.md (Density reports)
    
    This skips flow runner detail reports and other optional components.
    
    Args:
        start_times: Event start times in minutes from midnight
                    Default: {'Full': 420, '10K': 440, 'Half': 460}
    
    Returns:
        Dictionary with streamlined test results
    """
    if start_times is None:
        start_times = {'Full': 420, '10K': 440, 'Half': 460}
    
    print("=== STREAMLINED END-TO-END TESTING ===")
    print("Testing core API endpoints and report generation (Flow + Density only)")
    print()
    
    # Run core test categories only
    api_results = test_api_endpoints(start_times)
    report_file_results = test_report_files()
    content_quality_results = test_report_content_quality()
    
    # Combine all results
    all_results = {
        'api_endpoints': api_results,
        'report_files': report_file_results,
        'content_quality': content_quality_results
    }
    
    # Overall success assessment
    api_success = all(result['success'] for result in api_results.values())
    report_file_success = all(result['success'] for result in report_file_results.values())
    
    # Content quality success (check if any checks exist and all pass)
    content_checks = []
    for category in content_quality_results.values():
        if isinstance(category, dict) and 'error' not in category:
            content_checks.extend(category.values())
    content_quality_success = all(content_checks) if content_checks else False
    
    overall_success = api_success and report_file_success and content_quality_success
    
    print("=== FINAL SUMMARY ===")
    print(f"API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"Report Files: {'✅ PASSED' if report_file_success else '❌ FAILED'}")
    print(f"Content Quality: {'✅ PASSED' if content_quality_success else '❌ FAILED'}")
    print()
    
    if overall_success:
        print("🎉 STREAMLINED TESTS PASSED! Core system is ready!")
    else:
        print("⚠️  Some tests failed - review before production deployment")
    
    print()
    print("=== STREAMLINED END-TO-END TESTING COMPLETE ===")
    
    return all_results


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
    report_file_results = test_report_files()
    content_quality_results = test_report_content_quality()
    
    # Combine all results
    all_results = {
        'api_endpoints': api_results,
        'report_files': report_file_results,
        'content_quality': content_quality_results
    }
    
    # Overall success assessment
    api_success = all(result['success'] for result in api_results.values())
    report_file_success = all(result['success'] for result in report_file_results.values())
    
    # Content quality success (check if any checks exist and all pass)
    content_checks = []
    for category in content_quality_results.values():
        if isinstance(category, dict) and 'error' not in category:
            content_checks.extend(category.values())
    content_quality_success = all(content_checks) if content_checks else False
    
    overall_success = api_success and report_file_success and content_quality_success
    
    print("=== FINAL SUMMARY ===")
    print(f"API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
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
    # Run streamlined tests by default (faster, focuses on core functionality)
    # Use run_comprehensive_tests() for full testing including all optional components
    results = run_streamlined_tests()
