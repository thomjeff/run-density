"""
Unit tests for Runflow v2 bin generation.

Phase 3: Timeline & Bin Rewrite (Issue #497)
"""

import pytest
import pandas as pd
from app.core.v2.models import Day, Event
from app.core.v2.bins import (
    calculate_runner_arrival_time,
    enforce_cross_day_guard,
    filter_segments_by_events,
    resolve_segment_spans,
    create_bins_for_segment_v2,
    generate_bins_per_day,
)


class TestCalculateRunnerArrivalTime:
    """Test runner arrival time calculation."""
    
    def test_arrival_time_calculation(self):
        """Test arrival time formula matches existing codebase pattern."""
        # Event starts at 7:20 AM (440 min = 26400 sec)
        # Runner offset: 10 seconds
        # Pace: 4 min/km, Distance: 5 km
        # Travel time: 4 * 5 * 60 = 1200 seconds
        
        arrival = calculate_runner_arrival_time(
            event_start_time_minutes=440,
            runner_start_offset_seconds=10,
            pace_minutes_per_km=4.0,
            segment_distance_km=5.0
        )
        
        # Expected: 26400 + 10 + 1200 = 27610 seconds from midnight
        assert arrival == 27610
    
    def test_arrival_time_with_zero_offset(self):
        """Test arrival time with zero runner offset."""
        arrival = calculate_runner_arrival_time(
            event_start_time_minutes=420,
            runner_start_offset_seconds=0,
            pace_minutes_per_km=5.0,
            segment_distance_km=2.0
        )
        
        # Expected: (420*60) + 0 + (5*2*60) = 25200 + 0 + 600 = 25800
        assert arrival == 25800
    
    def test_arrival_time_conversion(self):
        """Test time unit conversions are correct."""
        # Verify minutes to seconds conversion
        # Verify pace conversion (min/km to sec/km)
        arrival = calculate_runner_arrival_time(
            event_start_time_minutes=1,  # 1 minute = 60 seconds
            runner_start_offset_seconds=0,
            pace_minutes_per_km=1.0,  # 1 min/km = 60 sec/km
            segment_distance_km=1.0  # 1 km
        )
        
        # Expected: 60 + 0 + 60 = 120 seconds
        assert arrival == 120


class TestEnforceCrossDayGuard:
    """Test cross-day guard enforcement."""
    
    def test_same_day_events_pass(self):
        """Test same-day events pass guard."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
        ]
        
        # Should not raise
        enforce_cross_day_guard(events)
    
    def test_different_day_events_raise_error(self):
        """Test different-day events raise ValueError."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
        ]
        
        with pytest.raises(ValueError) as exc_info:
            enforce_cross_day_guard(events)
        assert "Cross-day guard violation" in str(exc_info.value)
    
    def test_empty_list_passes(self):
        """Test empty list passes guard."""
        enforce_cross_day_guard([])


