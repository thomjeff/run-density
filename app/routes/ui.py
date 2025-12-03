"""
UI Route Handlers for Run-Density Web Interface (RF-FE-002)

Serves the 7-page web UI using Jinja2 templates.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 4
Architecture: Option 3 - Hybrid Approach
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.common.config import load_reporting
from app.utils.auth import (
    validate_password,
    create_session_response,
    clear_session_response,
    is_session_valid,
    require_auth
)

# Setup logger
logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Create router
router = APIRouter()


# ===== Stub Context Helper =====

def get_stub_meta() -> dict:
    """
    Get stub meta context for template rendering.
    
    Returns:
        dict: Stub metadata for provenance badge
        
    Note:
        This will be replaced in Steps 5-6 with actual meta.json loading
    """
    return {
        "run_timestamp": "pending",
        "environment": "local",
        "run_hash": "dev"
    }


# ===== Route Handlers =====

@router.get("/", response_class=HTMLResponse)
async def password_page(request: Request):
    """
    Password/login page (authentication screen).
    
    Issue #314: If user already has valid session, redirect to dashboard.
    
    Returns:
        HTML: Password entry form, or redirects to dashboard if authenticated
    """
    # If already authenticated, redirect to dashboard
    if is_session_valid(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/password.html",
        {"request": request, "meta": meta}
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    """
    Handle password authentication and create session.
    
    Issue #314: Server-side password validation with session creation.
    
    Args:
        password: Password submitted from form
        
    Returns:
        RedirectResponse: Redirects to dashboard on success, back to login on failure
    """
    if validate_password(password):
        # Create session and redirect to dashboard
        return create_session_response("/dashboard")
    else:
        # Invalid password - redirect back to login page with error
        # Note: In production, you might want to add a delay to prevent brute force
        meta = get_stub_meta()
        return templates.TemplateResponse(
            "pages/password.html",
            {
                "request": request,
                "meta": meta,
                "error": "Incorrect password. Please try again."
            },
            status_code=401
        )


@router.get("/logout")
async def logout(request: Request):
    """
    Handle logout and clear session.
    
    Issue #314: Clear session cookies and redirect to password page.
    
    Returns:
        RedirectResponse: Redirects to password page
    """
    return clear_session_response("/")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard page with KPIs and summary tiles.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Dashboard with model inputs/outputs and LOS colors
    """
    require_auth(request)
    meta = get_stub_meta()
    
    # Load LOS colors from SSOT
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
    except Exception as e:
        # Fallback to hardcoded colors if YAML loading fails
        los_colors = {
            "A": "#4CAF50",
            "B": "#8BC34A", 
            "C": "#FFC107",
            "D": "#FF9800",
            "E": "#FF5722",
            "F": "#F44336"
        }
    
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request, 
            "meta": meta,
            "los_colors": los_colors
        }
    )


@router.get("/segments", response_class=HTMLResponse)
async def segments(request: Request):
    """
    Segments page with Leaflet map and metadata table.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Segment list and course map with LOS colors injected
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    
    # Load LOS colors from SSOT
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
    except Exception as e:
        # Fallback to hardcoded colors if YAML loading fails
        los_colors = {
            "A": "#4CAF50",
            "B": "#8BC34A", 
            "C": "#FFC107",
            "D": "#FF9800",
            "E": "#FF5722",
            "F": "#F44336"
        }
    
    return templates.TemplateResponse(
        "pages/segments.html",
        {
            "request": request, 
            "meta": meta,
            "los_colors": los_colors
        }
    )


@router.get("/density", response_class=HTMLResponse)
async def density(request: Request):
    """
    Density analysis page with segment table and detail panel.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Density metrics with heatmap and bin-level data
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    
    # Load LOS colors from SSOT
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
    except Exception as e:
        los_colors = {
            "A": "#4CAF50", "B": "#8BC34A", "C": "#FFC107",
            "D": "#FF9800", "E": "#FF5722", "F": "#F44336"
        }
    
    # Issue #460 Phase 5: Get current run_id from runflow/latest.json
    run_id = None
    try:
        from app.utils.metadata import get_latest_run_id
        run_id = get_latest_run_id()
    except (FileNotFoundError, ValueError) as e:
        logger.warning(f"Could not load run_id from runflow/latest.json: {e}")
    except Exception as e:
        logger.error(f"Error getting latest run_id: {e}")
    
    return templates.TemplateResponse(
        "pages/density.html",
        {"request": request, "meta": meta, "los_colors": los_colors, "run_id": run_id}
    )


@router.get("/flow", response_class=HTMLResponse)
async def flow(request: Request):
    """
    Flow analysis page with temporal flow metrics table.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Event interactions and convergence analysis
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/flow.html",
        {"request": request, "meta": meta}
    )


@router.get("/locations", response_class=HTMLResponse)
async def locations(request: Request):
    """
    Locations report page with course resource timing table.
    
    Issue #277: Phase 3 - UI Report Page
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Location operational timing windows and peak flow periods
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/locations.html",
        {"request": request, "meta": meta}
    )


# Issue #374: Bins page moved to archive (functionality moved to Density page)
# @router.get("/bins", response_class=HTMLResponse)
# async def bins(request: Request):
#     """
#     Bin-level details page with granular density and flow metrics.
#     
#     Returns:
#         HTML: Bin-level table with sorting, filtering, and pagination
#     """
#     meta = get_stub_meta()
#     
#     # Load LOS colors from SSOT
#     try:
#         reporting_config = load_reporting()
#         los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
#     except Exception as e:
#         # Fallback to hardcoded colors if YAML loading fails
#         los_colors = {
#             "A": "#4CAF50",
#             "B": "#8BC34A", 
#             "C": "#FFC107",
#             "D": "#FF9800",
#             "E": "#FF5722",
#             "F": "#F44336"
#         }
#     
#     return templates.TemplateResponse(
#         "pages/bins.html",
#         {
#             "request": request, 
#             "meta": meta,
#             "los_colors": los_colors
#         }
#     )


@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    """
    Reports page with download links for generated artifacts.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Available reports and datasets
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/reports.html",
        {"request": request, "meta": meta}
    )


@router.get("/health-check", response_class=HTMLResponse)
async def health_page(request: Request):
    """
    Health check page with system status and diagnostics.
    
    Issue #314: Requires authentication.
    
    Returns:
        HTML: Environment info, file status, endpoint checks
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/health.html",
        {"request": request, "meta": meta}
    )


@router.get("/api/auth/check")
async def check_session(request: Request):
    """
    Check if current session is valid.
    
    Issue #314: Frontend session check endpoint for supplementary validation.
    
    Returns:
        JSON: {"authenticated": true/false}
    """
    from fastapi.responses import JSONResponse
    is_valid = is_session_valid(request)
    return JSONResponse(content={"authenticated": is_valid})

