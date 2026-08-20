"""Build Progression setup (geometry + clock) and field (snapshot) payloads (#864).

The field is the whole modeled pack so later visualizations can reuse the same
boundary. Setup carries per-event course-active windows (#881) and a fixed
Mid-pack/P50 runner (#885). Lead/Last remain a client display cohort.
"""

from __future__ import annotations

import json
from math import floor
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.core.gpx.processor import cumulative_km, parse_gpx_file
from app.core.motion.course_map import compiled_course_length_km
from app.core.trajectory.crossing import arrival_at_km, runner_start_sec
from app.core.trajectory.layer import try_load_day_snapshot
from app.utils.constants import (
    DISPLAY_TIMEZONE,
    MOTION_DIRNAME,
    MOTION_METADATA_FILENAME,
    MOTION_MODEL_VERSION,
    MOTION_POSITION_SOURCE,
    MOTION_TIME_SOURCE,
    PROGRESSION_EVENT_COLORS,
    PROGRESSION_POLYLINE_MAX_POINTS,
)
from app.utils.run_id import get_runflow_root


PROGRESSION_MODEL_LABEL = "Modeled constant-pace from chip times — not GPS"


class ProgressionError(ValueError):
    """Caller sent or persisted data that cannot drive Progression (HTTP 400)."""

    status_code = 400


class ProgressionNotFound(FileNotFoundError):
    """Required run/day snapshot is missing (HTTP 404)."""

    status_code = 404


def _existing_path(path: Path) -> Path:
    """Return ``path`` if it exists, else remap ``/app/runflow`` → runtime root."""
    if path.exists():
        return path
    text = str(path)
    container = "/app/runflow"
    if text == container or text.startswith(container + "/"):
        mapped = get_runflow_root() / text[len(container) :].lstrip("/")
        if mapped.exists():
            return mapped
    return path


def _load_analysis(run_dir: Path) -> Dict[str, Any]:
    analysis_path = Path(run_dir) / "analysis.json"
    if not analysis_path.is_file():
        raise ProgressionNotFound(f"analysis.json not found at {analysis_path}")
    return json.loads(analysis_path.read_text(encoding="utf-8"))


def _load_motion_metadata(day_path: Path) -> Dict[str, Any]:
    meta_path = Path(day_path) / MOTION_DIRNAME / MOTION_METADATA_FILENAME
    if not meta_path.is_file():
        return {}
    raw = meta_path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _resolve_data_dir(analysis: Mapping[str, Any]) -> Path:
    raw = analysis.get("data_dir")
    if not raw:
        raise ProgressionError("analysis.json missing data_dir")
    path = _existing_path(Path(str(raw)))
    if not path.is_dir():
        raise ProgressionError(f"data_dir not found: {raw}")
    return path


def _gpx_path_for_event(analysis: Mapping[str, Any], event: str, data_dir: Path) -> Path:
    event_l = str(event).lower()
    gpx_map = (analysis.get("data_files") or {}).get("gpx") or {}
    raw = gpx_map.get(event_l) or gpx_map.get(event)
    if not raw:
        for ev in analysis.get("events") or []:
            if str(ev.get("name") or "").lower() == event_l:
                raw = ev.get("gpx_file")
                break
    if not raw:
        raise ProgressionError(f"GPX path missing for event '{event_l}'")
    candidate = Path(str(raw))
    if not candidate.is_absolute():
        candidate = data_dir / candidate
    path = _existing_path(candidate)
    if not path.is_file():
        raise ProgressionError(f"GPX file not found for event '{event_l}': {path}")
    return path


def _gun_sec_by_event(
    *,
    metadata: Mapping[str, Any],
    analysis: Mapping[str, Any],
    events: Sequence[str],
) -> Dict[str, int]:
    guns: Dict[str, int] = {}
    meta_guns = metadata.get("gun_sec_by_event") or {}
    if isinstance(meta_guns, Mapping):
        for key, val in meta_guns.items():
            guns[str(key).lower()] = int(val)
    start_times = analysis.get("start_times") or {}
    if isinstance(start_times, Mapping):
        for key, val in start_times.items():
            event = str(key).lower()
            if event not in guns:
                guns[event] = int(val) * 60
    if not guns:
        for ev in analysis.get("events") or []:
            name = str(ev.get("name") or "").lower()
            start = ev.get("start_time")
            if name and start is not None:
                guns[name] = int(start) * 60
    missing = [e for e in events if e not in guns]
    if missing:
        raise ProgressionError(f"Gun time missing for event(s): {', '.join(missing)}")
    return {e: guns[e] for e in events}


