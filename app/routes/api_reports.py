"""
API Routes for Reports (RF-FE-002)

Provides report listing and download endpoints.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from io import BytesIO
import logging
import re
import zipfile

# Issue #466 Step 2: Storage consolidated to app.storage

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

_HUMAN_REPORT_EXACT = {"finish_times.csv", "finish_area_demand.pdf"}
_HUMAN_REPORT_SUBSTRINGS = ("Density", "Flow", "Locations", "Passes")
_TECHNICAL_SUBSTRINGS = ("bins.", "map_data_", "segment_windows_", "segments_legacy_")
_TECHNICAL_SUFFIXES = (".parquet", ".geojson", ".json")


def is_human_report_name(filename: str) -> bool:
    """Same allow-list as the former Reports page (Issue #891)."""
    name = str(filename or "")
    if any(token in name for token in _TECHNICAL_SUBSTRINGS) or name.endswith(_TECHNICAL_SUFFIXES):
        return False
    if name in _HUMAN_REPORT_EXACT:
        return True
    if not (name.endswith(".md") or name.endswith(".csv") or name == "finish_area_demand.pdf"):
        return False
    return any(token in name for token in _HUMAN_REPORT_SUBSTRINGS)


def _safe_export_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned or "unknown"


def _get_file_description_from_extension(filename: str) -> str:
    """Get file description based on file extension."""
    from pathlib import Path as PathLib
    ext = PathLib(filename).suffix
    
    if ext == ".md":
        return "Markdown report"
    elif ext == ".csv":
        return "CSV data export"
    elif ext == ".parquet":
        return "Parquet data export"
    elif ext == ".gz":
        return "Compressed GeoJSON"
    else:
        return ""


# Issue #466 Step 4 Cleanup: GCS metadata function removed (archived storage_service dependency)
# _get_file_metadata_from_gcs archived - local-only architecture uses direct filesystem access


def _get_file_metadata_from_local(file_path: str) -> tuple[Optional[float], Optional[int]]:
    """Get file metadata (mtime, size) from local filesystem."""
    import os
    
    try:
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            return stat.st_mtime, stat.st_size
        else:
            logger.warning(f"Local file not found: {file_path}")
            return None, None
    except Exception as e:
        logger.warning(f"Could not get metadata for {file_path}: {e}")
        return None, None


def _get_file_metadata(storage, file_path: str) -> tuple[Optional[float], Optional[int]]:
    """Get file metadata (mtime, size) from local filesystem."""
    # Issue #466 Step 4 Cleanup: Local-only, GCS branch removed
    full_path = storage._full_local(file_path)
    return _get_file_metadata_from_local(str(full_path))


def _add_core_data_files(reports: list, run_id: str) -> None:
    """Add all .csv and .gpx files from analysis.json data_dir to reports list (Issue #596)."""
    from app.config.loader import load_analysis_context
    from app.utils.run_id import get_runflow_root
    
    # Issue #682: Use centralized get_run_directory() for correct path
    from app.utils.run_id import get_run_directory
    run_path = get_run_directory(run_id)
    analysis_context = load_analysis_context(run_path)
    data_dir = analysis_context.data_dir
    if not data_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"data_dir not found at {data_dir}"
        )
    
    # Find all .csv and .gpx files in the data directory
    csv_files = list(data_dir.glob("*.csv"))
    gpx_files = list(data_dir.glob("*.gpx"))
    all_data_files = csv_files + gpx_files
    
    # File descriptions mapping (optional, for known files)
    file_descriptions = {
        "runners.csv": "Runner data with start times and event assignments",
        "segments.csv": "Course segment definitions and characteristics",
        "flow_expected_results.csv": "Expected results for validation",
        "locations.csv": "Location definitions and resource counts",
        "flow.csv": "Flow analysis input data"
    }
    
    for file_path in all_data_files:
        if file_path.is_file():
            stat = file_path.stat()
            file_name = file_path.name
            description = file_descriptions.get(file_name, f"{file_path.suffix.upper().replace('.', '')} data file")
            reports.append({
                "name": file_name,
                "path": f"data/{file_name}",
                "local_path": str(file_path),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "description": description,
                "type": "data_file"
            })


