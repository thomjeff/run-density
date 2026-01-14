"""
Contract Tests for Health API Parity (Issue #687)

Validates health data presence and structure.

Test Cases:
- health_data_presence - Verify health.json exists and is readable
- health_data_structure - Verify health.json has expected structure
- required_artifacts_presence - Verify all required artifacts exist for a run
- artifact_readability - Verify all artifacts are valid JSON/GeoJSON
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional
from pathlib import Path

from app.storage import create_runflow_storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day


class TestHealthContracts:
    """Contract tests for Health API parity."""
    
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
    def api_response(self, base_url) -> Dict[str, Any]:
        """Call Health API and return response."""
        response = requests.get(
            f"{base_url}/api/health/data",
            timeout=10
        )
        assert response.status_code == 200, f"API call failed with {response.status_code}: {response.text}"
        return response.json()
    
    def test_health_data_presence(self, storage, selected_day):
        """Verify health.json exists and is readable."""
        try:
            health_data = storage.read_json(f"{selected_day}/ui/metadata/health.json")
            assert health_data is not None, "health.json should exist and be readable"
        except Exception as e:
            pytest.fail(f"Could not read health.json: {e}")
    
    def test_health_data_structure(self, api_response):
        """Verify health.json has expected structure."""
        # Health data should be a dictionary
        assert isinstance(api_response, dict), "health.json should be a dictionary"
        
        # Common fields that may exist in health.json
        # (exact structure may vary, so we check for basic validity)
        assert len(api_response) > 0, "health.json should not be empty"
    
    def test_required_artifacts_presence(self, storage, selected_day):
        """Verify all required artifacts exist for a run."""
        required_artifacts = [
            f"{selected_day}/ui/metadata/meta.json",
            f"{selected_day}/ui/metrics/segment_metrics.json",
            f"{selected_day}/ui/metrics/flags.json",
            f"{selected_day}/ui/geospatial/segments.geojson",
            f"{selected_day}/ui/metadata/health.json",
        ]
        
        missing_artifacts = []
        for artifact_path in required_artifacts:
            try:
                data = storage.read_json(artifact_path)
                if data is None:
                    missing_artifacts.append(artifact_path)
            except Exception:
                missing_artifacts.append(artifact_path)
        
        assert len(missing_artifacts) == 0, (
            f"Missing required artifacts: {', '.join(missing_artifacts)}"
        )
    
    def test_artifact_readability(self, storage, selected_day):
        """Verify all artifacts are valid JSON/GeoJSON."""
        artifacts_to_check = [
            f"{selected_day}/ui/metadata/meta.json",
            f"{selected_day}/ui/metrics/segment_metrics.json",
            f"{selected_day}/ui/metrics/flags.json",
            f"{selected_day}/ui/geospatial/segments.geojson",
            f"{selected_day}/ui/metadata/health.json",
        ]
        
        # Optional artifacts (may not exist in all runs)
        optional_artifacts = [
            f"{selected_day}/ui/visualizations/captions.json",
            f"{selected_day}/ui/metrics/flow_segments.json",
            f"{selected_day}/ui/visualizations/zone_captions.json",
        ]
        
        all_artifacts = artifacts_to_check + optional_artifacts
        
        for artifact_path in all_artifacts:
            try:
                data = storage.read_json(artifact_path)
                # If data is None, it doesn't exist (which is OK for optional artifacts)
                if data is not None:
                    # Verify it's a valid JSON structure (dict or list)
                    assert isinstance(data, (dict, list)), (
                        f"{artifact_path} should be a dict or list, got {type(data)}"
                    )
            except json.JSONDecodeError as e:
                pytest.fail(f"{artifact_path} is not valid JSON: {e}")
            except Exception:
                # For optional artifacts, it's OK if they don't exist
                if artifact_path not in optional_artifacts:
                    raise
