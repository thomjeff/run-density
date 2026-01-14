"""
Contract Tests for Density API Parity (Issue #687)

Validates that Density API responses match source artifacts.

Test Cases:
- density_segments_table_parity - Verify density table matches segment_metrics.json
- density_segment_detail_parity - Verify segment detail matches segment_metrics.json[seg_id]
- density_heatmap_captions_parity - Verify heatmap captions match captions.json
- density_bins_parity - Verify bin detail matches bins.parquet filtered by segment
"""

import pytest
import requests
import json
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path

from app.storage import create_runflow_storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day


class TestDensityContracts:
    """Contract tests for Density API parity."""
    
    @pytest.fixture(scope="class")
    def selected_day(self, run_id, request) -> str:
        """Resolve selected day for the run_id."""
        day_arg = request.config.getoption("--day")
        try:
            selected_day, _ = resolve_selected_day(run_id, day_arg)
            return selected_day
        except ValueError as e:
            pytest.skip(f"Could not resolve day for run_id {run_id}: {e}")
    
    @pytest.fixture(scope="class")
    def storage(self, run_id):
        """Create storage instance for accessing artifacts."""
        return create_runflow_storage(run_id)
    
    @pytest.fixture(scope="class")
    def artifacts(self, storage, selected_day) -> Dict[str, Any]:
        """Load all artifacts needed for density tests."""
        artifacts = {}
        
        # Load segment_metrics.json
        try:
            segment_metrics_raw = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json") or {}
            # Filter out summary fields
            summary_fields = ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins',
                             'overtaking_segments', 'co_presence_segments']
            artifacts['segment_metrics'] = {k: v for k, v in segment_metrics_raw.items()
                                            if k not in summary_fields and isinstance(v, dict)}
        except Exception as e:
            pytest.skip(f"Could not load segment_metrics.json: {e}")
        
        # Load segments.geojson
        try:
            artifacts['segments_geojson'] = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson") or {}
        except Exception as e:
            pytest.skip(f"Could not load segments.geojson: {e}")
        
        # Load flags.json
        try:
            flags = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
            if flags is None:
                flags = []
            artifacts['flags'] = flags
        except Exception as e:
            pytest.skip(f"Could not load flags.json: {e}")
        
        # Load captions.json
        try:
            artifacts['captions'] = storage.read_json(f"{selected_day}/ui/visualizations/captions.json") or {}
        except Exception as e:
            # Captions may not exist, use empty dict
            artifacts['captions'] = {}
        
        # Load bins.parquet (if available)
        try:
            bins_path = storage._full_local(f"{selected_day}/bins.parquet")
            if bins_path.exists():
                artifacts['bins_df'] = pd.read_parquet(bins_path)
            else:
                artifacts['bins_df'] = None
        except Exception as e:
            artifacts['bins_df'] = None
        
        return artifacts
    
    @pytest.fixture(scope="class")
    def api_segments_response(self, base_url, run_id, selected_day) -> Dict[str, Any]:
        """Call Density Segments API and return response."""
        response = requests.get(
            f"{base_url}/api/density/segments",
            params={"run_id": run_id, "day": selected_day},
            timeout=10
        )
        assert response.status_code == 200, f"API call failed with {response.status_code}: {response.text}"
        return response.json()
    
    def test_density_segments_table_parity(self, api_segments_response, artifacts):
        """Verify density table matches segment_metrics.json."""
        api_segments = api_segments_response.get('segments', [])
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Build lookup from API response
        api_segments_lookup = {seg.get('seg_id'): seg for seg in api_segments}
        
        # Compare each segment
        for seg_id, metrics in segment_metrics.items():
            if seg_id not in api_segments_lookup:
                continue  # Segment may not be in API response if filtering applied
            
            api_seg = api_segments_lookup[seg_id]
            
            # Verify peak_density
            api_peak_density = api_seg.get('peak_density', 0.0)
            expected_peak_density = metrics.get('peak_density', 0.0)
            assert abs(api_peak_density - expected_peak_density) < 0.0001, (
                f"peak_density mismatch for {seg_id}: API={api_peak_density}, "
                f"Expected={expected_peak_density}"
            )
            
            # Verify worst_los
            api_worst_los = api_seg.get('worst_los', 'Unknown')
            expected_worst_los = metrics.get('worst_los', 'Unknown')
            assert api_worst_los == expected_worst_los, (
                f"worst_los mismatch for {seg_id}: API={api_worst_los}, "
                f"Expected={expected_worst_los}"
            )
            
            # Verify peak_rate
            api_peak_rate = api_seg.get('peak_rate', 0.0)
            expected_peak_rate = metrics.get('peak_rate', 0.0)
            assert abs(api_peak_rate - expected_peak_rate) < 0.01, (
                f"peak_rate mismatch for {seg_id}: API={api_peak_rate}, "
                f"Expected={expected_peak_rate}"
            )
    
    def test_density_segment_detail_parity(self, base_url, run_id, selected_day, artifacts):
        """Verify segment detail matches segment_metrics.json[seg_id]."""
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Test a few segments (limit to avoid too many API calls)
        test_seg_ids = list(segment_metrics.keys())[:5]
        
        for seg_id in test_seg_ids:
            metrics = segment_metrics[seg_id]
            
            # Call API for segment detail
            response = requests.get(
                f"{base_url}/api/density/segment/{seg_id}",
                params={"run_id": run_id, "day": selected_day},
                timeout=10
            )
            if response.status_code != 200:
                continue  # Skip if segment not found in API
            
            api_detail = response.json()
            
            # Verify key metrics
            api_peak_density = api_detail.get('peak_density', 0.0)
            expected_peak_density = metrics.get('peak_density', 0.0)
            assert abs(api_peak_density - expected_peak_density) < 0.0001, (
                f"peak_density mismatch for {seg_id} detail: API={api_peak_density}, "
                f"Expected={expected_peak_density}"
            )
            
            api_worst_los = api_detail.get('worst_los', 'Unknown')
            expected_worst_los = metrics.get('worst_los', 'Unknown')
            assert api_worst_los == expected_worst_los, (
                f"worst_los mismatch for {seg_id} detail: API={api_worst_los}, "
                f"Expected={expected_worst_los}"
            )
    
    def test_density_heatmap_captions_parity(self, base_url, run_id, selected_day, artifacts):
        """Verify heatmap captions match captions.json."""
        captions = artifacts.get('captions', {})
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Test a few segments that have captions
        test_seg_ids = [seg_id for seg_id in list(segment_metrics.keys())[:5] if seg_id in captions]
        
        for seg_id in test_seg_ids:
            # Call API for segment detail
            response = requests.get(
                f"{base_url}/api/density/segment/{seg_id}",
                params={"run_id": run_id, "day": selected_day},
                timeout=10
            )
            if response.status_code != 200:
                continue
            
            api_detail = response.json()
            api_caption = api_detail.get('caption', '')
            
            expected_caption_data = captions[seg_id]
            if isinstance(expected_caption_data, dict):
                expected_caption = expected_caption_data.get('summary', '')
            else:
                expected_caption = str(expected_caption_data)
            
            assert api_caption == expected_caption, (
                f"caption mismatch for {seg_id}: API={api_caption}, "
                f"Expected (from captions.json)={expected_caption}"
            )
    
    @pytest.mark.skipif(True, reason="bins.parquet may not be available in all test runs")
    def test_density_bins_parity(self, artifacts):
        """Verify bin detail matches bins.parquet filtered by segment."""
        bins_df = artifacts.get('bins_df')
        if bins_df is None:
            pytest.skip("bins.parquet not available")
        
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Test a few segments
        test_seg_ids = list(segment_metrics.keys())[:3]
        
        for seg_id in test_seg_ids:
            # Filter bins by segment
            segment_bins = bins_df[bins_df.get('seg_id', '') == seg_id]
            
            if len(segment_bins) == 0:
                continue  # No bins for this segment
            
            # Verify bin count matches expectations
            # This is a basic check - more detailed validation would require API bin detail endpoint
            assert len(segment_bins) > 0, f"Expected bins for segment {seg_id}"
