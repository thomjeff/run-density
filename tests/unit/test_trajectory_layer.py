"""Unit tests for trajectory-layer crossing math and staged analysis (#859–#861)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.locations.shadow_diff import compare_locations_csv, compare_locations_frames
from app.core.trajectory.crossing import arrival_at_km, runner_start_sec
from app.core.v2.through import (
    THROUGH_FULL,
    THROUGH_LOCATIONS,
    THROUGH_TRAJECTORY,
    ThroughError,
    normalize_through,
    run_locations_report,
    run_plan_engines,
)


def test_arrival_at_km_matches_constant_pace():
    gun = 7 * 3600  # 07:00
    t = arrival_at_km(gun_sec=gun, start_offset_sec=30, pace_min_per_km=5.0, km=2.0)
    # 07:00 + 30s + 5 min/km * 2 km = 07:10:30
    assert t == gun + 30 + 5 * 60 * 2
    assert runner_start_sec(gun, 30) == gun + 30


def test_arrival_rejects_non_positive_pace():
    with pytest.raises(ValueError, match="Non-positive"):
        arrival_at_km(gun_sec=0, start_offset_sec=0, pace_min_per_km=0, km=1)


def test_normalize_through():
    assert normalize_through(None) == THROUGH_FULL
    assert normalize_through("Locations") == THROUGH_LOCATIONS
    assert run_plan_engines(THROUGH_TRAJECTORY) is False
    assert run_locations_report(THROUGH_TRAJECTORY) is False
    assert run_locations_report(THROUGH_LOCATIONS) is True
    with pytest.raises(ThroughError):
        normalize_through("density")


def test_shadow_diff_exact_and_mismatch():
    baseline = pd.DataFrame(
        {
            "day": ["sun", "sun"],
            "loc_id": [1, 2],
            "pass_id": [1, 2],
            "first_runner": ["07:10:00", "07:20:00"],
            "last_runner": ["08:00:00", "08:10:00"],
        }
    )
    same = baseline.copy()
    assert compare_locations_frames(baseline, same) == []

    drifted = baseline.copy()
    drifted.loc[0, "first_runner"] = "07:10:05"
    diffs = compare_locations_frames(baseline, drifted)
    assert len(diffs) == 1
    assert diffs[0]["column"] == "first_runner"

    within = compare_locations_frames(baseline, drifted, tolerance_sec=5)
    assert within == []


def test_shadow_diff_csv_roundtrip(tmp_path: Path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    pd.DataFrame(
        {
            "loc_id": [10],
            "first_runner": ["07:00:00"],
            "last_runner": ["08:00:00"],
        }
    ).to_csv(a, index=False)
    pd.DataFrame(
        {
            "loc_id": [10],
            "first_runner": ["07:00:00"],
            "last_runner": ["08:00:00"],
        }
    ).to_csv(b, index=False)
    assert compare_locations_csv(a, b) == []
