"""Execute GPS OsmAnd ingest and Operations overlay (Issue #925)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.execute.gps import (
    GpsError,
    ingest_osmand,
    merge_client_payload,
    overlay,
)
from app.utils.auth import is_session_valid
from app.utils.env import env_bool

router = APIRouter()


def _guard(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _fail(exc: GpsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _query_params(request: Request) -> Dict[str, Any]:
    q = request.query_params
    return {
        "id": q.get("id") or q.get("deviceid"),
        "deviceid": q.get("deviceid"),
        "lat": q.get("lat"),
        "lon": q.get("lon"),
        "timestamp": q.get("timestamp"),
        "speed": q.get("speed"),
        "bearing": q.get("bearing") or q.get("heading"),
        "heading": q.get("heading"),
        "accuracy": q.get("accuracy") or q.get("hdop"),
        "batt": q.get("batt"),
        "alarm": q.get("alarm"),
    }


@router.api_route("/api/execute/gps/osmand", methods=["GET", "POST"])
async def osmand_ingest(
    request: Request,
    token: Optional[str] = Query(None),
) -> PlainTextResponse:
    header = request.headers.get("x-execute-gps-token") or ""
    provided = (token or header).strip()
    params = _query_params(request)
    body = None
    if request.method == "POST":
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            try:
                raw = await request.json()
            except Exception:
                raw = None
            if isinstance(raw, dict):
                body = raw
        elif "application/x-www-form-urlencoded" in ctype:
            form = await request.form()
            for key in (
                "id",
                "deviceid",
                "lat",
                "lon",
                "timestamp",
                "speed",
                "bearing",
                "heading",
                "accuracy",
                "hdop",
                "batt",
                "alarm",
            ):
                if form.get(key) not in (None, ""):
                    params[key] = form.get(key)
    merged = merge_client_payload(params, body)
    try:
        ingest_osmand(merged, token=provided)
    except GpsError as exc:
        raise _fail(exc) from exc
    return PlainTextResponse("OK")


@router.get("/api/execute/gps/overlay")
async def gps_overlay(request: Request) -> JSONResponse:
    _guard(request)
    return JSONResponse(content=overlay())
