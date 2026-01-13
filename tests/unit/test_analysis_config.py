"""
Unit tests for Runflow v2 analysis.json generation and helper functions.

Phase 2: analysis.json Creation (Issue #553)
"""

import pytest
import json
import tempfile
from pathlib import Path
import pandas as pd

from app.core.v2.analysis_config import (
    generate_analysis_json,
    load_analysis_json,
    get_event_names,
    get_events_by_day,
    get_event_duration_minutes,
    get_start_time,
    get_all_start_times,
    get_segments_file,
    get_flow_file,
    get_locations_file,
    get_runners_file,
    get_gpx_file,
    count_runners_in_file,
)


class TestGenerateAnalysisJson:
    """Test analysis.json generation."""
    
    def test_generate_analysis_json_basic(self, tmp_path):
        """Test basic analysis.json generation."""
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
                }
            ]
        }
        
        run_id = "test-run-123"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        # Create a dummy runners file
        runners_file = tmp_path / "data" / "full_runners.csv"
        runners_file.parent.mkdir(parents=True)
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2", "3"],
            "pace": [4.0, 4.5, 5.0]
        })
        runners_df.to_csv(runners_file, index=False)
        
        # Set DATA_ROOT environment variable
        import os
        os.environ["DATA_ROOT"] = str(tmp_path / "data")
        
        try:
            analysis_config = generate_analysis_json(
                request_payload=request_payload,
                run_id=run_id,
                run_path=run_path
            )
            
            assert analysis_config["description"] == "Test analysis"
            assert analysis_config["segments_file"] == "segments.csv"
            assert analysis_config["flow_file"] == "flow.csv"
            assert analysis_config["locations_file"] == "locations.csv"
            assert len(analysis_config["events"]) == 1
            assert analysis_config["events"][0]["name"] == "full"
            assert analysis_config["events"][0]["runners"] == 3
            assert analysis_config["runners"] == 3
            
            # Verify analysis.json file was created
            analysis_json_path = run_path / "analysis.json"
            assert analysis_json_path.exists()
            
            # Verify file content
            with open(analysis_json_path, 'r') as f:
                saved_config = json.load(f)
            assert saved_config == analysis_config
            
        finally:
            if "DATA_ROOT" in os.environ:
                del os.environ["DATA_ROOT"]
    
    def test_generate_analysis_json_default_description(self, tmp_path):
        """Test analysis.json generation with default description."""
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
        
        run_id = "test-run-456"
        run_path = tmp_path / run_id
        run_path.mkdir()
        
        # Create a dummy runners file
        runners_file = tmp_path / "data" / "full_runners.csv"
        runners_file.parent.mkdir(parents=True)
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2"],
            "pace": [4.0, 4.5]
        })
        runners_df.to_csv(runners_file, index=False)
        
        import os
        os.environ["DATA_ROOT"] = str(tmp_path / "data")
        
        try:
            analysis_config = generate_analysis_json(
                request_payload=request_payload,
                run_id=run_id,
                run_path=run_path
            )
            
            # Description should be auto-generated
            assert "description" in analysis_config
            assert analysis_config["description"].startswith("Analysis run on")
            
        finally:
            if "DATA_ROOT" in os.environ:
                del os.environ["DATA_ROOT"]


class TestLoadAnalysisJson:
    """Test analysis.json loading."""
    
    def test_load_analysis_json(self, tmp_path):
        """Test loading analysis.json from file."""
        run_path = tmp_path / "test-run"
        run_path.mkdir()
        
        analysis_json_path = run_path / "analysis.json"
        test_config = {
            "description": "Test",
            "segments_file": "segments.csv",
            "events": [{"name": "full", "day": "sun"}]
        }
        
        with open(analysis_json_path, 'w') as f:
            json.dump(test_config, f)
        
        loaded_config = load_analysis_json(run_path)
        assert loaded_config == test_config
    
    def test_load_analysis_json_not_found(self, tmp_path):
        """Test loading non-existent analysis.json raises error."""
        run_path = tmp_path / "test-run"
        run_path.mkdir()
        
        with pytest.raises(FileNotFoundError):
            load_analysis_json(run_path)