def collect_report_listing(
    run_id: Optional[str] = None,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect report + data-file entries for a run (shared by list and ZIP export)."""
    from app.utils.run_id import get_latest_run_id, get_available_days, get_run_directory

    if not run_id:
        run_id = get_latest_run_id()

    if not run_id:
        raise HTTPException(
            status_code=404,
            detail="No run ID available. Run analysis first or provide run_id parameter."
        )

    available_days = get_available_days(run_id)
    if not available_days:
        raise HTTPException(
            status_code=404,
            detail=f"No day directories found for run_id={run_id}"
        )

    if day:
        day_lower = day.lower()
        if day_lower not in available_days:
            raise HTTPException(
                status_code=400,
                detail=f"Requested day '{day}' not available for run_id={run_id}. Available days: {', '.join(available_days)}"
            )
        days_to_list = [day_lower]
    else:
        days_to_list = available_days

    reports = []
    run_dir = get_run_directory(run_id)

    for day_code in days_to_list:
        day_reports_dir = run_dir / day_code / "reports"
        if not day_reports_dir.exists():
            logger.debug(f"Reports directory not found for day {day_code}: {day_reports_dir}")
            continue

        for report_file in day_reports_dir.iterdir():
            if not report_file.is_file():
                continue

            filename = report_file.name
            report_descriptions = {
                "Locations.csv": "Consolidated Location report (one row per loc_id; combined windows)",
                "Passes.csv": "Pass-level report (one row per pass_id; outbound/return detail)",
                "finish_times.csv": "Predicted finisher counts by 20-minute clock window (per event and all)",
                "finish_area_demand.pdf": "Finish-area operational PDF: bar chart, cumulative curve, demand table (event=all)",
            }
            description = report_descriptions.get(
                filename, _get_file_description_from_extension(filename)
            )
            stat = report_file.stat()
            reports.append({
                "name": filename,
                "path": f"runflow/analysis/{run_id}/{day_code}/reports/{filename}",
                "local_path": str(report_file),
                "day": day_code,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "description": description,
                "type": "report"
            })

    _add_core_data_files(reports, run_id)
    return {
        "reports": reports,
        "run_id": run_id,
        "available_days": available_days,
        "days_listed": days_to_list,
    }


def export_entries_for_kind(entries: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    """Apply the Reports-page allow-list for ZIP contents."""
    if kind == "data_files":
        return [entry for entry in entries if entry.get("type") == "data_file"]
    if kind == "reports":
        return [
            entry for entry in entries
            if entry.get("type") == "report" and is_human_report_name(entry.get("name") or "")
        ]
    raise HTTPException(status_code=400, detail="kind must be 'reports' or 'data_files'")


def build_export_zip_bytes(entries: List[Dict[str, Any]], kind: str) -> bytes:
    """Zip allow-listed artifacts as bytes. Arcnames keep day prefixes for reports."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            name = entry.get("name") or "file"
            local_path = Path(entry["local_path"]) if entry.get("local_path") else None
            if local_path is None or not local_path.is_file():
                logger.warning("Skipping missing export file: %s", entry.get("path") or name)
                continue
            if kind == "reports" and entry.get("day"):
                arcname = f"{entry['day']}/{name}"
            else:
                arcname = name
            zf.write(local_path, arcname=arcname)
    return buf.getvalue()


@router.get("/api/reports/list")
async def get_reports_list(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon) - if not provided, shows all days")
):
    """
    Get list of available report files for a run, optionally filtered by day.
    
    If day is not provided, returns reports from all available days for the run_id.
    
    Returns:
        Array of file objects with name, path, mtime, size, day
    """
    try:
        payload = collect_report_listing(run_id, day)
        response = JSONResponse(content=payload)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get("/api/reports/download")
