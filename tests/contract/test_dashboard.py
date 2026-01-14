"""
Contract Tests for Dashboard API Parity (Issue #687)

Validates that Dashboard API responses match source artifacts.

Test Cases:
- total_runners matches sum from metadata.json events
- peak_density matches calculated value from segment_metrics.json
- peak_density_los matches worst_los from segment with peak density
- segments_flagged matches count from flags.json
- bins_flagged matches count from flags.json
- overtaking_segments matches summary field in segment_metrics.json
- co_presence_segments matches summary field in segment_metrics.json
- status calculation logic (normal vs action_required)
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional
from pathlib import Path

from app.storage import create_runflow_storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day


class TestDashboardContracts:
    """Contract tests for Dashboard API parity."""
    
    @pytest.fixture(scope="class")
    def selected_day(self, run_id, request) -> str:
        """Resolve selected day for the run_id."""
        # Check for --day pytest option
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
        """Load all artifacts needed for dashboard tests."""
        artifacts = {}
        
        # Load metadata.json for events
        try:
            metadata_path = storage._full_local(f"{selected_day}/metadata.json")
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    artifacts['metadata'] = json.load(f)
            else:
                artifacts['metadata'] = {}
        except Exception as e:
            pytest.skip(f"Could not load metadata.json: {e}")
        
        # Load segment_metrics.json
        try:
            artifacts['segment_metrics'] = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json") or {}
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
    def api_response(self, base_url, run_id, selected_day) -> Dict[str, Any]:
        """Call Dashboard API and return response."""
        response = requests.get(
            f"{base_url}/api/dashboard/summary",
            params={"run_id": run_id, "day": selected_day},
            timeout=10
        )
        assert response.status_code == 200, f"API call failed with {response.status_code}: {response.text}"
        return response.json()
    
    def test_dashboard_total_runners_parity(self, api_response, artifacts):
        """Verify total_runners matches sum from metadata.json events."""
        # Calculate expected total_runners from metadata.json events
        metadata = artifacts.get('metadata', {})
        events = metadata.get('events', {})
        
        expected_total = 0
        if isinstance(events, dict):
            for ev_info in events.values():
                if isinstance(ev_info, dict):
                    expected_total += int(ev_info.get('participants', 0))
        
        # Compare with API response
        api_total = api_response.get('total_runners', 0)
        assert api_total == expected_total, (
            f"total_runners mismatch: API={api_total}, "
            f"Expected (sum of metadata.json events)={expected_total}"
        )
    
    def test_dashboard_peak_density_parity(self, api_response, artifacts):
        """Verify peak_density matches calculated value from segment_metrics.json."""
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Filter out summary fields to get segment-level data
        summary_fields = ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins',
                         'overtaking_segments', 'co_presence_segments']
        segment_level_metrics = {k: v for k, v in segment_metrics.items()
                                if k not in summary_fields}
        
        # Calculate peak density from segment-level data
        expected_peak_density = 0.0
        for seg_id, metrics in segment_level_metrics.items():
            if isinstance(metrics, dict):
                seg_peak_density = metrics.get('peak_density', 0.0)
                expected_peak_density = max(expected_peak_density, seg_peak_density)
        
        # Compare with API response (allow small floating-point tolerance)
        api_peak_density = api_response.get('peak_density', 0.0)
        assert abs(api_peak_density - expected_peak_density) < 0.0001, (
            f"peak_density mismatch: API={api_peak_density}, "
            f"Expected (calculated from segment_metrics.json)={expected_peak_density}"
        )
    
    def test_dashboard_peak_density_los_parity(self, api_response, artifacts):
        """Verify peak_density_los matches worst_los from segment with peak density."""
        segment_metrics = artifacts.get('segment_metrics', {})
        
        # Filter out summary fields
        summary_fields = ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins',
                         'overtaking_segments', 'co_presence_segments']
        segment_level_metrics = {k: v for k, v in segment_metrics.items()
                                if k not in summary_fields}
        
        # Find segment with peak density
        peak_segment_id = None
        peak_density = 0.0
        for seg_id, metrics in segment_level_metrics.items():
            if isinstance(metrics, dict):
                seg_peak_density = metrics.get('peak_density', 0.0)
                if seg_peak_density > peak_density:
                    peak_density = seg_peak_density
                    peak_segment_id = seg_id
                elif seg_peak_density == peak_density and peak_segment_id:
                    # Tie-breaker: use segment with worse LOS
                    current_los = segment_level_metrics.get(peak_segment_id, {}).get('worst_los', 'A')
                    candidate_los = metrics.get('worst_los', 'A')
                    los_order = {'F': 6, 'E': 5, 'D': 4, 'C': 3, 'B': 2, 'A': 1}
                    if los_order.get(candidate_los, 0) > los_order.get(current_los, 0):
                        peak_segment_id = seg_id
        
        # Get expected LOS from segment with peak density
        expected_los = 'A'  # Default
        if peak_segment_id and peak_segment_id in segment_level_metrics:
            expected_los = segment_level_metrics[peak_segment_id].get('worst_los', 'A')
        
        # Compare with API response
        api_los = api_response.get('peak_density_los', 'A')
        assert api_los == expected_los, (
            f"peak_density_los mismatch: API={api_los}, "
            f"Expected (worst_los from peak density segment {peak_segment_id})={expected_los}"
        )
    
    def test_dashboard_segments_flagged_parity(self, api_response, artifacts):
        """Verify segments_flagged matches count from flags.json."""
        flags = artifacts.get('flags', [])
        
        # Calculate expected segments_flagged
        expected_segments_flagged = 0
        if isinstance(flags, list):
            expected_segments_flagged = len(flags)
        elif isinstance(flags, dict):
            expected_segments_flagged = len(flags.get('flagged_segments', []))
        
        # Compare with API response
        api_segments_flagged = api_response.get('segments_flagged', 0)
        assert api_segments_flagged == expected_segments_flagged, (
            f"segments_flagged mismatch: API={api_segments_flagged}, "
            f"Expected (count from flags.json)={expected_segments_flagged}"
        )
    
    def test_dashboard_bins_flagged_parity(self, api_response, artifacts):
        """Verify bins_flagged matches count from flags.json."""
        flags = artifacts.get('flags', [])
        
        # Calculate expected bins_flagged
        expected_bins_flagged = 0
        if isinstance(flags, list):
            expected_bins_flagged = sum(f.get('flagged_bins', 0) for f in flags if isinstance(f, dict))
        elif isinstance(flags, dict):
            expected_bins_flagged = flags.get('total_bins_flagged', 0)
        
        # Compare with API response
        api_bins_flagged = api_response.get('bins_flagged', 0)
        assert api_bins_flagged == expected_bins_flagged, (
            f"bins_flagged mismatch: API={api_bins_flagged}, "
            f"Expected (sum from flags.json)={expected_bins_flagged}"
        )
    
    def test_dashboard_overtaking_segments_parity(self, api_response, artifacts):
        """Verify overtaking_segments matches summary field in segment_metrics.json."""
        segment_metrics = artifacts.get('segment_metrics', {})
        expected_overtaking = segment_metrics.get('overtaking_segments', 0)
        
        # Compare with API response
        api_overtaking = api_response.get('segments_overtaking', 0)
        assert api_overtaking == expected_overtaking, (
            f"segments_overtaking mismatch: API={api_overtaking}, "
            f"Expected (from segment_metrics.json)={expected_overtaking}"
        )
    
    def test_dashboard_copresence_segments_parity(self, api_response, artifacts):
        """Verify co_presence_segments matches summary field in segment_metrics.json."""
        segment_metrics = artifacts.get('segment_metrics', {})
        expected_copresence = segment_metrics.get('co_presence_segments', 0)
        
        # Compare with API response
        api_copresence = api_response.get('segments_copresence', 0)
        assert api_copresence == expected_copresence, (
            f"segments_copresence mismatch: API={api_copresence}, "
            f"Expected (from segment_metrics.json)={expected_copresence}"
        )
    
    def test_dashboard_status_calculation(self, api_response, artifacts):
        """Verify status calculation logic (normal vs action_required)."""
        peak_density_los = api_response.get('peak_density_los', 'A')
        segments_flagged = api_response.get('segments_flagged', 0)
        
        # Calculate expected status
        expected_status = 'normal'
        if peak_density_los in ['E', 'F'] or segments_flagged > 0:
            expected_status = 'action_required'
        
        # Compare with API response
        api_status = api_response.get('status', 'normal')
        assert api_status == expected_status, (
            f"status mismatch: API={api_status}, "
            f"Expected (normal if LOS <= D and segments_flagged == 0, else action_required)={expected_status}, "
            f"peak_density_los={peak_density_los}, segments_flagged={segments_flagged}"
        )
