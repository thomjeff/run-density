"""Execute Participants and Incidents against the active plan."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.execute import incidents as hs_incidents
from app.core.execute import participants as hs_participants
from app.core.execute.published_plan import (
    PublishedPlanError,
    active_plan_id,
    load_imported_plan,
)
from app.storage import Storage
from app.utils.auth import is_session_valid
from app.utils.env import env_bool

router = APIRouter()



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



def _require_execute_plan(
    plan_id: Optional[str] = None,
) -> tuple:
    pid = str(plan_id or "").strip() or active_plan_id()
    if not pid:
        raise HTTPException(
            status_code=400,
            detail="Activate a plan on Execute → Plans.",
        )
    try:
        loaded = load_imported_plan(pid)
    except PublishedPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    day = str(loaded["manifest"].get("weekday_code") or "").strip()
    storage = Storage(root=str(loaded["directory"]))
    return pid, day, storage, loaded


def _guard_session(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
            "plan_id": rid,
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="CSV must be UTF-8.",
        ) from exc
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
            "plan_id": rid,
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
            "plan_id": rid,
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
    rid, selected_day, storage, loaded = _require_execute_plan()
    return JSONResponse(
        content={
            "ok": True,
            "plan_id": rid,
            "day": selected_day,
            "locations": hs_incidents.location_catalog_from_rows(
                (loaded.get("locations") or {}).get("locations") or []
            ),
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
    rid, selected_day, storage, _loaded = _require_execute_plan()
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
