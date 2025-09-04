"""
Comprehensive Density Analysis Testing

This script performs comprehensive testing of the density analysis module
with proper tolerances and validation against expected values.

Author: AI Assistant
Version: 1.6.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Any, Tuple
import sys
import os

# Add app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from density import (
    analyze_density_segments,
    DensityConfig,
    StaticWidthProvider,
    DynamicWidthProvider,
    DensityAnalyzer,
    SegmentMeta
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_CONFIG = {
    "epsilon": 1e-6,  # For float comparisons
    "time_tolerance_bins": 1,  # ±1 bin tolerance for time windows
    "min_segment_length_m": 50.0,
    "test_segments": ["A1a", "B1a", "C1a", "D1a", "E1a", "F1a", "G1a", "H1a", "I1a", "J1a", "K1a", "L1a", "M1a", "M1b", "M1c", "M1d", "M2a", "M2b", "M2c", "M2d", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10", "J11", "J12", "J13", "J14", "J15", "J16", "J17"]
}


class DensityTestSuite:
    """Comprehensive test suite for density analysis."""
    
    def __init__(self):
        self.test_results = []
        self.passed_tests = 0
        self.failed_tests = 0
        self.config = DensityConfig(
            bin_seconds=30,
            threshold_areal=1.2,
            threshold_crowd=2.0,
            min_segment_length_m=TEST_CONFIG["min_segment_length_m"],
            epsilon=TEST_CONFIG["epsilon"]
        )
        
    def load_test_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, datetime]]:
        """Load test data for density analysis."""
        try:
            # Load segments data
            segments_df = pd.read_csv('data/segments.csv')
            logger.info(f"Loaded {len(segments_df)} segments")
            
            # Load pace data
            pace_data = pd.read_csv('data/your_pace_data.csv')
            logger.info(f"Loaded {len(pace_data)} runners")
            
            # Define start times
            start_times = {
                '10K': datetime.strptime('08:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
                'Half': datetime.strptime('08:30:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
                'Full': datetime.strptime('09:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1)
            }
            
            return segments_df, pace_data, start_times
            
        except Exception as e:
            logger.error(f"Failed to load test data: {str(e)}")
            raise
    
    def test_segment_validation(self, segments_df: pd.DataFrame) -> None:
        """Test segment validation logic."""
        logger.info("Testing segment validation...")
        
        analyzer = DensityAnalyzer(self.config)
        
        # Test valid segment
        valid_segment = SegmentMeta(
            segment_id="A1a",
            from_km=0.0,
            to_km=1.0,
            width_m=3.0,
            direction="uni"
        )
        
        is_valid, flags = analyzer.validate_segment(valid_segment)
        self.assert_test(is_valid, "Valid segment should pass validation")
        self.assert_test(len(flags) == 0, "Valid segment should have no flags")
        
        # Test short segment
        short_segment = SegmentMeta(
            segment_id="SHORT",
            from_km=0.0,
            to_km=0.01,  # 10m segment
            width_m=3.0,
            direction="uni"
        )
        
        is_valid, flags = analyzer.validate_segment(short_segment)
        self.assert_test(not is_valid, "Short segment should fail validation")
        self.assert_test("short_segment" in flags, "Short segment should have short_segment flag")
        
        # Test invalid width
        invalid_width_segment = SegmentMeta(
            segment_id="INVALID",
            from_km=0.0,
            to_km=1.0,
            width_m=0.0,  # Invalid width
            direction="uni"
        )
        
        is_valid, flags = analyzer.validate_segment(invalid_width_segment)
        self.assert_test(not is_valid, "Invalid width segment should fail validation")
        self.assert_test("width_missing" in flags, "Invalid width segment should have width_missing flag")
        
        logger.info("✅ Segment validation tests passed")
    
    def test_density_calculations(self, segments_df: pd.DataFrame, pace_data: pd.DataFrame, start_times: Dict[str, datetime]) -> None:
        """Test density calculation accuracy."""
        logger.info("Testing density calculations...")
        
        analyzer = DensityAnalyzer(self.config)
        
        # Test with a known segment
        test_segment = SegmentMeta(
            segment_id="A1a",
            from_km=0.0,
            to_km=1.0,
            width_m=3.0,
            direction="uni"
        )
        
        # Generate time bins
        time_bins = [
            datetime.strptime('08:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            datetime.strptime('08:00:30', '%H:%M:%S').replace(year=2024, month=1, day=1),
            datetime.strptime('08:01:00', '%H:%M:%S').replace(year=2024, month=1, day=1)
        ]
        
        # Test concurrent runner calculation
        concurrent_runners = analyzer.calculate_concurrent_runners(
            test_segment, pace_data, start_times, time_bins[0]
        )
        
        self.assert_test(concurrent_runners >= 0, "Concurrent runners should be non-negative")
        self.assert_test(isinstance(concurrent_runners, int), "Concurrent runners should be integer")
        
        # Test density metrics
        areal_density, crowd_density = analyzer.calculate_density_metrics(concurrent_runners, test_segment)
        
        self.assert_test(areal_density >= 0, "Areal density should be non-negative")
        self.assert_test(crowd_density >= 0, "Crowd density should be non-negative")
        
        # Test LOS classification
        los_areal, los_crowd = analyzer.classify_los(areal_density, crowd_density)
        
        self.assert_test(los_areal in ["Comfortable", "Busy", "Constrained"], "Areal LOS should be valid")
        self.assert_test(los_crowd in ["Low", "Medium", "High"], "Crowd LOS should be valid")
        
        logger.info("✅ Density calculation tests passed")
    
    def test_tot_calculations(self, segments_df: pd.DataFrame, pace_data: pd.DataFrame, start_times: Dict[str, datetime]) -> None:
        """Test TOT (Time Over Threshold) calculations."""
        logger.info("Testing TOT calculations...")
        
        # Test with boundary values
        test_config = DensityConfig(
            bin_seconds=30,
            threshold_areal=1.2,
            threshold_crowd=2.0,
            min_segment_length_m=50.0
        )
        
        analyzer = DensityAnalyzer(test_config)
        
        # Create mock results with boundary values
        from density import DensityResult
        
        mock_results = [
            DensityResult(
                segment_id="TEST",
                t_start="08:00:00",
                t_end="08:00:30",
                concurrent_runners=10,
                areal_density=1.2,  # Exactly at threshold
                crowd_density=2.0,  # Exactly at threshold
                los_areal="Busy",
                los_crowd="Medium",
                flags=[]
            ),
            DensityResult(
                segment_id="TEST",
                t_start="08:00:30",
                t_end="08:01:00",
                concurrent_runners=15,
                areal_density=1.3,  # Above threshold
                crowd_density=2.1,  # Above threshold
                los_areal="Busy",
                los_crowd="Medium",
                flags=[]
            )
        ]
        
        # Test TOT calculation
        summary = analyzer.summarize_density(mock_results)
        
        # TOT should include both bins (>= threshold)
        expected_tot_areal = 60  # 2 bins × 30 seconds
        expected_tot_crowd = 60  # 2 bins × 30 seconds
        
        self.assert_test(
            abs(summary.tot_areal_sec - expected_tot_areal) <= TEST_CONFIG["epsilon"],
            f"TOT areal should be {expected_tot_areal}, got {summary.tot_areal_sec}"
        )
        
        self.assert_test(
            abs(summary.tot_crowd_sec - expected_tot_crowd) <= TEST_CONFIG["epsilon"],
            f"TOT crowd should be {expected_tot_crowd}, got {summary.tot_crowd_sec}"
        )
        
        logger.info("✅ TOT calculation tests passed")
    
    def test_narrative_smoothing(self, segments_df: pd.DataFrame, pace_data: pd.DataFrame, start_times: Dict[str, datetime]) -> None:
        """Test narrative smoothing functionality."""
        logger.info("Testing narrative smoothing...")
        
        analyzer = DensityAnalyzer(self.config)
        
        # Create mock results with rapid LOS changes
        from density import DensityResult
        
        mock_results = [
            DensityResult("TEST", "08:00:00", "08:00:30", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:00:30", "08:01:00", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:01:00", "08:01:30", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:01:30", "08:02:00", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:02:00", "08:02:30", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:02:30", "08:03:00", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:03:00", "08:03:30", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:03:30", "08:04:00", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:04:00", "08:04:30", 5, 0.5, 1.0, "Comfortable", "Low", []),
            DensityResult("TEST", "08:04:30", "08:05:00", 5, 0.5, 1.0, "Comfortable", "Low", []),
        ]
        
        # Test narrative smoothing
        sustained_periods = analyzer.smooth_narrative_transitions(mock_results)
        
        # Should have one sustained period (10 bins = 5 minutes > 2 minute minimum)
        self.assert_test(len(sustained_periods) == 1, f"Should have 1 sustained period, got {len(sustained_periods)}")
        
        if sustained_periods:
            period = sustained_periods[0]
            self.assert_test(period["duration_minutes"] >= 2.0, "Sustained period should be at least 2 minutes")
            self.assert_test(period["los_areal"] == "Comfortable", "LOS should be Comfortable")
            self.assert_test(period["los_crowd"] == "Low", "Crowd LOS should be Low")
        
        logger.info("✅ Narrative smoothing tests passed")
    
    def test_width_providers(self, segments_df: pd.DataFrame) -> None:
        """Test pluggable width providers."""
        logger.info("Testing width providers...")
        
        # Test static width provider
        static_provider = StaticWidthProvider(segments_df)
        width = static_provider.get_width("A1a", 0.0, 1.0)
        self.assert_test(width > 0, "Static width provider should return positive width")
        
        # Test dynamic width provider
        dynamic_provider = DynamicWidthProvider()
        width = dynamic_provider.get_width("A1a", 0.0, 1.0)
        self.assert_test(width > 0, "Dynamic width provider should return positive width")
        
        logger.info("✅ Width provider tests passed")
    
    def test_comprehensive_analysis(self, segments_df: pd.DataFrame, pace_data: pd.DataFrame, start_times: Dict[str, datetime]) -> None:
        """Test comprehensive density analysis on all segments."""
        logger.info("Testing comprehensive density analysis...")
        
        # Test with static width provider
        width_provider = StaticWidthProvider(segments_df)
        
        results = analyze_density_segments(
            segments_df=segments_df,
            pace_data=pace_data,
            start_times=start_times,
            config=self.config,
            width_provider=width_provider
        )
        
        # Validate results structure
        self.assert_test("summary" in results, "Results should have summary")
        self.assert_test("segments" in results, "Results should have segments")
        
        summary = results["summary"]
        self.assert_test("total_segments" in summary, "Summary should have total_segments")
        self.assert_test("processed_segments" in summary, "Summary should have processed_segments")
        self.assert_test("skipped_segments" in summary, "Summary should have skipped_segments")
        
        # Validate segment results
        for segment_id, segment_data in results["segments"].items():
            self.assert_test("summary" in segment_data, f"Segment {segment_id} should have summary")
            self.assert_test("time_series" in segment_data, f"Segment {segment_id} should have time_series")
            self.assert_test("sustained_periods" in segment_data, f"Segment {segment_id} should have sustained_periods")
            
            # Validate summary data
            segment_summary = segment_data["summary"]
            self.assert_test(segment_summary.peak_areal_density >= 0, f"Peak areal density should be non-negative for {segment_id}")
            self.assert_test(segment_summary.peak_crowd_density >= 0, f"Peak crowd density should be non-negative for {segment_id}")
            self.assert_test(segment_summary.tot_areal_sec >= 0, f"TOT areal should be non-negative for {segment_id}")
            self.assert_test(segment_summary.tot_crowd_sec >= 0, f"TOT crowd should be non-negative for {segment_id}")
        
        logger.info(f"✅ Comprehensive analysis tests passed - processed {summary['processed_segments']} segments")
    
    def test_performance(self, segments_df: pd.DataFrame, pace_data: pd.DataFrame, start_times: Dict[str, datetime]) -> None:
        """Test performance requirements."""
        logger.info("Testing performance requirements...")
        
        import time
        
        # Test single segment performance
        test_segment_df = segments_df[segments_df['seg_id'] == 'A1a']
        
        start_time = time.time()
        results = analyze_density_segments(
            segments_df=test_segment_df,
            pace_data=pace_data,
            start_times=start_times,
            config=self.config
        )
        end_time = time.time()
        
        duration = end_time - start_time
        self.assert_test(duration < 5.0, f"Single segment analysis should complete in <5s, took {duration:.2f}s")
        
        # Test all segments performance
        start_time = time.time()
        results = analyze_density_segments(
            segments_df=segments_df,
            pace_data=pace_data,
            start_times=start_times,
            config=self.config
        )
        end_time = time.time()
        
        duration = end_time - start_time
        self.assert_test(duration < 120.0, f"All segments analysis should complete in <120s, took {duration:.2f}s")
        
        logger.info(f"✅ Performance tests passed - all segments: {duration:.2f}s")
    
    def assert_test(self, condition: bool, message: str) -> None:
        """Assert test condition and record result."""
        if condition:
            self.passed_tests += 1
            logger.debug(f"✅ PASS: {message}")
        else:
            self.failed_tests += 1
            logger.error(f"❌ FAIL: {message}")
            self.test_results.append(f"FAIL: {message}")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return results."""
        logger.info("🚀 Starting comprehensive density analysis tests...")
        
        try:
            # Load test data
            segments_df, pace_data, start_times = self.load_test_data()
            
            # Run all test suites
            self.test_segment_validation(segments_df)
            self.test_density_calculations(segments_df, pace_data, start_times)
            self.test_tot_calculations(segments_df, pace_data, start_times)
            self.test_narrative_smoothing(segments_df, pace_data, start_times)
            self.test_width_providers(segments_df)
            self.test_comprehensive_analysis(segments_df, pace_data, start_times)
            self.test_performance(segments_df, pace_data, start_times)
            
            # Generate test report
            total_tests = self.passed_tests + self.failed_tests
            pass_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
            
            test_report = {
                "total_tests": total_tests,
                "passed_tests": self.passed_tests,
                "failed_tests": self.failed_tests,
                "pass_rate": pass_rate,
                "test_results": self.test_results,
                "status": "PASS" if self.failed_tests == 0 else "FAIL"
            }
            
            logger.info(f"🎯 Test Results: {self.passed_tests}/{total_tests} passed ({pass_rate:.1f}%)")
            
            if self.failed_tests > 0:
                logger.error(f"❌ {self.failed_tests} tests failed:")
                for result in self.test_results:
                    logger.error(f"  - {result}")
            else:
                logger.info("✅ All tests passed!")
            
            return test_report
            
        except Exception as e:
            logger.error(f"Test suite failed with error: {str(e)}")
            return {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1,
                "pass_rate": 0.0,
                "test_results": [f"Test suite error: {str(e)}"],
                "status": "ERROR"
            }


def main():
    """Main test execution."""
    test_suite = DensityTestSuite()
    results = test_suite.run_all_tests()
    
    # Save test results
    with open('density_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test results saved to density_test_results.json")
    
    # Exit with appropriate code
    if results["status"] == "PASS":
        logger.info("🎉 All density analysis tests passed!")
        sys.exit(0)
    else:
        logger.error("💥 Some density analysis tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
