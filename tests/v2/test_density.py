"""
Unit tests for Runflow v2 Density Pipeline Module

Phase 4: Density Pipeline Refactor (Issue #498)
"""

import pytest
import pandas as pd
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from app.core.v2.models import Day, Event, Runner
from app.core.v2.timeline import DayTimeline, generate_day_timelines
from app.core.v2.density import (
    get_event_interval_v2,
    filter_runners_by_day,
    aggregate_same_day_events,
    prepare_density_inputs_v2,
    load_all_runners_for_events,
    analyze_density_segments_v2,
)


class TestGetEventIntervalV2:
    """Test v2 event interval lookup."""
    
    def test_get_event_interval_full(self):
        """Test getting interval for full event."""
        event = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            runners_file="full_runners.csv",
            gpx_file="full.gpx",
            seg_ids=["A1", "A2"]
        )
        segment_data = {
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        }
        
        interval = get_event_interval_v2(event, segment_data)
        assert interval == (0.0, 0.9)
    
    def test_get_event_interval_half(self):
        """Test getting interval for half event."""
        event = Event(
            name="half",
            day=Day.SUN,
            start_time=460,
            runners_file="half_runners.csv",
            gpx_file="half.gpx",
            seg_ids=["A1"]
        )
        segment_data = {
            "seg_id": "A1",
            "half_from_km": 0.0,
            "half_to_km": 0.5,
        }
        
        interval = get_event_interval_v2(event, segment_data)
        assert interval == (0.0, 0.5)
    
    def test_get_event_interval_10k(self):
        """Test getting interval for 10k event (case-insensitive)."""
        event = Event(
            name="10k",
            day=Day.SAT,
            start_time=480,
            runners_file="10k_runners.csv",
            gpx_file="10k.gpx",
            seg_ids=["A1"]
        )
        # Test both "10K_from_km" and "10k_from_km" formats
        segment_data = {
            "seg_id": "A1",
            "10k_from_km": 0.0,
            "10k_to_km": 0.1,
        }
        
        interval = get_event_interval_v2(event, segment_data)
        assert interval == (0.0, 0.1)
    
    def test_get_event_interval_elite(self):
        """Test getting interval for elite event (v2 only)."""
        event = Event(
            name="elite",
            day=Day.SAT,
            start_time=480,
            runners_file="elite_runners.csv",
            gpx_file="elite.gpx",
            seg_ids=["A1"]
        )
        segment_data = {
            "seg_id": "A1",
            "elite_from_km": 0.0,
            "elite_to_km": 0.1,
        }
        
        interval = get_event_interval_v2(event, segment_data)
        assert interval == (0.0, 0.1)
    
    def test_get_event_interval_missing(self):
        """Test getting interval when event span columns are missing."""
        event = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            runners_file="full_runners.csv",
            gpx_file="full.gpx",
            seg_ids=["A1"]
        )
        segment_data = {
            "seg_id": "A1",
            # Missing full_from_km and full_to_km
        }
        
        interval = get_event_interval_v2(event, segment_data)
        assert interval is None


class TestFilterRunnersByDay:
    """Test filtering runners by day."""
    
    def test_filter_runners_single_day(self):
        """Test filtering runners for a single day."""
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2", "3", "4"],
            "event": ["full", "half", "elite", "open"],
            "pace": [5.0, 5.5, 4.5, 6.0],
            "start_offset": [0, 0, 0, 0]
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        filtered = filter_runners_by_day(runners_df, Day.SUN, events)
        
        assert len(filtered) == 2
        assert set(filtered["event"].values) == {"full", "half"}
    
    def test_filter_runners_empty_result(self):
        """Test filtering when no runners match the day."""
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["full", "half"],
            "pace": [5.0, 5.5],
            "start_offset": [0, 0]
        })
        
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=[]),
        ]
        
        filtered = filter_runners_by_day(runners_df, Day.SAT, events)
        
        assert len(filtered) == 0
    
    def test_filter_runners_case_insensitive(self):
        """Test filtering with case-insensitive event names."""
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["Full", "HALF"],  # Mixed case
            "pace": [5.0, 5.5],
            "start_offset": [0, 0]
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        filtered = filter_runners_by_day(runners_df, Day.SUN, events)
        
        assert len(filtered) == 2


