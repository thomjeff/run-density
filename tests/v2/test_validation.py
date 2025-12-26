"""
Unit tests for Runflow v2 validation functions.

Phase 1: Models & Validation Layer (Issue #495)

This file contains unit tests for individual validation functions:
- validate_day_codes() - Day code validation
- validate_start_times() - Start time range validation
- validate_event_names() - Event name validation
- validate_file_existence() - File existence checks
- validate_segment_spans() - Segment range validation
- validate_runner_uniqueness() - Runner ID uniqueness
- validate_gpx_files() - GPX file validation
- validate_api_payload() - Complete API payload validation

Each test class focuses on testing a single validation function in isolation.
For error handling and error code tests, see test_validation_errors.py.
"""

import pytest
import tempfile
import os
from pathlib import Path
import pandas as pd
from app.core.v2.validation import (
    ValidationError,
    validate_day_codes,
    validate_start_times,
    validate_event_names,
    validate_file_existence,
    validate_segment_spans,
    validate_runner_uniqueness,
    validate_gpx_files,
    validate_api_payload,
)


class TestValidateDayCodes:
    """Test day code validation."""
    
    def test_valid_day_codes(self):
        """Test valid day codes pass validation."""
        events = [
            {"name": "full", "day": "sun"},
            {"name": "half", "day": "sat"},
            {"name": "elite", "day": "fri"},
        ]
        # Should not raise
        validate_day_codes(events)
    
    def test_invalid_day_code(self):
        """Test invalid day code raises ValidationError."""
        events = [
            {"name": "full", "day": "Saturday"},  # Invalid: should be "sat"
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_day_codes(events)
        assert exc_info.value.code == 400
        assert "Invalid day code" in exc_info.value.message
    
    def test_case_insensitive(self):
        """Test day codes are case-insensitive."""
        events = [
            {"name": "full", "day": "SUN"},  # Uppercase
        ]
        # Should normalize and pass
        validate_day_codes(events)


class TestValidateStartTimes:
    """Test start time validation."""
    
    def test_valid_start_times(self):
        """Test valid start times pass validation."""
        events = [
            {"name": "full", "start_time": 420},
            {"name": "half", "start_time": 300},  # Issue #553: Range is 300-1200
            {"name": "elite", "start_time": 1200},  # Issue #553: Range is 300-1200
        ]
        validate_start_times(events)
    
    def test_missing_start_time(self):
        """Test missing start_time raises ValidationError."""
        events = [
            {"name": "full"},  # Missing start_time
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        assert exc_info.value.code == 400
        assert "Missing required field 'start_time'" in exc_info.value.message
    
    def test_start_time_out_of_range(self):
        """Test start_time out of range raises ValidationError."""
        events = [
            {"name": "full", "start_time": 1201},  # Too high (Issue #553: Range is 300-1200)
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        assert exc_info.value.code == 400
        assert "must be between 300 and 1200" in exc_info.value.message
    
    def test_start_time_not_integer(self):
        """Test non-integer start_time raises ValidationError."""
        events = [
            {"name": "full", "start_time": 420.5},  # Float
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        assert exc_info.value.code == 400
        assert "must be an integer" in exc_info.value.message


class TestValidateEventNames:
    """Test event name uniqueness validation."""
    
    def test_unique_event_names(self):
        """Test unique event names pass validation."""
        events = [
            {"name": "full"},
            {"name": "half"},
            {"name": "10k"},
        ]
        validate_event_names(events)
    
    def test_duplicate_event_names(self):
        """Test duplicate event names raise ValidationError."""
        events = [
            {"name": "full"},
            {"name": "half"},
            {"name": "full"},  # Duplicate
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_event_names(events)
        assert exc_info.value.code == 400
        assert "Duplicate event name" in exc_info.value.message
    
    def test_missing_event_name(self):
        """Test missing event name raises ValidationError."""
        events = [
            {"day": "sun"},  # Missing name
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_event_names(events)
        assert exc_info.value.code == 400


class TestValidateFileExistence:
    """Test file existence validation."""
    
    def test_all_files_exist(self, tmp_path):
        """Test validation passes when all files exist."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create required files
        (data_dir / "segments.csv").write_text("seg_id\nA1")
        (data_dir / "locations.csv").write_text("loc_id\nL1")
        (data_dir / "flow.csv").write_text("seg_id\nA1")
        (data_dir / "full_runners.csv").write_text("runner_id,event,pace,distance,start_offset\n1,full,4,42,0")
        (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        
        events = [
            {"name": "full", "runners_file": "full_runners.csv", "gpx_file": "full.gpx"}
        ]
        
        validate_file_existence(
            "segments.csv",
            "locations.csv",
            "flow.csv",
            events,
            str(data_dir)
        )
    
    def test_missing_segments_file(self, tmp_path):
        """Test missing segments file raises ValidationError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        with pytest.raises(ValidationError) as exc_info:
            validate_file_existence(
                "segments.csv",  # Doesn't exist
                "locations.csv",
                "flow.csv",
                [],
                str(data_dir)
            )
        assert exc_info.value.code == 404
    
    def test_invalid_file_extension(self, tmp_path):
        """Test invalid file extension raises ValidationError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create required files first
        (data_dir / "segments.csv").write_text("seg_id\nA1")
        (data_dir / "locations.csv").write_text("loc_id\nL1")
        (data_dir / "flow.csv").write_text("seg_id\nA1")
        # Create file with wrong extension to test extension validation
        (data_dir / "full.txt").write_text("runner_id,event,pace,distance,start_offset\n1,full,4,42,0")
        (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        
        events = [
            {"name": "full", "runners_file": "full.txt", "gpx_file": "full.gpx"}  # Wrong extension
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_file_existence(
                "segments.csv",
                "locations.csv",
                "flow.csv",
                events,
                str(data_dir)
            )
        assert exc_info.value.code == 400
        assert ".csv extension" in exc_info.value.message


class TestValidateSegmentSpans:
    """Test segment span validation."""
    
    def test_valid_segment_spans(self, tmp_path):
        """Test validation passes when span columns exist."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv with span columns
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "full_from_km": [0.0],
            "full_to_km": [0.9],
            "half_from_km": [0.0],
            "half_to_km": [0.9],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        events = [
            {"name": "full"},
            {"name": "half"},
        ]
        
        validate_segment_spans("segments.csv", events, str(data_dir))
    
    def test_missing_span_columns(self, tmp_path):
        """Test missing span columns raise ValidationError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv without span columns
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        events = [
            {"name": "full"},
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_segment_spans("segments.csv", events, str(data_dir))
        assert exc_info.value.code == 422
        assert "missing required span columns" in exc_info.value.message.lower()


class TestValidateRunnerUniqueness:
    """Test runner uniqueness validation."""
    
    def test_unique_runner_ids(self, tmp_path):
        """Test validation passes when runner IDs are unique."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create runner files with unique IDs
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["full", "full"],
            "pace": [4.0, 4.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 1],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["3", "4"],
            "event": ["half", "half"],
            "pace": [3.5, 3.8],
            "distance": [21.1, 21.1],
            "start_offset": [0, 2],
        })
        half_runners.to_csv(data_dir / "half_runners.csv", index=False)
        
        events = [
            {"name": "full", "runners_file": "full_runners.csv"},
            {"name": "half", "runners_file": "half_runners.csv"},
        ]
        
        validate_runner_uniqueness(events, str(data_dir))
    
    def test_duplicate_runner_ids_across_events(self, tmp_path):
        """Test duplicate runner IDs across events raise ValidationError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create runner files with duplicate IDs
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["full", "full"],
            "pace": [4.0, 4.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 1],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["1", "3"],  # "1" duplicates full_runners
            "event": ["half", "half"],
            "pace": [3.5, 3.8],
            "distance": [21.1, 21.1],
            "start_offset": [0, 2],
        })
        half_runners.to_csv(data_dir / "half_runners.csv", index=False)
        
        events = [
            {"name": "full", "runners_file": "full_runners.csv"},
            {"name": "half", "runners_file": "half_runners.csv"},
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_runner_uniqueness(events, str(data_dir))
        assert exc_info.value.code == 422
        assert "Duplicate runner_id" in exc_info.value.message


class TestValidateApiPayload:
    """Test complete API payload validation."""
    
    def test_valid_payload(self, tmp_path):
        """Test valid payload passes all validation checks."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create all required files
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "full": ["y"],
            "full_from_km": [0.0],
            "full_to_km": [0.9],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        (data_dir / "locations.csv").write_text("loc_id\nL1")
        (data_dir / "flow.csv").write_text("seg_id\nA1")
        
        full_runners = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["full"],
            "pace": [4.0],
            "distance": [42.2],
            "start_offset": [0],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        
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
        
        events, seg_file, loc_file, flow_file = validate_api_payload(payload, str(data_dir))
        assert len(events) == 1
        assert seg_file == "segments.csv"
    
    def test_missing_events_field(self):
        """Test missing events field raises ValidationError."""
        payload = {
            "segments_file": "segments.csv",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_api_payload(payload)
        assert exc_info.value.code == 400
        assert "Missing required field 'events'" in exc_info.value.message

