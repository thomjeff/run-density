"""Motion / time-at-place API (#850 Child B / #854)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.motion.occupancy import (
    PlaceSpec,
    PlaceStream,
    build_location_pins_from_passes,
    build_location_places_from_passes,
    build_places_from_passes,
    pin_place_from_location,
    place_spec_from_location,
    query_occupancy,
    query_planar_occupancy,
)
from app.core.motion.stream_passage import build_stream_passage_table
from app.core.motion.movement_drilldown import load_authored_movements
from app.utils.constants import (
    MOTION_DEFAULT_PLACE_BUFFER_M,
    MOTION_DIRNAME,
    MOTION_METADATA_FILENAME,
    MOTION_SAMPLES_FILENAME,
    MOTION_STREAM_WINDOW_SEC,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _motion_rel(day: str, name: str) -> str:
    return f"{day}/{MOTION_DIRNAME}/{name}"


def _load_motion_samples(storage, day: str) -> pd.DataFrame:
    path = _motion_rel(day, MOTION_SAMPLES_FILENAME)
    frame = storage.read_parquet(path)
    if frame is None or frame.empty:
        raise FileNotFoundError(f"Motion samples missing at {path}")
    return frame


def _load_motion_metadata(storage, day: str) -> Dict[str, Any]:
    path = _motion_rel(day, MOTION_METADATA_FILENAME)
    try:
        raw = storage.read_text(path)
    except FileNotFoundError:
        return {}
    if not raw:
        return {}
    return json.loads(raw)


def _analysis_data_dir(run_id: str) -> Optional[Path]:
    from app.utils.run_id import get_run_directory

    analysis_path = get_run_directory(run_id) / "analysis.json"
    if not analysis_path.is_file():
        return None
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    data_dir = payload.get("data_dir")
    if not data_dir:
        return None
    return Path(str(data_dir))


def _parse_events(events: Optional[str]) -> Optional[List[str]]:
    if not events:
        return None
    parts = [p.strip() for p in events.split(",") if p.strip()]
    return parts or None


def _load_package_runners(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load event runners CSVs for pace quintiles (optional)."""
    frames: List[pd.DataFrame] = []
    for path in sorted(data_dir.glob("*_runners.csv")):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        if "event" not in frame.columns:
            # Infer from filename: 10k_runners.csv → 10k
            stem = path.stem.replace("_runners", "")
            frame = frame.copy()
            frame["event"] = stem.lower()
        frames.append(frame)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _parse_metrics(metrics: Optional[str]) -> List[str]:
    if not metrics:
        return ["instantaneous", "window_uniques", "throughput"]
    return [m.strip().lower() for m in metrics.split(",") if m.strip()]


@router.get("/api/motion/metadata")
async def get_motion_metadata(
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
):
    """Return motion metadata.json for a run/day."""
    try:
        from app.storage import create_runflow_storage
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        meta = _load_motion_metadata(storage, selected_day)
        ok = bool(meta)
        return JSONResponse(
            {
                "ok": ok,
                "run_id": run_id,
                "selected_day": selected_day,
                "available_days": available_days,
                "metadata": meta,
                "notes": []
                if ok
                else ["Motion metadata not found for this run/day."],
            }
        )
    except Exception as exc:
        logger.exception("get_motion_metadata failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )


@router.get("/api/motion/places")
async def get_motion_places(
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    buffer_m: float = Query(MOTION_DEFAULT_PLACE_BUFFER_M),
    mode: str = Query(
        "planar",
        description="planar (default GPS pins) or course (stream-projected)",
    ),
):
    """
    Location catalog for motion queries.

    Default ``planar`` lists loc_id pins from passes.csv (fast, lat/lon only).
    """
    try:
        from app.storage import create_runflow_storage
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        mode_l = (mode or "planar").strip().lower()

        data_dir = _analysis_data_dir(run_id)
        if data_dir is None:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": "analysis.json data_dir not found",
                    "places": [],
                },
            )
        passes_path = data_dir / "passes.csv"
        if not passes_path.is_file():
            return JSONResponse(
                {
                    "ok": True,
                    "run_id": run_id,
                    "selected_day": selected_day,
                    "available_days": available_days,
                    "places": [],
                    "mode": mode_l,
                    "notes": ["passes.csv not found in package"],
                }
            )
        passes_df = pd.read_csv(passes_path)

        if mode_l == "course":
            storage = create_runflow_storage(run_id)
            samples = _load_motion_samples(storage, selected_day)
            places = build_location_places_from_passes(
                passes_df,
                samples,
                default_buffer_m=float(buffer_m),
            )
        else:
            places = build_location_pins_from_passes(
                passes_df,
                default_radius_m=float(buffer_m),
            )

        return JSONResponse(
            {
                "ok": True,
                "run_id": run_id,
                "selected_day": selected_day,
                "available_days": available_days,
                "places": places,
                "default_buffer_m": float(buffer_m),
                "place_key": "loc_id",
                "mode": mode_l if mode_l in {"planar", "course"} else "planar",
            }
        )
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": str(exc), "places": []},
        )
    except Exception as exc:
        logger.exception("get_motion_places failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc), "places": []},
        )


