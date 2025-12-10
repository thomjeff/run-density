"""
Runflow v2 Core Module

This module provides the foundational models and validation layer for Runflow v2.
It includes Event/Day data structures, payload parsing, and comprehensive validation logic.

Phase 1: Models & Validation Layer (Issue #495)
"""

from app.core.v2.models import Day, Event, Segment, Runner
from app.core.v2.validation import (
    ValidationError,
    validate_api_payload,
    validate_file_existence,
    validate_event_names,
    validate_day_codes,
    validate_start_times,
    validate_segment_spans,
    validate_runner_uniqueness,
    validate_gpx_files,
)
from app.core.v2.loader import (
    load_events_from_payload,
    load_runners_for_event,
    load_segments_with_spans,
    group_events_by_day,
)
from app.core.v2.timeline import (
    DayTimeline,
    generate_day_timelines,
    get_day_start,
    normalize_time_to_day,
)
from app.core.v2.bins import (
    calculate_runner_arrival_time,
    enforce_cross_day_guard,
    filter_segments_by_events,
    resolve_segment_spans,
    create_bins_for_segment_v2,
    generate_bins_per_day,
)
from app.core.v2.flow import (
    generate_event_pairs_v2,
    enforce_same_day_pairs,
    get_shared_segments,
    get_event_distance_range_v2,
    filter_flow_csv_by_events,
    analyze_temporal_flow_segments_v2,
)

__all__ = [
    # Models
    "Day",
    "Event",
    "Segment",
    "Runner",
    # Validation
    "ValidationError",
    "validate_api_payload",
    "validate_file_existence",
    "validate_event_names",
    "validate_day_codes",
    "validate_start_times",
    "validate_segment_spans",
    "validate_runner_uniqueness",
    "validate_gpx_files",
    # Loaders
    "load_events_from_payload",
    "load_runners_for_event",
    "load_segments_with_spans",
    "group_events_by_day",
    # Timeline
    "DayTimeline",
    "generate_day_timelines",
    "get_day_start",
    "normalize_time_to_day",
    # Bins
    "calculate_runner_arrival_time",
    "enforce_cross_day_guard",
    "filter_segments_by_events",
    "resolve_segment_spans",
    "create_bins_for_segment_v2",
    "generate_bins_per_day",
    # Flow (Phase 5)
    "generate_event_pairs_v2",
    "enforce_same_day_pairs",
    "get_shared_segments",
    "get_event_distance_range_v2",
    "filter_flow_csv_by_events",
    "analyze_temporal_flow_segments_v2",
]

