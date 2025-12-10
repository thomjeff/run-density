"""
Unit tests for Runflow v2 Flow Pipeline Module

Phase 5: Flow Pipeline Refactor (Issue #499)
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os

from app.core.v2.models import Day, Event
from app.core.v2.timeline import generate_day_timelines
from app.core.v2.flow import (
    generate_event_pairs_v2,
    enforce_same_day_pairs,
    get_shared_segments,
    get_event_distance_range_v2,
    filter_flow_csv_by_events,
    _create_converted_segment_v2,
)


class TestGenerateEventPairsV2:
    """Test v2 event pair generation."""
    
    def test_generate_pairs_single_day(self):
        """Test generating pairs for events on the same day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"]),
        ]
        
        pairs = generate_event_pairs_v2(events)
        
        # Should generate 4 pairs: (full, full), (full, half), (half, full), (half, half)
        assert len(pairs) == 4
        assert (events[0], events[0]) in pairs
        assert (events[0], events[1]) in pairs
        assert (events[1], events[0]) in pairs
        assert (events[1], events[1]) in pairs
    
    def test_generate_pairs_multiple_days(self):
        """Test generating pairs for events on different days."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"]),
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"]),
        ]
        
        pairs = generate_event_pairs_v2(events)
        
        # Should generate 1 pair for SAT (elite, elite) and 4 pairs for SUN (full, half combinations)
        assert len(pairs) == 5
        # Check that no cross-day pairs exist
        for event_a, event_b in pairs:
            assert event_a.day == event_b.day
    
    def test_generate_pairs_empty_list(self):
        """Test generating pairs from empty events list raises error."""
        with pytest.raises(ValueError, match="Cannot generate event pairs from empty events list"):
            generate_event_pairs_v2([])
    
    def test_generate_pairs_saturday_events(self):
        """Test generating pairs for Saturday events (elite, open)."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"]),
            Event(name="open", day=Day.SAT, start_time=500, runners_file="open_runners.csv", gpx_file="open.gpx", seg_ids=["A1"]),
        ]
        
        pairs = generate_event_pairs_v2(events)
        
        # Should generate 4 pairs: (elite, elite), (elite, open), (open, elite), (open, open)
        assert len(pairs) == 4
        assert all(event_a.day == Day.SAT and event_b.day == Day.SAT for event_a, event_b in pairs)


class TestEnforceSameDayPairs:
    """Test same-day pair enforcement."""
    
    def test_enforce_same_day_valid(self):
        """Test that same-day pairs are accepted."""
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        event_b = Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"])
        
        # Should not raise
        enforce_same_day_pairs(event_a, event_b)
    
    def test_enforce_same_day_cross_day(self):
        """Test that cross-day pairs raise error."""
        event_a = Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"])
        event_b = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        
        with pytest.raises(ValueError, match="Cross-day event pair detected"):
            enforce_same_day_pairs(event_a, event_b)