class TestFilterSegmentsByEvents:
    """Test segment filtering by events."""
    
    def test_filter_segments_by_single_event(self):
        """Test filtering segments for single event."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "B1"],
            "full": ["y", "y", "n"],
            "half": ["y", "n", "n"],
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")
        ]
        
        filtered = filter_segments_by_events(segments_df, events)
        
        assert len(filtered) == 2
        assert "A1" in filtered["seg_id"].values
        assert "A2" in filtered["seg_id"].values
        assert "B1" not in filtered["seg_id"].values
    
    def test_filter_segments_by_multiple_events(self):
        """Test filtering segments for multiple events."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "B1"],
            "full": ["y", "y", "n"],
            "half": ["y", "n", "n"],
            "10k": ["y", "y", "y"],
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="10k", day=Day.SUN, start_time=440, gpx_file="10k.gpx", runners_file="10k_runners.csv"),
        ]
        
        filtered = filter_segments_by_events(segments_df, events)
        
        # Should include segments used by full OR 10k
        assert len(filtered) == 3  # A1 (full+y, 10k+y), A2 (full+y, 10k+y), B1 (10k+y)
        assert "A1" in filtered["seg_id"].values
        assert "A2" in filtered["seg_id"].values
        assert "B1" in filtered["seg_id"].values
    
    def test_case_insensitive_event_matching(self):
        """Test event name matching is case-insensitive."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "Full": ["y"],  # Capitalized column
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")  # Lowercase
        ]
        
        filtered = filter_segments_by_events(segments_df, events)
        
        assert len(filtered) == 1
        assert "A1" in filtered["seg_id"].values


class TestResolveSegmentSpans:
    """Test segment span resolution."""
    
    def test_resolve_spans_single_event(self):
        """Test resolving spans for single event."""
        segment_data = {
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        }
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")
        ]
        
        min_km, max_km = resolve_segment_spans(segment_data, events)
        
        assert min_km == 0.0
        assert max_km == 0.9
    
    def test_resolve_spans_multiple_events(self):
        """Test resolving spans for multiple events (union of spans)."""
        segment_data = {
            "seg_id": "F1",
            "full_from_km": 16.35,
            "full_to_km": 18.65,
            "half_from_km": 2.7,
            "half_to_km": 5.0,
        }
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
        ]
        
        min_km, max_km = resolve_segment_spans(segment_data, events)
        
        assert min_km == 2.7  # Minimum across all spans
        assert max_km == 18.65  # Maximum across all spans
    
    def test_resolve_spans_missing_columns(self):
        """Test resolving spans when some event columns are missing."""
        segment_data = {
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
            # Missing half columns
        }
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
        ]
        
        min_km, max_km = resolve_segment_spans(segment_data, events)
        
        # Should only use full spans (half columns missing)
        assert min_km == 0.0
        assert max_km == 0.9


class TestCreateBinsForSegmentV2:
    """Test v2 bin creation."""
    
    def test_create_bins_single_event(self):
        """Test creating bins for segment with single event."""
        segment_data = {
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        }
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")
        ]
        
        bins = create_bins_for_segment_v2(segment_data, events, bin_size_km=0.1)
        
        # 0.9 km / 0.1 km = 9 bins
        assert len(bins) == 9
        assert bins[0]["start_km"] == 0.0
        assert bins[0]["end_km"] == 0.1
        assert bins[-1]["end_km"] == 0.9
    
    def test_create_bins_cross_day_guard(self):
        """Test bin creation enforces cross-day guard."""
        segment_data = {
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        }
        
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
        ]
        
        with pytest.raises(ValueError) as exc_info:
            create_bins_for_segment_v2(segment_data, events)
        assert "Cross-day guard violation" in str(exc_info.value)


class TestGenerateBinsPerDay:
    """Test day-partitioned bin generation."""
    
    def test_generate_bins_multiple_days(self):
        """Test bin generation partitioned by day."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "full": ["y", "y"],
            "half": ["y", "n"],
            "elite": ["n", "y"],
            "full_from_km": [0.0, 0.9],
            "full_to_km": [0.9, 1.8],
            "half_from_km": [0.0, 0.0],
            "half_to_km": [0.9, 0.0],
            "elite_from_km": [0.0, 0.0],
            "elite_to_km": [0.0, 0.9],
        })
        
        events_by_day = {
            Day.SUN: [
                Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
                Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
            ],
            Day.SAT: [
                Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            ],
        }
        
        bins_by_day = generate_bins_per_day(segments_df, events_by_day)
        
        assert Day.SUN in bins_by_day
        assert Day.SAT in bins_by_day
        
        # Sunday should have A1 (used by full and half)
        assert "A1" in bins_by_day[Day.SUN]
        # A2 is not used by half (half='n'), so might not be included
        
        # Saturday should have A2 (used by elite)
        assert "A2" in bins_by_day[Day.SAT]

