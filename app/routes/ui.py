"""
UI Route Handlers for Run-Density Web Interface (RF-FE-002)

Serves the 7-page web UI using Jinja2 templates.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 4
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    
    Returns:
        HTML: Password entry form
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/password.html",
        {"request": request, "meta": meta}
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard page with KPIs and summary tiles.
    
    Returns:
        HTML: Dashboard with model inputs/outputs
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {"request": request, "meta": meta}
    )


@router.get("/segments", response_class=HTMLResponse)
async def segments(request: Request):
    """
    Segments page with Leaflet map and metadata table.
    
    Returns:
        HTML: Segment list and course map
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/segments.html",
        {"request": request, "meta": meta}
    )


@router.get("/density", response_class=HTMLResponse)
async def density(request: Request):
    """
    Density analysis page with segment table and detail panel.
    
    Returns:
        HTML: Density metrics with heatmap and bin-level data
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/density.html",
        {"request": request, "meta": meta}
    )


@router.get("/flow", response_class=HTMLResponse)
async def flow(request: Request):
    """
    Flow analysis page with temporal flow metrics table.
    
    Returns:
        HTML: Event interactions and convergence analysis
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/flow.html",
        {"request": request, "meta": meta}
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    """
    Reports page with download links for generated artifacts.
    
    Returns:
        HTML: Available reports and datasets
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/reports.html",
        {"request": request, "meta": meta}
    )


@router.get("/health-check", response_class=HTMLResponse)
async def health_page(request: Request):
    """
    Health check page with system status and diagnostics.
    
    Returns:
        HTML: Environment info, file status, endpoint checks
    """
    meta = get_stub_meta()
    return templates.TemplateResponse(
        "pages/health.html",
        {"request": request, "meta": meta}
    )

