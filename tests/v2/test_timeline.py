"""
Unit tests for Runflow v2 timeline generation.

Phase 3: Timeline & Bin Rewrite (Issue #497)
"""

import pytest
from app.core.v2.models import Day, Event
from app.core.v2.timeline import (
    DayTimeline,
    generate_day_timelines,
    get_day_start,
    normalize_time_to_day,
)


class TestGetDayStart:
    """Test day start time calculation."""
    
    def test_get_day_start_single_event(self):
        """Test get_day_start with single event."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")
        ]
        
        day_start = get_day_start(events)
        assert day_start == 420 * 60  # 420 minutes = 25200 seconds
    
    def test_get_day_start_multiple_events(self):
        """Test get_day_start returns earliest start time."""
        events = [
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="10k", day=Day.SUN, start_time=440, gpx_file="10k.gpx", runners_file="10k_runners.csv"),
        ]
        
        day_start = get_day_start(events)
        assert day_start == 420 * 60  # Earliest is full at 420 minutes
    
    def test_get_day_start_different_days_raises_error(self):
        """Test get_day_start raises error for events from different days."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
        ]
        
        with pytest.raises(ValueError) as exc_info:
            get_day_start(events)
        assert "same day" in str(exc_info.value).lower()
    
    def test_get_day_start_empty_list_raises_error(self):
        """Test get_day_start raises error for empty list."""
        with pytest.raises(ValueError) as exc_info:
            get_day_start([])
        assert "empty" in str(exc_info.value).lower()


class TestGenerateDayTimelines:
    """Test day timeline generation."""
    
    def test_generate_day_timelines_single_day(self):
        """Test timeline generation for single day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
        ]
        
        timelines = generate_day_timelines(events)
        
        assert len(timelines) == 1
        assert timelines[0].day == Day.SUN
        assert timelines[0].t0 == 420 * 60  # Earliest start (full at 420 min)
        assert len(timelines[0].events) == 2
    
    def test_generate_day_timelines_multiple_days(self):
        """Test timeline generation for multiple days."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
            Event(name="open", day=Day.SAT, start_time=510, gpx_file="open.gpx", runners_file="open_runners.csv"),
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="half", day=Day.SUN, start_time=460, gpx_file="half.gpx", runners_file="half_runners.csv"),
        ]
        
        timelines = generate_day_timelines(events)
        
        assert len(timelines) == 2
        
        # Find Saturday timeline
        sat_timeline = next(t for t in timelines if t.day == Day.SAT)
        assert sat_timeline.t0 == 480 * 60  # Earliest Saturday (elite at 480 min)
        assert len(sat_timeline.events) == 2
        
        # Find Sunday timeline
        sun_timeline = next(t for t in timelines if t.day == Day.SUN)
        assert sun_timeline.t0 == 420 * 60  # Earliest Sunday (full at 420 min)
        assert len(sun_timeline.events) == 2


class TestNormalizeTimeToDay:
    """Test time normalization to day-relative time."""
    
    def test_normalize_time_to_day(self):
        """Test converting absolute time to day-relative time."""
        timeline = DayTimeline(
            day=Day.SUN,
            t0=420 * 60,  # 7:00 AM = 25200 seconds
            events=[Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")]
        )
        
        # Absolute time: 7:10 AM = 430 minutes = 25800 seconds
        absolute_time = 430 * 60
        day_relative = normalize_time_to_day(absolute_time, timeline)
        
        assert day_relative == 600  # 10 minutes = 600 seconds after day start


class TestDayTimeline:
    """Test DayTimeline dataclass."""
    
    def test_day_timeline_creation(self):
        """Test DayTimeline creation."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv")
        ]
        
        timeline = DayTimeline(day=Day.SUN, t0=420*60, events=events)
        
        assert timeline.day == Day.SUN
        assert timeline.t0 == 25200
        assert len(timeline.events) == 1
    
    def test_day_timeline_validates_event_days(self):
        """Test DayTimeline validates all events belong to timeline day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),  # Wrong day
        ]
        
        with pytest.raises(ValueError) as exc_info:
            DayTimeline(day=Day.SUN, t0=420*60, events=events)
        assert "day" in str(exc_info.value).lower()

