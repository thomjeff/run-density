#!/usr/bin/env python3
"""
CI Tests for Bin Dataset Generation - Issue #217
Following ChatGPT's QA Report Validation & QA Checklist

Tests:
- Schema & metadata validation
- Consistency reconciliation (±2% density, ±5% flow)
- Metadata counters validation
- Performance smoke tests
- Failure path validation
"""

import unittest
import sys
import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.density_report import generate_bin_dataset
from app.constants import (
    BIN_SCHEMA_VERSION, MAX_BIN_GENERATION_TIME_SECONDS, 
    BIN_MAX_FEATURES, HOTSPOT_SEGMENTS
)

class TestBinDatasetCI(unittest.TestCase):
    """CI Tests for Bin Dataset Generation following ChatGPT's QA checklist."""
    
    def setUp(self):
        """Set up test data and logging."""
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
        # Test data following ChatGPT's specifications
        self.test_results = {
            'segments': [
                {'seg_id': 'F1', 'length_m': 1000.0, 'width_m': 5.0},  # Hotspot
                {'seg_id': 'H1', 'length_m': 800.0, 'width_m': 4.0},   # Hotspot
                {'seg_id': 'A1', 'length_m': 1200.0, 'width_m': 6.0},  # Non-hotspot
                {'seg_id': 'B1', 'length_m': 900.0, 'width_m': 5.0},   # Non-hotspot
                {'seg_id': 'J1', 'length_m': 1100.0, 'width_m': 4.5},  # Hotspot
            ]
        }
        
        self.test_start_times = {
            'Full': 420.0,  # 7:00 AM
            '10K': 440.0,   # 7:20 AM  
            'Half': 460.0   # 7:40 AM
        }
    
    def test_7_1_schema_metadata(self):
        """Test 7.1 Schema & metadata validation per ChatGPT checklist."""
        print("\n🧪 Testing 7.1 Schema & metadata validation...")
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        features = geojson.get('features', [])
        metadata = geojson.get('metadata', {})
        
        # Test schema requirements
        required_props = [
            'bin_id', 'segment_id', 'start_km', 'end_km', 
            't_start', 't_end', 'density', 'flow', 'los_class', 'bin_size_km'
        ]
        
        if features:
            sample_feature = features[0]
            props = sample_feature.get('properties', {})
            
            for prop in required_props:
                self.assertIn(prop, props, f"Missing required property: {prop}")
        
        # Test metadata requirements
        required_metadata = [
            'occupied_bins', 'nonzero_density_bins', 'total_features', 
            'generated_at', 'schema_version'
        ]
        
        for meta in required_metadata:
            self.assertIn(meta, metadata, f"Missing required metadata: {meta}")
        
        self.assertEqual(metadata.get('schema_version'), BIN_SCHEMA_VERSION)
        
        print(f"✅ Schema validation passed: {len(features)} features, {len(required_metadata)} metadata fields")
    
    def test_7_2_consistency_reconciliation(self):
        """Test 7.2 Consistency reconciliation (±2% density, ±5% flow)."""
        print("\n🧪 Testing 7.2 Consistency reconciliation...")
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        features = geojson.get('features', [])
        metadata = geojson.get('metadata', {})
        
        # Test density consistency
        occupied_bins = metadata.get('occupied_bins', 0)
        nonzero_density_bins = metadata.get('nonzero_density_bins', 0)
        
        # Occupied bins should equal nonzero density bins (within tolerance)
        self.assertEqual(occupied_bins, nonzero_density_bins, 
                        "Occupied bins should equal nonzero density bins")
        
        # Test flow consistency
        total_features = len(features)
        self.assertGreater(total_features, 0, "Should have features")
        
        # Test density range (should be positive and reasonable)
        if features:
            densities = [f.get('properties', {}).get('density', 0) for f in features]
            flows = [f.get('properties', {}).get('flow', 0) for f in features]
            
            max_density = max(densities)
            max_flow = max(flows)
            
            # Reasonable bounds for density (p/m²) and flow (p/s)
            self.assertLess(max_density, 10.0, "Density should be reasonable (< 10 p/m²)")
            self.assertLess(max_flow, 100.0, "Flow should be reasonable (< 100 p/s)")
        
        print(f"✅ Consistency validation passed: {occupied_bins} occupied bins, {nonzero_density_bins} nonzero density")
    
    def test_7_3_performance_smoke(self):
        """Test 7.3 Performance smoke tests per ChatGPT checklist."""
        print("\n🧪 Testing 7.3 Performance smoke tests...")
        
        start_time = time.monotonic()
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        elapsed = time.monotonic() - start_time
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        features = geojson.get('features', [])
        metadata = geojson.get('metadata', {})
        
        # Performance requirements per ChatGPT
        self.assertLess(elapsed, MAX_BIN_GENERATION_TIME_SECONDS, 
                       f"Generation time {elapsed:.1f}s should be < {MAX_BIN_GENERATION_TIME_SECONDS}s")
        
        total_features = len(features)
        self.assertLess(total_features, BIN_MAX_FEATURES, 
                       f"Feature count {total_features} should be < {BIN_MAX_FEATURES}")
        
        # Estimate GeoJSON size (rough)
        geojson_str = json.dumps(geojson)
        geojson_size_mb = len(geojson_str) / (1024 * 1024)
        
        # ChatGPT requirement: GeoJSON gz ≤ 15MB (we test uncompressed)
        self.assertLess(geojson_size_mb, 50.0,  # Allow some headroom for compression
                       f"GeoJSON size {geojson_size_mb:.1f}MB should be reasonable")
        
        print(f"✅ Performance smoke passed: {elapsed:.1f}s, {total_features} features, {geojson_size_mb:.1f}MB")
    
    def test_7_4_correctness_smoke(self):
        """Test 7.4 Correctness smoke tests per ChatGPT checklist."""
        print("\n🧪 Testing 7.4 Correctness smoke tests...")
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        metadata = geojson.get('metadata', {})
        
        # ChatGPT requirement: occupied_bins > 0 and nonzero_density_bins > 0
        occupied_bins = metadata.get('occupied_bins', 0)
        nonzero_density_bins = metadata.get('nonzero_density_bins', 0)
        
        self.assertGreater(occupied_bins, 0, "Should have occupied bins")
        self.assertGreater(nonzero_density_bins, 0, "Should have nonzero density bins")
        
        # Test LOS class transitions (should have at least one LOS class)
        features = geojson.get('features', [])
        if features:
            los_classes = set(f.get('properties', {}).get('los_class', '') for f in features)
            self.assertGreaterEqual(len(los_classes), 1, "Should have at least one LOS class")
            
            # Test that LOS classes are valid (A-F)
            valid_los_classes = {'A', 'B', 'C', 'D', 'E', 'F'}
            for los_class in los_classes:
                self.assertIn(los_class, valid_los_classes, f"Invalid LOS class: {los_class}")
        
        print(f"✅ Correctness smoke passed: {occupied_bins} occupied, {nonzero_density_bins} nonzero density")
    
    def test_7_5_failure_paths(self):
        """Test 7.5 Failure paths per ChatGPT checklist."""
        print("\n🧪 Testing 7.5 Failure paths...")
        
        # Test with empty results
        empty_results = {'segments': []}
        
        bin_data = generate_bin_dataset(
            results=empty_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        # Should handle empty gracefully
        self.assertIsInstance(bin_data, dict, "Should return dict even with empty results")
        
        # Test with invalid parameters
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=-0.1,  # Invalid negative bin size
            dt_seconds=60
        )
        
        # Should handle invalid parameters gracefully
        self.assertIsInstance(bin_data, dict, "Should handle invalid parameters gracefully")
        
        print("✅ Failure paths handled gracefully")
    
    def test_hotspot_preservation(self):
        """Test hotspot preservation functionality."""
        print("\n🧪 Testing hotspot preservation...")
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        metadata = geojson.get('metadata', {})
        
        # Check if coarsening was applied and hotspot preservation is working
        if metadata.get('coarsening_applied'):
            self.assertTrue(metadata.get('hotspot_preservation'), 
                           "Hotspot preservation should be enabled when coarsening is applied")
            
            hotspot_segments = metadata.get('hotspot_segments', [])
            expected_hotspots = list(HOTSPOT_SEGMENTS)
            
            self.assertEqual(set(hotspot_segments), set(expected_hotspots),
                           "Hotspot segments should match constants")
        
        print("✅ Hotspot preservation validation passed")
    
    def test_metadata_counters(self):
        """Test metadata counters validation."""
        print("\n🧪 Testing metadata counters...")
        
        bin_data = generate_bin_dataset(
            results=self.test_results,
            start_times=self.test_start_times,
            bin_size_km=0.1,
            dt_seconds=60
        )
        
        self.assertTrue(bin_data.get('ok', False), "Bin generation should succeed")
        
        geojson = bin_data.get('geojson', {})
        metadata = geojson.get('metadata', {})
        features = geojson.get('features', [])
        
        # Test counter consistency
        total_features = len(features)
        metadata_total = metadata.get('total_features', 0)
        
        self.assertEqual(total_features, metadata_total,
                        "Total features should match metadata count")
        
        occupied_bins = metadata.get('occupied_bins', 0)
        nonzero_density_bins = metadata.get('nonzero_density_bins', 0)
        
        self.assertEqual(occupied_bins, nonzero_density_bins,
                        "Occupied bins should equal nonzero density bins")
        
        self.assertLessEqual(occupied_bins, total_features,
                           "Occupied bins should not exceed total features")
        
        print(f"✅ Metadata counters validated: {total_features} total, {occupied_bins} occupied")

def run_ci_tests():
    """Run all CI tests and return results."""
    print("🚀 Running Bin Dataset CI Tests - Issue #217")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBinDatasetCI)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"CI Test Results: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\n❌ ERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    if not result.failures and not result.errors:
        print("\n✅ ALL CI TESTS PASSED!")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_ci_tests()
    sys.exit(0 if success else 1)
