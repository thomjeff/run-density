"""
Canonical event start-time contract (Issue #798 Phase 2).

Product rule: race operating hours — minutes after midnight, inclusive.
  300  = 05:00
  1200 = 20:00

Use these constants and helpers at every API / config / analysis boundary.
Do not reintroduce a parallel 0–1439 "any minute of day" range without updating
docs/architecture/domain-glossary.md and this module together.
"""

from __future__ import annotations

from typing import Any

# Inclusive operating-hours window (minutes after midnight)
START_TIME_MIN_MINUTES = 300
START_TIME_MAX_MINUTES = 1200

START_TIME_RANGE_DESCRIPTION = (
    f"Start time in minutes after midnight "
    f"({START_TIME_MIN_MINUTES}-{START_TIME_MAX_MINUTES}, 05:00–20:00)"
)


class StartTimeValidationError(ValueError):
    """Invalid start_time under the canonical operating-hours contract."""

    def __init__(self, message: str, *, code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_start_minute(start_time: Any, *, event_name: str = "unknown") -> int:
    """
    Validate and return start_time as int in [START_TIME_MIN_MINUTES, START_TIME_MAX_MINUTES].

    Raises:
        StartTimeValidationError: missing, non-int, or out of range
    """
    if start_time is None:
        raise StartTimeValidationError(
            f"Missing required field 'start_time' for event '{event_name}'",
            code=400,
        )
    if isinstance(start_time, bool) or not isinstance(start_time, int):
        raise StartTimeValidationError(
            f"start_time must be an integer for event '{event_name}', "
            f"got {type(start_time).__name__}",
            code=400,
        )
    if start_time < START_TIME_MIN_MINUTES or start_time > START_TIME_MAX_MINUTES:
        raise StartTimeValidationError(
            f"start_time {start_time} for event '{event_name}' must be between "
            f"{START_TIME_MIN_MINUTES} and {START_TIME_MAX_MINUTES} "
            f"(5:00 AM to 8:00 PM)",
            code=400,
        )
    return start_time
