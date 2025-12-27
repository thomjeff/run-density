"""
UI Route Handlers for Run-Density Web Interface (RF-FE-002)

Serves the 7-page web UI using Jinja2 templates.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 4
Architecture: Option 3 - Hybrid Approach
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

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
templates = Jinja2Templates(directory="frontend/templates")

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


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    """
    Analysis request page for submitting new analysis requests.
    
    Issue #554: New page for submitting analysis requests via UI.
    
    Returns:
        HTML: Analysis request form
    """
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/analysis.html",
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


@router.get("/api/data/files")
async def get_data_files(request: Request, extension: Optional[str] = Query(None)):
    """
    List files in the data directory, optionally filtered by extension.
    
    Issue #554: API endpoint to populate file dropdowns in Analysis UI.
    
    Args:
        extension: Optional file extension filter (e.g., "csv", "gpx")
                  If not provided, returns all files
    
    Returns:
        JSON: List of file names matching the extension filter
    """
    require_auth(request)
    
    try:
        from app.core.v2.analysis_config import get_data_directory
        
        data_dir = get_data_directory()
        data_path = Path(data_dir)
        
        if not data_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Data directory not found: {data_dir}"
            )
        
        # List all files in data directory
        files = []
        for file_path in data_path.iterdir():
            if file_path.is_file():
                file_ext = file_path.suffix.lower()
                file_name = file_path.name
                
                # Filter by extension if provided
                if extension:
                    # Remove leading dot if present
                    ext_filter = extension.lower().lstrip('.')
                    if file_ext == f'.{ext_filter}':
                        files.append(file_name)
                else:
                    files.append(file_name)
        
        # Sort files alphabetically
        files.sort()
        
        return JSONResponse(content={"files": files})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing data files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list data files: {str(e)}"
        )


@router.get("/api/analysis/{run_id}/config")
async def get_analysis_config(request: Request, run_id: str):
    """
    Fetch analysis.json for a given run_id.
    
    Issue #554: API endpoint to fetch analysis configuration for display in UI.
    
    Args:
        run_id: Run identifier
    
    Returns:
        JSON: analysis.json content
    
    Raises:
        HTTPException: 404 if run_id or analysis.json not found
    """
    from fastapi.responses import JSONResponse
    from fastapi import HTTPException
    from pathlib import Path
    
    require_auth(request)
    
    try:
        from app.utils.run_id import get_runflow_root
        from app.core.v2.analysis_config import load_analysis_json
        
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        
        if not run_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Run ID {run_id} not found"
            )
        
        analysis_config = load_analysis_json(run_path)
        return JSONResponse(content=analysis_config)
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"analysis.json not found for run_id {run_id}"
        )
    except Exception as e:
        logger.error(f"Error loading analysis.json for run_id {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load analysis configuration: {str(e)}"
        )

