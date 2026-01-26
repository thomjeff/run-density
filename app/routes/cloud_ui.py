"""
Cloud UI route handlers for the skinny, read-only container.

Provides a password-gated Locations UI for a single run_id.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.utils.auth import (
    validate_password,
    create_session_response,
    clear_session_response,
    is_session_valid,
    require_auth
)
from app.utils.env import env_str
from app.utils.run_id import get_available_days, get_run_directory

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter()


def _get_cloud_run_id() -> str:
    run_id = env_str("CLOUD_RUN_ID", "").strip()
    if not run_id:
        raise HTTPException(status_code=500, detail="CLOUD_RUN_ID is not configured")
    run_dir = get_run_directory(run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=500, detail=f"Run directory not found for run_id={run_id}")
    return run_id


def _get_cloud_context(request: Request) -> dict:
    run_id = _get_cloud_run_id()
    available_days = get_available_days(run_id)
    if not available_days:
        raise HTTPException(status_code=500, detail=f"No day folders found for run_id={run_id}")

    return {
        "request": request,
        "meta": {
            "run_timestamp": "cloud",
            "environment": "cloud",
            "run_hash": run_id
        },
        "cloud_mode": True,
        "cloud_run_id_json": json.dumps(run_id),
        "cloud_available_days_json": json.dumps(available_days)
    }


@router.get("/", response_class=HTMLResponse)
async def password_page(request: Request):
    if is_session_valid(request):
        return RedirectResponse(url="/locations", status_code=303)
    context = _get_cloud_context(request)
    return templates.TemplateResponse("pages/password.html", context)


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if validate_password(password):
        return create_session_response("/locations", request)
    context = _get_cloud_context(request)
    context["error"] = "Incorrect password. Please try again."
    return templates.TemplateResponse("pages/password.html", context, status_code=401)


@router.get("/logout")
async def logout(request: Request):
    return clear_session_response("/", request)


@router.get("/locations", response_class=HTMLResponse)
async def locations(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    context = _get_cloud_context(request)
    return templates.TemplateResponse("pages/locations.html", context)


@router.get("/api/auth/check")
async def check_session(request: Request):
    return JSONResponse(content={"authenticated": is_session_valid(request)})
