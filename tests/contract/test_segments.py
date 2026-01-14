"""
Contract Tests for Segments GeoJSON API Parity (Issue #687)

Validates that Segments GeoJSON API responses match source artifacts.

Test Cases:
- All segments have enriched properties
- worst_los matches segment_metrics.json[seg_id].worst_los
- peak_density matches segment_metrics.json[seg_id].peak_density
- peak_rate matches segment_metrics.json[seg_id].peak_rate
- is_flagged matches presence in flags.json
- Coordinate conversion to WGS84 (EPSG:4326)
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional, List

from app.storage import create_runflow_storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day


class TestSegmentsContracts:
    """Contract tests for Segments GeoJSON API parity."""
    
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
        """Load all artifacts needed for segments tests."""
        artifacts = {}
        
        # Load segments.geojson
        try:
            artifacts['segments_geojson'] = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson") or {}
        except Exception as e:
            pytest.skip(f"Could not load segments.geojson: {e}")
        
        # Load segment_metrics.json
        try:
            segment_metrics = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json") or {}
            # Filter out summary fields
            summary_fields = ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins',
                             'overtaking_segments', 'co_presence_segments']
            artifacts['segment_metrics'] = {k: v for k, v in segment_metrics.items()
                                            if k not in summary_fields}
        except Exception as e:
            pytest.skip(f"Could not load segment_metrics.json: {e}")
        
        # Load flags.json
        try:
            flags = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
            if flags is None:
                flags = []
            artifacts['flags'] = flags
        except Exception as e:
            pytest.skip(f"Could not load flags.json: {e}")
        
        return artifacts
    
    @pytest.fixture(scope="class")
    def flagged_seg_ids(self, artifacts) -> set:
        """Extract flagged segment IDs from flags.json."""
        flags = artifacts.get('flags', [])
        flagged_seg_ids = set()
        
        if isinstance(flags, list):
            flagged_seg_ids = {f.get("seg_id") for f in flags if f.get("seg_id")}
        elif isinstance(flags, dict):
            flagged_seg_ids = {f.get("seg_id") for f in flags.get("flagged_segments", []) if f.get("seg_id")}
        
        return flagged_seg_ids
    
    @pytest.fixture(scope="class")
    def api_response(self, base_url, run_id, selected_day) -> Dict[str, Any]:
        """Call Segments GeoJSON API and return response."""
        response = requests.get(
            f"{base_url}/api/segments/geojson",
            params={"run_id": run_id, "day": selected_day},
            timeout=10
        )
        assert response.status_code == 200, f"API call failed with {response.status_code}: {response.text}"
        return response.json()
    
    def test_segments_geojson_enrichment(self, api_response, artifacts):
        """Verify all segments have enriched properties."""
        features = api_response.get('features', [])
        segments_geojson = artifacts.get('segments_geojson', {})
        source_features = segments_geojson.get('features', [])
        
        assert len(features) == len(source_features), (
            f"Feature count mismatch: API={len(features)}, "
            f"Source={len(source_features)}"
        )
        
        # Verify each feature has required enriched properties
        for feature in features:
            props = feature.get('properties', {})
            assert 'worst_los' in props, "Feature missing worst_los property"
            assert 'peak_density' in props, "Feature missing peak_density property"
            assert 'peak_rate' in props, "Feature missing peak_rate property"
            assert 'active' in props, "Feature missing active property"
            assert 'is_flagged' in props, "Feature missing is_flagged property"
    
    def test_segments_worst_los_parity(self, api_response, artifacts):
        """Verify worst_los matches segment_metrics.json[seg_id].worst_los."""
        features = api_response.get('features', [])
        segment_metrics = artifacts.get('segment_metrics', {})
        
        for feature in features:
            props = feature.get('properties', {})
            seg_id = props.get('seg_id', '')
            api_worst_los = props.get('worst_los', 'Unknown')
            
            if seg_id in segment_metrics:
                expected_worst_los = segment_metrics[seg_id].get('worst_los', 'Unknown')
                assert api_worst_los == expected_worst_los, (
                    f"worst_los mismatch for {seg_id}: API={api_worst_los}, "
                    f"Expected (from segment_metrics.json)={expected_worst_los}"
                )
    
    def test_segments_peak_density_parity(self, api_response, artifacts):
        """Verify peak_density matches segment_metrics.json[seg_id].peak_density."""
        features = api_response.get('features', [])
        segment_metrics = artifacts.get('segment_metrics', {})
        
        for feature in features:
            props = feature.get('properties', {})
            seg_id = props.get('seg_id', '')
            api_peak_density = props.get('peak_density', 0.0)
            
            if seg_id in segment_metrics:
                expected_peak_density = segment_metrics[seg_id].get('peak_density', 0.0)
                assert abs(api_peak_density - expected_peak_density) < 0.0001, (
                    f"peak_density mismatch for {seg_id}: API={api_peak_density}, "
                    f"Expected (from segment_metrics.json)={expected_peak_density}"
                )
    
    def test_segments_peak_rate_parity(self, api_response, artifacts):
        """Verify peak_rate matches segment_metrics.json[seg_id].peak_rate."""
        features = api_response.get('features', [])
        segment_metrics = artifacts.get('segment_metrics', {})
        
        for feature in features:
            props = feature.get('properties', {})
            seg_id = props.get('seg_id', '')
            api_peak_rate = props.get('peak_rate', 0.0)
            
            if seg_id in segment_metrics:
                expected_peak_rate = segment_metrics[seg_id].get('peak_rate', 0.0)
                assert abs(api_peak_rate - expected_peak_rate) < 0.01, (
                    f"peak_rate mismatch for {seg_id}: API={api_peak_rate}, "
                    f"Expected (from segment_metrics.json)={expected_peak_rate}"
                )
    
    def test_segments_is_flagged_parity(self, api_response, flagged_seg_ids):
        """Verify is_flagged matches presence in flags.json."""
        features = api_response.get('features', [])
        
        for feature in features:
            props = feature.get('properties', {})
            seg_id = props.get('seg_id', '')
            api_is_flagged = props.get('is_flagged', False)
            
            expected_is_flagged = seg_id in flagged_seg_ids
            assert api_is_flagged == expected_is_flagged, (
                f"is_flagged mismatch for {seg_id}: API={api_is_flagged}, "
                f"Expected (from flags.json)={expected_is_flagged}"
            )
    
    def test_segments_coordinate_conversion(self, api_response):
        """Verify coordinates are WGS84 (EPSG:4326), not Web Mercator."""
        features = api_response.get('features', [])
        
        for feature in features:
            geometry = feature.get('geometry', {})
            if not geometry:
                continue
            
            coords = geometry.get('coordinates', [])
            if not coords:
                continue
            
            # WGS84 longitude should be between -180 and 180
            # WGS84 latitude should be between -90 and 90
            # Web Mercator coordinates would be much larger (e.g., -20037508 to 20037508)
            
            def check_coord(coord):
                """Recursively check coordinates."""
                if isinstance(coord, (list, tuple)):
                    if len(coord) >= 2 and isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float)):
                        lon, lat = coord[0], coord[1]
                        assert -180 <= lon <= 180, f"Longitude {lon} out of WGS84 range (-180 to 180)"
                        assert -90 <= lat <= 90, f"Latitude {lat} out of WGS84 range (-90 to 90)"
                    else:
                        for item in coord:
                            check_coord(item)
            
            check_coord(coords)