def _finish_km_by_event(
    *,
    metadata: Mapping[str, Any],
    analysis: Mapping[str, Any],
    data_dir: Path,
    events: Sequence[str],
) -> Dict[str, float]:
    finishes: Dict[str, float] = {}
    compiled = metadata.get("compiled_course_lengths_km") or {}
    if isinstance(compiled, Mapping):
        for key, val in compiled.items():
            finishes[str(key).lower()] = float(val)
    missing = [e for e in events if e not in finishes or finishes[e] <= 0]
    if not missing:
        return {e: finishes[e] for e in events}

    segments_raw = (analysis.get("data_files") or {}).get("segments")
    if not segments_raw:
        segments_raw = analysis.get("segments_file")
    if not segments_raw:
        raise ProgressionError(
            "Compiled course length missing and analysis.json has no segments path"
        )
    seg_path = Path(str(segments_raw))
    if not seg_path.is_absolute():
        seg_path = data_dir / seg_path
    seg_path = _existing_path(seg_path)
    if not seg_path.is_file():
        raise ProgressionError(f"segments.csv not found at {seg_path}")
    segments_df = pd.read_csv(seg_path)
    for event in missing:
        length = compiled_course_length_km(segments_df, event)
        if length <= 0:
            raise ProgressionError(f"Compiled course length is 0 for event '{event}'")
        finishes[event] = float(length)
    return {e: finishes[e] for e in events}


def event_color(event: str) -> str:
    key = str(event).lower()
    if key in PROGRESSION_EVENT_COLORS:
        return PROGRESSION_EVENT_COLORS[key]
    return "#34495e"


def downsample_polyline(
    points: Sequence[Tuple[float, float]],
    cum_km: Sequence[float],
    *,
    max_points: int = PROGRESSION_POLYLINE_MAX_POINTS,
    finish_km: Optional[float] = None,
) -> List[List[float]]:
    """Return ``[[lat, lon, km], ...]`` capped at ``max_points``, keeping endpoints."""
    if not points or not cum_km or len(points) != len(cum_km):
        raise ProgressionError("GPX polyline is empty or km array length mismatch")
    pairs = list(zip(points, cum_km))
    if finish_km is not None and finish_km > 0:
        kept: List[Tuple[Tuple[float, float], float]] = []
        for pt, km in pairs:
            kept.append((pt, float(km)))
            if float(km) >= float(finish_km):
                break
        if kept:
            pairs = kept
    n = len(pairs)
    cap = max(2, int(max_points))
    if n <= cap:
        idxs: Iterable[int] = range(n)
    else:
        # Inclusive endpoints; unique rounded linspace indices.
        raw = [round(i * (n - 1) / (cap - 1)) for i in range(cap)]
        idxs = sorted(set(int(i) for i in raw))
    out: List[List[float]] = []
    for i in idxs:
        (lat, lon), km = pairs[i]
        out.append([float(lat), float(lon), float(km)])
    return out


def _snapshot_rows(snapshot: pd.DataFrame) -> List[Dict[str, Any]]:
    required = {"runner_id", "event", "pace"}
    missing = required - set(snapshot.columns)
    if missing:
        raise ProgressionError(
            f"runners_snapshot.parquet missing columns: {', '.join(sorted(missing))}"
        )
    rows: List[Dict[str, Any]] = []
    for rec in snapshot.to_dict("records"):
        pace = float(rec["pace"])
        if pace <= 0:
            raise ProgressionError(f"Non-positive pace for runner {rec.get('runner_id')}")
        offset = rec.get("start_offset", 0)
        if offset is None or (isinstance(offset, float) and pd.isna(offset)):
            offset = 0
        rows.append(
            {
                "id": str(rec["runner_id"]),
                "event": str(rec["event"]).lower(),
                "start_offset_sec": float(offset),
                "pace_min_per_km": pace,
            }
        )
    if not rows:
        raise ProgressionError("runners_snapshot.parquet has no runners")
    return rows


