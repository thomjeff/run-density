"""
Unit tests for Runflow v2 loader functions.

Phase 1: Models & Validation Layer (Issue #495)
"""

import pytest
import tempfile
from pathlib import Path
import pandas as pd
from app.core.v2.models import Day, Event, Runner
from app.core.v2.loader import (
    load_events_from_payload,
    load_runners_for_event,
    load_segments_with_spans,
    group_events_by_day,
)


class TestLoadEventsFromPayload:
    """Test loading events from API payload."""
    
    def test_load_events_with_seg_ids(self, tmp_path):
        """Test loading events with segment IDs determined from event flags."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv with event flags
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "B1"],
            "full": ["y", "y", "n"],
            "half": ["y", "n", "n"],
            "10k": ["y", "y", "y"],
            "full_from_km": [0.0, 0.9, 0.0],
            "full_to_km": [0.9, 1.8, 0.0],
            "half_from_km": [0.0, 0.0, 0.0],
            "half_to_km": [0.9, 0.0, 0.0],
            "10k_from_km": [0.0, 0.9, 2.7],
            "10k_to_km": [0.9, 1.8, 4.25],
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
        
        events = load_events_from_payload(payload, str(data_dir))
        
        assert len(events) == 1
        event = events[0]
        assert event.name == "full"
        assert event.day == Day.SUN
        assert event.start_time == 420
        # Should have seg_ids A1 and A2 (where full='y')
        assert "A1" in event.seg_ids
        assert "A2" in event.seg_ids
        assert "B1" not in event.seg_ids
    
    def test_event_name_normalization(self, tmp_path):
        """Test event names are normalized to lowercase."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "Full": ["y"],  # Capitalized column
            "full_from_km": [0.0],
            "full_to_km": [0.9],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        (data_dir / "locations.csv").write_text("loc_id\nL1")
        (data_dir / "flow.csv").write_text("seg_id\nA1")
        
        full_runners = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["Full"],  # Capitalized in CSV
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
                    "name": "Full",  # Capitalized in payload
                    "day": "sun",
                    "start_time": 420,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx"
                }
            ]
        }
        
        events = load_events_from_payload(payload, str(data_dir))
        
        assert events[0].name == "full"  # Should be normalized to lowercase


class TestLoadRunnersForEvent:
    """Test loading runners for an event."""
    
    def test_load_runners(self, tmp_path):
        """Test loading runners from CSV file."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2", "3"],
            "event": ["full", "full", "full"],
            "pace": [4.0, 4.5, 5.0],
            "distance": [42.2, 42.2, 42.2],
            "start_offset": [0, 1, 2],
        })
        runners_df.to_csv(data_dir / "full_runners.csv", index=False)
        
        event = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        
        runners = load_runners_for_event(event, str(data_dir))
        
        assert len(runners) == 3
        assert runners[0].runner_id == "1"
        assert runners[0].event == "full"  # Normalized
        assert runners[0].pace == 4.0
        assert runners[0].distance == 42.2
        assert runners[0].start_offset == 0
    
    def test_runner_event_normalization(self, tmp_path):
        """Test runner event names are normalized to lowercase."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        runners_df = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["Full"],  # Capitalized
            "pace": [4.0],
            "distance": [42.2],
            "start_offset": [0],
        })
        runners_df.to_csv(data_dir / "full_runners.csv", index=False)
        
        event = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        
        runners = load_runners_for_event(event, str(data_dir))
        
        assert runners[0].event == "full"  # Should be normalized


class TestGroupEventsByDay:
    """Test grouping events by day."""
    
    def test_group_events_by_day(self):
        """Test events are grouped correctly by day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            Event(name="open", day=Day.SAT, start_time=510, gpx_file="open.gpx", runners_file="open_runners.csv"),
        ]
        
        grouped = group_events_by_day(events)
        
        assert Day.SUN in grouped
        assert Day.SAT in grouped
        assert len(grouped[Day.SUN]) == 2
        assert len(grouped[Day.SAT]) == 2
        assert grouped[Day.SUN][0].name == "full"
        assert grouped[Day.SAT][0].name == "elite"

