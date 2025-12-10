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
]

