"""
Unit tests for Runflow v2 validation error handling.

Phase 1: Validation Layer (Issue #553)
Tests fail-fast behavior and correct error codes.
"""

import pytest
import tempfile
import os
from pathlib import Path
import pandas as pd

from app.core.v2.validation import (
    ValidationError,
    validate_api_payload,
)


class TestValidationErrorHandling:
    """Test validation error handling and fail-fast behavior."""
    
    @pytest.fixture
    def setup_test_data(self, tmp_path):
        """Set up test data files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
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
        
        # Create flow.csv
        flow_df = pd.DataFrame({
            "seg_id": ["A1"],
            "event_a": ["full"],
            "event_b": ["half"],
        })
        flow_df.to_csv(data_dir / "flow.csv", index=False)
        
        # Create locations.csv
        locations_df = pd.DataFrame({
            "loc_id": ["L1"],
            "lat": [45.0],
            "lon": [-75.0],
            "seg_id": ["A1"],
            "full": ["y"],
            "half": ["y"],
        })
        locations_df.to_csv(data_dir / "locations.csv", index=False)
        
        # Create runner files
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2"],
            "pace": [4.0, 4.5],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        # Create GPX file
        (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        
        return str(data_dir)
    
    def test_missing_file_404(self, setup_test_data, monkeypatch):
        """Test missing file returns 404 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            "segments_file": "nonexistent.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 404
        assert "not found" in exc_info.value.message.lower()
    
    def test_invalid_start_time_400(self, setup_test_data, monkeypatch):
        """Test invalid start time returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 299,  # Too low (must be 300-1200)
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "start_time" in exc_info.value.message.lower()
        assert "300" in exc_info.value.message or "1200" in exc_info.value.message
    
    def test_missing_event_in_segments_400(self, setup_test_data, monkeypatch):
        """Test missing event in segments.csv returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "nonexistent",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "nonexistent" in exc_info.value.message.lower()
        assert "segments.csv" in exc_info.value.message.lower()
    
    def test_missing_event_in_flow_400(self, setup_test_data, monkeypatch):
        """Test missing event in flow.csv returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        # Create flow.csv without the event
        flow_df = pd.DataFrame({
            "seg_id": ["A1"],
            "event_a": ["other"],
            "event_b": ["another"],
        })
        flow_df.to_csv(Path(setup_test_data) / "flow.csv", index=False)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "flow.csv" in exc_info.value.message.lower()
    
    def test_missing_event_in_locations_400(self, setup_test_data, monkeypatch):
        """Test event with no locations returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        # Create locations.csv without the event flag
        locations_df = pd.DataFrame({
            "loc_id": ["L1"],
            "lat": [45.0],
            "lon": [-75.0],
            "seg_id": ["A1"],
            "full": ["n"],  # Event not flagged
        })
        locations_df.to_csv(Path(setup_test_data) / "locations.csv", index=False)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "locations.csv" in exc_info.value.message.lower()
        assert "no locations" in exc_info.value.message.lower()
    
    def test_malformed_gpx_406(self, setup_test_data, monkeypatch):
        """Test malformed GPX file returns 406 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        # Create invalid GPX file
        (Path(setup_test_data) / "full.gpx").write_text("not valid xml")
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 406
        assert "gpx" in exc_info.value.message.lower()
    
    def test_invalid_csv_structure_422(self, setup_test_data, monkeypatch):
        """Test invalid CSV structure returns 422 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        # Create invalid segments.csv (missing required columns)
        invalid_segments = pd.DataFrame({
            "seg_id": ["A1"],
            # Missing required columns
        })
        invalid_segments.to_csv(Path(setup_test_data) / "segments.csv", index=False)
        
        payload = {
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 422
        assert "segments.csv" in exc_info.value.message.lower()
    
    def test_invalid_event_duration_400(self, setup_test_data, monkeypatch):
        """Test invalid event duration returns 400 error."""
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
                    "event_duration_minutes": 501,  # Too high (must be 1-500)
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "event_duration_minutes" in exc_info.value.message.lower()
        assert "500" in exc_info.value.message
    
    def test_description_too_long_400(self, setup_test_data, monkeypatch):
        """Test description too long returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            "description": "x" * 255,  # Too long (max 254)
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "description" in exc_info.value.message.lower()
        assert "254" in exc_info.value.message
    
    def test_missing_required_fields_400(self, setup_test_data, monkeypatch):
        """Test missing required fields returns 400 error."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        payload = {
            # Missing segments_file, locations_file, flow_file
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload, data_dir=setup_test_data)
        assert exc_info.value.code == 400
        assert "required" in exc_info.value.message.lower()