class TestHelperFunctions:
    """Test helper functions for accessing analysis.json data."""
    
    @pytest.fixture
    def sample_analysis_config(self):
        """Create a sample analysis.json config for testing."""
        return {
            "description": "Test analysis",
            "data_dir": "data",
            "segments_file": "segments.csv",
            "flow_file": "flow.csv",
            "locations_file": "locations.csv",
            "runners": 100,
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx",
                    "runners": 50
                },
                {
                    "name": "half",
                    "day": "sun",
                    "start_time": 460,
                    "event_duration_minutes": 180,
                    "runners_file": "half_runners.csv",
                    "gpx_file": "half.gpx",
                    "runners": 50
                },
                {
                    "name": "elite",
                    "day": "sat",
                    "start_time": 480,
                    "event_duration_minutes": 45,
                    "runners_file": "elite_runners.csv",
                    "gpx_file": "elite.gpx",
                    "runners": 10
                }
            ],
            "event_days": ["sat", "sun"],
            "event_names": ["elite", "full", "half"],
            "start_times": {
                "full": 420,
                "half": 460,
                "elite": 480
            },
            "data_files": {
                "segments": "data/segments.csv",
                "flow": "data/flow.csv",
                "locations": "data/locations.csv",
                "runners": {
                    "full": "data/full_runners.csv",
                    "half": "data/half_runners.csv",
                    "elite": "data/elite_runners.csv"
                },
                "gpx": {
                    "full": "data/full.gpx",
                    "half": "data/half.gpx",
                    "elite": "data/elite.gpx"
                }
            }
        }
    
    def test_get_event_names(self, sample_analysis_config):
        """Test getting event names from analysis.json."""
        event_names = get_event_names(run_path=None, analysis_config=sample_analysis_config)
        assert set(event_names) == {"elite", "full", "half"}
    
    def test_get_events_by_day(self, sample_analysis_config):
        """Test getting events filtered by day."""
        sun_events = get_events_by_day("sun", analysis_config=sample_analysis_config)
        assert set(sun_events) == {"full", "half"}
        
        sat_events = get_events_by_day("sat", analysis_config=sample_analysis_config)
        assert set(sat_events) == {"elite"}
    
    def test_get_event_duration_minutes(self, sample_analysis_config):
        """Test getting event duration from analysis.json."""
        duration = get_event_duration_minutes("full", analysis_config=sample_analysis_config)
        assert duration == 390
        
        duration = get_event_duration_minutes("elite", analysis_config=sample_analysis_config)
        assert duration == 45
    
    def test_get_event_duration_minutes_not_found(self, sample_analysis_config):
        """Test getting duration for non-existent event raises error."""
        with pytest.raises(ValueError, match="not found in analysis.json"):
            get_event_duration_minutes("nonexistent", analysis_config=sample_analysis_config)
    
    def test_get_start_time(self, sample_analysis_config):
        """Test getting start time from analysis.json."""
        start_time = get_start_time("full", analysis_config=sample_analysis_config)
        assert start_time == 420
        
        start_time = get_start_time("elite", analysis_config=sample_analysis_config)
        assert start_time == 480
    
    def test_get_start_time_not_found(self, sample_analysis_config):
        """Test getting start time for non-existent event raises error."""
        with pytest.raises(ValueError, match="not found in analysis.json"):
            get_start_time("nonexistent", analysis_config=sample_analysis_config)
    
    def test_get_all_start_times(self, sample_analysis_config):
        """Test getting all start times dictionary."""
        start_times = get_all_start_times(analysis_config=sample_analysis_config)
        assert start_times == {
            "full": 420,
            "half": 460,
            "elite": 480
        }
    
    def test_get_segments_file(self, sample_analysis_config):
        """Test getting segments file path."""
        segments_path = get_segments_file(analysis_config=sample_analysis_config)
        assert segments_path == "data/segments.csv"
    
    def test_get_flow_file(self, sample_analysis_config):
        """Test getting flow file path."""
        flow_path = get_flow_file(analysis_config=sample_analysis_config)
        assert flow_path == "data/flow.csv"
    
    def test_get_locations_file(self, sample_analysis_config):
        """Test getting locations file path."""
        locations_path = get_locations_file(analysis_config=sample_analysis_config)
        assert locations_path == "data/locations.csv"
    
    def test_get_runners_file(self, sample_analysis_config):
        """Test getting runners file path for event."""
        runners_path = get_runners_file("full", analysis_config=sample_analysis_config)
        assert runners_path == "data/full_runners.csv"
        
        runners_path = get_runners_file("elite", analysis_config=sample_analysis_config)
        assert runners_path == "data/elite_runners.csv"
    
    def test_get_runners_file_not_found(self, sample_analysis_config):
        """Test getting runners file for non-existent event raises error."""
        with pytest.raises(ValueError, match="not found in analysis.json"):
            get_runners_file("nonexistent", analysis_config=sample_analysis_config)
    
    def test_get_gpx_file(self, sample_analysis_config):
        """Test getting GPX file path for event."""
        gpx_path = get_gpx_file("full", analysis_config=sample_analysis_config)
        assert gpx_path == "data/full.gpx"
        
        gpx_path = get_gpx_file("elite", analysis_config=sample_analysis_config)
        assert gpx_path == "data/elite.gpx"
    
    def test_get_gpx_file_not_found(self, sample_analysis_config):
        """Test getting GPX file for non-existent event raises error."""
        with pytest.raises(ValueError, match="not found in analysis.json"):
            get_gpx_file("nonexistent", analysis_config=sample_analysis_config)


class TestCountRunnersInFile:
    """Test runner counting function."""
    
    def test_count_runners_in_file(self, tmp_path):
        """Test counting runners in CSV file."""
        runners_file = tmp_path / "runners.csv"
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2", "3", "4", "5"],
            "pace": [4.0, 4.5, 5.0, 5.5, 6.0]
        })
        runners_df.to_csv(runners_file, index=False)
        
        count = count_runners_in_file(runners_file)
        assert count == 5
    
    def test_count_runners_in_file_empty(self, tmp_path):
        """Test counting runners in empty CSV file (header only)."""
        runners_file = tmp_path / "runners.csv"
        runners_df = pd.DataFrame({
            "runner_id": [],
            "pace": []
        })
        runners_df.to_csv(runners_file, index=False)
        
        count = count_runners_in_file(runners_file)
        assert count == 0

