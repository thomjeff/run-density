"""Issue #798 Phase 8: race-specific defaults live in templates, not as universal law."""

from __future__ import annotations

from pathlib import Path

from app.core.race_templates import (
    DEFAULT_RACE_TEMPLATE_ID,
    get_hotspot_segments,
    get_map_center,
    get_suggested_event_schedule,
    get_v1_event_duration_minutes,
)
from app.utils import constants as C


def test_sample_template_has_expected_shape():
    schedule = get_suggested_event_schedule()
    assert "full" in schedule
    assert schedule["full"]["start_time"] == 420
    hotspots = get_hotspot_segments()
    assert "F1" in hotspots
    lat, lon = get_map_center()
    assert abs(lat - 45.9620) < 1e-6
    assert abs(lon - (-66.6500)) < 1e-6
    durations = get_v1_event_duration_minutes()
    assert durations["full"] == 390


def test_constants_reexport_template_values():
    assert C.EVENT_DURATION_MINUTES["full"] == 390
    assert "F1" in C.HOTSPOT_SEGMENTS
    assert abs(C.MAP_CENTER_LAT - 45.9620) < 1e-6


def test_package_analysis_uses_template_schedule():
    from app.core.config_package.package_analysis import SUGGESTED_EVENT_SCHEDULE

    assert SUGGESTED_EVENT_SCHEDULE["elite"]["start_time"] == 480


def test_no_hardcoded_fredericton_schedule_block_in_package_analysis():
    text = Path("app/core/config_package/package_analysis.py").read_text(encoding="utf-8")
    assert "SUGGESTED_EVENT_SCHEDULE: Dict[str, Dict[str, int]] = {" not in text
    assert "get_suggested_event_schedule" in text


def test_default_template_id():
    assert DEFAULT_RACE_TEMPLATE_ID == "sample_fredericton"