def course_active_windows(
    runners: Sequence[Mapping[str, Any]],
    gun_sec_by_event: Mapping[str, int],
    finish_km_by_event: Mapping[str, float],
) -> Dict[str, Tuple[int, int]]:
    """Per-event modeled course-active window: first start → last finish.

    Operational, not Lead/Last: late chips extend the clear time. Used by the
    Progression wallboard (#881). Clock ``t0`` remains first gun.
    """
    windows: Dict[str, Tuple[int, int]] = {}
    for r in runners:
        event = r["event"]
        if event not in gun_sec_by_event or event not in finish_km_by_event:
            raise ProgressionError(
                f"Course-active window missing gun or finish km for event '{event}'"
            )
        gun = float(gun_sec_by_event[event])
        start = int(runner_start_sec(gun, r["start_offset_sec"]))
        end = int(
            arrival_at_km(
                gun_sec=gun,
                start_offset_sec=float(r["start_offset_sec"]),
                pace_min_per_km=float(r["pace_min_per_km"]),
                km=float(finish_km_by_event[event]),
            )
        )
        if event not in windows:
            windows[event] = (start, end)
        else:
            prev_start, prev_end = windows[event]
            windows[event] = (min(prev_start, start), max(prev_end, end))
    if not windows:
        raise ProgressionError("Cannot compute course-active windows: no runners")
    return windows


def _package_event_rank(
    analysis: Mapping[str, Any],
    events: Sequence[str],
) -> Dict[str, int]:
    """Tie-break rank from analysis/package event order (not distance vocabulary)."""
    ordered: List[str] = []
    seen: set = set()

    def _push(raw: Any) -> None:
        name = str(raw or "").lower().strip()
        if not name or name in seen:
            return
        seen.add(name)
        ordered.append(name)

    for ev in analysis.get("events") or []:
        if isinstance(ev, Mapping):
            _push(ev.get("name"))
        else:
            _push(ev)
    start_times = analysis.get("start_times") or {}
    if isinstance(start_times, Mapping):
        for key in start_times.keys():
            _push(key)
    for event in events:
        _push(event)
    return {name: i for i, name in enumerate(ordered)}


def order_progression_events(
    events: Sequence[str],
    windows: Mapping[str, Tuple[int, int]],
    analysis: Mapping[str, Any],
) -> List[str]:
    """Legend/wallboard order: earliest modeled start, then package event order."""
    present = [str(e).lower().strip() for e in events if str(e).strip()]
    unique: List[str] = []
    seen: set = set()
    for event in present:
        if event in seen:
            continue
        seen.add(event)
        unique.append(event)
    missing = [e for e in unique if e not in windows]
    if missing:
        raise ProgressionError(
            f"Course-active window missing for event(s): {', '.join(missing)}"
        )
    rank = _package_event_rank(analysis, unique)
    return sorted(
        unique,
        key=lambda event: (int(windows[event][0]), rank.get(event, 10**9)),
    )


def select_midpack(
    runners: Sequence[Mapping[str, Any]],
    *,
    gun_sec: float,
    finish_km: float,
) -> Dict[str, Any]:
    """Fixed P50 representative: all event runners, modeled finish order (#885).

    Index is ``floor(0.50 * (n - 1))``. Late chips stay in the sort; they do not
    use the Last main-wave cap. Tie-break is runner id.
    """
    if not runners:
        raise ProgressionError("Cannot select Mid-pack: no runners")
    ranked: List[Tuple[float, str, Mapping[str, Any]]] = []
    for r in runners:
        finish_t = arrival_at_km(
            gun_sec=float(gun_sec),
            start_offset_sec=float(r["start_offset_sec"]),
            pace_min_per_km=float(r["pace_min_per_km"]),
            km=float(finish_km),
        )
        ranked.append((float(finish_t), str(r["id"]), r))
    ranked.sort(key=lambda row: (row[0], row[1]))
    idx = int(floor(0.50 * (len(ranked) - 1)))
    idx = max(0, min(len(ranked) - 1, idx))
    finish_t, runner_id, chosen = ranked[idx]
    return {
        "id": runner_id,
        "finish_sec": int(finish_t),
        "start_sec": int(
            runner_start_sec(float(gun_sec), chosen["start_offset_sec"])
        ),
    }


