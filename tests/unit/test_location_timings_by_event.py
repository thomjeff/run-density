"""Issue #828: per-event location timing windows."""

from __future__ import annotations

import json

from app.location_report import (
    build_by_event_timings,
    compute_timing_window,
    merge_by_event_timings,
    parse_by_event,
    serialize_by_event,
)
from app.one_pager import _by_event_timing_html, _by_event_timing_lines


def test_compute_timing_window_percentiles():
    # 4 arrivals → p25 idx=1, p75 idx=3
    times = [100.0, 200.0, 300.0, 400.0]
    window = compute_timing_window(times)
    assert window["first_runner"] == "00:01:40"
    assert window["last_runner"] == "00:06:40"
    assert window["peak_start"] == "00:03:20"
    assert window["peak_end"] == "00:06:40"


def test_build_by_event_and_aggregate_union():
    arrivals = {
        "10k": [100.0, 120.0],
        "half": [500.0, 700.0],
    }
    by_event = build_by_event_timings(arrivals)
    assert set(by_event) == {"10k", "half"}
    assert by_event["10k"]["first_runner"] == "00:01:40"
    assert by_event["half"]["last_runner"] == "00:11:40"

    flat = []
    for times in arrivals.values():
        flat.extend(times)
    aggregate = compute_timing_window(flat)
    assert aggregate["first_runner"] == "00:01:40"
    assert aggregate["last_runner"] == "00:11:40"


def test_serialize_parse_roundtrip():
    payload = {
        "full": {
            "first_runner": "07:00:00",
            "peak_start": "07:10:00",
            "peak_end": "07:40:00",
            "last_runner": "08:00:00",
        }
    }
    text = serialize_by_event(payload)
    assert json.loads(text)["full"]["first_runner"] == "07:00:00"
    assert parse_by_event(text)["full"]["last_runner"] == "08:00:00"


def test_merge_by_event_across_passes():
    outbound = {
        "full": {
            "first_runner": "07:00:00",
            "peak_start": "07:10:00",
            "peak_end": "07:20:00",
            "last_runner": "07:30:00",
        }
    }
    ret = {
        "full": {
            "first_runner": "08:00:00",
            "peak_start": "08:10:00",
            "peak_end": "08:40:00",
            "last_runner": "09:00:00",
        },
        "half": {
            "first_runner": "07:45:00",
            "peak_start": "08:00:00",
            "peak_end": "08:15:00",
            "last_runner": "08:30:00",
        },
    }
    merged = merge_by_event_timings([outbound, ret])
    assert merged["full"]["first_runner"] == "07:00:00"
    assert merged["full"]["last_runner"] == "09:00:00"
    assert merged["full"]["peak_start"] == "07:10:00"
    assert merged["full"]["peak_end"] == "08:40:00"
    assert "half" in merged


def test_one_pager_by_event_lines_and_html():
    row = {
        "by_event": {
            "10k": {
                "first_runner": "09:00:00",
                "peak_start": "09:10:00",
                "peak_end": "09:20:00",
                "last_runner": "09:30:00",
            }
        }
    }
    lines = _by_event_timing_lines(row)
    assert len(lines) == 1
    assert lines[0].startswith("10k:")
    html = _by_event_timing_html(row)
    assert "By event" in html
    assert "10k:" in html
