"""Trajectory layer: shared runner timing substrate (analysis Phase 2.5).

Motion (Stream Passage, occupancy) is a *consumer* of this layer, not the layer name.
Locations first/last at a course point uses the same crossing math.
"""

from app.core.trajectory.crossing import arrival_at_km, elapsed_km_at, runner_start_sec
from app.core.trajectory.layer import TrajectoryLayer, try_load_day_layer, try_load_day_snapshot

__all__ = [
    "arrival_at_km",
    "elapsed_km_at",
    "runner_start_sec",
    "TrajectoryLayer",
    "try_load_day_layer",
    "try_load_day_snapshot",
]
