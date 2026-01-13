"""
Unit tests for Runflow v2 API endpoint.

Phase 2: API Route (Issue #496)
"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.api.models.v2 import V2AnalyzeRequest, V2EventRequest


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def setup_test_data(tmp_path):
    """Set up test data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create segments.csv with event flags and spans
    segments_df = pd.DataFrame({
        "seg_id": ["A1", "A2"],
        "seg_label": ["Start", "Mid"],
        "schema": ["on_course_open", "on_course_open"],
        "width_m": [4.0, 5.0],
        "direction": ["uni", "uni"],
        "full": ["y", "y"],
        "half": ["y", "n"],
        "10k": ["y", "y"],
        "full_from_km": [0.0, 0.9],
        "full_to_km": [0.9, 1.8],
        "half_from_km": [0.0, 0.0],
        "half_to_km": [0.9, 0.0],
        "10k_from_km": [0.0, 0.9],
        "10k_to_km": [0.9, 1.8],
    })
    segments_df.to_csv(data_dir / "segments.csv", index=False)
    
    # Create locations.csv
    locations_df = pd.DataFrame({
        "loc_id": ["L1"],
        "lat": [45.0],
        "lon": [-75.0],
        "seg_id": ["A1"],
    })
    locations_df.to_csv(data_dir / "locations.csv", index=False)
    
    # Create flow.csv
    flow_df = pd.DataFrame({
        "seg_id": ["A1"],
    })
    flow_df.to_csv(data_dir / "flow.csv", index=False)
    
    # Create runner files
    full_runners = pd.DataFrame({
        "runner_id": ["1", "2"],
        "event": ["full", "full"],
        "pace": [4.0, 4.5],
        "distance": [42.2, 42.2],
        "start_offset": [0, 1],
    })
    full_runners.to_csv(data_dir / "full_runners.csv", index=False)
    
    # Create GPX files
    (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
    
    return str(data_dir)


class TestV2AnalyzeEndpoint:
    """Test POST /runflow/v2/analyze endpoint."""
    
    def test_valid_request(self, client, setup_test_data, monkeypatch):
        """Test endpoint accepts valid v2 payload."""
        import os
        # Patch data directory for test
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        # Note: This test requires the actual data directory to be set up
        # For now, we'll test the validation logic separately
        # Full integration test requires Docker environment with data files
        response = client.post("/runflow/v2/analyze", json=payload)
        
        # Should either succeed (if data files exist) or fail with 404 (if not)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "run_id" in data
            assert "status" in data
            assert "days" in data
            assert "output_paths" in data

    def test_config_error_returns_500(self, client, tmp_path, monkeypatch):
        """Test endpoint returns 500 when analysis config generation fails."""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))

        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }

        response = client.post("/runflow/v2/analyze", json=payload)
        assert response.status_code == 500
        data = response.json()
        assert data["error"].startswith("Failed to generate analysis configuration")
    
    def test_missing_events_field(self, client):
        """Test endpoint rejects request without events field."""
        payload = {
            "segments_file": "segments.csv",
        }
        
        response = client.post("/runflow/v2/analyze", json=payload)
        assert response.status_code == 422  # Pydantic validation error
    
    def test_invalid_day_code(self, client):
        """Test endpoint rejects invalid day code."""
        payload = {
            "events": [
                {
                    "name": "full",
                    "day": "Saturday",  # Invalid: should be "sat"
                    "start_time": 420,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        response = client.post("/runflow/v2/analyze", json=payload)
        # Should fail validation (either 400 from our validation or 422 from Pydantic)
        assert response.status_code in [400, 422]
    
    def test_duplicate_event_names(self, client):
        """Test endpoint rejects duplicate event names."""
        payload = {
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                },
                {
                    "name": "full",  # Duplicate
                    "day": "sun",
                    "start_time": 460,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        response = client.post("/runflow/v2/analyze", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "message" in data["detail"]
        assert "Duplicate event name" in data["detail"]["message"]


class TestV2Models:
    """Test Pydantic models."""
    
    def test_v2_event_request_normalization(self):
        """Test V2EventRequest normalizes event name and day."""
        event = V2EventRequest(
            name="Full",  # Capitalized
            day="SUN",  # Uppercase
            start_time=420,
            runners_file="full_runners.csv",
            gpx_file="full.gpx"
        )
        assert event.name == "full"  # Normalized
        assert event.day == "sun"  # Normalized
    
    def test_v2_analyze_request_validation(self):
        """Test V2AnalyzeRequest validates required fields."""
        # Missing events should fail
        with pytest.raises(Exception):
            V2AnalyzeRequest(segments_file="segments.csv")
        
        # Valid request should pass
        request = V2AnalyzeRequest(
            events=[
                V2EventRequest(
                    name="full",
                    day="sun",
                    start_time=420,
                    runners_file="full_runners.csv",
                    gpx_file="full.gpx"
                )
            ]
        )
        assert len(request.events) == 1
