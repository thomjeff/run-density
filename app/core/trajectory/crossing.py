"""Point-crossing timing shared by the trajectory compiler and Locations (#859 / #861).

Constant-pace model:

    t = gun_sec + start_offset_sec + pace_sec_per_km * km
"""

from __future__ import annotations

from app.utils.constants import SECONDS_PER_MINUTE


def runner_start_sec(gun_sec: float, start_offset_sec: float) -> float:
    """Wall-clock seconds from local midnight when this runner starts."""
    offset = 0.0 if start_offset_sec is None else float(start_offset_sec)
    return float(gun_sec) + offset


def arrival_at_km(
    *,
    gun_sec: float,
    start_offset_sec: float,
    pace_min_per_km: float,
    km: float,
) -> float:
    """Seconds from local midnight when a runner reaches ``km`` on the compiled course.

    Same formula the trajectory layer uses to place samples. Locations projects a
    GPS pin to ``km`` then calls this — it does not scan the 5s parquet grid.
    """
    pace = float(pace_min_per_km)
    if pace <= 0:
        raise ValueError(f"Non-positive pace: {pace_min_per_km}")
    pace_sec_per_km = pace * SECONDS_PER_MINUTE
    return runner_start_sec(gun_sec, start_offset_sec) + pace_sec_per_km * float(km)
