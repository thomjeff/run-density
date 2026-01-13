import pandas as pd
import pytest

from app.core.v2.flow import create_flow_segments_from_flow_csv
from app.core.v2.models import Day, Event
from app.new_flagging import _load_and_apply_segment_metadata
from app.rulebook import get_thresholds


def test_rulebook_missing_schema_raises() -> None:
    with pytest.raises(ValueError, match="Schema 'unknown' not found"):
        get_thresholds("unknown")


def test_new_flagging_requires_width_m() -> None:
    result_df = pd.DataFrame(
        {
            "segment_id": ["A1"],
            "density": [1.0],
            "rate": [0.5],
        }
    )
    segments_df = pd.DataFrame(
        {
            "seg_id": ["A1"],
            "seg_label": ["Start"],
            "width_m": [None],
            "schema": ["on_course_open"],
        }
    )

    with pytest.raises(ValueError, match="Missing width_m for segments"):
        _load_and_apply_segment_metadata(result_df, segments_df)


def test_flow_segments_require_flow_type() -> None:
    flow_rows = pd.DataFrame(
        {
            "seg_id": ["A1"],
            "event_a": ["full"],
            "event_b": ["half"],
            "from_km_a": [0.0],
            "to_km_a": [1.0],
            "from_km_b": [0.0],
            "to_km_b": [1.0],
        }
    )
    segments_df = pd.DataFrame(
        {
            "seg_id": ["A1"],
            "width_m": [4.0],
            "direction": ["uni"],
        }
    )
    event_a = Event(name="full", day=Day.SUN, start_time=0, gpx_file="full.gpx", runners_file="full.csv")
    event_b = Event(name="half", day=Day.SUN, start_time=0, gpx_file="half.gpx", runners_file="half.csv")

    with pytest.raises(ValueError, match="flow_type is required"):
        create_flow_segments_from_flow_csv(flow_rows, event_a, event_b, segments_df)
