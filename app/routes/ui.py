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

from app.common.config import load_reporting

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
        HTML: Dashboard with model inputs/outputs and LOS colors
    """
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
    
    Returns:
        HTML: Segment list and course map with LOS colors injected
    """
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
    
    Returns:
        HTML: Density metrics with heatmap and bin-level data
    """
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
    
    return templates.TemplateResponse(
        "pages/density.html",
        {"request": request, "meta": meta, "los_colors": los_colors}
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


@router.get("/bins", response_class=HTMLResponse)
async def bins(request: Request):
    """
    Bin-level details page with granular density and flow metrics.
    
    Returns:
        HTML: Bin-level table with sorting, filtering, and pagination
    """
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
        "pages/bins.html",
        {
            "request": request, 
            "meta": meta,
            "los_colors": los_colors
        }
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

