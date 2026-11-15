"""Issue #961: zone pass/co-presence use zone boundaries, not first-20% fallback."""

from __future__ import annotations

import numpy as np

from app.core.flow.flow import (
    ConflictZone,
    ConvergencePoint,
    SegmentFlowCache,
    build_conflict_zones,
    calculate_zone_metrics_vectorized_direct,
)


def _cache(
    *,
    from_a: float,
    to_a: float,
    from_b: float,
    to_b: float,
    paces_a,
    paces_b,
    offsets_a=None,
    offsets_b=None,
    flow_type: str = "overtake",
    start_a: float = 0.0,
    start_b: float = 0.0,
) -> SegmentFlowCache:
    n = len(paces_a)
    m = len(paces_b)
    return SegmentFlowCache(
        event_a="5k",
        event_b="5k",
        start_time_a=start_a,
        start_time_b=start_b,
        pace_a=np.asarray(paces_a, dtype=float),
        pace_b=np.asarray(paces_b, dtype=float),
        offset_a=np.asarray(offsets_a if offsets_a is not None else [0.0] * n),
        offset_b=np.asarray(offsets_b if offsets_b is not None else [0.0] * m),
        runner_id_a=np.asarray([f"a{i}" for i in range(n)]),
        runner_id_b=np.asarray([f"b{i}" for i in range(m)]),
        from_km_a=from_a,
        to_km_a=to_a,
        from_km_b=from_b,
        to_km_b=to_b,
        flow_type=flow_type,
    )


def test_zone_local_boundaries_count_pass_outside_first_20_percent():
    """
    Lap-style pair: A 0–2.222 km, B 2.222–4.444 km (no absolute intersection).

    A fast B runner (3.2 min/km) overtakes a slow A walker (12 min/km) near
    ~0.8 km into the loop — outside the old first-20% window (~0.44 km).
    Zone-local scoring must still count the pass.
    """
    # Zone covering ~0.6–1.0 km on A → mapped proportionally onto B's range
    zone = ConflictZone(
        cp=ConvergencePoint(km=0.8, type="true_pass"),
        zone_start_km_a=0.6,
        zone_end_km_a=1.0,
        zone_start_km_b=2.822,
        zone_end_km_b=3.222,
        zone_index=0,
        source="true_pass",
        metrics={},
    )
    # pace in sec/km: walker 720 s/km, leader 192 s/km
    cache = _cache(
        from_a=0.0,
        to_a=2.222,
        from_b=2.222,
        to_b=4.444,
        paces_a=[720.0],
        paces_b=[192.0],
        offsets_a=[0.0],
        offsets_b=[0.0],
        start_a=0.0,
        start_b=0.0,
        flow_type="overtake",
    )
    metrics = calculate_zone_metrics_vectorized_direct(
        zone, cache, min_overlap_duration=1.0
    )
    # B (fast) should overtake A (slow) inside this mid-segment zone
    assert (
        metrics["overtaking_b"] >= 1
        or metrics.get("overtakes_b", 0) >= 1
        or (
            len(metrics.get("sample_b") or []) >= 1
            or metrics.get("unique_encounters", 0) >= 1
        )
    )
    # Prefer explicit overtaking fields used by the vectorized path
    assert (
        metrics.get("overtaking_b", metrics.get("overtakes_b", 0)) >= 1
        or len(metrics.get("_b_bibs_overtakes") or []) >= 1
        or len(metrics.get("sample_b") or []) >= 1
    )


def test_build_conflict_zones_reverses_b_for_counterflow():
    cps = [ConvergencePoint(km=1.0, type="true_pass")]
    zones = build_conflict_zones(
        cps,
        from_km_a=0.0,
        to_km_a=2.0,
        from_km_b=10.0,
        to_km_b=12.0,
        conflict_length_m=200.0,
        reverse_b=True,
    )
    assert len(zones) == 1
    z = zones[0]
    # A fraction around 0.5 → B should sit near the opposite end of [10, 12]
    mid_a = (z.zone_start_km_a + z.zone_end_km_a) / 2.0
    mid_b = (z.zone_start_km_b + z.zone_end_km_b) / 2.0
    s_a = (mid_a - 0.0) / 2.0
    s_b = (mid_b - 10.0) / 2.0
    assert abs((s_a + s_b) - 1.0) < 0.15


def test_counterflow_counts_meetings_not_directional_only():
    # Boundaries already reversed for counterflow; both in similar absolute km
    # so arrival times can overlap.
    zone = ConflictZone(
        cp=ConvergencePoint(km=1.0, type="true_pass"),
        zone_start_km_a=0.8,
        zone_end_km_a=1.2,
        zone_start_km_b=0.8,
        zone_end_km_b=1.2,
        zone_index=0,
        source="true_pass",
        metrics={},
    )
    cache = _cache(
        from_a=0.0,
        to_a=2.0,
        from_b=0.0,
        to_b=2.0,
        paces_a=[300.0],
        paces_b=[300.0],
        offsets_a=[0.0],
        offsets_b=[30.0],
        flow_type="counterflow",
    )
    metrics = calculate_zone_metrics_vectorized_direct(
        zone, cache, min_overlap_duration=1.0
    )
    # Counterflow treats sufficient overlaps as meetings (overtaking slots)
    assert metrics["unique_encounters"] >= 1
    assert metrics["overtaking_a"] >= 1
    assert metrics["overtaking_b"] >= 1
