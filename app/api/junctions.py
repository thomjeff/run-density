"""
API routes for Junction Flow results (Issue #818).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/junctions")
async def get_junctions(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)"),
):
    """
    Load Junction Flow UI metrics for a run/day.

    SSOT: ``{day}/ui/metrics/junctions.json`` (written in Phase 6.4).
    """
    try:
        from app.storage import create_runflow_storage
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)

        try:
            raw = storage.read_text(f"{selected_day}/ui/metrics/junctions.json")
            if not raw:
                payload: Dict[str, Any] = {"ok": True, "method": {}, "junctions": []}
            else:
                payload = json.loads(raw)
        except FileNotFoundError:
            logger.warning(
                "junctions.json UI metrics missing for run=%s day=%s",
                run_id,
                selected_day,
            )
            payload = {
                "ok": True,
                "method": {},
                "junctions": [],
                "notes": ["Junction Flow artifact not found for this run/day."],
            }
        except Exception as e:
            logger.error("Failed to load junctions UI metrics: %s", e)
            payload = {"ok": False, "method": {}, "junctions": [], "error": str(e)}

        return JSONResponse(
            content={
                "selected_day": selected_day,
                "available_days": available_days,
                "run_id": run_id,
                **payload,
            }
        )
    except Exception as e:
        logger.exception("get_junctions failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "junctions": []},
        )
