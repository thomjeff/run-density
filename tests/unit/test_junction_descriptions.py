"""Tests for Junction Flow interaction descriptions (#819 §4–§5)."""

from __future__ import annotations

from app.core.junction_flow.descriptions import (
    format_event_list,
    format_interaction_description,
    role_headline_labels,
)


NEARBY = {
    "S8": {
        "seg_id": "S8",
        "seg_label": "Walking Bridge South to George",
        "events": ["full", "half", "10k"],
        "event_kms": {"full": {}, "half": {}, "10k": {}},
    },
    "S11": {
        "seg_id": "S11",
        "seg_label": "George to Aberdeen via Trail (reverse)",
        "events": ["full"],
        "event_kms": {"full": {}},
    },
    "S25": {
        "seg_id": "S25",
        "seg_label": "George to Forest Hill (via University)",
        "events": ["10k"],
        "event_kms": {"10k": {}},
    },
    "S26": {
        "seg_id": "S26",
        "seg_label": "Forest Hill (via University) to George",
        "events": ["10k"],
        "event_kms": {"10k": {}},
    },
    "S9": {
        "seg_id": "S9",
        "seg_label": "George to Aberdeen via Trail",
        "events": ["full", "half", "10k"],
        "event_kms": {"full": {}, "half": {}, "10k": {}},
    },
    "S22": {
        "seg_id": "S22",
        "seg_label": "George to Aberdeen via Trail (2)",
        "events": ["full"],
        "event_kms": {"full": {}},
    },
}


def test_format_event_list():
    assert format_event_list(["10k", "full"]) == "Full+10k"
    assert format_event_list(["half", "full"]) == "Full+Half"


def test_cross_description_george():
    ix = {
        "type": "cross",
        "side": "left",
        "from_seg_id": "S8",
        "to_seg_ids": ["S25"],
        "conflicts_with_seg_id": "S11",
        "events": ["full", "10k"],
    }
    desc = format_interaction_description(ix, NEARBY)
    assert "10k runners from Walking Bridge South to George (S8)" in desc
    assert "Full runners from George to Aberdeen via Trail (reverse) (S11)" in desc
    assert "left to George to Forest Hill (via University) (S25)" in desc


def test_merge_description_george():
    ix = {
        "type": "merge",
        "from_seg_id": "S26",
        "to_seg_ids": ["S9", "S22"],
        "events": ["full", "half", "10k"],
    }
    desc = format_interaction_description(ix, NEARBY)
    assert "10k runners from Forest Hill (via University) to George (S26)" in desc
    assert "merging into Full+Half traffic" in desc
    assert "S9" in desc and "S22" in desc


def test_headline_labels_from_uniques():
    ix = {"type": "cross", "from_seg_id": "S8", "to_seg_ids": ["S25"], "conflicts_with_seg_id": "S11"}
    labels = role_headline_labels(
        ix,
        NEARBY,
        {
            "crossing_with_copresence": {"all": 222, "10k": 222},
            "crossed_with_copresence": {"all": 159, "full": 159},
        },
    )
    assert labels["primary_label"] == "10k Crossing (co-present)"
    assert labels["secondary_label"] == "Full Crossed (co-present)"


def test_normalize_preserves_description():
    from app.core.config_package.junctions import validate_junctions_doc

    doc = validate_junctions_doc(
        {
            "junctions": [
                {
                    "id": "j1",
                    "label": "George",
                    "lat": 45.95,
                    "lon": -66.63,
                    "interactions": [
                        {
                            "type": "cross",
                            "side": "left",
                            "from_seg_id": "S8",
                            "to_seg_ids": ["S25"],
                            "conflicts_with_seg_id": "S11",
                            "events": ["10k", "full"],
                            "description": "Custom RD wording for the spur cross.",
                        }
                    ],
                }
            ]
        }
    )
    assert doc["junctions"][0]["interactions"][0]["description"] == (
        "Custom RD wording for the spur cross."
    )