class TestGetSharedSegments:
    """Test shared segment resolution."""
    
    def test_get_shared_segments_both_events(self):
        """Test finding segments used by both events."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "A3"],
            "full": ["y", "y", "n"],
            "half": ["y", "n", "y"],
            "full_from_km": [0.0, 0.0, None],
            "full_to_km": [0.9, 0.5, None],
            "half_from_km": [0.0, None, 0.0],
            "half_to_km": [0.9, None, 0.5],
        })
        
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        event_b = Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"])
        
        shared = get_shared_segments(event_a, event_b, segments_df)
        
        # Only A1 is used by both full and half
        assert len(shared) == 1
        assert shared.iloc[0]["seg_id"] == "A1"
    
    def test_get_shared_segments_no_shared(self):
        """Test when no segments are shared between events."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "full": ["y", "n"],
            "half": ["n", "y"],
            "full_from_km": [0.0, None],
            "full_to_km": [0.9, None],
            "half_from_km": [None, 0.0],
            "half_to_km": [None, 0.5],
        })
        
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        event_b = Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A2"])
        
        shared = get_shared_segments(event_a, event_b, segments_df)
        
        # No shared segments
        assert len(shared) == 0
    
    def test_get_shared_segments_cross_day_error(self):
        """Test that cross-day pairs raise error."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "full": ["y"],
            "elite": ["y"],
        })
        
        event_a = Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"])
        event_b = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        
        with pytest.raises(ValueError, match="Cross-day event pair detected"):
            get_shared_segments(event_a, event_b, segments_df)


class TestGetEventDistanceRangeV2:
    """Test v2 event distance range lookup."""
    
    def test_get_distance_range_full(self):
        """Test getting distance range for full event."""
        segment = pd.Series({
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        })
        
        event = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        assert from_km == 0.0
        assert to_km == 0.9
    
    def test_get_distance_range_10k(self):
        """Test getting distance range for 10k event (case-insensitive)."""
        segment = pd.Series({
            "seg_id": "A1",
            "10k_from_km": 0.0,
            "10k_to_km": 0.1,
        })
        
        event = Event(name="10k", day=Day.SAT, start_time=480, runners_file="10k_runners.csv", gpx_file="10k.gpx", seg_ids=["A1"])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        assert from_km == 0.0
        assert to_km == 0.1
    
    def test_get_distance_range_elite(self):
        """Test getting distance range for elite event (v2 only)."""
        segment = pd.Series({
            "seg_id": "A1",
            "elite_from_km": 0.0,
            "elite_to_km": 0.1,
        })
        
        event = Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        assert from_km == 0.0
        assert to_km == 0.1
    
    def test_get_distance_range_missing(self):
        """Test getting distance range when columns are missing."""
        segment = pd.Series({
            "seg_id": "A1",
            # Missing full_from_km and full_to_km
        })
        
        event = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        assert from_km == 0.0
        assert to_km == 0.0


class TestFilterFlowCsvByEvents:
    """Test flow CSV filtering."""
    
    def test_filter_flow_csv_matching_events(self):
        """Test filtering flow.csv to matching events."""
        flow_df = pd.DataFrame({
            "event_a": ["Full", "Half", "Elite"],
            "event_b": ["Half", "10K", "Open"],
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"]),
        ]
        
        filtered = filter_flow_csv_by_events(flow_df, events)
        
        # Only Full-Half pair should remain
        assert len(filtered) == 1
        assert filtered.iloc[0]["event_a"] == "Full"
        assert filtered.iloc[0]["event_b"] == "Half"
    
    def test_filter_flow_csv_case_insensitive(self):
        """Test filtering with case-insensitive event names."""
        flow_df = pd.DataFrame({
            "event_a": ["full", "FULL", "Half"],
            "event_b": ["half", "HALF", "10K"],
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
            Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"]),
        ]
        
        filtered = filter_flow_csv_by_events(flow_df, events)
        
        # Both full-half pairs should remain (case-insensitive)
        assert len(filtered) == 2
    
    def test_filter_flow_csv_empty_result(self):
        """Test filtering when no events match."""
        flow_df = pd.DataFrame({
            "event_a": ["Elite", "Open"],
            "event_b": ["Open", "Elite"],
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"]),
        ]
        
        filtered = filter_flow_csv_by_events(flow_df, events)
        
        # No matching pairs
        assert len(filtered) == 0


class TestCreateConvertedSegmentV2:
    """Test v2 converted segment creation."""
    
    def test_create_converted_segment_full_half(self):
        """Test creating converted segment for full-half pair."""
        segment = pd.Series({
            "seg_id": "A1",
            "seg_label": "Start Segment",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
            "half_from_km": 0.0,
            "half_to_km": 0.5,
            "direction": "uni",
            "width_m": 5.0,
            "overtake_flag": "y",
            "flow_type": "merge",
            "length_km": 0.9,
        })
        
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=["A1"])
        event_b = Event(name="half", day=Day.SUN, start_time=460, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=["A1"])
        
        converted = _create_converted_segment_v2(segment, event_a, event_b)
        
        assert converted["seg_id"] == "A1"
        assert converted["eventa"] == "Full"
        assert converted["eventb"] == "Half"
        assert converted["from_km_a"] == 0.0
        assert converted["to_km_a"] == 0.9
        assert converted["from_km_b"] == 0.0
        assert converted["to_km_b"] == 0.5
        assert converted["flow_type"] == "merge"
    
    def test_create_converted_segment_elite_open(self):
        """Test creating converted segment for elite-open pair (v2 only)."""
        segment = pd.Series({
            "seg_id": "A1",
            "elite_from_km": 0.0,
            "elite_to_km": 0.1,
            "open_from_km": 0.0,
            "open_to_km": 0.1,
            "flow_type": "overtake",
        })
        
        event_a = Event(name="elite", day=Day.SAT, start_time=480, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=["A1"])
        event_b = Event(name="open", day=Day.SAT, start_time=500, runners_file="open_runners.csv", gpx_file="open.gpx", seg_ids=["A1"])
        
        converted = _create_converted_segment_v2(segment, event_a, event_b)
        
        assert converted["eventa"] == "Elite"
        assert converted["eventb"] == "Open"
        assert converted["from_km_a"] == 0.0
        assert converted["to_km_a"] == 0.1

