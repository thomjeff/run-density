"""
Hotspot preservation helpers for bin coarsening (Issue #798 Phase 9).

Extracted from ``app.density_report`` so race-template hotspot IDs and coarsening
policy live beside other bin core modules.
"""

from __future__ import annotations

from typing import Optional, Tuple

from app.utils.constants import HOTSPOT_SEGMENTS


def is_hotspot(seg_id: str, peak_los: Optional[str] = None) -> bool:
    """True when a segment should keep finer bin resolution during coarsening."""
    if seg_id in HOTSPOT_SEGMENTS:
        return True
    if peak_los and peak_los >= "D":
        return True
    return False


def coarsen_plan(
    seg_id: str,
    current_bin_km: float,
    current_dt_s: int,
    peak_los: Optional[str] = None,
) -> Tuple[float, int]:
    """
    Determine coarsening strategy (hotspot preservation policy).

    Hotspots keep current resolution; others widen time first, then space.
    """
    if is_hotspot(seg_id, peak_los):
        return current_bin_km, current_dt_s
    coarsened_dt = max(current_dt_s, 120)
    coarsened_bin = max(current_bin_km, 0.2)
    return coarsened_bin, coarsened_dt
