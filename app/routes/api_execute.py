"""Execute clock API (Issue #830 v1)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.utils.auth import is_session_valid
from app.utils.env import env_bool
from app.utils.run_id import get_latest_run_id, get_run_directory, resolve_selected_day

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/execute/playbook")
async def get_execute_playbook(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    now: Optional[str] = Query(
        None,
        description="Optional HH:MM[:SS] preview clock; omit for client wall clock",
    ),
) -> JSONResponse:
    """Guns + clearance playbook for the race-day Execute view."""
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not run_id:
            run_id = get_latest_run_id()
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id.",
            )
        selected_day, available_days = resolve_selected_day(run_id, day)

        from app.core.clearance.playbook import playbook_for_run
        from app.core.execute.clock import build_execute_snapshot, parse_clock_sec
        from app.core.v2.analysis_config import load_analysis_json

        csv_path = get_run_directory(run_id) / selected_day / "reports" / "Locations.csv"
        playbook = playbook_for_run(
            run_id,
            day=selected_day,
            locations_csv=csv_path,
        )
        try:
            analysis = load_analysis_json(get_run_directory(run_id))
        except (OSError, FileNotFoundError, ValueError):
            analysis = {}
        snapshot = build_execute_snapshot(
            playbook=playbook,
            analysis=analysis,
            day=selected_day,
            now_sec=parse_clock_sec(now),
        )
        snapshot["available_days"] = available_days
        return JSONResponse(content=snapshot)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Execute playbook failed")
        raise HTTPException(status_code=500, detail=str(e))
