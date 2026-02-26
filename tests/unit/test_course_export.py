"""
Unit tests for course export (segments.csv event-specific from_km/to_km).

Verifies that half_from_km/half_to_km (and other events) are cumulative only
along segments that use that event, not full-course distance.
"""

import csv
import io
import pytest

from app.core.course.export import _event_cumulative_distances, build_segments_csv
from app.utils.constants import COURSE_EVENT_IDS


def test_event_cumulative_distances_half_skips_segments():
    """Half uses only segments 1, 4, 5; event from/to must be cumulative for that event."""
    segments = [
        {"from_km": 0, "to_km": 2.72, "events": ["full", "half", "10k"]},
        {"from_km": 2.72, "to_km": 4.32, "events": ["full", "10k"]},
        {"from_km": 4.32, "to_km": 5.92, "events": ["full", "10k"]},
        {"from_km": 5.92, "to_km": 8.2, "events": ["full", "half", "10k"]},
        {"from_km": 8.2, "to_km": 10.08, "events": ["full", "half", "10k"]},
    ]
    result = _event_cumulative_distances(segments, COURSE_EVENT_IDS)
    # Half: seg1 0->2.72, seg4 2.72->5.0, seg5 5.0->6.88
    assert result[0]["half"] == (0.0, 2.72)
    assert result[1]["half"] == (0.0, 0.0)
    assert result[2]["half"] == (0.0, 0.0)
    assert result[3]["half"] == (2.72, 5.0)
    assert result[4]["half"] == (5.0, 6.88)
    # Full uses all segments: 0, 2.72, 4.32, 5.92, 8.2 -> 10.08
    assert result[0]["full"] == (0.0, 2.72)
    assert result[1]["full"] == (2.72, 4.32)
    assert result[3]["full"] == (5.92, 8.2)
    assert result[4]["full"] == (8.2, 10.08)


def test_build_segments_csv_half_from_to_km():
    """Build segments.csv and assert half_from_km/half_to_km for segment 4 and 5."""
    course = {
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        "segment_break_labels": {},
        "segments": [
            {"seg_label": "Start to Friel", "from_km": 0, "to_km": 2.72, "events": ["full", "half", "10k"], "start_index": 0, "end_index": 1},
            {"seg_label": "Friel to 10K Turn", "from_km": 2.72, "to_km": 4.32, "events": ["full", "10k"], "start_index": 1, "end_index": 2},
            {"seg_label": "10K Turn to Friel", "from_km": 4.32, "to_km": 5.92, "events": ["full", "10k"], "start_index": 2, "end_index": 3},
            {"seg_label": "Friel to Station", "from_km": 5.92, "to_km": 8.2, "events": ["full", "half", "10k"], "start_index": 3, "end_index": 4},
            {"seg_label": "Station to Finish", "from_km": 8.2, "to_km": 10.08, "events": ["full", "half", "10k"], "start_index": 4, "end_index": 5},
        ],
    }
    csv_content = build_segments_csv(course)
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    assert len(rows) == 5
    # Segment 4 (index 3): half_from_km=2.72, half_to_km=5.0
    assert float(rows[3]["half_from_km"]) == pytest.approx(2.72)
    assert float(rows[3]["half_to_km"]) == pytest.approx(5.0)
    # Segment 5 (index 4): half_from_km=5.0, half_to_km=6.88
    assert float(rows[4]["half_from_km"]) == pytest.approx(5.0)
    assert float(rows[4]["half_to_km"]) == pytest.approx(6.88)
    # Segments 2 and 3: half 0, 0
    assert float(rows[1]["half_from_km"]) == 0 and float(rows[1]["half_to_km"]) == 0
    assert float(rows[2]["half_from_km"]) == 0 and float(rows[2]["half_to_km"]) == 0
