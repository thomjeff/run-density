"""Trajectory layer: shared runner timing substrate (analysis Phase 2.5).

Motion (Stream Passage, occupancy) is a *consumer* of this layer, not the layer name.
Locations first/last at a course point uses the same crossing math.
"""

from app.core.trajectory.crossing import arrival_at_km, runner_start_sec

__all__ = ["arrival_at_km", "runner_start_sec"]
