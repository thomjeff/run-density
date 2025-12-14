"""
Runflow v2 Timeline Module

Provides per-day timeline generation for day-scoped analysis.
Replaces global earliest-start timeline with day-scoped timelines.

Phase 3: Timeline & Bin Rewrite (Issue #497)
"""

from dataclasses import dataclass
from typing import List, Dict
from app.core.v2.models import Day, Event
from app.core.v2.loader import group_events_by_day


@dataclass
class DayTimeline:
    """
    Timeline for a specific day.
    
    Attributes:
        day: Day enum (fri, sat, sun, mon)
        t0: Day start time in seconds from midnight (earliest event start on this day)
        events: List of events on this day
    """
    day: Day
    t0: int  # seconds from midnight
    events: List[Event]
    
    def __post_init__(self):
        """Validate that all events belong to this day."""
        for event in self.events:
            if event.day != self.day:
                raise ValueError(
                    f"Event '{event.name}' has day '{event.day.value}' but timeline is for day '{self.day.value}'"
                )


def get_day_start(events: List[Event]) -> int:
    """
    Calculate day start time (t0) as earliest start_time among events on this day.
    
    Args:
        events: List of events on the same day
        
    Returns:
        Earliest start_time in seconds from midnight
        
    Raises:
        ValueError: If events list is empty or events are from different days
    """
    if not events:
        raise ValueError("Cannot calculate day_start for empty events list")
    
    # Validate all events are on the same day
    first_day = events[0].day
    for event in events:
        if event.day != first_day:
            raise ValueError(
                f"Events must be on the same day. Found {first_day.value} and {event.day.value}"
            )
    
    # Find earliest start_time (in minutes) and convert to seconds
    earliest_start_minutes = min(event.start_time for event in events)
    return earliest_start_minutes * 60  # Convert minutes to seconds


def generate_day_timelines(events: List[Event]) -> List[DayTimeline]:
    """
    Generate day timelines for all unique days in events list.
    
    Groups events by day and creates a DayTimeline for each day with t0
    calculated as the earliest start_time on that day.
    
    Args:
        events: List of Event objects from API payload
        
    Returns:
        List of DayTimeline objects, one per unique day
        
    Example:
        >>> events = [
        ...     Event(name="elite", day=Day.SAT, start_time=480, ...),
        ...     Event(name="open", day=Day.SAT, start_time=510, ...),
        ...     Event(name="full", day=Day.SUN, start_time=420, ...),
        ... ]
        >>> timelines = generate_day_timelines(events)
        >>> len(timelines) == 2  # One for Saturday, one for Sunday
        True
        >>> timelines[0].t0 == 480 * 60  # Saturday t0 = earliest (elite at 480 min)
        True
        >>> timelines[1].t0 == 420 * 60  # Sunday t0 = earliest (full at 420 min)
        True
    """
    # Group events by day
    events_by_day = group_events_by_day(events)
    
    # Create DayTimeline for each day
    timelines = []
    for day, day_events in events_by_day.items():
        t0 = get_day_start(day_events)
        timeline = DayTimeline(day=day, t0=t0, events=day_events)
        timelines.append(timeline)
    
    return timelines


def normalize_time_to_day(absolute_time_seconds: int, timeline: DayTimeline) -> int:
    """
    Convert absolute time (seconds from midnight) to day-relative time.
    
    Day-relative time is measured from t0 (day start) rather than midnight.
    This is useful for binning and day-scoped analysis.
    
    Args:
        absolute_time_seconds: Absolute time in seconds from midnight
        timeline: DayTimeline for the day
        
    Returns:
        Time relative to day start (t0) in seconds
        
    Example:
        >>> timeline = DayTimeline(day=Day.SUN, t0=420*60, events=[...])
        >>> # Absolute time: 7:10 AM = 430 minutes = 25800 seconds
        >>> # Day start: 7:00 AM = 420 minutes = 25200 seconds
        >>> normalize_time_to_day(25800, timeline)
        600  # 10 minutes = 600 seconds after day start
    """
    return absolute_time_seconds - timeline.t0

