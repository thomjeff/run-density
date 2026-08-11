"""Unit tests for motion place occupancy (#850 Child B / #854)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.core.motion.occupancy import (
    PlaceSpec,
    PlaceStream,
    estimate_center_seg_km,
    instantaneous_occupancy,
    query_occupancy,
    throughput_passages,
    window_uniques,
)


def _samples() -> pd.DataFrame:
    # Two runners on S1; center at 0.50 km; 30 m buffer => ±0.03 km
    rows = [
        # r1 approaches and crosses 0.50
        {"runner_id": "r1", "event": "10k", "t": 100, "seg_id": "S1", "seg_km": 0.40, "lat": 45.0, "lon": -66.0},
        {"runner_id": "r1", "event": "10k", "t": 105, "seg_id": "S1", "seg_km": 0.50, "lat": 45.001, "lon": -66.0},
        {"runner_id": "r1", "event": "10k", "t": 110, "seg_id": "S1", "seg_km": 0.60, "lat": 45.002, "lon": -66.0},
        # r2 in zone at t=105 only (no crossing of center in window later)
        {"runner_id": "r2", "event": "half", "t": 105, "seg_id": "S1", "seg_km": 0.49, "lat": 45.0005, "lon": -66.0},
        {"runner_id": "r2", "event": "half", "t": 110, "seg_id": "S1", "seg_km": 0.48, "lat": 45.0004, "lon": -66.0},
        # other segment noise
        {"runner_id": "r3", "event": "full", "t": 105, "seg_id": "S2", "seg_km": 0.50, "lat": 46.0, "lon": -66.0},
    ]
    return pd.DataFrame(rows)


def _place() -> PlaceSpec:
    return PlaceSpec(
        streams=(PlaceStream(seg_id="S1", center_seg_km=0.50),),
        buffer_m=30.0,
        label="test",
        place_id="p1",
    )


def test_instantaneous_and_window_distinct():
    samples = _samples()
    place = _place()
    inst = instantaneous_occupancy(samples, place, t=105)
    assert inst["total"] == 2
    assert inst["by_event"] == {"10k": 1, "half": 1}

    win = window_uniques(samples, place, t0=100, t1=110)
    # r1 at 100 (0.40 outside 0.47–0.53), at 105 in zone; r2 in zone
    assert win["total"] == 2

    win2 = window_uniques(samples, place, t0=100, t1=106)
    assert win2["total"] == 2


def test_throughput_counts_crossing_not_zone_dwell():
    samples = _samples()
    place = _place()
    thr = throughput_passages(samples, place, t0=100, t1=120)
    # r1 crosses at t=105; r2 never crosses center
    assert thr["passages"] == 1
    assert thr["unique_runners"] == 1
    assert thr["by_event"] == {"10k": 1}


def test_event_filter_and_query_bundle():
    samples = _samples()
    place = _place()
    out = query_occupancy(
        samples,
        place,
        metrics=["instantaneous", "window_uniques", "throughput"],
        t=105,
        t0=100,
        t1=120,
        events=["10k"],
        include_runner_ids=True,
    )
    assert out["metrics"]["instantaneous"]["total"] == 1
    assert out["metrics"]["window_uniques"]["total"] == 1
    assert out["metrics"]["throughput"]["passages"] == 1
    assert out["metrics"]["instantaneous"]["runner_ids"] == ["r1"]


def test_estimate_center_seg_km():
    samples = _samples()
    center = estimate_center_seg_km(
        samples, seg_id="S1", lat=45.001, lon=-66.0, nearest_n=2
    )
    assert center == pytest.approx(0.50, abs=0.05)


def test_half_open_window_validation():
    with pytest.raises(ValueError):
        window_uniques(_samples(), _place(), t0=100, t1=100)


def test_location_places_aggregate_streams_by_loc_id():
    samples = pd.DataFrame(
        [
            {
                "runner_id": "r1",
                "event": "full",
                "t": 100,
                "seg_id": "S7",
                "seg_km": 0.49,
                "lat": 45.9716,
                "lon": -66.6326,
            },
            {
                "runner_id": "r1",
                "event": "full",
                "t": 105,
                "seg_id": "S8",
                "seg_km": 0.01,
                "lat": 45.9716,
                "lon": -66.6326,
            },
        ]
    )
    passes = pd.DataFrame(
        [
            {
                "pass_id": 129,
                "loc_id": 44,
                "loc_label": "Trail at Cliffe",
                "seg_id": "S7",
                "lat": 45.971624,
                "lon": -66.632641,
                "buffer": 10,
            },
            {
                "pass_id": 130,
                "loc_id": 44,
                "loc_label": "Trail at Cliffe",
                "seg_id": "S8",
                "lat": 45.971624,
                "lon": -66.632641,
                "buffer": 10,
            },
        ]
    )
    from app.core.motion.occupancy import (
        build_location_places_from_passes,
        place_spec_from_location,
        query_occupancy,
    )

    locs = build_location_places_from_passes(passes, samples, default_buffer_m=30)
    assert len(locs) == 1
    assert locs[0]["loc_id"] == "44"
    assert set(locs[0]["seg_ids"]) == {"S7", "S8"}
    place = place_spec_from_location(locs[0])
    assert len(place.streams) == 2
    out = query_occupancy(
        samples,
        place,
        metrics=["window_uniques"],
        t0=90,
        t1=120,
    )
    assert out["place"]["place_id"] == "44"
    assert out["metrics"]["window_uniques"]["total"] == 1


def test_planar_pin_enter_exit_aligns_uniques_and_throughput():
    """GPS disk: runners who touch the pin enter once → uniques ≈ throughput."""
    from app.core.motion.occupancy import PinPlace, query_planar_occupancy

    # Pin at origin; r1 walks in and out; r2 never enters; r3 only inside at end
    rows = [
        {"runner_id": "r1", "event": "10k", "t": 100, "lat": 45.0, "lon": -66.0},  # ~111m south if we offset
        {"runner_id": "r1", "event": "10k", "t": 105, "lat": 45.0001, "lon": -66.0},  # ~11m
        {"runner_id": "r1", "event": "10k", "t": 110, "lat": 45.0, "lon": -66.0},
        {"runner_id": "r2", "event": "half", "t": 105, "lat": 45.01, "lon": -66.0},  # far
        {"runner_id": "r3", "event": "full", "t": 100, "lat": 45.01, "lon": -66.0},
        {"runner_id": "r3", "event": "full", "t": 108, "lat": 45.00005, "lon": -66.0},
    ]
    # Fix coordinates properly with haversine-known offsets:
    # ~0.00027 deg lat ≈ 30m; use 0.00005 ≈ 5.5m inside 30m; 0.001 ≈ 111m outside
    rows = [
        {"runner_id": "r1", "event": "10k", "t": 100, "lat": 45.001, "lon": -66.0},
        {"runner_id": "r1", "event": "10k", "t": 105, "lat": 45.00005, "lon": -66.0},
        {"runner_id": "r1", "event": "10k", "t": 110, "lat": 45.001, "lon": -66.0},
        {"runner_id": "r2", "event": "half", "t": 105, "lat": 45.01, "lon": -66.0},
        {"runner_id": "r3", "event": "full", "t": 100, "lat": 45.01, "lon": -66.0},
        {"runner_id": "r3", "event": "full", "t": 108, "lat": 45.00005, "lon": -66.0},
    ]
    samples = pd.DataFrame(rows)
    pin = PinPlace(lat=45.0, lon=-66.0, radius_m=30.0, place_id="44", label="pin")
    out = query_planar_occupancy(
        samples,
        pin,
        metrics=["window_uniques", "throughput", "instantaneous"],
        t=105,
        t0=100,
        t1=120,
        include_passage_rows=True,
    )
    assert out["mode"] == "planar"
    assert out["metrics"]["instantaneous"]["total"] == 1  # r1 at 105
    assert out["metrics"]["window_uniques"]["total"] == 2  # r1, r3
    assert out["metrics"]["throughput"]["unique_runners"] == 2
    assert out["metrics"]["throughput"]["entries"] == 2
    assert out["metrics"]["throughput"]["exits"] == 1  # r1 exits; r3 still inside
