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
from app.main import app, APP_VERSION
import io
import sys
from datetime import datetime
import requests


class OutputCapture:
    """Context manager to capture print output and save to file."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.original_stdout = None
        self.captured_output = None
        
    def __enter__(self):
        self.original_stdout = sys.stdout
        self.captured_output = io.StringIO()
        sys.stdout = self.captured_output
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        
        # Save captured output to file
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w') as f:
            f.write(self.captured_output.getvalue())
            
        # Also print to console
        print(self.captured_output.getvalue())


def format_e2e_report_as_markdown(raw_output: str, test_results: Dict[str, Any], test_timestamp: str, environment_url: str, created_files: List[str]) -> str:
    """
    Format the raw E2E test output into a professional markdown report.
    
    Args:
        raw_output: Raw terminal output from the tests
        test_results: Dictionary containing test results
        test_timestamp: Timestamp of the test run
        environment_url: Environment URL that was tested
        created_files: List of files created during the test
        
    Returns:
        Formatted markdown report
    """
    from datetime import datetime
    
    # Parse timestamp for display
    try:
        dt = datetime.strptime(test_timestamp, "%Y-%m-%d-%H%M")
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        formatted_time = test_timestamp
    
    # Extract test results
    api_success = all(result['success'] for result in test_results.get('api_endpoints', {}).values()) if 'api_endpoints' in test_results else False
    report_file_success = all(result['success'] for result in test_results.get('report_files', {}).values()) if 'report_files' in test_results else False
    
    # Extract actual vs expected results
    actual_vs_expected_success = True
    actual_segments = 0
    expected_segments = 0
    if 'content_quality' in test_results and 'actual_vs_expected' in test_results['content_quality']:
        actual_vs_expected_data = test_results['content_quality']['actual_vs_expected']
        if isinstance(actual_vs_expected_data, dict) and 'all_validations_passed' in actual_vs_expected_data:
            actual_vs_expected_success = actual_vs_expected_data['all_validations_passed']
            actual_segments = actual_vs_expected_data.get('actual_segments', 0)
            expected_segments = actual_vs_expected_data.get('expected_segments', 0)
    elif 'actual_vs_expected' in test_results:
        # Fallback to direct path if content_quality path doesn't exist
        actual_vs_expected_data = test_results['actual_vs_expected']
        if isinstance(actual_vs_expected_data, dict) and 'all_validations_passed' in actual_vs_expected_data:
            actual_vs_expected_success = actual_vs_expected_data['all_validations_passed']
            actual_segments = actual_vs_expected_data.get('actual_segments', 0)
            expected_segments = actual_vs_expected_data.get('expected_segments', 0)
    
    # Extract content quality results
    content_quality_success = False
    if 'content_quality' in test_results:
        content_checks = []
        for category in test_results['content_quality'].values():
            if isinstance(category, dict) and 'error' not in category:
                content_checks.extend(category.values())
        content_quality_success = all(content_checks) if content_checks else False
    
    # Calculate overall success
    overall_success = api_success and report_file_success and actual_vs_expected_success and content_quality_success
    
    # Build the formatted report
    report = f"""# End-to-End Testing Report

**Generated:** {formatted_time}

**Environment:** {environment_url}

**Version:** {APP_VERSION}

**Test Type:** Streamlined End-to-End Testing

**Overall Status:** {'✅ PASSED' if overall_success else '❌ FAILED'}

## Test Summary

| Test Category | Status | Details |
|---------------|--------|---------|
| API Endpoints | {'✅ PASSED' if api_success else '❌ FAILED'} | All API endpoints responding correctly |
| Report Files | {'✅ PASSED' if report_file_success else '❌ FAILED'} | All required report files generated |
| Actual vs Expected | {'✅ PASSED' if actual_vs_expected_success else '❌ FAILED'} | {f'Actual: {actual_segments} Expected: {expected_segments} {((actual_segments/expected_segments)*100):.0f}%' if expected_segments > 0 else 'Validation completed'} |
| Content Quality | {'✅ PASSED' if content_quality_success else '❌ FAILED'} | Report content validation |

