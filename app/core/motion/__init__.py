"""Runflow motion clock (#850): persisted runner time series."""

from app.core.motion.persist import build_and_persist_motion_for_day

__all__ = ["build_and_persist_motion_for_day"]
