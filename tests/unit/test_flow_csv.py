"""Unit tests for conservative flow.csv export and validation."""

import csv
import io

import pytest

from app.core.course.flow_csv import (
    build_flow_csv_from_segments,
    default_flow_id,
    parse_flow_csv_text,
    validate_flow_csv,
    validate_flow_csv_text,
)


def _parse(csv_text: str):
    return parse_flow_csv_text(csv_text)


def test_cross_event_only_by_default():
    segments = [
        {
            "seg_id": "S1",
            "seg_label": "Shared start",
            "direction": "uni",
            "full": "y",
            "half": "y",
            "10k": "y",
            "full_from_km": 0,
            "full_to_km": 2.0,
            "half_from_km": 0,
            "half_to_km": 2.0,
            "10k_from_km": 0,
            "10k_to_km": 2.0,
        }
    ]
    csv_text = build_flow_csv_from_segments(segments, ["full", "half", "10k"])
    rows = _parse(csv_text)
    assert len(rows) == 3
    pairs = {(r["event_a"], r["event_b"]) for r in rows}
    assert pairs == {("full", "half"), ("full", "10k"), ("half", "10k")}
    assert all(r["flow_id"] == default_flow_id("S1", r["event_a"], r["event_b"]) for r in rows)
    assert not any(r["event_a"] == r["event_b"] for r in rows)


def test_same_event_from_override_with_distinct_km():
    segments = [
        {
            "seg_id": "S4",
            "seg_label": "Trail return",
            "direction": "bi",
            "full": "y",
            "10k": "y",
            "full_from_km": 15.0,
            "full_to_km": 17.0,
            "10k_from_km": 4.0,
            "10k_to_km": 6.0,
        }
    ]
    overrides = [
        {
            "seg_id": "S4",
            "event_a": "10k",
            "event_b": "10k",
            "from_km_a": 2.7,
            "to_km_a": 4.25,
            "from_km_b": 4.25,
            "to_km_b": 5.8,
            "flow_type": "overtake",
            "direction": "bi",
            "flow_id": "S4b",
            "notes": "10K outbound vs return",
        }
    ]
    csv_text = build_flow_csv_from_segments(
        segments, ["full", "10k"], overrides=overrides
    )
    rows = _parse(csv_text)
    same_event = [r for r in rows if r["event_a"] == r["event_b"]]
    assert len(same_event) == 1
    assert same_event[0]["flow_id"] == "S4b"
    cross = [r for r in rows if r["event_a"] != r["event_b"]]
    assert len(cross) == 1
    assert cross[0]["flow_id"] == "S4_full_10k"


def test_validate_rejects_duplicate_bi_output_id():
    rows = [
        {
            "flow_id": "S4",
            "seg_id": "S4",
            "event_a": "full",
            "event_b": "10k",
            "from_km_a": 15.0,
            "to_km_a": 17.0,
            "from_km_b": 4.0,
            "to_km_b": 6.0,
            "flow_type": "overtake",
            "direction": "bi",
        },
        {
            "flow_id": "S4",
            "seg_id": "S4",
            "event_a": "10k",
            "event_b": "10k",
            "from_km_a": 2.7,
            "to_km_a": 4.25,
            "from_km_b": 4.25,
            "to_km_b": 5.8,
            "flow_type": "overtake",
            "direction": "bi",
        },
    ]
    result = validate_flow_csv(rows)
    assert not result.ok
    assert any("share output id" in err for err in result.errors)


def test_validate_rejects_auto_same_event_identical_km():
    rows = [
        {
            "flow_id": "S4_full_full",
            "seg_id": "S4",
            "event_a": "full",
            "event_b": "full",
            "from_km_a": 15.44,
            "to_km_a": 17.03,
            "from_km_b": 15.44,
            "to_km_b": 17.03,
            "flow_type": "overtake",
            "direction": "bi",
            "auto_generated": True,
        }
    ]
    result = validate_flow_csv(rows)
    assert not result.ok
    assert any("auto-generated same-event" in err for err in result.errors)


def test_validate_allows_none_flow_type():
    rows = [
        {
            "flow_id": "C1",
            "seg_id": "C1",
            "event_a": "full",
            "event_b": "full",
            "from_km_a": 4.25,
            "to_km_a": 5.08,
            "from_km_b": 13.96,
            "to_km_b": 14.79,
            "flow_type": "none",
            "direction": "bi",
            "notes": "Full out/back reference",
        }
    ]
    result = validate_flow_csv(rows)
    assert result.ok


def test_validate_flow_csv_text_round_trip():
    segments = [
        {
            "seg_id": "S2",
            "seg_label": "Friel to turn",
            "direction": "bi",
            "full": "y",
            "10k": "y",
            "full_from_km": 2.7,
            "full_to_km": 4.3,
            "10k_from_km": 2.7,
            "10k_to_km": 4.3,
        }
    ]
    csv_text = build_flow_csv_from_segments(segments, ["full", "10k"])
    result = validate_flow_csv_text(csv_text)
    assert result.ok
