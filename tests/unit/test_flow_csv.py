"""Unit tests for conservative flow.csv export and validation."""

import csv
import io

import pytest

from app.core.course.flow_csv import (
    build_flow_csv_from_segments,
    corridor_flow_id,
    default_flow_id,
    parse_flow_csv_text,
    validate_flow_csv,
    validate_flow_csv_text,
)


def _parse(csv_text: str):
    return parse_flow_csv_text(csv_text)


def _corridor_segments():
    """Out-and-back corridor: leg 09 outbound (S11) paired with leg 13 return (S14)."""
    return [
        {
            "seg_id": "S11",
            "seg_label": "Bridge At Mill To Half Turn",
            "direction": "uni",
            "leg_id": "09",
            "paired_with": "13",
            "events": ["full", "half"],
            "full_from_km": 29.67,
            "full_to_km": 32.24,
            "half_from_km": 10.83,
            "half_to_km": 13.4,
        },
        {
            "seg_id": "S14",
            "seg_label": "Half Turn To Bridge At Mill",
            "direction": "uni",
            "leg_id": "13",
            "paired_with": "09",
            "events": ["full", "half"],
            "full_from_km": 33.82,
            "full_to_km": 36.4,
            "half_from_km": 13.4,
            "half_to_km": 15.98,
        },
    ]


def test_paired_legs_emit_opposing_pass_rows():
    csv_text = build_flow_csv_from_segments(_corridor_segments(), ["full", "half"])
    rows = _parse(csv_text)
    corridor = [r for r in rows if r["flow_id"].startswith("S11_S14_")]
    # full×full, full×half, half×full, half×half across the two passes
    assert len(corridor) == 4
    assert all(r["flow_type"] == "counterflow" for r in corridor)
    assert all(r["direction"] == "bi" for r in corridor)
    # C2-style same-event out/back row with distinct windows
    ff = next(r for r in corridor if r["event_a"] == "full" and r["event_b"] == "full")
    assert (float(ff["from_km_a"]), float(ff["to_km_a"])) == (29.67, 32.24)
    assert (float(ff["from_km_b"]), float(ff["to_km_b"])) == (33.82, 36.4)
    assert ff["flow_id"] == corridor_flow_id("S11", "S14", "full", "full")
    # Per-leg same-direction rows still present and unchanged
    assert any(r["flow_id"] == "S11_full_half" for r in rows)
    assert any(r["flow_id"] == "S14_full_half" for r in rows)
    # Generated CSV passes validation
    result = validate_flow_csv_text(csv_text)
    assert result.ok, result.errors


def test_self_paired_leg_occurrences_emit_corridor_rows():
    segments = [
        {
            "seg_id": "S2",
            "seg_label": "Friel To 10k Turn",
            "direction": "uni",
            "leg_id": "04",
            "leg_occurrence": 1,
            "events": ["10k"],
            "10k_from_km": 2.7,
            "10k_to_km": 4.3,
        },
        {
            "seg_id": "S5",
            "seg_label": "Friel To 10k Turn (2)",
            "direction": "uni",
            "leg_id": "04",
            "leg_occurrence": 2,
            "events": ["10k"],
            "10k_from_km": 4.3,
            "10k_to_km": 5.9,
        },
    ]
    rows = _parse(build_flow_csv_from_segments(segments, ["full", "10k"]))
    corridor = [r for r in rows if r["flow_id"].startswith("S2_S5_")]
    assert len(corridor) == 1
    row = corridor[0]
    assert (row["event_a"], row["event_b"]) == ("10k", "10k")
    assert row["flow_type"] == "counterflow"
    assert (float(row["from_km_a"]), float(row["to_km_a"])) == (2.7, 4.3)
    assert (float(row["from_km_b"]), float(row["to_km_b"])) == (4.3, 5.9)


def test_unpaired_segments_output_unchanged():
    segments = [
        {
            "seg_id": "S1",
            "seg_label": "Shared start",
            "direction": "uni",
            "leg_id": "01",
            "events": ["full", "half"],
            "full_from_km": 0,
            "full_to_km": 2.0,
            "half_from_km": 0,
            "half_to_km": 2.0,
        }
    ]
    with_pairing_support = build_flow_csv_from_segments(segments, ["full", "half"])
    rows = _parse(with_pairing_support)
    assert len(rows) == 1
    assert rows[0]["flow_id"] == "S1_full_half"


def test_corridor_skips_events_not_on_pass():
    segments = _corridor_segments()
    # Half only runs the outbound pass
    segments[1]["events"] = ["full"]
    segments[1]["half_from_km"] = 0.0
    segments[1]["half_to_km"] = 0.0
    rows = _parse(build_flow_csv_from_segments(segments, ["full", "half"]))
    corridor = [r for r in rows if r["flow_id"].startswith("S11_S14_")]
    assert {(r["event_a"], r["event_b"]) for r in corridor} == {
        ("full", "full"),
        ("half", "full"),
    }


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
