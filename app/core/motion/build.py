"""Build motion sample rows for one analysis day (#850 Child A)."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.core.gpx.processor import cumulative_km, parse_gpx_file
from app.core.trajectory.crossing import arrival_at_km, runner_start_sec
from app.core.motion.course_map import (
    compiled_course_length_km,
    event_spans,
    locate_on_course,
)
from app.core.v2.models import Event
from app.utils.constants import (
    MOTION_MODEL_VERSION,
    MOTION_POSITION_SOURCE,
    MOTION_SAMPLE_INTERVAL_SEC,
    MOTION_SCHEMA_VERSION,
    MOTION_TIME_SOURCE,
)

logger = logging.getLogger(__name__)

SAMPLE_COLUMNS = [
    "runner_id",
    "event",
    "t",
    "elapsed_km",
    "seg_id",
    "seg_km",
    "lat",
    "lon",
    "sample_kind",
    "time_source",
    "position_source",
]


@dataclass(frozen=True)
class EventMotionContext:
    event: str
    gun_sec: int
    finish_km: float
    csv_distance_km: Optional[float]
    spans: Tuple[Any, ...]
    points_latlon: Tuple[Tuple[float, float], ...]
    cum_km: Tuple[float, ...]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def aligned_ticks(start_sec: float, end_sec: float, interval_sec: int) -> np.ndarray:
    """Global wall-clock ticks in ``[start_sec, end_sec]`` aligned from midnight."""
    interval = int(interval_sec)
    if interval <= 0:
        raise ValueError("interval_sec must be positive")
    if end_sec < start_sec:
        return np.array([], dtype=np.int64)
    first = int(np.ceil(float(start_sec) / interval) * interval)
    last = int(np.floor(float(end_sec) / interval) * interval)
    if first > last:
        return np.array([], dtype=np.int64)
    return np.arange(first, last + 1, interval, dtype=np.int64)


def _interp_lat_lon(
    points: Sequence[Tuple[float, float]],
    cum: Sequence[float],
    target_km: float,
) -> Tuple[float, float]:
    if not points or not cum:
        return (float("nan"), float("nan"))
    # Reuse geometry convention from gpx.processor._interp_vertex (returns lon, lat).
    from app.core.gpx.processor import _interp_vertex

    lon, lat = _interp_vertex(list(points), list(cum), float(target_km))
    return float(lat), float(lon)


def prepare_event_contexts(
    *,
    day_events: Sequence[Event],
    segments_df: pd.DataFrame,
    runners_df: pd.DataFrame,
    gpx_paths: Mapping[str, str],
) -> Dict[str, EventMotionContext]:
    out: Dict[str, EventMotionContext] = {}
    for ev in day_events:
        name = str(ev.name).lower()
        spans = tuple(event_spans(segments_df, name))
        if not spans:
            raise ValueError(f"Motion: no compiled spans for event '{name}'")
        finish_km = compiled_course_length_km(segments_df, name)
        if finish_km <= 0:
            raise ValueError(f"Motion: compiled course length is 0 for event '{name}'")

        gpx_path = gpx_paths.get(name) or gpx_paths.get(ev.name)
        if not gpx_path:
            raise FileNotFoundError(f"Motion: GPX path missing for event '{name}'")
        course = parse_gpx_file(str(gpx_path))
        points = tuple((p.lat, p.lon) for p in course.points)
        if len(points) < 2:
            raise ValueError(f"Motion: GPX for '{name}' has insufficient points")
        cum = tuple(cumulative_km(list(points)))

        ev_runners = runners_df[runners_df["event"].astype(str).str.lower() == name]
        csv_dist = None
        if not ev_runners.empty and "distance" in ev_runners.columns:
            csv_dist = float(pd.to_numeric(ev_runners["distance"], errors="coerce").median())

        out[name] = EventMotionContext(
            event=name,
            gun_sec=int(ev.start_time) * 60,
            finish_km=float(finish_km),
            csv_distance_km=csv_dist,
            spans=spans,
            points_latlon=points,
            cum_km=cum,
        )
    return out


def _runner_samples(
    *,
    runner_id: str,
    event: str,
    pace_min_per_km: float,
    start_offset_sec: float,
    ctx: EventMotionContext,
    interval_sec: int,
) -> List[Dict[str, Any]]:
    if pace_min_per_km <= 0:
        raise ValueError(f"Motion: non-positive pace for runner {runner_id}")
    pace_sec = float(pace_min_per_km) * 60.0
    runner_start = runner_start_sec(ctx.gun_sec, start_offset_sec)
    finish_t = arrival_at_km(
        gun_sec=ctx.gun_sec,
        start_offset_sec=start_offset_sec,
        pace_min_per_km=pace_min_per_km,
        km=ctx.finish_km,
    )

    rows: List[Dict[str, Any]] = []

    def add_row(t: float, kind: str) -> None:
        elapsed = max(0.0, (float(t) - runner_start) / pace_sec)
        if elapsed > ctx.finish_km:
            elapsed = ctx.finish_km
        seg_id, seg_km = locate_on_course(elapsed, ctx.spans, ctx.finish_km)
        lat, lon = _interp_lat_lon(ctx.points_latlon, ctx.cum_km, elapsed)
        rows.append(
            {
                "runner_id": str(runner_id),
                "event": event,
                "t": int(round(t)),
                "elapsed_km": float(elapsed),
                "seg_id": seg_id,
                "seg_km": float(seg_km),
                "lat": lat,
                "lon": lon,
                "sample_kind": kind,
                "time_source": MOTION_TIME_SOURCE,
                "position_source": MOTION_POSITION_SOURCE,
            }
        )

    # Exact boundaries first; ticks may collide and are merged by kind preference.
    add_row(runner_start, "start")
    add_row(finish_t, "finish")

    ticks = aligned_ticks(runner_start, finish_t, interval_sec)
    for t in ticks:
        # Skip exact start/finish ticks — boundary row wins.
        if abs(float(t) - runner_start) < 1e-9 or abs(float(t) - finish_t) < 1e-9:
            continue
        add_row(float(t), "tick")

    # Collapse to unique (runner_id, t): prefer start > finish > tick if collision.
    kind_rank = {"start": 0, "finish": 1, "tick": 2}
    by_t: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        t_key = int(row["t"])
        prev = by_t.get(t_key)
        if prev is None or kind_rank[row["sample_kind"]] < kind_rank[prev["sample_kind"]]:
            by_t[t_key] = row
    return [by_t[k] for k in sorted(by_t.keys())]


def build_motion_samples(
    *,
    runners_df: pd.DataFrame,
    day_events: Sequence[Event],
    segments_df: pd.DataFrame,
    gpx_paths: Mapping[str, str],
    interval_sec: int = MOTION_SAMPLE_INTERVAL_SEC,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Build the day motion sample table and diagnostics for metadata.

    Raises on empty inputs, mapping failures, or duplicate ``(runner_id, t)``.
    """
    if runners_df is None or runners_df.empty:
        raise ValueError("Motion: no runners for day")
    required = {"runner_id", "event", "pace", "start_offset"}
    missing = sorted(required - set(runners_df.columns))
    if missing:
        raise ValueError(f"Motion: runners missing columns {missing}")

    contexts = prepare_event_contexts(
        day_events=day_events,
        segments_df=segments_df,
        runners_df=runners_df,
        gpx_paths=gpx_paths,
    )

    distance_warnings: List[Dict[str, Any]] = []
    for name, ctx in contexts.items():
        if ctx.csv_distance_km is None:
            continue
        delta = abs(ctx.csv_distance_km - ctx.finish_km)
        if delta > 1e-6:
            distance_warnings.append(
                {
                    "event": name,
                    "csv_distance_km": ctx.csv_distance_km,
                    "compiled_course_km": ctx.finish_km,
                    "delta_km": delta,
                }
            )
            logger.warning(
                "Motion: event '%s' CSV distance %.3f km vs compiled %.3f km (Δ=%.3f); "
                "compiled course is authoritative",
                name,
                ctx.csv_distance_km,
                ctx.finish_km,
                delta,
            )

    all_rows: List[Dict[str, Any]] = []
    for _, runner in runners_df.iterrows():
        event = str(runner["event"]).strip().lower()
        ctx = contexts.get(event)
        if ctx is None:
            raise ValueError(f"Motion: runner event '{event}' not in day events")
        rid = str(runner["runner_id"])
        pace = float(runner["pace"])
        offset = float(runner["start_offset"] if pd.notna(runner["start_offset"]) else 0.0)
        all_rows.extend(
            _runner_samples(
                runner_id=rid,
                event=event,
                pace_min_per_km=pace,
                start_offset_sec=offset,
                ctx=ctx,
                interval_sec=interval_sec,
            )
        )

    if not all_rows:
        raise ValueError("Motion: produced zero samples")

    frame = pd.DataFrame(all_rows, columns=SAMPLE_COLUMNS)
    frame = frame.sort_values(["runner_id", "t", "sample_kind"], kind="mergesort").reset_index(
        drop=True
    )

    dup_mask = frame.duplicated(subset=["runner_id", "t"], keep=False)
    if bool(dup_mask.any()):
        sample = frame.loc[dup_mask, ["runner_id", "t", "sample_kind"]].head(10)
        raise ValueError(
            f"Motion: duplicate (runner_id, t) before write:\n{sample.to_string(index=False)}"
        )

    diagnostics = {
        "row_count": int(len(frame)),
        "event_counts": {
            str(k): int(v) for k, v in frame["event"].value_counts().sort_index().items()
        },
        "min_t": int(frame["t"].min()),
        "max_t": int(frame["t"].max()),
        "compiled_course_lengths_km": {
            name: ctx.finish_km for name, ctx in sorted(contexts.items())
        },
        "csv_distance_mismatches": distance_warnings,
        "sample_interval_sec": int(interval_sec),
        "schema_version": MOTION_SCHEMA_VERSION,
        "model_version": MOTION_MODEL_VERSION,
    }
    return frame, diagnostics


