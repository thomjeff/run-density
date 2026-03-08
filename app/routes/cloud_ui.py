"""
Cloud UI route handlers for the skinny, read-only container.

Provides a password-gated Locations UI for a single run_id.
Issue #735: Loc Sheets index (auth) and public per-sheet HTML URLs.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
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


# Issue #735: Loc Sheets index (behind auth) and public sheet URLs
@router.get("/locsheets", response_class=HTMLResponse)
async def cloud_locsheets(request: Request, day: Optional[str] = Query(None)):
    """Day-based index of location sheets; requires auth."""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    run_id = _get_cloud_run_id()
    available_days = get_available_days(run_id)
    selected_day = (day or "").strip().lower() or (available_days[0] if available_days else "")
    if selected_day not in available_days:
        selected_day = available_days[0] if available_days else ""

    sheets = []
    run_dir = get_run_directory(run_id)
    comp_path = run_dir / selected_day / "computation" / "locations_results.json"
    if comp_path.exists():
        try:
            data = json.loads(comp_path.read_text(encoding="utf-8"))
            locations = data.get("locations") or []
            for loc in locations:
                if str(loc.get("onepage", "")).strip().lower() != "y":
                    continue
                loc_day = str(loc.get("day", "")).strip().lower()
                if loc_day and loc_day != selected_day:
                    continue
                sheets.append({"loc_id": loc.get("loc_id"), "label": loc.get("loc_label", "")})
            sheets.sort(key=lambda x: (x["loc_id"] is None, x["loc_id"]))
        except Exception as e:
            logger.warning("Failed to load locsheets for %s/%s: %s", run_id, selected_day, e)

    context = _get_cloud_context(request)
    context["run_id"] = run_id
    context["day"] = selected_day
    context["sheets"] = sheets
    return templates.TemplateResponse("pages/locsheets.html", context)


@router.get("/locsheets/{run_id}/{day}/{loc_id}", response_class=HTMLResponse)
async def cloud_locsheet_html(request: Request, run_id: str, day: str, loc_id: str):
    """Serve a single location one-pager HTML; public (no auth) for Volunteer Local (Issue #735)."""
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