class TestAggregateSameDayEvents:
    """Test aggregating events by day."""
    
    def test_aggregate_same_day_events(self):
        """Test aggregating events on the same day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
            Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=[]),
        ]
        
        same_day = aggregate_same_day_events(events, Day.SUN)
        
        assert len(same_day) == 2
        assert {e.name for e in same_day} == {"full", "half"}


class TestLoadAllRunnersForEvents:
    """Test loading all runners for events."""
    
    def test_load_all_runners(self, tmp_path):
        """Test loading runners from multiple event files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create test runner files
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["full", "full"],
            "pace": [5.0, 5.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 10]
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["3", "4"],
            "event": ["half", "half"],
            "pace": [5.0, 5.5],
            "distance": [21.1, 21.1],
            "start_offset": [0, 10]
        })
        half_runners.to_csv(data_dir / "half_runners.csv", index=False)
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        all_runners_df = load_all_runners_for_events(events, str(data_dir))
        
        assert len(all_runners_df) == 4
        assert set(all_runners_df["event"].values) == {"full", "half"}
    
    def test_load_all_runners_missing_file(self, tmp_path):
        """Test loading when a runner file is missing."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create only one runner file
        full_runners = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["full"],
            "pace": [5.0],
            "distance": [42.2],
            "start_offset": [0]
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        all_runners_df = load_all_runners_for_events(events, str(data_dir))
        
        # Should only load full runners, skip missing half file
        assert len(all_runners_df) == 1
        assert all_runners_df["event"].iloc[0] == "full"


class TestPrepareDensityInputsV2:
    """Test preparing density inputs per day."""
    
    def test_prepare_density_inputs_single_day(self):
        """Test preparing inputs for a single day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"]),
        ]
        
        timelines = generate_day_timelines(events)
        
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "full": ["y", "n"],
            "half": ["y", "n"],
            "full_from_km": [0.0, None],
            "full_to_km": [0.9, None],
            "half_from_km": [0.0, None],
            "half_to_km": [0.5, None],
        })
        
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2", "3"],
            "event": ["full", "full", "half"],
            "pace": [5.0, 5.5, 5.0],
            "start_offset": [0, 10, 0]
        })
        
        inputs_by_day = prepare_density_inputs_v2(events, timelines, segments_df, runners_df)
        
        assert Day.SUN in inputs_by_day
        day_inputs = inputs_by_day[Day.SUN]
        
        assert len(day_inputs["events"]) == 2
        assert len(day_inputs["segments_df"]) == 1  # Only A1 (used by full/half)
        assert len(day_inputs["runners_df"]) == 3  # All runners (full + half)
        assert "Full" in day_inputs["start_times"]  # Mapped to v1 format
        assert "Half" in day_inputs["start_times"]
    
    def test_prepare_density_inputs_multiple_days(self):
        """Test preparing inputs for multiple days."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"]),
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
        ]
        
        timelines = generate_day_timelines(events)
        
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "elite": ["y"],
            "full": ["y"],
            "elite_from_km": [0.0],
            "elite_to_km": [0.1],
            "full_from_km": [0.0],
            "full_to_km": [0.9],
        })
        
        runners_df = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["elite", "full"],
            "pace": [4.5, 5.0],
            "start_offset": [0, 0]
        })
        
        inputs_by_day = prepare_density_inputs_v2(events, timelines, segments_df, runners_df)
        
        assert Day.SAT in inputs_by_day
        assert Day.SUN in inputs_by_day
        
        # Check SAT inputs
        sat_inputs = inputs_by_day[Day.SAT]
        assert len(sat_inputs["events"]) == 1
        assert sat_inputs["events"][0].name == "elite"
        assert len(sat_inputs["runners_df"]) == 1
        
        # Check SUN inputs
        sun_inputs = inputs_by_day[Day.SUN]
        assert len(sun_inputs["events"]) == 1
        assert sun_inputs["events"][0].name == "full"
        assert len(sun_inputs["runners_df"]) == 1

