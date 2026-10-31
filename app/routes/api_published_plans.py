"""Publish, import, Plans, and Operations APIs (Issues #917 / #920)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.core.execute.assignments import (
    AssignmentError,
    assignment_roster,
    delete_assignment,
    upsert_assignment,
)
from app.core.execute.attention import (
    AttentionError,
    acknowledge_sos,
    clear_sos_attention,
    list_audit,
    record_audit,
)
from app.core.execute.operator import (
    OperatorError,
    operator_from_request,
    require_operator,
    set_operator_cookie,
)
from app.core.execute.participants import DuplicateBibError
from app.core.execute.plan_participants import (
    decode_roster,
    import_plan_participants,
    parse_roster,
    participant_count,
)
from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    active_day_context,
    active_plan_id,
    archive_published_plan,
    deactivate_published_plan,
    import_published_plan,
    list_plan_loc_sheets,
    listed_plans,
    map_snapshot,
    operations_board,
    operations_reopen_csv,
    preview_published_plan,
    record_operations_close,
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


class CloseBody(BaseModel):
    loc_id: int


class ClockBody(BaseModel):
    guns: Optional[dict] = None
    guns_accepted: Optional[bool] = None
    paused: Optional[bool] = None
    jump_to_now: bool = False


class AssignmentBody(BaseModel):
    device_id: str = Field(..., min_length=1)
    resource_name: str = Field(..., min_length=1)
    person_name: str = ""
    phone: str = ""
    agency: str = ""


class OperatorBody(BaseModel):
    operator: str = Field(..., min_length=1)


class SosBody(BaseModel):
    device_id: str = Field(..., min_length=1)


def _guard(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _fail(exc: PublishedPlanError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _actor_fail(exc: Exception) -> HTTPException:
    status = getattr(exc, "status_code", 400)
    return HTTPException(status_code=status, detail=str(exc))


NO_PARTICIPANTS_DETAIL = "Load a participant list before activating this Day Plan."


def _participant_count(plan_id: str) -> int:
    try:
        return participant_count(plan_id)
    except (PublishedPlanError, OSError, ValueError):
        return 0


async def _read_roster(upload: Optional[UploadFile]) -> Optional[str]:
    if upload is None:
        return None
    raw = await upload.read()
    if not raw:
        return None
    try:
        text = decode_roster(raw)
        parse_roster(text)
    except DuplicateBibError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return text


@router.post("/api/execute/plans/preview")
async def preview_plan(
    request: Request,
    package: UploadFile = File(...),  # noqa: B008
):
    _guard(request)
    raw = await package.read()
    try:
        return {"ok": True, **preview_published_plan(raw)}
    except PublishedPlanError as exc:
        raise _fail(exc) from exc


@router.post("/api/execute/plans/import")
async def import_plan(
    request: Request,
    package: UploadFile = File(...),  # noqa: B008
    participants: Optional[UploadFile] = File(None),  # noqa: B008
    name: Optional[str] = Form(None),  # noqa: B008
    calendar_date: Optional[str] = Form(None),  # noqa: B008
    activate: bool = Form(False),  # noqa: B008
):
    """Import a Day Plan; with a roster it can activate in one step (#947)."""
    _guard(request)
    raw = await package.read()
    roster = await _read_roster(participants)
    if activate and roster is None:
        raise HTTPException(status_code=400, detail=NO_PARTICIPANTS_DETAIL)
    try:
        if activate and preview_published_plan(raw)["archived"]:
            raise PublishedPlanError("Restore this Day Plan before activating.")
        result = import_published_plan(raw, name=name, calendar_date=calendar_date)
        plan_id = result["plan_id"]
        if roster is not None:
            result["participants"] = import_plan_participants(plan_id, roster)["stats"]
        result["activated"] = False
        if activate:
            activate_published_plan(plan_id)
            result["activated"] = True
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return result


@router.post("/api/execute/plans/{plan_id}/participants")
async def import_plan_roster(
    request: Request,
    plan_id: str,
    file: UploadFile = File(...),  # noqa: B008
):
    _guard(request)
    roster = await _read_roster(file)
    if roster is None:
        raise HTTPException(status_code=400, detail="Choose a participant CSV.")
    try:
        result = import_plan_participants(plan_id, roster)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {"ok": True, **result}


@router.post("/api/execute/plans/activate")
async def activate_plan(request: Request, body: ActivateBody):
    _guard(request)
    try:
        if participant_count(body.plan_id) < 1:
            raise HTTPException(status_code=400, detail=NO_PARTICIPANTS_DETAIL)
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
    rows = []
    for row in listing["plans"]:
        row = dict(row)
        row["participant_count"] = _participant_count(row.get("plan_id") or "")
        rows.append(row)
    return {
        "ok": True,
        "active_plan_id": listing["active_plan_id"],
        "plans": rows,
    }


@router.get("/api/execute/active-context")
async def get_active_context(request: Request):
    _guard(request)
    return active_day_context()


@router.get("/api/execute/plans/{plan_id}/locsheets")
async def get_plan_locsheets(request: Request, plan_id: str):
    _guard(request)
    try:
        listing = list_plan_loc_sheets(plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    return {"ok": True, **listing}


@router.get("/api/execute/plans/{plan_id}/assignments")
async def get_plan_assignments(request: Request, plan_id: str):
    _guard(request)
    try:
        rows = assignment_roster(plan_id)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    assigned = [row for row in rows if row.get("assigned")]
    unassigned = [row for row in rows if not row.get("assigned")]
    return {
        "ok": True,
        "plan_id": plan_id,
        "assignments": assigned,
        "unassigned": unassigned,
    }


@router.put("/api/execute/plans/{plan_id}/assignments")
async def put_plan_assignment(
    request: Request,
    plan_id: str,
    body: AssignmentBody,
):
    _guard(request)
    try:
        actor = require_operator(request)
        row = upsert_assignment(plan_id, body.model_dump())
        record_audit(
            plan_id,
            action="assignment_upsert",
            actor=actor,
            device_id=row["device_id"],
            detail={"resource_name": row.get("resource_name") or ""},
        )
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (AssignmentError, OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc
    return {"ok": True, "plan_id": plan_id, "assignment": row}


@router.delete("/api/execute/plans/{plan_id}/assignments/{device_id}")
async def delete_plan_assignment(
    request: Request,
    plan_id: str,
    device_id: str,
):
    _guard(request)
    try:
        actor = require_operator(request)
        delete_assignment(plan_id, device_id)
        record_audit(
            plan_id,
            action="assignment_delete",
            actor=actor,
            device_id=device_id,
        )
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (AssignmentError, OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc
    return {"ok": True, "plan_id": plan_id, "device_id": device_id}


@router.get("/api/execute/ops/session")
async def get_ops_session(request: Request):
    _guard(request)
    return {
        "ok": True,
        "operator": operator_from_request(request),
    }


@router.put("/api/execute/ops/session")
async def put_ops_session(request: Request, body: OperatorBody):
    _guard(request)
    try:
        from app.core.execute.operator import clean_operator

        name = clean_operator(body.operator)
        response = JSONResponse({"ok": True, "operator": name})
        set_operator_cookie(response, name, request)
        return response
    except OperatorError as exc:
        raise _actor_fail(exc) from exc


@router.get("/api/execute/ops/audit")
async def get_ops_audit(request: Request):
    _guard(request)
    plan_id = active_plan_id()
    if not plan_id:
        return {"ok": True, "plan_id": None, "audit": []}
    return {
        "ok": True,
        "plan_id": plan_id,
        "audit": list_audit(plan_id),
    }


@router.post("/api/execute/ops/sos/ack")
async def post_sos_ack(request: Request, body: SosBody):
    _guard(request)
    plan_id = active_plan_id()
    if not plan_id:
        raise HTTPException(status_code=400, detail="No Day Plan is active.")
    try:
        actor = require_operator(request)
        row = acknowledge_sos(plan_id, body.device_id, actor)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc
    return {"ok": True, "plan_id": plan_id, "attention": row}


@router.post("/api/execute/ops/sos/clear")
async def post_sos_clear(request: Request, body: SosBody):
    _guard(request)
    plan_id = active_plan_id()
    if not plan_id:
        raise HTTPException(status_code=400, detail="No Day Plan is active.")
    try:
        actor = require_operator(request)
        row = clear_sos_attention(plan_id, body.device_id, actor)
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc
    return {"ok": True, "plan_id": plan_id, "attention": row}


@router.get("/api/execute/ops/board")
async def get_ops_board(request: Request):
    _guard(request)
    return operations_board()


@router.post("/api/execute/ops/reopen")
async def post_ops_reopen(request: Request, body: ReopenBody):
    _guard(request)
    try:
        actor = require_operator(request)
        board = record_operations_reopen(
            body.loc_id,
            body.linked_loc_ids,
        )
        record_audit(
            board.get("plan_id") or active_plan_id() or "",
            action="reopen",
            actor=actor,
            loc_id=body.loc_id,
        )
        return board
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc


@router.post("/api/execute/ops/close")
async def post_ops_close(request: Request, body: CloseBody):
    _guard(request)
    try:
        actor = require_operator(request)
        board = record_operations_close(body.loc_id)
        record_audit(
            board.get("plan_id") or active_plan_id() or "",
            action="close",
            actor=actor,
            loc_id=body.loc_id,
        )
        return board
    except PublishedPlanError as exc:
        raise _fail(exc) from exc
    except (OperatorError, AttentionError) as exc:
        raise _actor_fail(exc) from exc


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
