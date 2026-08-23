"""
Execute race-day board API (Issue #893).

UI → API → JSON: Plan locations from locations_report.json;
operator actions in {day}/execution/state.json via write_json.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.execute.board import assemble_board
from app.core.execute.report import (
    build_reopen_rows,
    csv_columns,
    reopen_csv_text,
)
from app.core.execute.state import (
    apply_clock_update,
    load_or_create_state,
    persist_state,
    record_reopen,
)
from app.core.execute.times import wall_hhmm, wall_hhmmss
from app.core.locations.report_json import (
    locations_report_relpath,
    parse_optional_id,
)
from app.storage import create_runflow_storage
from app.utils.auth import is_session_valid
from app.utils.env import env_bool
from app.utils.run_id import get_run_directory, resolve_selected_day

logger = logging.getLogger(__name__)
router = APIRouter()


class ClockUpdateBody(BaseModel):
    guns: Optional[Dict[str, str]] = None
    guns_accepted: Optional[bool] = None
    paused: Optional[bool] = None
    jump_to_now: bool = False


class ReopenBody(BaseModel):
    loc_id: int
    linked_loc_ids: List[int] = Field(default_factory=list)


def _require_run_id(run_id: Optional[str]) -> str:
    if not run_id or not str(run_id).strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "run_id is required. "
                "Select a Plan analysis before Execute."
            ),
        )
    return str(run_id).strip()


def _guard_session(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _read_analysis(run_id: str) -> Dict[str, Any]:
    path = get_run_directory(run_id) / "analysis.json"
    if not path.exists():
        return {}
    try:
        from app.config.loader import load_analysis_config_readonly

        return dict(load_analysis_config_readonly(get_run_directory(run_id)))
    except Exception as exc:
        logger.warning("Execute could not read analysis.json: %s", exc)
        return {}


def _load_locations(storage: Any, day: str) -> Dict[str, Any]:
    report_path = locations_report_relpath(day)
    if not storage.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Locations report JSON not found for day={day}. "
                "Re-run analysis to write computation/locations_report.json."
            ),
        )
    payload = storage.read_json(report_path)
    locations = payload.get("locations") or []
    if not isinstance(locations, list):
        raise HTTPException(
            status_code=500,
            detail=(
                "locations_report.json is invalid: "
                "'locations' must be an array."
            ),
        )
    return payload


def _board_payload(run_id: str, day: str) -> Dict[str, Any]:
    storage = create_runflow_storage(run_id)
    report = _load_locations(storage, day)
    analysis = _read_analysis(run_id)
    state = load_or_create_state(
        storage, run_id=run_id, day=day, analysis=analysis
    )
    return assemble_board(
        locations=report.get("locations") or [],
        state=state,
        resources_available=report.get("resources_available") or [],
        run_id=run_id,
        day=day,
    )


@router.get("/api/execute/board")
async def get_execute_board(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    try:
        selected_day, available_days = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = _board_payload(rid, selected_day)
    payload["available_days"] = available_days
    return JSONResponse(content=payload)


def _safe_export_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned or "unknown"


@router.get("/api/execute/reopen.csv")
async def get_execute_reopen_csv(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> StreamingResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    try:
        selected_day, _available = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage = create_runflow_storage(rid)
    report = _load_locations(storage, selected_day)
    analysis = _read_analysis(rid)
    state = load_or_create_state(
        storage, run_id=rid, day=selected_day, analysis=analysis
    )
    locations = report.get("locations") or []
    available = report.get("resources_available") or []
    rows = build_reopen_rows(
        locations,
        state,
        resources_available=available,
    )
    fieldnames = csv_columns(locations, available)
    filename = (
        "execute_reopen_"
        + _safe_export_token(rid)
        + "_"
        + _safe_export_token(selected_day)
        + ".csv"
    )
    return StreamingResponse(
        io.BytesIO(reopen_csv_text(rows, fieldnames).encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.get("/api/execute/state")
async def get_execute_state(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    try:
        selected_day, _available = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage = create_runflow_storage(rid)
    analysis = _read_analysis(rid)
    state = load_or_create_state(
        storage, run_id=rid, day=selected_day, analysis=analysis
    )
    return JSONResponse(content={"ok": True, "state": state})


@router.put("/api/execute/clock")
async def put_execute_clock(
    request: Request,
    body: ClockUpdateBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    try:
        selected_day, _available = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage = create_runflow_storage(rid)
    analysis = _read_analysis(rid)
    state = load_or_create_state(
        storage, run_id=rid, day=selected_day, analysis=analysis
    )
    apply_clock_update(
        state,
        body.model_dump(exclude_none=True),
        now_hhmmss=wall_hhmmss(),
    )
    persist_state(storage, selected_day, state)
    payload = _board_payload(rid, selected_day)
    payload["state"] = state
    return JSONResponse(content=payload)


@router.post("/api/execute/reopen")
async def post_execute_reopen(
    request: Request,
    body: ReopenBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    loc_id = parse_optional_id(body.loc_id)
    if loc_id is None:
        raise HTTPException(status_code=400, detail="loc_id is required.")
    try:
        selected_day, _available = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage = create_runflow_storage(rid)
    report = _load_locations(storage, selected_day)
    known = {
        parse_optional_id(row.get("loc_id"))
        for row in (report.get("locations") or [])
        if isinstance(row, dict)
    }
    if loc_id not in known:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown loc_id {loc_id}.",
        )
    analysis = _read_analysis(rid)
    state = load_or_create_state(
        storage, run_id=rid, day=selected_day, analysis=analysis
    )
    if str(loc_id) in (state.get("reopened") or {}):
        raise HTTPException(
            status_code=409,
            detail=f"Location {loc_id} is already reopened.",
        )
    allowed_linked = {
        parse_optional_id(row.get("loc_id"))
        for row in (report.get("locations") or [])
        if isinstance(row, dict)
        and parse_optional_id(row.get("proxy_loc_id")) == loc_id
    }
    linked = []
    for raw in body.linked_loc_ids:
        lid = parse_optional_id(raw)
        if lid is None or lid == loc_id:
            continue
        if lid not in allowed_linked:
            raise HTTPException(
                status_code=400,
                detail=f"Location {lid} is not proxied to {loc_id}.",
            )
        if str(lid) in (state.get("reopened") or {}):
            continue
        linked.append(lid)
    record_reopen(
        state,
        loc_id=loc_id,
        linked_loc_ids=linked,
        at_hhmm=wall_hhmm(),
    )
    persist_state(storage, selected_day, state)
    payload = _board_payload(rid, selected_day)
    payload["state"] = state
    return JSONResponse(content=payload)
