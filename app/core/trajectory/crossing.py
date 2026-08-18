"""Point-crossing timing shared by the trajectory compiler and Locations (#859 / #861).

Constant-pace model:

    t = gun_sec + start_offset_sec + pace_sec_per_km * km
"""

from __future__ import annotations

from typing import Tuple

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


def elapsed_km_at(
    *,
    t_sec: float,
    gun_sec: float,
    start_offset_sec: float,
    pace_min_per_km: float,
    finish_km: float,
) -> Tuple[str, float]:
    """Inverse of ``arrival_at_km``: distance at wall-clock ``t_sec``.

    Returns ``(status, km)`` where status is ``not_started``, ``on_course``,
    or ``finished``. ``finished`` still reports ``finish_km``.
    """
    pace = float(pace_min_per_km)
    if pace <= 0:
        raise ValueError(f"Non-positive pace: {pace_min_per_km}")
    finish = max(0.0, float(finish_km))
    start = runner_start_sec(gun_sec, start_offset_sec)
    t = float(t_sec)
    if t < start:
        return "not_started", 0.0
    pace_sec_per_km = pace * SECONDS_PER_MINUTE
    km = (t - start) / pace_sec_per_km
    if km >= finish:
        return "finished", finish
    return "on_course", km
