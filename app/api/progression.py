"""Plan Progression API: setup + field for the spatial race clock (#864)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.progression.payload import (
    ProgressionError,
    ProgressionNotFound,
    build_progression_field,
    build_progression_setup,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_day(run_id: Optional[str], day: Optional[str]):
    from app.utils.run_id import get_latest_run_id, get_run_directory, resolve_selected_day

    if not run_id:
        run_id = get_latest_run_id()
    selected_day, available_days = resolve_selected_day(run_id, day)
    run_dir = get_run_directory(run_id)
    if not run_dir.is_dir():
        raise ProgressionNotFound(f"Run not found: {run_id}")
    return run_id, selected_day, available_days, run_dir


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProgressionNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ProgressionError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Progression API failed")
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/api/runs/{run_id}/progression/setup")
async def get_progression_setup(
    run_id: str,
    day: Optional[str] = Query(None),
):
    """Event polylines, guns, clock span, course-active windows, and Mid-pack P50."""
    try:
        resolved_id, selected_day, available_days, run_dir = _run_day(run_id, day)
        payload = build_progression_setup(run_dir, selected_day)
        payload["run_id"] = resolved_id
        payload["available_days"] = available_days
        return JSONResponse(payload)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/runs/{run_id}/progression/field")
async def get_progression_field(
    run_id: str,
    day: Optional[str] = Query(None),
):
    """Whole-field snapshot rows. UI paints Lead / Mid-pack / Last from this pack."""
    try:
        resolved_id, selected_day, available_days, run_dir = _run_day(run_id, day)
        payload = build_progression_field(run_dir, selected_day)
        payload["run_id"] = resolved_id
        payload["available_days"] = available_days
        return JSONResponse(payload)
    except Exception as exc:
        raise _http_error(exc) from exc
