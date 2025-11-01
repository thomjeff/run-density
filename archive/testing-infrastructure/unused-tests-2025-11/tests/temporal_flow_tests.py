#!/usr/bin/env python3
"""
Temporal Flow Test Suite
========================

Comprehensive test cases for temporal flow analysis functionality.
"""

import pandas as pd
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.temporal_flow import analyze_temporal_flow_segments
from app.temporal_flow_report import export_temporal_flow_csv
from tests.test_runner import TestResult

class TemporalFlowTests:
    """Test suite for temporal flow analysis"""
    
    def __init__(self):
        self.correct_start_times = {'Full': 420, '10K': 440, 'Half': 460}  # Start times in minutes
        self.expected_results_file = "comprehensive_segments_test_report_fixed.csv"
    
    def test_convergence_segments(self) -> TestResult:
        """
        Test ID: temporal_flow_convergence
        Test that all expected convergence segments are correctly identified
        """
        try:
            print("🔍 Testing temporal flow convergence segments...")
            
            # Run temporal flow analysis with correct start times
            flow_results = analyze_temporal_flow_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times
            )
            
            # Load expected results
            expected_df = pd.read_csv(self.expected_results_file)
            expected_convergence = expected_df[expected_df['convergence_point'].notna()]
            
            # Test results
            actual_convergence_count = flow_results.get('segments_with_convergence', 0)
            expected_convergence_count = len(expected_convergence)
            
            # Verify each convergence segment
            passed_segments = []
            failed_segments = []
            
            for _, expected_row in expected_convergence.iterrows():
                seg_id = expected_row['seg_id']
                expected_cp = expected_row['convergence_point']
                
                # Find actual result
                actual_seg = None
                for seg in flow_results['segments']:
                    if seg.get('seg_id') == seg_id:
                        actual_seg = seg
                        break
                
                if actual_seg and actual_seg.get('has_convergence', False):
                    actual_cp = actual_seg.get('convergence_point', None)
                    if actual_cp is not None and abs(float(expected_cp) - float(actual_cp)) < 0.1:
                        passed_segments.append(seg_id)
                    else:
                        failed_segments.append({
                            'seg_id': seg_id,
                            'expected_cp': expected_cp,
                            'actual_cp': actual_cp
                        })
                else:
                    failed_segments.append({
                        'seg_id': seg_id,
                        'expected_cp': expected_cp,
                        'actual_cp': None,
                        'error': 'No convergence found'
                    })
            
            # Determine overall status
            if len(failed_segments) == 0:
                status = "PASS"
                message = f"All {len(passed_segments)} convergence segments validated successfully"
            else:
                status = "FAIL"
                message = f"{len(failed_segments)} segments failed validation"
            
            details = {
                "total_segments_processed": len(flow_results['segments']),
                "expected_convergence": expected_convergence_count,
                "actual_convergence": actual_convergence_count,
                "passed_segments": passed_segments,
                "failed_segments": failed_segments,
                "start_times_used": self.correct_start_times
            }
            
            return TestResult(
                test_id="temporal_flow_convergence",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                test_id="temporal_flow_convergence",
                status="ERROR",
                message=f"Test execution failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def test_comprehensive_validation(self) -> TestResult:
        """
        Test ID: temporal_flow_comprehensive
        Comprehensive validation of all 36 segments against expected results
        """
        try:
            print("🔍 Running comprehensive temporal flow validation...")
            
            # Run temporal flow analysis
            flow_results = analyze_temporal_flow_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times
            )
            
            # Load expected results
            expected_df = pd.read_csv(self.expected_results_file)
            
            # Validate all segments
            validation_results = []
            total_passed = 0
            total_failed = 0
            
            for _, expected_row in expected_df.iterrows():
                seg_id = expected_row['seg_id']
                
                # Find actual result
                actual_seg = None
                for seg in flow_results['segments']:
                    if seg.get('seg_id') == seg_id:
                        actual_seg = seg
                        break
                
                if actual_seg:
                    # Validate convergence point
                    expected_cp = expected_row['convergence_point']
                    actual_cp = actual_seg.get('convergence_point', None)
                    
                    expected_has_conv = pd.notna(expected_cp)
                    actual_has_conv = actual_seg.get('has_convergence', False)
                    
                    # Check convergence match
                    convergence_match = expected_has_conv == actual_has_conv
                    cp_match = True
                    
                    if expected_has_conv and actual_has_conv:
                        cp_match = abs(float(expected_cp) - float(actual_cp)) < 0.1
                    
                    if convergence_match and cp_match:
                        total_passed += 1
                        status = "PASS"
                    else:
                        total_failed += 1
                        status = "FAIL"
                    
                    validation_results.append({
                        'seg_id': seg_id,
                        'status': status,
                        'expected_cp': expected_cp,
                        'actual_cp': actual_cp,
                        'expected_has_conv': expected_has_conv,
                        'actual_has_conv': actual_has_conv
                    })
                else:
                    total_failed += 1
                    validation_results.append({
                        'seg_id': seg_id,
                        'status': "ERROR",
                        'error': 'Segment not found in results'
                    })
            
            # Determine overall status
            total_tests = total_passed + total_failed
            success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
            
            if success_rate == 100.0:
                status = "PASS"
                message = f"All {total_passed} segments validated successfully (100% pass rate)"
            else:
                status = "FAIL"
                message = f"Validation failed: {total_passed}/{total_tests} segments passed ({success_rate:.1f}%)"
            
            details = {
                "total_segments": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "success_rate": success_rate,
                "validation_results": validation_results,
                "start_times_used": self.correct_start_times
            }
            
            return TestResult(
                test_id="temporal_flow_comprehensive",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                test_id="temporal_flow_comprehensive",
                status="ERROR",
                message=f"Comprehensive validation failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def test_comprehensive_comparison_csv(self) -> TestResult:
        """
        Test ID: temporal_flow_comparison_csv
        Generate comprehensive comparison CSV report like comprehensive_test_comparison_report.csv
        """
        try:
            print("🔍 Generating comprehensive comparison CSV report...")
            
            # Run temporal flow analysis
            flow_results = analyze_temporal_flow_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times
            )
            
            # Load expected results
            expected_df = pd.read_csv(self.expected_results_file)
            
            # Only compare segments where overtake_flag = 'y' (where temporal flow calculations make sense)
            expected_overtake_segments = expected_df[expected_df['overlap_flag'] == 'y']
            
            print(f"Comparing {len(expected_overtake_segments)} segments with overtake_flag = 'y'")
            
            # Create comparison dataframe
            comparison_data = []
            
            for _, expected_row in expected_overtake_segments.iterrows():
                seg_id = expected_row['seg_id']
                
                # Find actual result
                actual_seg = None
                for seg in flow_results['segments']:
                    if seg.get('seg_id') == seg_id:
                        actual_seg = seg
                        break
                
                if actual_seg:
                    # Extract actual values
                    actual_segment_label = actual_seg.get('segment_label', '')
                    actual_flow_type = actual_seg.get('flow_type', '')
                    
                    # Build range strings from from_km and to_km fields
                    from_km_a = actual_seg.get('from_km_a', 0)
                    to_km_a = actual_seg.get('to_km_a', 0)
                    from_km_b = actual_seg.get('from_km_b', 0)
                    to_km_b = actual_seg.get('to_km_b', 0)
                    actual_range_a = f"{from_km_a}km to {to_km_a}km" if from_km_a is not None and to_km_a is not None else ''
                    actual_range_b = f"{from_km_b}km to {to_km_b}km" if from_km_b is not None and to_km_b is not None else ''
                    
                    actual_total_a = actual_seg.get('total_a', 0)
                    actual_total_b = actual_seg.get('total_b', 0)
                    actual_cp = actual_seg.get('convergence_point', None)
                    actual_overtake_a = actual_seg.get('overtaking_a', 0)
                    actual_overtake_b = actual_seg.get('overtaking_b', 0)
                    
                    # Calculate percentages
                    actual_overtake_a_pct = (actual_overtake_a / actual_total_a * 100) if actual_total_a > 0 else 0.0
                    actual_overtake_b_pct = (actual_overtake_b / actual_total_b * 100) if actual_total_b > 0 else 0.0
                    
                    # Format time fields
                    actual_event_a_first_entry = actual_seg.get('first_entry_a', '')
                    actual_event_b_first_entry = actual_seg.get('first_entry_b', '')
                    actual_event_a_last_exit = actual_seg.get('last_exit_a', '')
                    actual_event_b_last_exit = actual_seg.get('last_exit_b', '')
                    
                    # Extract expected values
                    expected_segment_label = expected_row.get('segment_label', '')
                    expected_flow_type = expected_row.get('flow_type', '')
                    expected_range_a = expected_row.get('range_a', '')
                    expected_range_b = expected_row.get('range_b', '')
                    expected_total_a = expected_row.get('total_a', 0)
                    expected_total_b = expected_row.get('total_b', 0)
                    expected_cp = expected_row.get('convergence_point', None)
                    expected_overtake_a = expected_row.get('overtake_a', 0)
                    expected_overtake_b = expected_row.get('overtake_b', 0)
                    expected_overtake_a_pct = expected_row.get('overtake_aPct', 0.0)
                    expected_overtake_b_pct = expected_row.get('overtake_bPct', 0.0)
                    expected_event_a_first_entry = expected_row.get('event_a_firstEntry', '')
                    expected_event_b_first_entry = expected_row.get('event_b_firstEntry', '')
                    expected_event_a_last_exit = expected_row.get('event_a_lastExit', '')
                    expected_event_b_last_exit = expected_row.get('event_b_lastExit', '')
                    
                    # Calculate differences
                    differences = []
                    critical_failures = []
                    
                    # Check each field for differences
                    if expected_segment_label != actual_segment_label:
                        differences.append(f'segment_label: "{expected_segment_label}" → "{actual_segment_label}"')
                    
                    if expected_flow_type != actual_flow_type:
                        differences.append(f'flow_type: "{expected_flow_type}" → "{actual_flow_type}"')
                    
                    if expected_range_a != actual_range_a:
                        differences.append(f'range_a: "{expected_range_a}" → "{actual_range_a}"')
                    
                    if expected_range_b != actual_range_b:
                        differences.append(f'range_b: "{expected_range_b}" → "{actual_range_b}"')
                    
                    if expected_total_a != actual_total_a:
                        differences.append(f'total_a: {expected_total_a} → {actual_total_a}')
                        critical_failures.append('total_a_mismatch')
                    
                    if expected_total_b != actual_total_b:
                        differences.append(f'total_b: {expected_total_b} → {actual_total_b}')
                        critical_failures.append('total_b_mismatch')
                    
                    # Check convergence point
                    expected_has_conv = pd.notna(expected_cp)
                    actual_has_conv = actual_cp is not None
                    
                    if expected_has_conv != actual_has_conv:
                        differences.append(f'convergence: {"has" if expected_has_conv else "no"} → {"has" if actual_has_conv else "no"}')
                        critical_failures.append('convergence_mismatch')
                    elif expected_has_conv and actual_has_conv:
                        if abs(float(expected_cp) - float(actual_cp)) > 0.1:
                            differences.append(f'convergence_point: {expected_cp} → {actual_cp}')
                            critical_failures.append('convergence_point_mismatch')
                    
                    if expected_overtake_a != actual_overtake_a:
                        differences.append(f'overtake_a: {expected_overtake_a} → {actual_overtake_a}')
                        critical_failures.append('overtake_a_mismatch')
                    
                    if expected_overtake_b != actual_overtake_b:
                        differences.append(f'overtake_b: {expected_overtake_b} → {actual_overtake_b}')
                        critical_failures.append('overtake_b_mismatch')
                    
                    # Determine status
                    if len(critical_failures) == 0:
                        if len(differences) == 0:
                            status = "PASS"
                            status_reason = "Perfect match"
                        else:
                            status = "PASS"
                            status_reason = "Only enhancements/precision differences"
                    else:
                        status = "FAIL"
                        status_reason = f"Critical failures: {', '.join(critical_failures)}"
                    
                    comparison_data.append({
                        'seg_id': seg_id,
                        'segment_label_expected': expected_segment_label,
                        'segment_label_actual': actual_segment_label,
                        'overlap_flag_expected': expected_row.get('overlap_flag', ''),
                        'overlap_flag_actual': 'y' if actual_seg.get('has_convergence', False) else 'n',
                        'flow_type_expected': expected_flow_type,
                        'flow_type_actual': actual_flow_type,
                        'range_a_expected': expected_range_a,
                        'range_a_actual': actual_range_a,
                        'range_b_expected': expected_range_b,
                        'range_b_actual': actual_range_b,
                        'total_a_expected': expected_total_a,
                        'total_a_actual': actual_total_a,
                        'total_b_expected': expected_total_b,
                        'total_b_actual': actual_total_b,
                        'convergence_point_expected': expected_cp,
                        'convergence_point_actual': actual_cp,
                        'overtake_a_expected': expected_overtake_a,
                        'overtake_a_actual': actual_overtake_a,
                        'overtake_aPct_expected': expected_overtake_a_pct,
                        'overtake_aPct_actual': actual_overtake_a_pct,
                        'overtake_b_expected': expected_overtake_b,
                        'overtake_b_actual': actual_overtake_b,
                        'overtake_bPct_expected': expected_overtake_b_pct,
                        'overtake_bPct_actual': actual_overtake_b_pct,
                        'event_a_firstEntry_expected': expected_event_a_first_entry,
                        'event_a_firstEntry_actual': actual_event_a_first_entry,
                        'event_b_firstEntry_expected': expected_event_b_first_entry,
                        'event_b_firstEntry_actual': actual_event_b_first_entry,
                        'event_a_lastExit_expected': expected_event_a_last_exit,
                        'event_a_lastExit_actual': actual_event_a_last_exit,
                        'event_b_lastExit_expected': expected_event_b_last_exit,
                        'event_b_lastExit_actual': actual_event_b_last_exit,
                        'differences': '; '.join(differences) if differences else None,
                        'critical_failures': '; '.join(critical_failures) if critical_failures else None,
                        'status': status,
                        'status_reason': status_reason,
                        'num_differences': len(differences),
                        'num_critical_failures': len(critical_failures)
                    })
                else:
                    # Segment not found
                    comparison_data.append({
                        'seg_id': seg_id,
                        'segment_label_expected': expected_row.get('segment_label', ''),
                        'segment_label_actual': 'NOT_FOUND',
                        'overlap_flag_expected': expected_row.get('overlap_flag', ''),
                        'overlap_flag_actual': 'ERROR',
                        'flow_type_expected': expected_row.get('flow_type', ''),
                        'flow_type_actual': 'ERROR',
                        'range_a_expected': expected_row.get('range_a', ''),
                        'range_a_actual': 'ERROR',
                        'range_b_expected': expected_row.get('range_b', ''),
                        'range_b_actual': 'ERROR',
                        'total_a_expected': expected_row.get('total_a', 0),
                        'total_a_actual': 'ERROR',
                        'total_b_expected': expected_row.get('total_b', 0),
                        'total_b_actual': 'ERROR',
                        'convergence_point_expected': expected_row.get('convergence_point', None),
                        'convergence_point_actual': 'ERROR',
                        'overtake_a_expected': expected_row.get('overtake_a', 0),
                        'overtake_a_actual': 'ERROR',
                        'overtake_aPct_expected': expected_row.get('overtake_aPct', 0.0),
                        'overtake_aPct_actual': 'ERROR',
                        'overtake_b_expected': expected_row.get('overtake_b', 0),
                        'overtake_b_actual': 'ERROR',
                        'overtake_bPct_expected': expected_row.get('overtake_bPct', 0.0),
                        'overtake_bPct_actual': 'ERROR',
                        'event_a_firstEntry_expected': expected_row.get('event_a_firstEntry', ''),
                        'event_a_firstEntry_actual': 'ERROR',
                        'event_b_firstEntry_expected': expected_row.get('event_b_firstEntry', ''),
                        'event_b_firstEntry_actual': 'ERROR',
                        'event_a_lastExit_expected': expected_row.get('event_a_lastExit', ''),
                        'event_a_lastExit_actual': 'ERROR',
                        'event_b_lastExit_expected': expected_row.get('event_b_lastExit', ''),
                        'event_b_lastExit_actual': 'ERROR',
                        'differences': 'Segment not found in actual results',
                        'critical_failures': 'segment_not_found',
                        'status': 'ERROR',
                        'status_reason': 'Segment not found in actual results',
                        'num_differences': 1,
                        'num_critical_failures': 1
                    })
            
            # Create comparison dataframe
            comparison_df = pd.DataFrame(comparison_data)
            
            # Save comparison CSV
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            csv_filename = f"{timestamp} Temporal Flow Compare.csv"
            comparison_df.to_csv(csv_filename, index=False)
            
            # Calculate summary statistics
            total_overtake_segments = len(comparison_df)
            passed_segments = len(comparison_df[comparison_df['status'] == 'PASS'])
            failed_segments = len(comparison_df[comparison_df['status'] == 'FAIL'])
            error_segments = len(comparison_df[comparison_df['status'] == 'ERROR'])
            total_differences = comparison_df['num_differences'].sum()
            total_critical_failures = comparison_df['num_critical_failures'].sum()
            
            success_rate = (passed_segments / total_overtake_segments * 100) if total_overtake_segments > 0 else 0
            
            # Determine overall status
            if error_segments > 0:
                overall_status = "ERROR"
                message = f"Comparison completed with {error_segments} errors"
            elif failed_segments > 0:
                overall_status = "FAIL"
                message = f"Comparison completed with {failed_segments} failures"
            else:
                overall_status = "PASS"
                message = f"Comparison completed successfully - {passed_segments}/{total_overtake_segments} overtake segments passed"
            
            details = {
                "csv_filename": csv_filename,
                "total_overtake_segments": total_overtake_segments,
                "total_segments_in_analysis": len(flow_results['segments']),
                "passed_segments": passed_segments,
                "failed_segments": failed_segments,
                "error_segments": error_segments,
                "success_rate": success_rate,
                "total_differences": total_differences,
                "total_critical_failures": total_critical_failures,
                "start_times_used": self.correct_start_times,
                "note": "Only comparing segments with overtake_flag = 'y' where temporal flow calculations are meaningful"
            }
            
            return TestResult(
                test_id="temporal_flow_comparison_csv",
                status=overall_status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                test_id="temporal_flow_comparison_csv",
                status="ERROR",
                message=f"Comparison CSV generation failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def test_smoke(self) -> TestResult:
        """
        Test ID: temporal_flow_smoke
        Basic smoke test to ensure temporal flow analysis runs without errors
        """
        try:
            print("🔍 Running temporal flow smoke test...")
            
            # Run basic analysis
            flow_results = analyze_temporal_flow_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times
            )
            
            # Basic validation
            required_keys = ['segments', 'segments_with_convergence', 'total_segments']
            missing_keys = [key for key in required_keys if key not in flow_results]
            
            if missing_keys:
                return TestResult(
                    test_id="temporal_flow_smoke",
                    status="FAIL",
                    message=f"Missing required keys: {missing_keys}",
                    details={"missing_keys": missing_keys}
                )
            
            # Check segment count
            expected_segment_count = 36
            actual_segment_count = len(flow_results['segments'])
            
            if actual_segment_count != expected_segment_count:
                return TestResult(
                    test_id="temporal_flow_smoke",
                    status="FAIL",
                    message=f"Expected {expected_segment_count} segments, got {actual_segment_count}",
                    details={
                        "expected_segments": expected_segment_count,
                        "actual_segments": actual_segment_count
                    }
                )
            
            return TestResult(
                test_id="temporal_flow_smoke",
                status="PASS",
                message="Smoke test passed - temporal flow analysis runs successfully",
                details={
                    "total_segments": actual_segment_count,
                    "convergence_segments": flow_results.get('segments_with_convergence', 0),
                    "start_times_used": self.correct_start_times
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="temporal_flow_smoke",
                status="ERROR",
                message=f"Smoke test failed: {str(e)}",
                details={"error": str(e)}
            )