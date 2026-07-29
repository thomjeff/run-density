"""Tests for stable location_key allocation (Issue #780)."""

import re

from app.core.config_package.location_keys import (
    LOCATION_KEY_RE,
    ensure_location_key,
    generate_location_key,
    is_valid_location_key,
)


def test_generate_location_key_format():
    key = generate_location_key()
    assert is_valid_location_key(key)
    assert LOCATION_KEY_RE.match(key)


def test_ensure_location_key_preserves_existing():
    used = set()
    loc = {"location_key": "ABCDE", "loc_label": "A"}
    assert ensure_location_key(loc, used) == "ABCDE"
    assert loc["location_key"] == "ABCDE"
    assert "ABCDE" in used


def test_ensure_location_key_allocates_when_missing():
    used = {"ABCDE"}
    loc = {"loc_label": "B"}
    key = ensure_location_key(loc, used)
    assert is_valid_location_key(key)
    assert key != "ABCDE"
    assert loc["location_key"] == key
    assert key in used


def test_ensure_location_key_allows_shared_key_for_paired_legs():
    """Issue #810: paired reverse legs may reuse the same location_key."""
    used = set()
    a = {"location_key": "J6NJY", "loc_label": "George out"}
    b = {"location_key": "J6NJY", "loc_label": "George return"}
    assert ensure_location_key(a, used) == "J6NJY"
    assert ensure_location_key(b, used) == "J6NJY"
    assert a["location_key"] == b["location_key"] == "J6NJY"
    assert used == {"J6NJY"}


def test_ensure_location_key_preserves_when_already_in_used():
    used = {"J6NJY"}
    loc = {"location_key": "J6NJY", "loc_label": "Return pass"}
    assert ensure_location_key(loc, used) == "J6NJY"
    assert loc["location_key"] == "J6NJY"
