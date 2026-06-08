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


def test_ensure_location_key_allocates_when_missing():
    used = {"ABCDE"}
    loc = {"loc_label": "B"}
    key = ensure_location_key(loc, used)
    assert is_valid_location_key(key)
    assert key != "ABCDE"
    assert loc["location_key"] == key
