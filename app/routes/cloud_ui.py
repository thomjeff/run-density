"""
Cloud UI route handlers for the skinny, read-only container.

Provides a password-gated Dashboard + Locations UI for a single run_id.
Issue #735: Loc Sheets index and per-sheet HTML URLs.
Issue #740: Dashboard landing, session on all routes (middleware).
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.common.config import load_reporting
from app.utils.auth import (
    validate_password,
    create_session_response,
    clear_session_response,
    is_session_valid,
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
        return RedirectResponse(url="/dashboard", status_code=303)
    context = _get_cloud_context(request)
    # Starlette ≥0.29: TemplateResponse(request, name, context=...) — request must be first
    return templates.TemplateResponse(request, "pages/password.html", context)


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if validate_password(password):
        return create_session_response("/dashboard", request)
    context = _get_cloud_context(request)
    context["error"] = "Incorrect password. Please try again."
    return templates.TemplateResponse(request, "pages/password.html", context, status_code=401)


@router.get("/logout")
async def logout(request: Request):
    return clear_session_response("/", request)


@router.get("/dashboard", response_class=HTMLResponse)
async def cloud_dashboard(request: Request):
    """Dashboard with Run History, Analysis Inputs, Run Detail (Issue #740). Session: CloudSessionMiddleware."""
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
    except Exception:
        los_colors = {
            "A": "#4CAF50",
            "B": "#8BC34A",
            "C": "#FFC107",
            "D": "#FF9800",
            "E": "#FF5722",
            "F": "#F44336",
        }
    context = _get_cloud_context(request)
    context["los_colors"] = los_colors
    return templates.TemplateResponse(request, "pages/dashboard.html", context)


@router.get("/locations", response_class=HTMLResponse)
async def locations(request: Request):
    context = _get_cloud_context(request)
    return templates.TemplateResponse(request, "pages/locations.html", context)


@router.get("/api/auth/check")
async def check_session(request: Request):
    return JSONResponse(content={"authenticated": is_session_valid(request)})


# Issue #735: Loc Sheets index (behind auth) and public sheet URLs
# Issue #737: Short URL (no run_id) for stable Volunteer Local links; register before 3-param route
@router.get("/locsheets/{day}/{loc_id}", response_class=HTMLResponse)
async def cloud_locsheet_html_short(request: Request, day: str, loc_id: str):
    """Serve location one-pager HTML via short URL (session: CloudSessionMiddleware; Issue #740)."""
    run_id = _get_cloud_run_id()
    if day not in ("fri", "sat", "sun", "mon"):
        raise HTTPException(status_code=400, detail="Invalid day")
    if not loc_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid loc_id")
    run_dir = get_run_directory(run_id)
    html_path = Path(run_dir) / day / "reports" / "loc_sheets" / "html" / f"{loc_id}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Location sheet not found")
    return FileResponse(html_path, media_type="text/html")


@router.get("/locsheets", response_class=HTMLResponse)
async def cloud_locsheets(request: Request, day: Optional[str] = Query(None)):
    """Day-based index of location sheets (session: CloudSessionMiddleware)."""
    run_id = _get_cloud_run_id()
    available_days = get_available_days(run_id)
    selected_day = (day or "").strip().lower() or (available_days[0] if available_days else "")
    if selected_day not in available_days:
        selected_day = available_days[0] if available_days else ""

    run_dir = get_run_directory(run_id)
    from app.utils.loc_sheets_list import build_loc_sheet_entries

    sheets = build_loc_sheet_entries(run_dir, selected_day)

    context = _get_cloud_context(request)
    context["run_id"] = run_id
    context["day"] = selected_day
    context["sheets"] = sheets
    return templates.TemplateResponse(request, "pages/locsheets.html", context)


@router.get("/locsheets/{run_id}/{day}/{loc_id}", response_class=HTMLResponse)
async def cloud_locsheet_html(request: Request, run_id: str, day: str, loc_id: str):
    """Serve a single location one-pager HTML (session: CloudSessionMiddleware)."""
    cloud_run_id = _get_cloud_run_id()
    if run_id != cloud_run_id:
        raise HTTPException(status_code=404, detail="Not found")
    if day not in ("fri", "sat", "sun", "mon"):
        raise HTTPException(status_code=400, detail="Invalid day")
    if not loc_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid loc_id")
    run_dir = get_run_directory(run_id)
    html_path = Path(run_dir) / day / "reports" / "loc_sheets" / "html" / f"{loc_id}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Location sheet not found")
    return FileResponse(html_path, media_type="text/html")
