"""
API Routes for Locations Report (Issue #277)

Provides endpoints for location report generation and retrieval.

Author: Cursor AI Assistant
Epic: Issue #277
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from typing import Dict, Any, Optional
import logging

from app.location_report import parse_by_event
from app.utils.run_id import get_latest_run_id
from app.storage import create_runflow_storage
from app.utils.env import env_bool
from app.utils.auth import is_session_valid
from app.core.locations.report_json import locations_report_relpath

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def _merge_onepage_into_report_rows(
    report_data: list,
    locations_results: Optional[Dict[str, Any]],
    selected_day: str,
) -> None:
    """
    Issue #745: Add ``onepage`` per row from locations_results.json (SSOT for loc sheets).

    Day matching matches ``build_loc_sheet_entries`` / Loc Sheets index behavior.
    """
    sel = (selected_day or "").strip().lower()
    if not locations_results:
        for row in report_data:
            row["onepage"] = "n"
        return

    onepage_by_id: Dict[str, str] = {}
    for loc in locations_results.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        loc_day = str(loc.get("day", "")).strip().lower()
        if loc_day and loc_day != sel:
            continue
        lid = loc.get("loc_id")
        if lid is None or str(lid).strip() == "":
            continue
        key = str(lid).strip()
        raw = str(loc.get("onepage", "")).strip().lower()
        onepage_by_id[key] = raw if raw else "n"

    for row in report_data:
        lid = row.get("loc_id")
        key = str(lid).strip() if lid is not None else ""
        row["onepage"] = onepage_by_id.get(key, "n")


def _normalize_location_api_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce flag / by_event for the Locations UI without reading CSV."""
    if "by_event" in row:
        row["by_event"] = parse_by_event(row.get("by_event"))
    if "flag" in row:
        flag = row.get("flag")
        if isinstance(flag, bool):
            row["flag"] = flag
        else:
            row["flag"] = str(flag).strip().lower() in ("true", "1", "y", "yes")
    return row


@router.get("/api/locations")
async def get_locations_report(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)"),
    generate: bool = Query(False, description="Generate new report if not exists")
) -> JSONResponse:
    """
    Get locations report data from computed JSON (Issues #894 / #895).

    Artifact: ``{day}/computation/locations_report.json``. CSV remains an export only.
    Issue #745: each row may include ``onepage`` (y|n) from ``locations_results.json``.
    """
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        from app.utils.run_id import resolve_selected_day
        
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        # Resolve day for day-scoped paths
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Issue #591 / #745: Load locations_results.json for resources_available and onepage (SSOT)
        resources_available = []
        locations_results: Optional[Dict[str, Any]] = None
        locations_results_path = f"{selected_day}/computation/locations_results.json"
        if storage.exists(locations_results_path):
            try:
                locations_results = storage.read_json(locations_results_path)
                resources_available = locations_results.get("resources_available", [])
            except Exception as e:
                logger.warning(f"Could not load locations_results from {locations_results_path}: {e}")
        
        report_path = locations_report_relpath(selected_day)
        if not storage.exists(report_path):
            if generate:
                raise HTTPException(
                    status_code=400,
                    detail="start_times parameter required. Use v2 API endpoint /runflow/v2/analyze "
                           "which provides start times in the request, or provide start_times explicitly. (Issue #512)"
                )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Locations report JSON not found for run_id={run_id} day={selected_day}. "
                    "Re-run analysis to write computation/locations_report.json."
                ),
            )

        payload = storage.read_json(report_path)
        report_data = payload.get("locations") or []
        if not isinstance(report_data, list):
            raise HTTPException(
                status_code=500,
                detail="locations_report.json is invalid: 'locations' must be an array.",
            )
        report_data = [_normalize_location_api_row(dict(row)) for row in report_data if isinstance(row, dict)]
        _merge_onepage_into_report_rows(report_data, locations_results, selected_day)
        json_resources = payload.get("resources_available")
        if json_resources:
            resources_available = json_resources
        
        return JSONResponse(content={
            "ok": True,
            "run_id": run_id,
            "selected_day": selected_day,
            "available_days": available_days,
            "locations": report_data,
            "count": len(report_data) if report_data else 0,
            "resources_available": resources_available  # Issue #591: Day-specific resource list
        })
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving locations report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/api/locations/generate")
async def generate_locations_report(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure")
) -> JSONResponse:
    """
    Generate locations report.
    
    Issue #277: Forces generation of a new locations report.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        
    Returns:
        JSON response with generation result
    """
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        logger.info(f"Generating locations report for run_id={run_id}")
        
        # Issue #512: Start times must be provided - cannot use hardcoded constants
        raise HTTPException(
            status_code=400,
            detail="start_times parameter required. Use v2 API endpoint /runflow/v2/analyze "
                   "which provides start times in the request, or provide start_times explicitly. (Issue #512)"
        )
        # Phase 3 cleanup: Removed unreachable code after raise HTTPException
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating locations report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/api/locations/csv")
async def get_locations_csv(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure")
) -> FileResponse:
    """
    Download locations report as CSV.
    
    Issue #277: Serves the locations report CSV file.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        
    Returns:
        CSV file response
    """
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        storage = create_runflow_storage(run_id)
        report_path = f"reports/Locations.csv"
        
        if not storage.exists(report_path):
            raise HTTPException(
                status_code=404,
                detail=f"Locations report not found for run_id={run_id}"
            )
        
        # Get full file path using internal method
        file_path = storage._full_local(report_path)
        
        return FileResponse(
            str(file_path),
            filename="Locations.csv",
            media_type="text/csv"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving locations CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/api/locations/sheets.zip")
async def download_location_sheets_zip(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)"),
) -> StreamingResponse:
    """Zip on-disk HTML loc sheets. Does not regenerate PDFs or HTML (#871)."""
    import io

    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not run_id:
        run_id = get_latest_run_id()
    if not run_id:
        raise HTTPException(status_code=404, detail="No run ID available.")
    from app.utils.run_id import get_run_directory, resolve_selected_day
    from app.utils.loc_sheets_list import zip_loc_sheet_html

    try:
        selected_day, _available = resolve_selected_day(run_id, day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    run_dir = get_run_directory(run_id)
    try:
        payload = zip_loc_sheet_html(run_dir, selected_day)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No location sheet HTML for this run and day. Run analysis with onepage='y' locations.",
        )
    filename = f"loc_sheets_{run_id}_{selected_day}.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

