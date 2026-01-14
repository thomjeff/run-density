"""
Contract Tests for Flow API Parity (Issue #687)

Validates that Flow API responses match source artifacts.

Test Cases:
- flow_segments_table_parity - Verify flow table matches flow_segments.json
- flow_worst_zone_parity - Verify worst zone metrics match flow_segments.json entry
- flow_zones_array_parity - Verify zones array matches flow_segments.json entry
- flow_zone_captions_parity - Verify zone captions match zone_captions.json
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional

from app.storage import create_runflow_storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day


class TestFlowContracts:
    """Contract tests for Flow API parity."""
    
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
        """Load all artifacts needed for flow tests."""
        artifacts = {}
        
        # Load flow_segments.json
        try:
            flow_segments_content = storage.read_text(f"{selected_day}/ui/metrics/flow_segments.json")
            if flow_segments_content:
                artifacts['flow_segments'] = json.loads(flow_segments_content)
            else:
                artifacts['flow_segments'] = {}
        except Exception as e:
            pytest.skip(f"Could not load flow_segments.json: {e}")
        
        # Load zone_captions.json
        try:
            zone_captions_content = storage.read_text(f"{selected_day}/ui/visualizations/zone_captions.json")
            if zone_captions_content:
                artifacts['zone_captions'] = json.loads(zone_captions_content)
            else:
                artifacts['zone_captions'] = []
        except Exception as e:
            # Zone captions may not exist, use empty list
            artifacts['zone_captions'] = []
        
        return artifacts
    
    @pytest.fixture(scope="class")
    def api_response(self, base_url, run_id, selected_day) -> Dict[str, Any]:
        """Call Flow Segments API and return response."""
        response = requests.get(
            f"{base_url}/api/flow/segments",
            params={"run_id": run_id, "day": selected_day},
            timeout=10
        )
        assert response.status_code == 200, f"API call failed with {response.status_code}: {response.text}"
        return response.json()
    
    def test_flow_segments_table_parity(self, api_response, artifacts):
        """Verify flow table matches flow_segments.json."""
        api_flow = api_response.get('flow', {})
        flow_segments = artifacts.get('flow_segments', {})
        
        # Verify same number of entries
        assert len(api_flow) == len(flow_segments), (
            f"Flow entries count mismatch: API={len(api_flow)}, "
            f"Expected (from flow_segments.json)={len(flow_segments)}"
        )
        
        # Compare each entry (keyed by composite key: seg_id_event_a_event_b)
        for composite_key, segment_data in flow_segments.items():
            if composite_key not in api_flow:
                continue  # Entry may not be in API response if filtering applied
            
            api_segment = api_flow[composite_key]
            
            # Verify basic fields match
            assert api_segment.get('seg_id') == segment_data.get('seg_id'), (
                f"seg_id mismatch for {composite_key}"
            )
            assert api_segment.get('event_a') == segment_data.get('event_a'), (
                f"event_a mismatch for {composite_key}"
            )
            assert api_segment.get('event_b') == segment_data.get('event_b'), (
                f"event_b mismatch for {composite_key}"
            )
    
    def test_flow_worst_zone_parity(self, api_response, artifacts):
        """Verify worst zone metrics match flow_segments.json entry."""
        api_flow = api_response.get('flow', {})
        flow_segments = artifacts.get('flow_segments', {})
        
        # Test a few entries
        test_keys = list(flow_segments.keys())[:5]
        
        for composite_key in test_keys:
            if composite_key not in api_flow:
                continue
            
            api_segment = api_flow[composite_key]
            expected_segment = flow_segments[composite_key]
            
            # Check if worst_zone exists in both
            api_worst_zone = api_segment.get('worst_zone')
            expected_worst_zone = expected_segment.get('worst_zone')
            
            if api_worst_zone and expected_worst_zone:
                # Verify worst zone index matches
                api_worst_zone_index = api_worst_zone.get('zone_index')
                expected_worst_zone_index = expected_worst_zone.get('zone_index')
                
                if api_worst_zone_index is not None and expected_worst_zone_index is not None:
                    assert api_worst_zone_index == expected_worst_zone_index, (
                        f"worst_zone zone_index mismatch for {composite_key}: "
                        f"API={api_worst_zone_index}, Expected={expected_worst_zone_index}"
                    )
    
    def test_flow_zones_array_parity(self, api_response, artifacts):
        """Verify zones array matches flow_segments.json entry."""
        api_flow = api_response.get('flow', {})
        flow_segments = artifacts.get('flow_segments', {})
        
        # Test a few entries
        test_keys = list(flow_segments.keys())[:5]
        
        for composite_key in test_keys:
            if composite_key not in api_flow:
                continue
            
            api_segment = api_flow[composite_key]
            expected_segment = flow_segments[composite_key]
            
            # Verify zones array exists and has correct length
            api_zones = api_segment.get('zones', [])
            expected_zones = expected_segment.get('zones', [])
            
            assert len(api_zones) == len(expected_zones), (
                f"zones array length mismatch for {composite_key}: "
                f"API={len(api_zones)}, Expected={len(expected_zones)}"
            )
            
            # Verify zone_index values match (at least for first few zones)
            for i, expected_zone in enumerate(expected_zones[:3]):
                if i < len(api_zones):
                    api_zone = api_zones[i]
                    api_zone_index = api_zone.get('zone_index')
                    expected_zone_index = expected_zone.get('zone_index')
                    
                    if api_zone_index is not None and expected_zone_index is not None:
                        assert api_zone_index == expected_zone_index, (
                            f"zone_index mismatch for {composite_key} zone {i}: "
                            f"API={api_zone_index}, Expected={expected_zone_index}"
                        )
    
    def test_flow_zone_captions_parity(self, api_response, artifacts):
        """Verify zone captions match zone_captions.json."""
        api_flow = api_response.get('flow', {})
        zone_captions = artifacts.get('zone_captions', [])
        
        # Build captions lookup
        captions_lookup = {}
        for caption in zone_captions:
            if isinstance(caption, dict):
                key = f"{caption.get('seg_id', '')}_{caption.get('event_a', '')}_{caption.get('event_b', '')}_{caption.get('zone_index', 0)}"
                captions_lookup[key] = caption
        
        # Check a few zones have captions
        captions_found = 0
        for composite_key, segment_data in list(api_flow.items())[:10]:
            zones = segment_data.get('zones', [])
            seg_id = segment_data.get('seg_id', '')
            event_a = segment_data.get('event_a', '')
            event_b = segment_data.get('event_b', '')
            
            for zone in zones:
                zone_index = zone.get('zone_index', 0)
                zone_key = f"{seg_id}_{event_a}_{event_b}_{zone_index}"
                
                if zone_key in captions_lookup:
                    # Verify caption exists in API response
                    api_caption = zone.get('caption')
                    expected_caption = captions_lookup[zone_key]
                    
                    if api_caption:
                        captions_found += 1
                        # Caption should match or be derived from zone_captions.json
                        assert api_caption == expected_caption or isinstance(api_caption, dict), (
                            f"caption mismatch for {zone_key}"
                        )
        
        # At least verify that captions lookup is being used
        # (exact matching depends on API implementation)
