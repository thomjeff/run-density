"""
Runflow v2 Data Models

Defines the core data structures for Event, Day, Segment, and Runner.
These models represent the v2 architecture's event-driven, day-scoped data organization.

Phase 1: Models & Validation Layer (Issue #495)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Day(str, Enum):
    """
    Day enumeration for event scheduling.
    
    Values are lowercase short codes matching the API specification:
    - fri: Friday
    - sat: Saturday  
    - sun: Sunday
    - mon: Monday (supported but not currently used)
    
    Serializes to lowercase strings for JSON compatibility.
    """
    FRI = 'fri'
    SAT = 'sat'
    SUN = 'sun'
    MON = 'mon'
    
    def __str__(self) -> str:
        return self.value


@dataclass
class Runner:
    """
    Runner data model representing a participant in an event.
    
    Attributes:
        runner_id: Unique identifier for the runner
        event: Event name (string reference, normalized to lowercase)
        pace: Runner's pace in minutes per kilometer
        distance: Total distance the runner will cover (kilometers)
        start_offset: Time offset in seconds from event start time when runner crosses start line
    """
    runner_id: str
    event: str  # Event name reference (normalized to lowercase)
    pace: float  # minutes per kilometer
    distance: float  # kilometers
    start_offset: int  # seconds from event start time
    
    def __post_init__(self):
        """Normalize event name to lowercase."""
        self.event = self.event.lower()


@dataclass
class Segment:
    """
    Segment data model representing a contiguous portion of the course.
    
    Segments may be shared across multiple events. Per-event distance spans
    are stored in segments.csv with columns like {event}_from_km and {event}_to_km.
    
    Attributes:
        seg_id: Unique segment identifier (e.g., "A1", "B2")
        name: Optional verbose name/label for the segment
        start_distance: Start distance in meters (event-relative)
        end_distance: End distance in meters (event-relative)
        used_by_event_names: List of event names that use this segment (normalized to lowercase)
    """
    seg_id: str
    name: Optional[str] = None
    start_distance: float = 0.0  # meters
    end_distance: float = 0.0  # meters
    used_by_event_names: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Normalize event names to lowercase."""
        self.used_by_event_names = [name.lower() for name in self.used_by_event_names]


@dataclass
class Event:
    """
    Event data model representing a single race instance.
    
    Event is the canonical source for day assignment and start time.
    Segments and Runners derive their day from the Event they belong to.
    
    Attributes:
        name: Event name (normalized to lowercase, e.g., "full", "half", "10k")
        day: Day enumeration (fri, sat, sun, mon)
        start_time: Start time in minutes after midnight (0-1439)
        gpx_file: Path to GPX file defining this event's course
        runners_file: Path to CSV file containing runners for this event
        seg_ids: List of segment IDs used by this event (references, not copies)
        runners: List of Runner objects (populated dynamically from runners_file)
    """
    name: str
    day: Day
    start_time: int  # minutes after midnight (0-1439)
    gpx_file: str
    runners_file: str
    seg_ids: List[str] = field(default_factory=list)
    runners: List[Runner] = field(default_factory=list)
    
    def __post_init__(self):
        """Normalize event name to lowercase."""
        self.name = self.name.lower()
    
    def __hash__(self) -> int:
        """Make Event hashable for use in sets/dicts."""
        return hash((self.name, self.day.value, self.start_time))
    
    def __eq__(self, other) -> bool:
        """Compare Events by name, day, and start_time."""
        if not isinstance(other, Event):
            return False
        return (self.name == other.name and 
                self.day == other.day and 
                self.start_time == other.start_time)

