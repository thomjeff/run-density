"""
Unit tests for validating analysis.json matches request payload.

Phase 2: analysis.json Validation (Issue #553)
"""

import pytest
import tempfile
from pathlib import Path
import pandas as pd
import json

from app.core.v2.analysis_config import generate_analysis_json, load_analysis_json


class TestAnalysisJsonValidation:
    """Test that analysis.json matches request payload exactly."""
    
    @pytest.fixture
    def setup_test_data(self, tmp_path):
        """Set up test data files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create runner files
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2", "3"],
            "pace": [4.0, 4.5, 5.0],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["4", "5"],
            "pace": [5.0, 5.5],
        })
        half_runners.to_csv(data_dir / "half_runners.csv", index=False)
        
        return str(data_dir)
    
    def test_analysis_json_matches_request(self, setup_test_data, tmp_path, monkeypatch):
        """Test that analysis.json matches request payload exactly."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        request_payload = {
            "description": "Test analysis",
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                },
                {
                    "name": "half",
                    "day": "sun",
                    "start_time": 460,
                    "event_duration_minutes": 180,
                    "runners_file": "half_runners.csv",
                    "gpx_file": "half.gpx"
                }
            ]
        }
        
        run_id = "test-run"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        analysis_config = generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path
        )
        
        # Verify description matches
        assert analysis_config["description"] == "Test analysis"
        
        # Verify file names match
        assert analysis_config["segments_file"] == "segments.csv"
        assert analysis_config["flow_file"] == "flow.csv"
        assert analysis_config["locations_file"] == "locations.csv"
        
        # Verify events match
        assert len(analysis_config["events"]) == 2
        
        full_event = next(e for e in analysis_config["events"] if e["name"] == "full")
        assert full_event["day"] == "sun"
        assert full_event["start_time"] == 420
        assert full_event["event_duration_minutes"] == 390
        assert full_event["runners_file"] == "full_runners.csv"
        assert full_event["gpx_file"] == "full.gpx"
        
        half_event = next(e for e in analysis_config["events"] if e["name"] == "half")
        assert half_event["day"] == "sun"
        assert half_event["start_time"] == 460
        assert half_event["event_duration_minutes"] == 180
        assert half_event["runners_file"] == "half_runners.csv"
        assert half_event["gpx_file"] == "half.gpx"
    
    def test_analysis_json_runner_counts(self, setup_test_data, tmp_path, monkeypatch):
        """Test that runner counts are accurate."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        request_payload = {
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                },
                {
                    "name": "half",
                    "day": "sun",
                    "start_time": 460,
                    "event_duration_minutes": 180,
                    "runners_file": "half_runners.csv",
                    "gpx_file": "half.gpx"
                }
            ]
        }
        
        run_id = "test-run"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        analysis_config = generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path
        )
        
        # Verify runner counts
        assert analysis_config["runners"] == 5  # 3 full + 2 half
        
        full_event = next(e for e in analysis_config["events"] if e["name"] == "full")
        assert full_event["runners"] == 3
        
        half_event = next(e for e in analysis_config["events"] if e["name"] == "half")
        assert half_event["runners"] == 2
    
    def test_analysis_json_event_durations(self, setup_test_data, tmp_path, monkeypatch):
        """Test that event durations match request."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        request_payload = {
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
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
        
        run_id = "test-run"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        analysis_config = generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path
        )
        
        # Verify event duration
        full_event = next(e for e in analysis_config["events"] if e["name"] == "full")
        assert full_event["event_duration_minutes"] == 390
    
    def test_analysis_json_start_times(self, setup_test_data, tmp_path, monkeypatch):
        """Test that start times match request."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        request_payload = {
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                },
                {
                    "name": "half",
                    "day": "sun",
                    "start_time": 460,
                    "event_duration_minutes": 180,
                    "runners_file": "half_runners.csv",
                    "gpx_file": "half.gpx"
                }
            ]
        }
        
        run_id = "test-run"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        analysis_config = generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path
        )
        
        # Verify start times dictionary
        assert analysis_config["start_times"]["full"] == 420
        assert analysis_config["start_times"]["half"] == 460
    
    def test_analysis_json_data_files(self, setup_test_data, tmp_path, monkeypatch):
        """Test that data_files paths are correct."""
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        request_payload = {
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
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
        
        run_id = "test-run"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        analysis_config = generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path
        )
        
        # Verify data_files structure
        data_files = analysis_config["data_files"]
        assert data_files["segments"] == f"{setup_test_data}/segments.csv"
        assert data_files["flow"] == f"{setup_test_data}/flow.csv"
        assert data_files["locations"] == f"{setup_test_data}/locations.csv"
        assert data_files["runners"]["full"] == f"{setup_test_data}/full_runners.csv"
        assert data_files["gpx"]["full"] == f"{setup_test_data}/full.gpx"

