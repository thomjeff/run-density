"""Tests for 2027 pass / location identity stamping."""

from app.core.locations.identity import (
    effective_pass_key,
    get_loc_id,
    get_pass_id,
    stamp_pass_identity,
)


def test_stamp_pass_identity_assigns_shared_loc_id():
    locs = [
        {"id": 32, "location_key": "7EFZ9", "loc_label": "Fulton out"},
        {"id": 3, "location_key": "7EFZ9", "loc_label": "Fulton return"},
        {"id": 94, "location_key": "73634", "loc_label": "WSB"},
    ]
    stamp_pass_identity(locs)
    assert get_pass_id(locs[0]) == 32
    assert get_pass_id(locs[1]) == 3
    assert locs[0]["pass_key"] == locs[1]["pass_key"] == "7EFZ9"
    assert get_loc_id(locs[0]) == get_loc_id(locs[1])
    assert get_loc_id(locs[0]) != get_pass_id(locs[0])
    assert get_loc_id(locs[2]) != get_loc_id(locs[0])
    assert effective_pass_key(locs[2]) == "73634"


def test_stamp_pass_identity_preserves_existing_shared_loc_id():
    locs = [
        {"id": 10, "pass_key": "ABCDE", "loc_id": 7, "loc_label": "A"},
        {"id": 20, "pass_key": "ABCDE", "loc_id": 7, "loc_label": "B"},
    ]
    stamp_pass_identity(locs)
    assert get_loc_id(locs[0]) == 7
    assert get_loc_id(locs[1]) == 7
    assert get_pass_id(locs[0]) == 10
    assert get_pass_id(locs[1]) == 20