@router.get("/api/motion/occupancy")
async def get_motion_occupancy(
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    metrics: Optional[str] = Query(
        None,
        description="Comma list: instantaneous,window_uniques,throughput",
    ),
    t: Optional[int] = Query(None, description="Clock seconds from midnight"),
    t0: Optional[int] = Query(None),
    t1: Optional[int] = Query(None),
    events: Optional[str] = Query(None, description="Comma event filter"),
    loc_id: Optional[str] = Query(
        None, description="Package location id (preferred user-facing key)"
    ),
    pass_id: Optional[str] = Query(
        None, description="Advanced: single pass/stream only"
    ),
    seg_id: Optional[str] = Query(None),
    center_seg_km: Optional[float] = Query(None),
    buffer_m: float = Query(MOTION_DEFAULT_PLACE_BUFFER_M),
    mode: str = Query(
        "planar",
        description="planar (GPS disk, default) or course (along-path streams)",
    ),
    include_runner_ids: bool = Query(False),
    include_passage_rows: bool = Query(False),
):
    """
    Query instantaneous / window-uniques / throughput for a place.

    Default ``mode=planar`` uses loc_id lat/lon ± radius (enter/exit of disk).
    ``mode=course`` keeps along-path stream occupancy (advanced).
    """
    try:
        from app.storage import create_runflow_storage
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        samples = _load_motion_samples(storage, selected_day)
        meta = _load_motion_metadata(storage, selected_day)
        mode_l = (mode or "planar").strip().lower()
        if mode_l not in {"planar", "course"}:
            mode_l = "planar"

        if loc_id and mode_l == "planar":
            data_dir = _analysis_data_dir(run_id)
            if data_dir is None or not (data_dir / "passes.csv").is_file():
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "error": "passes.csv not found"},
                )
            pins = build_location_pins_from_passes(
                pd.read_csv(data_dir / "passes.csv"),
                default_radius_m=float(buffer_m),
            )
            match = next(
                (p for p in pins if str(p["loc_id"]) == str(loc_id)),
                None,
            )
            if match is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "error": f"loc_id {loc_id} not found",
                    },
                )
            pin = pin_place_from_location(match, radius_m=float(buffer_m))
            payload = query_planar_occupancy(
                samples,
                pin,
                metrics=_parse_metrics(metrics),
                t=t,
                t0=t0,
                t1=t1,
                events=_parse_events(events),
                include_runner_ids=include_runner_ids,
                include_passage_rows=include_passage_rows,
            )
        else:
            place: Optional[PlaceSpec] = None
            if loc_id:
                data_dir = _analysis_data_dir(run_id)
                if data_dir is None or not (data_dir / "passes.csv").is_file():
                    return JSONResponse(
                        status_code=404,
                        content={"ok": False, "error": "passes.csv not found"},
                    )
                locations = build_location_places_from_passes(
                    pd.read_csv(data_dir / "passes.csv"),
                    samples,
                    default_buffer_m=float(buffer_m),
                )
                match = next(
                    (p for p in locations if str(p["loc_id"]) == str(loc_id)),
                    None,
                )
                if match is None:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "ok": False,
                            "error": (
                                f"loc_id {loc_id} not found or unmappable"
                            ),
                        },
                    )
                place = place_spec_from_location(
                    match, buffer_m=float(buffer_m)
                )
            elif pass_id:
                data_dir = _analysis_data_dir(run_id)
                if data_dir is None or not (data_dir / "passes.csv").is_file():
                    return JSONResponse(
                        status_code=404,
                        content={"ok": False, "error": "passes.csv not found"},
                    )
                places = build_places_from_passes(
                    pd.read_csv(data_dir / "passes.csv"),
                    samples,
                    default_buffer_m=float(buffer_m),
                )
                match = next(
                    (p for p in places if str(p["pass_id"]) == str(pass_id)),
                    None,
                )
                if match is None:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "ok": False,
                            "error": (
                                f"pass_id {pass_id} not found or unmappable"
                            ),
                        },
                    )
                place = PlaceSpec(
                    streams=(
                        PlaceStream(
                            seg_id=str(match["seg_id"]),
                            center_seg_km=float(match["center_seg_km"]),
                        ),
                    ),
                    buffer_m=float(buffer_m),
                    label=match.get("label"),
                    place_id=str(match.get("loc_id") or match["pass_id"]),
                )
            elif seg_id is not None and center_seg_km is not None:
                place = PlaceSpec(
                    streams=(
                        PlaceStream(
                            seg_id=str(seg_id),
                            center_seg_km=float(center_seg_km),
                        ),
                    ),
                    buffer_m=float(buffer_m),
                    place_id=f"{seg_id}@{center_seg_km}",
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "ok": False,
                        "error": (
                            "Provide loc_id (preferred), pass_id, "
                            "or seg_id + center_seg_km"
                        ),
                    },
                )

            payload = query_occupancy(
                samples,
                place,
                metrics=_parse_metrics(metrics),
                t=t,
                t0=t0,
                t1=t1,
                events=_parse_events(events),
                include_runner_ids=include_runner_ids,
                include_passage_rows=include_passage_rows,
            )

        return JSONResponse(
            {
                "ok": True,
                "run_id": run_id,
                "selected_day": selected_day,
                "available_days": available_days,
                "sample_interval_sec": meta.get("sample_interval_sec"),
                "clock": meta.get("clock"),
                **payload,
            }
        )
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": str(exc)},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )
    except Exception as exc:
        logger.exception("get_motion_occupancy failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )


@router.get("/api/motion/stream-passage")
async def get_motion_stream_passage(
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    loc_id: str = Query(..., description="Package location id"),
    buffer_m: float = Query(MOTION_DEFAULT_PLACE_BUFFER_M),
    window_sec: int = Query(MOTION_STREAM_WINDOW_SEC),
    t0: Optional[int] = Query(None, description="Optional span start (sec)"),
    t1: Optional[int] = Query(None, description="Optional span end exclusive"),
    events: Optional[str] = Query(None, description="Comma event filter"),
):
    """
    Time-windowed pin enter/exit table (Motion Stream Passage, #855 / #856).

    Midnight-aligned bins; visit-cluster context; movement drill-down with
    same-window concurrent stream volumes (not Junctions).
    """
    try:
        from app.storage import create_runflow_storage
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        samples = _load_motion_samples(storage, selected_day)
        meta = _load_motion_metadata(storage, selected_day)

        data_dir = _analysis_data_dir(run_id)
        if data_dir is None or not (data_dir / "passes.csv").is_file():
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "passes.csv not found"},
            )
        pins = build_location_pins_from_passes(
            pd.read_csv(data_dir / "passes.csv"),
            default_radius_m=float(buffer_m),
        )
        match = next(
            (p for p in pins if str(p["loc_id"]) == str(loc_id)),
            None,
        )
        if match is None:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": f"loc_id {loc_id} not found"},
            )
        pin = pin_place_from_location(match, radius_m=float(buffer_m))
        payload = build_stream_passage_table(
            samples,
            pin,
            window_sec=int(window_sec),
            t0=t0,
            t1=t1,
            events=_parse_events(events),
            runners_df=_load_package_runners(data_dir),
            authored_movements=load_authored_movements(data_dir, loc_id),
        )
        return JSONResponse(
            {
                "ok": True,
                "run_id": run_id,
                "selected_day": selected_day,
                "available_days": available_days,
                "sample_interval_sec": meta.get("sample_interval_sec"),
                "clock": meta.get("clock"),
                **payload,
            }
        )
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": str(exc)},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )
    except Exception as exc:
        logger.exception("get_motion_stream_passage failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )
