#!/usr/bin/env python3
"""
Density Analysis Test Suite
===========================

Comprehensive test cases for density analysis functionality.
"""

import pandas as pd
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.density import analyze_density_segments, DensityConfig, StaticWidthProvider
from tests.test_runner import TestResult

class DensityTests:
    """Test suite for density analysis"""
    
    def __init__(self):
        self.correct_start_times = {'Full': 420, '10K': 440, 'Half': 460}  # Start times in seconds
        self.density_config = DensityConfig(
            bin_seconds=30,
            threshold_areal=1.2,
            threshold_crowd=2.0,
            min_segment_length_m=50.0
        )
    
    def test_comprehensive_density(self) -> TestResult:
        """
        Test ID: density_comprehensive
        Comprehensive test of density analysis for all segments
        """
        try:
            print("🔍 Running comprehensive density analysis test...")
            
            # Run density analysis
            density_results = analyze_density_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times,
                config=self.density_config,
                width_provider=StaticWidthProvider()
            )
            
            # Basic validation
            total_segments = len(density_results)
            segments_with_density = sum(1 for seg in density_results if seg.get('summary'))
            
            # Check for critical issues
            issues = []
            
            # Check for segments with no density data
            segments_without_density = []
            for seg in density_results:
                if not seg.get('summary'):
                    segments_without_density.append(seg.get('seg_id', 'unknown'))
            
            if segments_without_density:
                issues.append(f"Segments without density data: {segments_without_density}")
            
            # Check for unrealistic density values
            unrealistic_density = []
            for seg in density_results:
                summary = seg.get('summary')
                if summary:
                    # Parse summary if it's a string
                    if isinstance(summary, str):
                        try:
                            summary_dict = json.loads(summary.replace("'", '"'))
                        except:
                            continue
                    else:
                        summary_dict = summary
                    
                    max_areal = summary_dict.get('max_areal_density', 0)
                    max_crowd = summary_dict.get('max_crowd_density', 0)
                    
                    # Check for unrealistic values (e.g., > 10 runners/m² or > 100 runners/m)
                    if max_areal > 10:
                        unrealistic_density.append(f"{seg.get('seg_id')}: areal={max_areal:.2f}")
                    if max_crowd > 100:
                        unrealistic_density.append(f"{seg.get('seg_id')}: crowd={max_crowd:.2f}")
            
            if unrealistic_density:
                issues.append(f"Unrealistic density values: {unrealistic_density}")
            
            # Determine status
            if not issues:
                status = "PASS"
                message = f"Density analysis completed successfully for {segments_with_density}/{total_segments} segments"
            else:
                status = "FAIL"
                message = f"Density analysis completed with {len(issues)} issues"
            
            details = {
                "total_segments": total_segments,
                "segments_with_density": segments_with_density,
                "issues": issues,
                "config_used": {
                    "bin_seconds": self.density_config.bin_seconds,
                    "threshold_areal": self.density_config.threshold_areal,
                    "threshold_crowd": self.density_config.threshold_crowd,
                    "min_segment_length_m": self.density_config.min_segment_length_m
                },
                "start_times_used": self.correct_start_times
            }
            
            return TestResult(
                test_id="density_comprehensive",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                test_id="density_comprehensive",
                status="ERROR",
                message=f"Density analysis failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def test_density_validation(self) -> TestResult:
        """
        Test ID: density_validation
        Validate density calculations against known constraints
        """
        try:
            print("🔍 Running density validation test...")
            
            # Run density analysis
            density_results = analyze_density_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times,
                config=self.density_config,
                width_provider=StaticWidthProvider()
            )
            
            # Load segments data for validation
            segments_df = pd.read_csv('data/flow.csv')
            pace_df = pd.read_csv('data/runners.csv')
            
            validation_issues = []
            validated_segments = 0
            
            for seg_result in density_results:
                seg_id = seg_result.get('seg_id')
                if not seg_id:
                    continue
                
                # Get segment info
                segment_info = segments_df[segments_df['seg_id'] == seg_id]
                if segment_info.empty:
                    validation_issues.append(f"{seg_id}: Segment not found in flow.csv")
                    continue
                
                segment_info = segment_info.iloc[0]
                width_m = segment_info.get('width_m', 0)
                from_km = segment_info.get('from_km', 0)
                to_km = segment_info.get('to_km', 0)
                segment_length_m = (to_km - from_km) * 1000
                
                # Get event info
                event_a = segment_info.get('eventa', '')
                event_b = segment_info.get('eventb', '')
                
                # Count total runners for each event
                total_a = len(pace_df[pace_df['event'] == event_a]) if event_a else 0
                total_b = len(pace_df[pace_df['event'] == event_b]) if event_b else 0
                
                # Validate density calculations
                summary = seg_result.get('summary')
                if summary:
                    if isinstance(summary, str):
                        try:
                            summary_dict = json.loads(summary.replace("'", '"'))
                        except:
                            continue
                    else:
                        summary_dict = summary
                    
                    max_concurrent = summary_dict.get('max_concurrent_runners', 0)
                    max_areal = summary_dict.get('max_areal_density', 0)
                    max_crowd = summary_dict.get('max_crowd_density', 0)
                    
                    # Validation checks
                    total_possible = total_a + total_b
                    if max_concurrent > total_possible:
                        validation_issues.append(f"{seg_id}: Concurrent runners ({max_concurrent}) > total possible ({total_possible})")
                    
                    # Check areal density calculation
                    if width_m > 0 and max_concurrent > 0:
                        expected_areal = max_concurrent / (segment_length_m * width_m)
                        if abs(max_areal - expected_areal) > 0.01:  # Allow small floating point differences
                            validation_issues.append(f"{seg_id}: Areal density mismatch - expected {expected_areal:.4f}, got {max_areal:.4f}")
                    
                    # Check crowd density calculation
                    if segment_length_m > 0 and max_concurrent > 0:
                        expected_crowd = max_concurrent / segment_length_m
                        if abs(max_crowd - expected_crowd) > 0.01:
                            validation_issues.append(f"{seg_id}: Crowd density mismatch - expected {expected_crowd:.4f}, got {max_crowd:.4f}")
                    
                    validated_segments += 1
            
            # Determine status
            if not validation_issues:
                status = "PASS"
                message = f"Density validation passed for {validated_segments} segments"
            else:
                status = "FAIL"
                message = f"Density validation failed with {len(validation_issues)} issues"
            
            details = {
                "validated_segments": validated_segments,
                "validation_issues": validation_issues,
                "total_segments_processed": len(density_results)
            }
            
            return TestResult(
                test_id="density_validation",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return TestResult(
                test_id="density_validation",
                status="ERROR",
                message=f"Density validation failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def test_smoke(self) -> TestResult:
        """
        Test ID: density_smoke
        Basic smoke test to ensure density analysis runs without errors
        """
        try:
            print("🔍 Running density smoke test...")
            
            # Run basic density analysis
            density_results = analyze_density_segments(
                pace_csv='data/runners.csv',
                segments_csv='data/flow.csv',
                start_times=self.correct_start_times,
                config=self.density_config,
                width_provider=StaticWidthProvider()
            )
            
            # Basic validation
            if not isinstance(density_results, list):
                return TestResult(
                    test_id="density_smoke",
                    status="FAIL",
                    message="Density analysis did not return a list",
                    details={"result_type": type(density_results).__name__}
                )
            
            expected_segment_count = 36
            actual_segment_count = len(density_results)
            
            if actual_segment_count != expected_segment_count:
                return TestResult(
                    test_id="density_smoke",
                    status="FAIL",
                    message=f"Expected {expected_segment_count} segments, got {actual_segment_count}",
                    details={
                        "expected_segments": expected_segment_count,
                        "actual_segments": actual_segment_count
                    }
                )
            
            # Check that segments have required fields
            required_fields = ['seg_id', 'summary']
            missing_fields = []
            
            for seg in density_results[:5]:  # Check first 5 segments
                for field in required_fields:
                    if field not in seg:
                        missing_fields.append(field)
            
            if missing_fields:
                return TestResult(
                    test_id="density_smoke",
                    status="FAIL",
                    message=f"Missing required fields: {missing_fields}",
                    details={"missing_fields": missing_fields}
                )
            
            return TestResult(
                test_id="density_smoke",
                status="PASS",
                message="Density smoke test passed - analysis runs successfully",
                details={
                    "total_segments": actual_segment_count,
                    "config_used": {
                        "bin_seconds": self.density_config.bin_seconds,
                        "threshold_areal": self.density_config.threshold_areal,
                        "threshold_crowd": self.density_config.threshold_crowd
                    }
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="density_smoke",
                status="ERROR",
                message=f"Density smoke test failed: {str(e)}",
                details={"error": str(e)}
            )