def _clock_span(
    runners: Sequence[Mapping[str, Any]],
    gun_sec_by_event: Mapping[str, int],
    finish_km_by_event: Mapping[str, float],
) -> Tuple[int, int, Dict[str, Tuple[int, int]]]:
    windows = course_active_windows(runners, gun_sec_by_event, finish_km_by_event)
    t0 = min(int(gun_sec_by_event[r["event"]]) for r in runners)
    t1 = max(end for _start, end in windows.values())
    return int(t0), int(t1), windows


def _event_polyline(gpx_path: Path, finish_km: float) -> List[List[float]]:
    course = parse_gpx_file(str(gpx_path))
    points = [(p.lat, p.lon) for p in course.points]
    if len(points) < 2:
        raise ProgressionError(f"GPX has insufficient points: {gpx_path}")
    cum = cumulative_km(points)
    return downsample_polyline(points, cum, finish_km=finish_km)


def _load_day_inputs(run_dir: Path, day: str) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    day_l = str(day).lower().strip()
    day_path = run_dir / day_l
    snapshot = try_load_day_snapshot(day_path)
    if snapshot is None or snapshot.empty:
        raise ProgressionNotFound(
            f"Motion snapshot missing for day '{day_l}' "
            f"(expected {day_path / MOTION_DIRNAME})"
        )
    if "event" in snapshot.columns:
        snapshot = snapshot.copy()
        snapshot["event"] = snapshot["event"].astype(str).str.lower()
    analysis = _load_analysis(run_dir)
    metadata = _load_motion_metadata(day_path)
    runners = _snapshot_rows(snapshot)
    events = list(dict.fromkeys(r["event"] for r in runners))
    data_dir = _resolve_data_dir(analysis)
    guns = _gun_sec_by_event(metadata=metadata, analysis=analysis, events=events)
    finishes = _finish_km_by_event(
        metadata=metadata, analysis=analysis, data_dir=data_dir, events=events
    )
    return {
        "run_dir": run_dir,
        "day": day_l,
        "analysis": analysis,
        "metadata": metadata,
        "data_dir": data_dir,
        "runners": runners,
        "events": events,
        "guns": guns,
        "finishes": finishes,
    }


def build_progression_setup(run_dir: Path, day: str) -> Dict[str, Any]:
    """Geometry, guns, and clock span for the Plan Progression map."""
    ctx = _load_day_inputs(run_dir, day)
    t0, t1, windows = _clock_span(ctx["runners"], ctx["guns"], ctx["finishes"])
    metadata = ctx["metadata"]
    events = order_progression_events(ctx["events"], windows, ctx["analysis"])
    events_out: List[Dict[str, Any]] = []
    for event in events:
        gpx_path = _gpx_path_for_event(ctx["analysis"], event, ctx["data_dir"])
        finish_km = float(ctx["finishes"][event])
        active_start, active_end = windows[event]
        event_runners = [r for r in ctx["runners"] if r["event"] == event]
        midpack = select_midpack(
            event_runners,
            gun_sec=float(ctx["guns"][event]),
            finish_km=finish_km,
        )
        events_out.append(
            {
                "id": event,
                "gun_sec": int(ctx["guns"][event]),
                "finish_km": finish_km,
                "active_start_sec": int(active_start),
                "active_end_sec": int(active_end),
                "midpack_id": midpack["id"],
                "midpack_finish_sec": int(midpack["finish_sec"]),
                "color": event_color(event),
                "polyline": _event_polyline(gpx_path, finish_km),
            }
        )
    return {
        "ok": True,
        "day": ctx["day"],
        "t0_sec": t0,
        "t1_sec": t1,
        "timezone": DISPLAY_TIMEZONE,
        "model": {
            "label": PROGRESSION_MODEL_LABEL,
            "time_source": metadata.get("time_source") or MOTION_TIME_SOURCE,
            "position_source": metadata.get("position_source") or MOTION_POSITION_SOURCE,
            "model_version": metadata.get("model_version") or MOTION_MODEL_VERSION,
            "interpolation_method": metadata.get("interpolation_method")
            or "along_event_gpx_polyline_by_elapsed_km",
        },
        "events": events_out,
    }


def build_progression_field(run_dir: Path, day: str) -> Dict[str, Any]:
    """Whole-field snapshot rows. UI paints Lead / Mid-pack / Last from this pack."""
    ctx = _load_day_inputs(run_dir, day)
    return {
        "ok": True,
        "day": ctx["day"],
        "runners": ctx["runners"],
    }