def download_report(path: str = Query(..., description="Report file path")):
    """
    Download a specific report file.
    
    Args:
        path: File path in format runflow/<run_id>/<day>/reports/<filename> or data/<filename>
        
    Returns:
        File download
    """
    logger.info(f"[Download] Requested path: {path}")

    # Case A: Read from local data folder
    if path.startswith("data/"):
        try:
            content = open(path, "r", encoding="utf-8").read()
            logger.info(f"[Download] Loaded local data file: {path}")
        except Exception as e:
            logger.error(f"[Download] Failed to read local file {path}: {e}")
            raise HTTPException(status_code=404, detail="File not found")

    # Case B: Read report files from runflow structure (v2 day-partitioned)
    # Path format: runflow/analysis/<run_id>/<day>/reports/<filename>
    # Issue #682: Updated to use runflow/analysis/{run_id} structure
    elif path.startswith("runflow/"):
        try:
            parts = path.split("/")
            if len(parts) >= 6 and parts[0] == "runflow" and parts[1] == "analysis":
                report_run_id = parts[2]
                day_code = parts[3]
                relative_path = "/".join(parts[4:])  # e.g., "reports/Density.md"
                
                # Create storage with root pointing to runflow/analysis/<run_id>/<day>/
                from app.utils.run_id import get_run_directory
                from app.storage import Storage
                
                run_dir = get_run_directory(report_run_id)
                day_dir = run_dir / day_code
                storage = Storage(root=str(day_dir))
                
                # Read from relative_path (e.g., "reports/Density.md")
                content = storage.read_text(relative_path)
                
                if not content:
                    logger.warning(f"[Download] File not found: {path}")
                    raise HTTPException(status_code=404, detail="File not found")
                
                logger.info(f"[Download] Loaded runflow file: {path}")
            else:
                logger.error(f"[Download] Invalid path format: {path}")
                raise HTTPException(status_code=400, detail="Invalid path format. Expected: runflow/analysis/<run_id>/<day>/reports/<filename>")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[Download] Failed to read file {path}: {e}")
            raise HTTPException(status_code=404, detail="File not found")
    else:
        logger.warning(f"[Download] Access denied for path: {path}")
        raise HTTPException(status_code=403, detail="Access denied. Path must start with 'runflow/' or 'data/'")

    # Safe encoding
    try:
        content_bytes = content.encode("utf-8")
    except Exception as e:
        logger.error(f"[Download] Failed to encode content: {e}")
        raise HTTPException(status_code=500, detail="Encoding error")

    filename = path.split("/")[-1]
    logger.info(f"[Download] Sending file: {filename}")
    
    from io import BytesIO
    return StreamingResponse(
        BytesIO(content_bytes),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/api/reports/export.zip")
def export_reports_zip(
    kind: str = Query(..., description="reports | data_files"),
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """ZIP the Reports-page allow-list for the selected run/day (Issue #891)."""
    kind_norm = (kind or "").strip().lower()
    if kind_norm not in {"reports", "data_files"}:
        raise HTTPException(status_code=400, detail="kind must be 'reports' or 'data_files'")

    listing = collect_report_listing(run_id, day)
    entries = export_entries_for_kind(listing["reports"], kind_norm)
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No {kind_norm.replace('_', ' ')} available for this run/day."
        )

    zip_bytes = build_export_zip_bytes(entries, kind_norm)
    if not zip_bytes:
        raise HTTPException(status_code=404, detail="Export files could not be read.")

    run_token = _safe_export_token(listing["run_id"])
    days = listing.get("days_listed") or []
    day_token = _safe_export_token(days[0] if len(days) == 1 else "all")
    suffix = "reports" if kind_norm == "reports" else "data_files"
    filename = f"runflow_{run_token}_{day_token}_{suffix}.zip"

    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

