"""
Execute race-day board API (Issue #893).

UI → API → JSON: Plan locations from locations_report.json;
operator actions in {day}/execution/state.json via write_json.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.execute.board import assemble_board
from app.core.execute import incidents as hs_incidents
from app.core.execute import participants as hs_participants
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


class IncidentCreateBody(BaseModel):
    reg_id: str
    bib: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    sub_event: Optional[str] = None


class IncidentUpdateBody(BaseModel):
    bib: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    sub_event: Optional[str] = None
    fm_event: Optional[List[str]] = None
    location_text: Optional[str] = None
    location_loc_id: Optional[str] = None
    description: Optional[str] = None
    incident_types: Optional[List[str]] = None
    incident_type_note: Optional[str] = None
    incident_type_other: Optional[str] = None
    care_types: Optional[List[str]] = None
    care_note: Optional[str] = None
    care_transferred: Optional[str] = None
    care_transferred_at: Optional[str] = None
    transferred_to: Optional[List[str]] = None
    reported_by_name: Optional[str] = None
    reported_by_agency: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_note: Optional[str] = None
    called_911: Optional[str] = None
    called_911_at: Optional[str] = None
    outcome: Optional[str] = None
    completed_by_name: Optional[str] = None
    completed_by_agency: Optional[str] = None


class IncidentNoteBody(BaseModel):
    text: str


class IncidentTransferBody(BaseModel):
    to_agency: str
    text: Optional[str] = None


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


def _resolve_execute_day(rid: str, day: Optional[str]) -> str:
    try:
        selected_day, _available = resolve_selected_day(rid, day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return selected_day


def _roster_by_reg(store: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in store.get("rows") or []:
        if isinstance(row, dict) and row.get("reg_id"):
            out[str(row["reg_id"])] = row
    return out


def _incident_view(
    incident: Mapping[str, Any],
    roster: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    payload = dict(incident)
    row = roster.get(str(incident.get("reg_id") or ""))
    if row:
        payload["display_bib"] = hs_incidents.display_bib(incident, row)
        payload["bib"] = payload["display_bib"] or str(incident.get("bib") or "")
        payload["sub_event"] = (
            payload.get("sub_event") or row.get("sub_event") or ""
        )
        payload["given_name"] = (
            payload.get("given_name") or row.get("given_name") or ""
        )
        payload["family_name"] = (
            payload.get("family_name") or row.get("family_name") or ""
        )
        payload["age"] = payload.get("age") or row.get("age") or ""
        payload["sex"] = payload.get("sex") or row.get("sex") or ""
        payload["medical_disclosed"] = row.get("medical_disclosed") or ""
        payload["medical_conditions"] = list(
            row.get("medical_conditions") or []
        )
        payload["medical_note"] = row.get("medical_note") or ""
        payload["medical_avoid"] = row.get("medical_avoid") or ""
    else:
        payload["display_bib"] = str(incident.get("bib") or "").strip()
        payload.setdefault("medical_conditions", [])
        payload.setdefault("medical_note", "")
    life = hs_incidents.lifecycle(incident)
    payload["lifecycle"] = life
    payload["lifecycle_display"] = life.get("display") or life.get("label")
    return payload


@router.get("/api/execute/participants")
async def get_execute_participants(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    field: Optional[str] = Query("any"),
    condition: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    store = hs_participants.load_store(
        storage, run_id=rid, day=selected_day
    )
    starts = hs_participants.lookup_rows(store.get("rows") or [])
    needle = (q or "").strip()
    wanted = [
        part.strip()
        for part in str(condition or "").split(",")
        if part.strip()
    ]
    hits = [
        row
        for row in starts
        if hs_participants.query_matches(needle, field or "any", row)
        and hs_participants.condition_matches_any(row, wanted)
    ]
    conditions: List[str] = []
    seen = set()
    for row in starts:
        for token in row.get("medical_conditions") or []:
            label = str(token).strip()
            if label and label not in seen:
                seen.add(label)
                conditions.append(label)
    return JSONResponse(
        content={
            "ok": True,
            "run_id": rid,
            "day": selected_day,
            "count": len(hits),
            "starts": len(starts),
            "imported": len(store.get("rows") or []),
            "conditions": conditions,
            "participants": hits,
        }
    )


@router.post("/api/execute/participants/import")
async def post_execute_participants_import(
    request: Request,
    file: UploadFile = File(...),
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="CSV must be UTF-8.",
        ) from exc
    storage = create_runflow_storage(rid)
    try:
        store, stats = hs_participants.import_csv_text(
            storage, run_id=rid, day=selected_day, text=text
        )
    except hs_participants.DuplicateBibError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    starts = hs_participants.lookup_rows(store.get("rows") or [])
    return JSONResponse(
        content={
            "ok": True,
            "run_id": rid,
            "day": selected_day,
            "stats": stats,
            "participants": starts,
        }
    )


@router.get("/api/execute/incidents")
async def get_execute_incidents(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    items = [
        _incident_view(item, roster) for item in store.get("incidents") or []
    ]
    def _when(item: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value:
                return str(value)
        return ""

    active = [
        item for item in items if item.get("incident_status") == "active"
    ]
    closed = [
        item for item in items if item.get("incident_status") == "closed"
    ]
    closed.sort(
        key=lambda item: _when(item, "closed_at", "updated_at", "opened_at"),
        reverse=True,
    )
    return JSONResponse(
        content={
            "ok": True,
            "run_id": rid,
            "day": selected_day,
            "catalog": hs_incidents.catalog(),
            "counts": {"active": len(active), "closed": len(closed)},
            "active": active,
            "closed": closed,
        }
    )


@router.post("/api/execute/incidents")
async def post_execute_incident(
    request: Request,
    body: IncidentCreateBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    row = roster.get(str(body.reg_id).strip())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown reg_id {body.reg_id}.",
        )
    if str(row.get("row_kind") or "") != "start":
        raise HTTPException(
            status_code=400,
            detail="Incidents can only be opened on a start row.",
        )
    incident = hs_incidents.empty_incident(reg_id=row["reg_id"])
    hs_incidents.apply_fields(
        incident,
        {
            "bib": body.bib if body.bib is not None else row.get("bib"),
            "given_name": (
                body.given_name
                if body.given_name is not None
                else row.get("given_name")
            ),
            "family_name": (
                body.family_name
                if body.family_name is not None
                else row.get("family_name")
            ),
            "age": body.age if body.age is not None else row.get("age"),
            "sex": body.sex if body.sex is not None else row.get("sex"),
            "sub_event": (
                body.sub_event
                if body.sub_event is not None
                else row.get("sub_event")
            ),
        },
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    store["incidents"] = list(store.get("incidents") or []) + [incident]
    hs_incidents.persist_store(storage, selected_day, store)
    return JSONResponse(
        content={
            "ok": True,
            "incident": _incident_view(incident, roster),
        }
    )


@router.get("/api/execute/incidents/{incident_id}")
async def get_execute_incident(
    request: Request,
    incident_id: str,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    try:
        incident = hs_incidents.find_incident(store, incident_id)
    except hs_incidents.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident_id {incident_id}.",
        ) from exc
    return JSONResponse(
        content={
            "ok": True,
            "catalog": hs_incidents.catalog(),
            "incident": _incident_view(incident, roster),
        }
    )


@router.put("/api/execute/incidents/{incident_id}")
async def put_execute_incident(
    request: Request,
    incident_id: str,
    body: IncidentUpdateBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    try:
        incident = hs_incidents.find_incident(store, incident_id)
    except hs_incidents.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident_id {incident_id}.",
        ) from exc
    try:
        hs_incidents.apply_fields(incident, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hs_incidents.persist_store(storage, selected_day, store)
    return JSONResponse(
        content={
            "ok": True,
            "incident": _incident_view(incident, roster),
        }
    )


@router.post("/api/execute/incidents/{incident_id}/notes")
async def post_execute_incident_note(
    request: Request,
    incident_id: str,
    body: IncidentNoteBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    try:
        incident = hs_incidents.find_incident(store, incident_id)
    except hs_incidents.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident_id {incident_id}.",
        ) from exc
    try:
        hs_incidents.require_open(incident)
        hs_incidents.append_note(incident, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hs_incidents.persist_store(storage, selected_day, store)
    return JSONResponse(
        content={
            "ok": True,
            "incident": _incident_view(incident, roster),
        }
    )


@router.post("/api/execute/incidents/{incident_id}/transfer")
async def post_execute_incident_transfer(
    request: Request,
    incident_id: str,
    body: IncidentTransferBody,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    try:
        incident = hs_incidents.find_incident(store, incident_id)
    except hs_incidents.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident_id {incident_id}.",
        ) from exc
    try:
        hs_incidents.transfer_care(incident, body.to_agency, body.text or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hs_incidents.persist_store(storage, selected_day, store)
    return JSONResponse(
        content={
            "ok": True,
            "incident": _incident_view(incident, roster),
        }
    )


@router.get("/api/execute/locations")
async def get_execute_incident_locations(
    request: Request,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    return JSONResponse(
        content={
            "ok": True,
            "run_id": rid,
            "day": selected_day,
            "locations": hs_incidents.location_catalog(storage, selected_day),
        }
    )


@router.post("/api/execute/incidents/{incident_id}/close")
async def post_execute_incident_close(
    request: Request,
    incident_id: str,
    run_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
) -> JSONResponse:
    _guard_session(request)
    rid = _require_run_id(run_id)
    selected_day = _resolve_execute_day(rid, day)
    storage = create_runflow_storage(rid)
    roster = _roster_by_reg(
        hs_participants.load_store(storage, run_id=rid, day=selected_day)
    )
    store = hs_incidents.load_store(
        storage, run_id=rid, day=selected_day
    )
    try:
        incident = hs_incidents.find_incident(store, incident_id)
    except hs_incidents.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident_id {incident_id}.",
        ) from exc
    hs_incidents.close_incident(incident)
    hs_incidents.persist_store(storage, selected_day, store)
    return JSONResponse(
        content={
            "ok": True,
            "incident": _incident_view(incident, roster),
        }
    )
