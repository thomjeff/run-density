"""Publish, import, and Operations Map APIs (Issue #917)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    active_published_plan_id,
    import_published_plan,
    load_registry,
    map_snapshot,
)
from app.core.plan.publish_day_plan import publish_day_plan_zip
from app.routes.ui import get_stub_meta, templates
from app.utils.auth import is_session_valid, require_auth
from app.utils.env import env_bool

router = APIRouter()


class PublishBody(BaseModel):
    run_id: str
    day: str
    calendar_date: str
    name: Optional[str] = None
    event_series: Optional[str] = None
    event_edition: Optional[str] = None


class ActivateBody(BaseModel):
    published_plan_id: str = Field(..., min_length=36)


def _guard(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _fail(exc: PublishedPlanError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/api/plan/published-plans")
async def publish_plan(request: Request, body: PublishBody):
    _guard(request)
    try:
        archive = publish_day_plan_zip(
            run_id=body.run_id.strip(),
            day=body.day.strip().lower(),
            calendar_date=body.calendar_date.strip(),
            name=body.name,
            event_series=body.event_series,
            event_edition=body.event_edition,
        )
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    filename = f"day-plan-{body.calendar_date}.zip"
    disposition = f'attachment; filename="{filename}"'
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


@router.post("/api/execute/published-plans/import")
async def import_plan(
    request: Request,
    package: UploadFile = File(...),
):
    _guard(request)
    raw = await package.read()
    try:
        result = import_published_plan(raw)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    result["activated"] = False
    return result


@router.post("/api/execute/published-plans/activate")
async def activate_plan(request: Request, body: ActivateBody):
    _guard(request)
    try:
        loaded = activate_published_plan(body.published_plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {
        "ok": True,
        "published_plan_id": loaded["manifest"]["published_plan_id"],
        "calendar_date": loaded["manifest"]["calendar_date"],
        "active": True,
    }


@router.get("/api/execute/published-plans")
async def list_plans(request: Request):
    _guard(request)
    registry = load_registry()
    return {
        "ok": True,
        "active_published_plan_id": registry.get("active_published_plan_id"),
        "plans": list((registry.get("plans") or {}).values()),
    }


@router.get("/execute/map", response_class=HTMLResponse)
async def execute_map_page(request: Request):
    """Execute Operations Map page (Issue #917)."""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        request=request,
        name="pages/execute_map.html",
        context={"request": request, "meta": meta},
    )


@router.get("/api/execute/map")
async def get_operations_map(
    request: Request,
    published_plan_id: Optional[str] = Query(None),
):
    _guard(request)
    plan_id = published_plan_id or active_published_plan_id()
    try:
        return map_snapshot(plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
