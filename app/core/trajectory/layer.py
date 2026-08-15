"""Load persisted trajectory-layer artifacts for Density / Flow (#862 / #869)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.utils.constants import (
    MOTION_DIRNAME,
    MOTION_METADATA_FILENAME,
    MOTION_RUNNERS_SNAPSHOT_FILENAME,
    MOTION_SAMPLES_FILENAME,
)


@dataclass(frozen=True)
class TrajectoryLayer:
    """One analysis day's Phase 2.5 artifacts."""

    day_path: Path
    samples: pd.DataFrame
    snapshot: pd.DataFrame
    metadata: Dict[str, Any]


def motion_dir(day_path: Path) -> Path:
    return Path(day_path) / MOTION_DIRNAME


def try_load_day_snapshot(day_path: Path) -> Optional[pd.DataFrame]:
    """Load ``runners_snapshot.parquet`` only (no 5s sample grid)."""
    snapshot_path = motion_dir(day_path) / MOTION_RUNNERS_SNAPSHOT_FILENAME
    if not snapshot_path.is_file():
        return None
    return pd.read_parquet(snapshot_path)


def try_load_day_layer(day_path: Path) -> Optional[TrajectoryLayer]:
    """Return the layer if parquet artifacts exist; otherwise None."""
    root = motion_dir(day_path)
    samples_path = root / MOTION_SAMPLES_FILENAME
    snapshot_path = root / MOTION_RUNNERS_SNAPSHOT_FILENAME
    meta_path = root / MOTION_METADATA_FILENAME
    if not samples_path.is_file() or not snapshot_path.is_file():
        return None
    samples = pd.read_parquet(samples_path)
    snapshot = pd.read_parquet(snapshot_path)
    metadata: Dict[str, Any] = {}
    if meta_path.is_file():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    return TrajectoryLayer(
        day_path=Path(day_path),
        samples=samples,
        snapshot=snapshot,
        metadata=metadata,
    )


def snapshot_to_runners_df(
    layer_or_snapshot: "TrajectoryLayer | pd.DataFrame",
    *,
    fallback: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Pace-table shape used by Flow (`event`, `runner_id`, `pace`, `distance`, `start_offset`)."""
    if isinstance(layer_or_snapshot, pd.DataFrame):
        snap = layer_or_snapshot.copy()
    else:
        snap = layer_or_snapshot.snapshot.copy()
    if "event" in snap.columns:
        snap["event"] = snap["event"].astype(str).str.lower()
    if "runner_id" in snap.columns:
        snap["runner_id"] = snap["runner_id"].astype(str)
    if fallback is not None and not fallback.empty and "distance" not in snap.columns:
        extra = fallback.loc[:, [c for c in ("runner_id", "event", "distance") if c in fallback.columns]].copy()
        if "event" in extra.columns:
            extra["event"] = extra["event"].astype(str).str.lower()
        if "runner_id" in extra.columns:
            extra["runner_id"] = extra["runner_id"].astype(str)
        snap = snap.merge(extra, on=[c for c in ("runner_id", "event") if c in extra.columns], how="left")
    if "distance" not in snap.columns:
        snap["distance"] = 0.0
    if "start_offset" not in snap.columns:
        snap["start_offset"] = 0
    return snap
