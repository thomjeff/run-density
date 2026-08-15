"""Persist motion samples.parquet + metadata.json for one analysis day (#850)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import pandas as pd

from app.core.motion.build import (
    build_motion_metadata,
    build_motion_samples,
    hash_course_file,
    hash_guns,
    hash_runners_inputs,
)
from app.core.v2.models import Event
from app.utils.constants import (
    MOTION_DIRNAME,
    MOTION_METADATA_FILENAME,
    MOTION_RUNNERS_SNAPSHOT_FILENAME,
    MOTION_SAMPLE_INTERVAL_SEC,
    MOTION_SAMPLES_FILENAME,
)

logger = logging.getLogger(__name__)


def build_and_persist_motion_for_day(
    *,
    day_path: Path,
    day_code: str,
    day_events: Sequence[Event],
    runners_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    gpx_paths: Mapping[str, str],
    runner_csv_paths: Mapping[str, str],
    package_id: Optional[str] = None,
    course_json_path: Optional[Path] = None,
    interval_sec: int = MOTION_SAMPLE_INTERVAL_SEC,
) -> Dict[str, object]:
    """
    Build and write motion artifacts under ``day_path/motion/``.

    Raises on any failure (analysis must not continue without motion).
    """
    day_path = Path(day_path)
    motion_dir = day_path / MOTION_DIRNAME
    motion_dir.mkdir(parents=True, exist_ok=True)

    samples, diagnostics = build_motion_samples(
        runners_df=runners_df,
        day_events=day_events,
        segments_df=segments_df,
        gpx_paths=gpx_paths,
        interval_sec=interval_sec,
    )

    gun_by_event = {str(ev.name).lower(): int(ev.start_time) * 60 for ev in day_events}
    runner_paths = []
    for ev in day_events:
        key = str(ev.name).lower()
        raw = runner_csv_paths.get(key) or runner_csv_paths.get(ev.name)
        if raw:
            runner_paths.append(Path(raw))

    metadata = build_motion_metadata(
        diagnostics=diagnostics,
        package_id=package_id,
        day=day_code,
        gun_by_event=gun_by_event,
        course_hash=hash_course_file(Path(course_json_path) if course_json_path else None),
        runners_hash=hash_runners_inputs(runner_paths) if runner_paths else None,
        guns_hash=hash_guns(gun_by_event),
        generated_at_iso=datetime.now(timezone.utc).isoformat(),
    )

    samples_path = motion_dir / MOTION_SAMPLES_FILENAME
    meta_path = motion_dir / MOTION_METADATA_FILENAME

    # Deterministic column order + row order already enforced in build.
    samples.to_parquet(samples_path, index=False, compression="zstd", compression_level=3)

    snapshot_cols = [
        c
        for c in ("runner_id", "event", "pace", "start_offset", "distance")
        if c in runners_df.columns
    ]
    snapshot = runners_df.loc[:, snapshot_cols].copy()
    snapshot_path = motion_dir / MOTION_RUNNERS_SNAPSHOT_FILENAME
    snapshot.to_parquet(snapshot_path, index=False, compression="zstd", compression_level=3)

    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    logger.info(
        "Motion persisted for %s: %s rows → %s",
        day_code,
        metadata["row_count"],
        samples_path,
    )
    return {
        "day": day_code,
        "samples_path": str(samples_path),
        "metadata_path": str(meta_path),
        "runners_snapshot_path": str(snapshot_path),
        "row_count": metadata["row_count"],
        "event_counts": metadata["event_counts"],
    }
