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
from app.core.v2.bins import generate_bins_v2, filter_segments_by_events
from app.core.v2.density import (
    get_event_distance_range_v2,
    combine_runners_for_events,
    load_all_runners_for_events,
    filter_runners_by_day,
    analyze_density_segments_v2,
)
from app.core.v2.flow import (
    get_shared_segments,
    load_flow_csv,
    extract_event_pairs_from_flow_csv,
    generate_event_pairs_fallback,
    analyze_temporal_flow_segments_v2,
)
from app.core.v2.reports import (
    get_day_output_path,
    generate_flow_report_v2,
    generate_density_report_v2,
    generate_locations_report_v2,
    copy_bin_artifacts,
    generate_reports_per_day,
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
    "generate_bins_v2",
    "filter_segments_by_events",
    # Density
    "get_event_distance_range_v2",
    "combine_runners_for_events",
    "load_all_runners_for_events",
    "filter_runners_by_day",
    "analyze_density_segments_v2",
    # Flow
    "get_shared_segments",
    "load_flow_csv",
    "extract_event_pairs_from_flow_csv",
    "generate_event_pairs_fallback",
    "analyze_temporal_flow_segments_v2",
    # Reports
    "get_day_output_path",
    "generate_flow_report_v2",
    "generate_density_report_v2",
    "generate_locations_report_v2",
    "copy_bin_artifacts",
    "generate_reports_per_day",
]