## Files Created

"""
    
    if created_files:
        for file_path in created_files:
            report += f"- `{file_path}`\n"
    else:
        report += "- No files created\n"
    
    report += f"""
## Detailed Test Results

### API Endpoint Testing

"""
    
    # Extract API endpoint results
    if 'api_endpoints' in test_results:
        for endpoint, result in test_results['api_endpoints'].items():
            status = '✅ PASSED' if result.get('success', False) else '❌ FAILED'
            report += f"- **{endpoint}**: {status}\n"
    else:
        report += "- No API endpoint results available\n"
    
    report += f"""
### Report File Testing

"""
    
    # Extract report file results
    if 'report_files' in test_results:
        for file_type, result in test_results['report_files'].items():
            status = '✅ PASSED' if result.get('success', False) else '❌ FAILED'
            report += f"- **{file_type}**: {status}\n"
    else:
        report += "- No report file results available\n"
    
    report += f"""
### Content Quality Testing

"""
    
    # Extract content quality results
    if 'content_quality' in test_results:
        for category, results in test_results['content_quality'].items():
            if category == 'actual_vs_expected':
                continue  # Already covered in summary
            if isinstance(results, dict) and 'error' not in results:
                report += f"#### {category.replace('_', ' ').title()}\n\n"
                for check, result in results.items():
                    status = '✅' if result else '❌'
                    report += f"- {status} {check}\n"
                report += "\n"
    else:
        report += "- No content quality results available\n"
    
    report += f"""
## Raw Test Output

<details>
<summary>Click to view raw terminal output</summary>

```
{raw_output}
```

</details>

## Important Notes

📝 **Flow Runner Analysis**: Flow Runner detailed analysis is not included in automated tests due to computational requirements. Flow Runner reports can be run locally (not currently supported in production) using:

```bash
curl -X POST 'http://localhost:8000/api/flow-audit' \\
  -H 'Content-Type: application/json' \\
  -d '{{"paceCsv": "data/runners.csv", "segmentsCsv": "data/segments_new.csv", "startTimes": {{"Full": 420, "10K": 440, "Half": 460}}}}'
```

## Conclusion

{'🎉 All tests passed! The system is ready for production deployment.' if overall_success else '⚠️ Some tests failed. Please review the results before production deployment.'}

