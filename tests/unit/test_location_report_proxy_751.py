"""Issue #751: proxy_loc_id timing helpers and conflict detection."""

import math

import pandas as pd
import pytest

from app.location_report import (
    location_has_proxy_and_seg_conflict,
    proxy_loc_id_is_set,
    seg_id_effectively_empty,
)


@pytest.mark.parametrize(
    "seg_val,expected",
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("N1", False),
        ('"N1,N2"', False),
        (" N1 , N2 ", False),
    ],
)
def test_seg_id_effectively_empty(seg_val, expected):
    assert seg_id_effectively_empty(seg_val) is expected


@pytest.mark.parametrize(
    "proxy_val,expected",
    [
        (None, False),
        ("", False),
        ("  ", False),
        (99, True),
        (99.0, True),
        ("99", True),
    ],
)
def test_proxy_loc_id_is_set(proxy_val, expected):
    assert proxy_loc_id_is_set(proxy_val) is expected


def test_proxy_loc_id_is_set_nan_like():
    assert proxy_loc_id_is_set(float("nan")) is False
    assert proxy_loc_id_is_set(math.nan) is False
    assert proxy_loc_id_is_set(pd.NA) is False


def test_location_conflict_series():
    row = pd.Series(
        {
            "proxy_loc_id": 99,
            "seg_id": "N1",
        }
    )
    assert location_has_proxy_and_seg_conflict(row) is True

    row2 = pd.Series({"proxy_loc_id": 99, "seg_id": ""})
    assert location_has_proxy_and_seg_conflict(row2) is False

    row3 = pd.Series({"proxy_loc_id": float("nan"), "seg_id": "N1"})
    assert location_has_proxy_and_seg_conflict(row3) is False
