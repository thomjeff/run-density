"""Execute-only HTML pages, login, and readiness (Issue #922)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.utils.auth import (
    clear_session_response,
    create_session_response,
    is_session_valid,
    require_auth,
    validate_password,
)
from app.utils.carto_basemaps import register_jinja_map_tiles
from app.version import get_version

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")
register_jinja_map_tiles(templates)


def _meta() -> dict:
    return {
        "run_timestamp": "pending",
        "environment": "execute",
        "run_hash": "dev",
    }


def _page(request: Request, name: str):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"request": request, "meta": _meta()},
    )


@router.get("/", response_class=HTMLResponse)
async def password_page(request: Request):
    if is_session_valid(request):
        return RedirectResponse(url="/execute/plans", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="pages/password.html",
        context={"request": request, "meta": _meta()},
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if validate_password(password):
        return create_session_response("/execute/plans", request)
    return templates.TemplateResponse(
        request=request,
        name="pages/password.html",
        context={
            "request": request,
            "meta": _meta(),
            "error": "Incorrect password. Please try again.",
        },
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    return clear_session_response("/", request)


@router.get("/health")
async def health():
    return {"ok": True, "status": "healthy", "runtime": "execute"}


@router.get("/ready")
async def ready():
    return {
        "ok": True,
        "runtime": "execute",
        "version": get_version(),
    }


@router.get("/api/auth/check")
async def check_session(request: Request):
    return JSONResponse(
        content={"authenticated": is_session_valid(request)}
    )


@router.get("/execute", response_class=HTMLResponse)
async def execute_operations(request: Request):
    return _page(request, "pages/execute.html")


@router.get("/execute/participants", response_class=HTMLResponse)
async def execute_participants(request: Request):
    return _page(request, "pages/execute_participants.html")


@router.get("/execute/incidents", response_class=HTMLResponse)
async def execute_incidents(request: Request):
    return _page(request, "pages/execute_incidents.html")