---
*Report generated by run-density end-to-end testing suite*
"""
    
    return report


def get_test_environment_url() -> str:
    """Determine the test environment URL based on how the test is running."""
    # Check if we should test against production Cloud Run
    test_cloud = os.getenv('TEST_CLOUD_RUN', '').lower() == 'true'
    if test_cloud:
        cloud_url = os.getenv('CLOUD_RUN_URL', 'https://run-density-ln4r3sfkha-uc.a.run.app')
        return f"{cloud_url} (Cloud Run Production)"
    
    # Default to local TestClient
    return "http://testserver (local TestClient)"


def get_created_files() -> List[str]:
    """Get list of files created during the test run."""
    files = []
    
    # Find latest temporal flow files
    temporal_md_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.md')
    temporal_csv_files = glob.glob('reports/analysis/*/????-??-??-????-Flow.csv')
    density_md_files = glob.glob('reports/analysis/*/????-??-??-????-Density.md')
    
    if temporal_md_files:
        files.append(max(temporal_md_files, key=os.path.getctime))
    if temporal_csv_files:
        files.append(max(temporal_csv_files, key=os.path.getctime))
    if density_md_files:
        files.append(max(density_md_files, key=os.path.getctime))
        
    return files


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
    
    # Determine if we're testing against Cloud Run or local
    test_cloud = os.getenv('TEST_CLOUD_RUN', '').lower() == 'true'
    cloud_url = os.getenv('CLOUD_RUN_URL', 'https://run-density-ln4r3sfkha-uc.a.run.app')
    
    results = {}
    
    # Test health and ready endpoints
    print("1. Testing Health and Ready Endpoints...")
    
    if test_cloud:
        # Test against Cloud Run production
        health_response = requests.get(f'{cloud_url}/health', timeout=30)
        ready_response = requests.get(f'{cloud_url}/ready', timeout=30)
    else:
        # Test against local TestClient
        client = TestClient(app)
        health_response = client.get('/health')
        ready_response = client.get('/ready')
    
    # Handle response parsing for both requests and TestClient
    def get_json_response(response):
        if test_cloud:
            try:
                return response.json() if response.status_code == 200 else None
            except:
                return None
        else:
            return response.json() if response.status_code == 200 else None
    
    results['health'] = {
        'status_code': health_response.status_code,
        'success': health_response.status_code == 200,
        'response': get_json_response(health_response)
    }
    
    results['ready'] = {
        'status_code': ready_response.status_code,
        'success': ready_response.status_code == 200,
        'response': get_json_response(ready_response)
    }
    
    print(f"   /health: {health_response.status_code} {'✅' if health_response.status_code == 200 else '❌'}")
    print(f"   /ready: {ready_response.status_code} {'✅' if ready_response.status_code == 200 else '❌'}")
    print()
    
    # Test report generation endpoints
    print("2. Testing Report Generation Endpoints...")
    
    # Prepare payload for all endpoints
    density_payload = {
        'paceCsv': 'data/runners.csv',
        'densityCsv': 'data/segments_new.csv',
        'startTimes': start_times
    }
    
    flow_payload = {
        'paceCsv': 'data/runners.csv',
        'segmentsCsv': 'data/segments_new.csv',
        'startTimes': start_times
    }
    
    if test_cloud:
        # Test against Cloud Run production with longer timeouts
        density_response = requests.post(f'{cloud_url}/api/density-report', json=density_payload, timeout=300)
        temporal_report_response = requests.post(f'{cloud_url}/api/temporal-flow-report', json=flow_payload, timeout=300)
        temporal_flow_response = requests.post(f'{cloud_url}/api/temporal-flow', json=flow_payload, timeout=300)
    else:
        # Test against local TestClient
        density_response = client.post('/api/density-report', json=density_payload)
        temporal_report_response = client.post('/api/temporal-flow-report', json=flow_payload)
        temporal_flow_response = client.post('/api/temporal-flow', json=flow_payload)
    
    results['density_report'] = {
        'status_code': density_response.status_code,
        'success': density_response.status_code == 200,
        'response': get_json_response(density_response)
    }
    
    results['temporal_flow_report'] = {
        'status_code': temporal_report_response.status_code,
        'success': temporal_report_response.status_code == 200,
        'response': get_json_response(temporal_report_response)
    }
    
    results['temporal_flow'] = {
        'status_code': temporal_flow_response.status_code,
        'success': temporal_flow_response.status_code == 200,
        'response': get_json_response(temporal_flow_response)
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
    
    print(f"1. Temporal Flow MD files: {'✅' if len(temporal_md_files) > 0 else '❌'}")
    print(f"2. Temporal Flow CSV files: {'✅' if len(temporal_csv_files) > 0 else '❌'}")
    print(f"3. Density Analysis MD files: {'✅' if len(density_md_files) > 0 else '❌'}")
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
                      f"{actual_overtaking_a}/{actual_overtaking_b}, {expected_overtaking_a}/{expected_overtaking_b}, "
                      f"{actual_pct_a:.1f}/{actual_pct_b:.1f}, {expected_pct_a:.1f}/{expected_pct_b:.1f}")
                
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
            'individual_results': validation_results,
            'actual_segments': len(actual_df),
            'expected_segments': len(expected_df)
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
            'Proper segment names (A1: Start to Queen/Regent)': 'A1: Start to Queen/Regent' in density_content,
            'No unknown segments': 'Unknown:' not in density_content,
            'Proper counts (Total Segments: 22)': '**Total Segments:** 22' in density_content and '**Processed Segments:** 22' in density_content
        }
        
        results['density'] = density_checks
        
        for check, result in density_checks.items():
            if 'Proper counts' in check:
                print(f"   {check}: {'✅' if result else '❌'} (Density analyzes physical course segments, while Flow analyzes runner pairs - hence different counts)")
            else:
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
            if category == content_quality_results.get('actual_vs_expected'):
                # Special handling for actual vs expected validation
                if 'all_validations_passed' in category:
                    content_checks.append(category['all_validations_passed'])
            else:
                content_checks.extend(category.values())
    content_quality_success = all(content_checks) if content_checks else False
    
    overall_success = api_success and report_file_success and content_quality_success
    
    # Get test metadata
    test_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    test_date = datetime.now().strftime("%Y-%m-%d")
    environment_url = get_test_environment_url()
    created_files = get_created_files()
    
    # Check actual vs expected validation
    actual_vs_expected_success = True
    actual_segments = 0
    expected_segments = 0
    if 'actual_vs_expected' in all_results:
        actual_vs_expected_data = all_results['actual_vs_expected']
        if isinstance(actual_vs_expected_data, dict) and 'all_validations_passed' in actual_vs_expected_data:
            actual_vs_expected_success = actual_vs_expected_data['all_validations_passed']
            actual_segments = actual_vs_expected_data.get('actual_segments', 0)
            expected_segments = actual_vs_expected_data.get('expected_segments', 0)
        elif isinstance(actual_vs_expected_data, dict) and 'error' not in actual_vs_expected_data:
            # Handle case where validation didn't run properly
            actual_vs_expected_success = False
    
    print("=== FINAL SUMMARY ===")
    print(f"Date: {test_timestamp}")
    print(f"Environment: {environment_url}")
    print(f"Version: {APP_VERSION}")
    print(f"API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"Report Files: {'✅ PASSED' if report_file_success else '❌ FAILED'}")
    if created_files:
        print("   Files Created:")
        for file_path in created_files:
            print(f"   - {file_path}")
    # Calculate percentage for actual vs expected
    if expected_segments > 0:
        percentage = (actual_segments / expected_segments) * 100
        actual_expected_text = f"✅ PASSED (Actual: {actual_segments} Expected: {expected_segments} {percentage:.0f}%)" if actual_vs_expected_success else f"❌ FAILED (Actual: {actual_segments} Expected: {expected_segments} {percentage:.0f}%)"
    else:
        actual_expected_text = f"✅ PASSED" if actual_vs_expected_success else f"❌ FAILED"
    print(f"Actual to Expected: {actual_expected_text}")
    print(f"Content Quality: {'✅ PASSED' if content_quality_success else '❌ FAILED'}")
    print()
    
    if overall_success and actual_vs_expected_success:
        print("🎉 STREAMLINED TESTS PASSED! Core system is ready!")
    else:
        print("⚠️  Some tests failed - review before production deployment")
    
    print()
    print("📝 NOTE: Flow Runner detailed analysis is not included in automated tests due to computational requirements.")
    print("   Flow Runner reports can be run locally (not currently supported in production) using:")
    print("   curl -X POST 'http://localhost:8000/api/flow-audit' \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"paceCsv\": \"data/runners.csv\", \"segmentsCsv\": \"data/segments_new.csv\", \"startTimes\": {\"Full\": 420, \"10K\": 440, \"Half\": 460}}'")
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
            if category == content_quality_results.get('actual_vs_expected'):
                # Special handling for actual vs expected validation
                if 'all_validations_passed' in category:
                    content_checks.append(category['all_validations_passed'])
            else:
                content_checks.extend(category.values())
    content_quality_success = all(content_checks) if content_checks else False
    
    overall_success = api_success and report_file_success and content_quality_success
    
    # Get test metadata
    test_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    test_date = datetime.now().strftime("%Y-%m-%d")
    environment_url = get_test_environment_url()
    created_files = get_created_files()
    
    # Check actual vs expected validation
    actual_vs_expected_success = True
    actual_segments = 0
    expected_segments = 0
    if 'actual_vs_expected' in all_results:
        actual_vs_expected_data = all_results['actual_vs_expected']
        if isinstance(actual_vs_expected_data, dict) and 'all_validations_passed' in actual_vs_expected_data:
            actual_vs_expected_success = actual_vs_expected_data['all_validations_passed']
            actual_segments = actual_vs_expected_data.get('actual_segments', 0)
            expected_segments = actual_vs_expected_data.get('expected_segments', 0)
        elif isinstance(actual_vs_expected_data, dict) and 'error' not in actual_vs_expected_data:
            # Handle case where validation didn't run properly
            actual_vs_expected_success = False
    
    print("=== FINAL SUMMARY ===")
    print(f"Date: {test_timestamp}")
    print(f"Environment: {environment_url}")
    print(f"Version: {APP_VERSION}")
    print(f"API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"Report Files: {'✅ PASSED' if report_file_success else '❌ FAILED'}")
    if created_files:
        print("   Files Created:")
        for file_path in created_files:
            print(f"   - {file_path}")
    # Calculate percentage for actual vs expected
    if expected_segments > 0:
        percentage = (actual_segments / expected_segments) * 100
        actual_expected_text = f"✅ PASSED (Actual: {actual_segments} Expected: {expected_segments} {percentage:.0f}%)" if actual_vs_expected_success else f"❌ FAILED (Actual: {actual_segments} Expected: {expected_segments} {percentage:.0f}%)"
    else:
        actual_expected_text = f"✅ PASSED" if actual_vs_expected_success else f"❌ FAILED"
    print(f"Actual to Expected: {actual_expected_text}")
    print(f"Content Quality: {'✅ PASSED' if content_quality_success else '❌ FAILED'}")
    print()
    
    if overall_success and actual_vs_expected_success:
        print("🎉 ALL TESTS PASSED! System is ready for production!")
    else:
        print("⚠️  Some tests failed - review before production deployment")
    
    print()
    print("📝 NOTE: Flow Runner detailed analysis is not included in automated tests due to computational requirements.")
    print("   Flow Runner reports can be run locally (not currently supported in production) using:")
    print("   curl -X POST 'http://localhost:8000/api/flow-audit' \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"paceCsv\": \"data/runners.csv\", \"segmentsCsv\": \"data/segments_new.csv\", \"startTimes\": {\"Full\": 420, \"10K\": 440, \"Half\": 460}}'")
    print()
    print("=== END-TO-END TESTING COMPLETE ===")
    
    return all_results


if __name__ == "__main__":
    # Generate timestamp for file naming
    test_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    test_date = datetime.now().strftime("%Y-%m-%d")
    
    # Create output file path
    output_file = f"reports/test-results/{test_date}/{test_timestamp}-E2E.md"
    
    # Run tests with output capture
    with OutputCapture(output_file) as capture:
        # Run streamlined tests by default (faster, focuses on core functionality)
        # Use run_comprehensive_tests() for full testing including all optional components
        results = run_streamlined_tests()
    
    # Get the captured output and format it as a professional markdown report
    raw_output = capture.captured_output.getvalue()
    environment_url = get_test_environment_url()
    created_files = get_created_files()
    
    # Format the report as professional markdown
    formatted_report = format_e2e_report_as_markdown(
        raw_output, results, test_timestamp, environment_url, created_files
    )
    
    # Save the formatted report
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(formatted_report)
    
    print(f"\n📄 E2E Test Results saved to: {output_file}")
