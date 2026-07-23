"""
Issue #798 Phase 2: canonical start-time contract (300–1200 operating hours).
"""

from __future__ import annotations

import pytest

from app.core.v2.models import Day, Event
from app.core.v2.start_time import (
    START_TIME_MAX_MINUTES,
    START_TIME_MIN_MINUTES,
    StartTimeValidationError,
    validate_start_minute,
)
from app.core.v2.validation import ValidationError, validate_start_times


def test_canonical_bounds():
    assert START_TIME_MIN_MINUTES == 300
    assert START_TIME_MAX_MINUTES == 1200


@pytest.mark.parametrize("minute", [300, 420, 900, 1200])
def test_validate_start_minute_accepts_boundaries(minute):
    assert validate_start_minute(minute, event_name="full") == minute


@pytest.mark.parametrize("minute", [-1, 0, 299, 1201, 1439, 1440])
def test_validate_start_minute_rejects_outside_operating_hours(minute):
    with pytest.raises(StartTimeValidationError) as exc_info:
        validate_start_minute(minute, event_name="full")
    assert exc_info.value.code == 400


def test_event_post_init_enforces_contract():
    Event(name="full", day=Day.SUN, start_time=420, gpx_file="a.gpx", runners_file="a.csv")
    with pytest.raises(StartTimeValidationError):
        Event(name="full", day=Day.SUN, start_time=0, gpx_file="a.gpx", runners_file="a.csv")


def test_validate_start_times_wraps_as_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        validate_start_times([{"name": "full", "start_time": 299}])
    assert exc_info.value.code == 400


def test_api_model_and_package_schedule_use_same_bounds():
    from app.api.models.v2 import V2EventRequest
    from app.routes.api_config_packages import RunPackageAnalysisEventSchedule

    for model in (V2EventRequest, RunPackageAnalysisEventSchedule):
        schema = model.model_json_schema()["properties"]["start_time"]
        assert schema["minimum"] == START_TIME_MIN_MINUTES
        assert schema["maximum"] == START_TIME_MAX_MINUTES