def build_motion_metadata(
    *,
    diagnostics: Mapping[str, Any],
    package_id: Optional[str],
    day: str,
    gun_by_event: Mapping[str, int],
    course_hash: Optional[str],
    runners_hash: Optional[str],
    guns_hash: Optional[str],
    generated_at_iso: str,
) -> Dict[str, Any]:
    return {
        "schema_version": diagnostics["schema_version"],
        "model_version": diagnostics["model_version"],
        "sample_interval_sec": diagnostics["sample_interval_sec"],
        "clock": {
            "basis": "seconds_from_local_midnight",
            "alignment": f"multiples_of_{diagnostics['sample_interval_sec']}_from_midnight",
        },
        "package_id": package_id,
        "day": day,
        "course_hash": course_hash,
        "runners_hash": runners_hash,
        "guns_hash": guns_hash,
        "gun_sec_by_event": {k: int(v) for k, v in sorted(gun_by_event.items())},
        "generated_at": generated_at_iso,
        "interpolation_method": "along_event_gpx_polyline_by_elapsed_km",
        "finish_rule": "compiled_course_length_from_segments_csv",
        "time_source": MOTION_TIME_SOURCE,
        "position_source": MOTION_POSITION_SOURCE,
        "row_count": diagnostics["row_count"],
        "event_counts": diagnostics["event_counts"],
        "min_t": diagnostics["min_t"],
        "max_t": diagnostics["max_t"],
        "compiled_course_lengths_km": diagnostics["compiled_course_lengths_km"],
        "csv_distance_mismatches": diagnostics["csv_distance_mismatches"],
    }


