"""Publish, import, Plans, and Operations APIs (Issues #917 / #920)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    active_day_context,
    active_plan_id,
    archive_published_plan,
    deactivate_published_plan,
    import_published_plan,
    listed_plans,
    map_snapshot,
    operations_board,
    operations_reopen_csv,
    record_operations_reopen,
    restore_published_plan,
    update_operations_clock,
)
from app.utils.auth import is_session_valid, require_auth
from app.utils.carto_basemaps import register_jinja_map_tiles
from app.utils.env import env_bool

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")
register_jinja_map_tiles(templates)


class ActivateBody(BaseModel):
    plan_id: str = Field(..., min_length=36)


class ReopenBody(BaseModel):
    loc_id: int
    linked_loc_ids: List[int] = Field(default_factory=list)


class ClockBody(BaseModel):
    guns: Optional[dict] = None
    guns_accepted: Optional[bool] = None
    paused: Optional[bool] = None
    jump_to_now: bool = False


def _guard(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _fail(exc: PublishedPlanError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/api/execute/plans/import")
async def import_plan(
    request: Request,
    package: UploadFile = File(...),  # noqa: B008
):
    _guard(request)
    raw = await package.read()
    try:
        result = import_published_plan(raw)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    result["activated"] = False
    return result


@router.post("/api/execute/plans/activate")
async def activate_plan(request: Request, body: ActivateBody):
    _guard(request)
    try:
        loaded = activate_published_plan(body.plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {
        "ok": True,
        "plan_id": loaded["manifest"]["plan_id"],
        "calendar_date": loaded["manifest"]["calendar_date"],
        "active": True,
    }


@router.post("/api/execute/plans/deactivate")
async def deactivate_plan(request: Request):
    _guard(request)
    deactivate_published_plan()
    return {"ok": True, "active": False}


@router.post("/api/execute/plans/archive")
async def archive_plan(request: Request, body: ActivateBody):
    _guard(request)
    try:
        row = archive_published_plan(body.plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {"ok": True, "plan": row}


@router.post("/api/execute/plans/restore")
async def restore_plan(request: Request, body: ActivateBody):
    _guard(request)
    try:
        row = restore_published_plan(body.plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {"ok": True, "plan": row}


@router.get("/api/execute/plans")
async def list_plans(request: Request):
    _guard(request)
    listing = listed_plans()
    return {
        "ok": True,
        "active_plan_id": listing["active_plan_id"],
        "plans": listing["plans"],
    }


@router.get("/api/execute/active-context")
async def get_active_context(request: Request):
    _guard(request)
    return active_day_context()


@router.get("/api/execute/ops/board")
async def get_ops_board(request: Request):
    _guard(request)
    return operations_board()


@router.post("/api/execute/ops/reopen")
async def post_ops_reopen(request: Request, body: ReopenBody):
    _guard(request)
    try:
        return record_operations_reopen(
            body.loc_id,
            body.linked_loc_ids,
        )
    except PublishedPlanError as exc:
        raise _fail(exc) from exc


@router.put("/api/execute/ops/clock")
async def put_ops_clock(request: Request, body: ClockBody):
    _guard(request)
    try:
        return update_operations_clock(body.model_dump())
    except PublishedPlanError as exc:
        raise _fail(exc) from exc


@router.get("/api/execute/ops/reopen.csv")
async def get_ops_reopen_csv(request: Request):
    _guard(request)
    try:
        text, filename = operations_reopen_csv()
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    disposition = 'attachment; filename="' + filename + '"'
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.get("/api/execute/map")
async def get_operations_map(
    request: Request,
    plan_id: Optional[str] = Query(None),  # noqa: B008
):
    _guard(request)
    plan_id = plan_id or active_plan_id()
    try:
        return map_snapshot(plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc


@router.get("/execute/plans", response_class=HTMLResponse)
async def execute_plans_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return templates.TemplateResponse(
        request=request,
        name="pages/execute_plans.html",
        context={
            "request": request,
            "meta": {
                "run_timestamp": "pending",
                "environment": "execute",
                "run_hash": "dev",
            },
        },
    )


@router.get("/execute/map")
async def execute_map_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/execute", status_code=303)
