"""
Unit tests for Runflow v2 data models.

Phase 1: Models & Validation Layer (Issue #495)
"""

import pytest
from app.core.v2.models import Day, Event, Segment, Runner


class TestDay:
    """Test Day enum."""
    
    def test_day_values(self):
        """Test Day enum has correct values."""
        assert Day.FRI.value == 'fri'
        assert Day.SAT.value == 'sat'
        assert Day.SUN.value == 'sun'
        assert Day.MON.value == 'mon'
    
    def test_day_string_conversion(self):
        """Test Day enum converts to string correctly."""
        assert str(Day.SAT) == 'sat'
        assert str(Day.SUN) == 'sun'
    
    def test_day_from_string(self):
        """Test Day enum can be created from string."""
        assert Day('sat') == Day.SAT
        assert Day('sun') == Day.SUN


class TestRunner:
    """Test Runner dataclass."""
    
    def test_runner_creation(self):
        """Test Runner creation with valid data."""
        runner = Runner(
            runner_id="123",
            event="full",
            pace=4.5,
            distance=42.2,
            start_offset=10
        )
        assert runner.runner_id == "123"
        assert runner.event == "full"  # Normalized to lowercase
        assert runner.pace == 4.5
        assert runner.distance == 42.2
        assert runner.start_offset == 10
    
    def test_runner_event_normalization(self):
        """Test Runner normalizes event name to lowercase."""
        runner = Runner(
            runner_id="123",
            event="Full",  # Capitalized
            pace=4.5,
            distance=42.2,
            start_offset=10
        )
        assert runner.event == "full"  # Should be normalized


class TestSegment:
    """Test Segment dataclass."""
    
    def test_segment_creation(self):
        """Test Segment creation with valid data."""
        segment = Segment(
            seg_id="A1",
            name="Start Segment",
            start_distance=0.0,
            end_distance=900.0,
            used_by_event_names=["full", "half"]
        )
        assert segment.seg_id == "A1"
        assert segment.name == "Start Segment"
        assert segment.start_distance == 0.0
        assert segment.end_distance == 900.0
        assert segment.used_by_event_names == ["full", "half"]
    
    def test_segment_event_normalization(self):
        """Test Segment normalizes event names to lowercase."""
        segment = Segment(
            seg_id="A1",
            used_by_event_names=["Full", "Half", "10K"]  # Mixed case
        )
        assert segment.used_by_event_names == ["full", "half", "10k"]


class TestEvent:
    """Test Event dataclass."""
    
    def test_event_creation(self):
        """Test Event creation with valid data."""
        event = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        assert event.name == "full"
        assert event.day == Day.SUN
        assert event.start_time == 420
        assert event.gpx_file == "full.gpx"
        assert event.runners_file == "full_runners.csv"
        assert event.seg_ids == []
        assert event.runners == []
    
    def test_event_name_normalization(self):
        """Test Event normalizes name to lowercase."""
        event = Event(
            name="Full",  # Capitalized
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        assert event.name == "full"  # Should be normalized
    
    def test_event_hashable(self):
        """Test Event is hashable for use in sets/dicts."""
        event1 = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        event2 = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        event_set = {event1, event2}
        assert len(event_set) == 1  # Should be deduplicated
    
    def test_event_equality(self):
        """Test Event equality comparison."""
        event1 = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        event2 = Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="full.gpx",
            runners_file="full_runners.csv"
        )
        event3 = Event(
            name="half",
            day=Day.SUN,
            start_time=460,
            gpx_file="half.gpx",
            runners_file="half_runners.csv"
        )
        assert event1 == event2
        assert event1 != event3