def hash_runners_inputs(paths: Iterable[Path]) -> str:
    payload = []
    for path in sorted(paths, key=lambda p: str(p)):
        payload.append(f"{path.name}:{_sha256_file(path)}")
    return _sha256_text("\n".join(payload))


def hash_guns(gun_by_event: Mapping[str, int]) -> str:
    blob = json.dumps({k: int(v) for k, v in sorted(gun_by_event.items())}, sort_keys=True)
    return _sha256_text(blob)


def hash_course_file(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.is_file():
        return None
    return _sha256_file(path)


def resolve_motion_package_id(
    *,
    analysis_config: Optional[Mapping[str, Any]] = None,
    data_dir: Optional[Path | str] = None,
) -> Optional[str]:
    """
    Resolve config package id for motion metadata provenance.

    ``analysis.json`` does not currently carry ``config_id``; prefer explicit
    fields when present, else ``config.json`` in the package dir, else the
    package directory basename (``runflow/config/{config_id}``).
    """
    if analysis_config:
        nested = analysis_config.get("package")
        nested_id = None
        if isinstance(nested, Mapping):
            nested_id = nested.get("config_id") or nested.get("package_id")
        candidate = (
            analysis_config.get("config_id")
            or analysis_config.get("package_id")
            or nested_id
        )
        if candidate:
            return str(candidate).strip() or None

    if not data_dir:
        return None
    path = Path(data_dir)
    manifest = path / "config.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Motion: could not read package config.json at %s: %s", manifest, exc)
        else:
            if isinstance(payload, Mapping):
                cid = payload.get("config_id") or payload.get("package_id")
                if cid:
                    return str(cid).strip() or None

    name = path.name.strip()
    return name or None
