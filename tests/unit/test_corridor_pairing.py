"""Unit tests for corridor pairing (Issue #785)."""

import pytest

from app.core.config_package.legs import apply_leg_pairing
from app.core.course.segment_library import validate_corridor_pairings


def _legs():
    return [
        {"id": "09", "seg_label": "Bridge to Half Turn"},
        {"id": "13", "seg_label": "Half Turn to Bridge"},
        {"id": "01", "seg_label": "Start leg"},
    ]


def test_pairing_sets_both_sides():
    legs = _legs()
    changed = apply_leg_pairing(legs, "09", "13")
    assert changed is True
    assert legs[0]["paired_with"] == "13"
    assert legs[1]["paired_with"] == "09"
    assert "paired_with" not in legs[2]


def test_pairing_clear_removes_both_sides():
    legs = _legs()
    apply_leg_pairing(legs, "09", "13")
    changed = apply_leg_pairing(legs, "13", "")
    assert changed is True
    assert "paired_with" not in legs[0]
    assert "paired_with" not in legs[1]


def test_repairing_clears_old_reciprocal():
    legs = _legs()
    apply_leg_pairing(legs, "09", "13")
    apply_leg_pairing(legs, "09", "01")
    assert legs[0]["paired_with"] == "01"
    assert legs[2]["paired_with"] == "09"
    assert "paired_with" not in legs[1]


def test_pairing_noop_returns_false():
    legs = _legs()
    apply_leg_pairing(legs, "09", "13")
    assert apply_leg_pairing(legs, "09", "13") is False


def test_pairing_rejects_self():
    with pytest.raises(ValueError, match="itself"):
        apply_leg_pairing(_legs(), "09", "09")


def test_pairing_rejects_unknown_target():
    with pytest.raises(ValueError, match="not found"):
        apply_leg_pairing(_legs(), "09", "99")


def test_pairing_rejects_target_paired_elsewhere():
    legs = _legs()
    apply_leg_pairing(legs, "09", "13")
    with pytest.raises(ValueError, match="already paired"):
        apply_leg_pairing(legs, "01", "13")


def _legs_by_id(reverse_geometry=True):
    # Leg 09: A -> B; leg 13 reversed (B -> A) or not depending on flag.
    a = [-66.640, 45.950]
    b = [-66.620, 45.960]
    legs = {
        "09": {"id": "09", "paired_with": "13", "start": a, "end": b},
        "13": {"id": "13", "paired_with": "09", "start": b if reverse_geometry else a,
               "end": a if reverse_geometry else b},
    }
    return legs


def test_validate_pairings_clean():
    warnings = validate_corridor_pairings(
        _legs_by_id(), {"full": ["09", "13"]}
    )
    assert warnings == []


def test_validate_pairings_inactive_when_leg_unused():
    warnings = validate_corridor_pairings(_legs_by_id(), {"full": ["09"]})
    assert any("inactive" in w and "13" in w for w in warnings)


def test_validate_pairings_flags_non_reversed_geometry():
    warnings = validate_corridor_pairings(
        _legs_by_id(reverse_geometry=False), {"full": ["09", "13"]}
    )
    assert any("not" in w and "reverses" in w for w in warnings)


def test_validate_pairings_flags_dangling_reference():
    legs = {"09": {"id": "09", "paired_with": "77", "start": [0, 0], "end": [1, 1]}}
    warnings = validate_corridor_pairings(legs, {"full": ["09"]})
    assert any("unknown leg 77" in w for w in warnings)


def test_validate_pairings_flags_asymmetric():
    legs = _legs_by_id()
    legs["13"]["paired_with"] = ""
    warnings = validate_corridor_pairings(legs, {"full": ["09", "13"]})
    assert any("Asymmetric" in w for w in warnings)
