# app/routes/reports.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from pathlib import Path
from typing import List, Dict, Optional
import os, mimetypes
from datetime import datetime

# Issue #466 Step 4 Cleanup: Removed storage_service imports (archived)

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")

REPORTS_DIR = Path(os.getenv("RUNFLOW_REPORTS_DIR", "reports")).resolve()
ALLOWED_EXTS = {".html", ".htm", ".md", ".pdf", ".csv"}

def _determine_report_kind(file_name: str) -> str:
    """Determine report kind (density, flow, other) from filename."""
    lower = file_name.lower()
    if "density" in lower:
        return "density"
    elif "flow" in lower:
        return "flow"
    else:
        return "other"


def _extract_timestamp_from_filename(file_name: str, check_date) -> datetime:
    """Extract timestamp from filename, falling back to current time."""
    try:
        # Extract timestamp from filename like "2025-09-16-0115-Density.md"
        if len(file_name) >= 19 and file_name[10] == '-':
            time_str = file_name[10:15]  # "0115"
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            return datetime.combine(check_date, datetime.min.time().replace(hour=hour, minute=minute))
        else:
            return datetime.now()
    except Exception:
        return datetime.now()


def _build_report_row(file_name: str, file_path: str, ts: datetime, is_cloud: bool) -> Dict:
    """Build report row dictionary."""
    return {
        "name": file_name,
        "kind": _determine_report_kind(file_name),
        "ext": file_name.split('.')[-1].lower(),
        "mtime": ts,
        "rel": file_path,
        "source": "cloud" if is_cloud else "local"
    }


def _scan_runflow_reports(limit: int) -> List[Dict]:
    """
    Scan reports from runflow index (Issue #460 Phase 5).
    
    Reads from runflow/index.json to get list of all runs.
    """
    from app.utils.metadata import get_run_index
    from app.utils.env import detect_storage_target
    
    rows = []
    storage_target = detect_storage_target()
    
    # Get all runs from index.json
    runs = get_run_index()  # Newest first
    
    # Take the most recent N runs
    recent_runs = runs[:limit] if limit > 0 else runs
    
    for run_entry in recent_runs:
        run_id = run_entry.get("run_id")
        created_at = run_entry.get("created_at")
        file_counts = run_entry.get("file_counts", {})
        
        # Parse timestamp
        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else datetime.now()
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse timestamp for run {run_id}: {e}")
            ts = datetime.now()
        
        # Add report files from this run
        for report_num in range(file_counts.get("reports", 0)):
            # Report filenames: Density.md, Flow.csv, Flow.md
            report_names = ["Density.md", "Flow.csv", "Flow.md"]
            for report_name in report_names:
                if any(report_name.lower().endswith(ext) for ext in ALLOWED_EXTS):
                    file_path = f"runflow/{run_id}/reports/{report_name}"
                    row = _build_report_row(report_name, file_path, ts, storage_target == "gcs")
                    rows.append(row)
    
    return rows


def _scan_local_reports(limit: int) -> List[Dict]:
    """Scan reports from local file system."""
    rows = []
    
    if not REPORTS_DIR.exists():
        return []
    
    for p in REPORTS_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            try:
                ts = datetime.fromtimestamp(p.stat().st_mtime)
            except Exception:
                ts = None
            
            row = _build_report_row(p.name, str(p.relative_to(REPORTS_DIR)), ts or datetime.now(), False)
            row["mtime"] = ts
            rows.append(row)
    
    return rows


def _scan_reports(limit: int = 20) -> List[Dict]:
    """Scan for reports using storage service (Cloud Storage or local file system)."""
    rows = []
    
    try:
        # Issue #460 Phase 5: Use runflow index instead of date-based scanning
        rows = _scan_runflow_reports(limit)
    except Exception as e:
        # Fallback to empty list (no legacy fallback)
        rows = _scan_local_reports(limit)
    
    # Sort by modification time (newest first)
    rows.sort(key=lambda r: (r["mtime"] or datetime.min), reverse=True)
    return rows[:limit]

# Issue #466 Step 4 Cleanup: Legacy date-based report functions removed
# _latest(), density_latest(), flow_latest() archived - used old date-based structure
# Modern API uses /api/reports/list endpoint with runflow/<uuid>/reports/ structure

def _safe_join(rel: str) -> Path:
    candidate = (REPORTS_DIR / rel).resolve()
    if REPORTS_DIR not in candidate.parents and candidate != REPORTS_DIR:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if candidate.suffix.lower() not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    return candidate

@router.get("/list", response_class=HTMLResponse)
def reports_list(request: Request, limit: int = 15):
    items = _scan_reports(limit=limit)
    return templates.TemplateResponse("_reports_list.html", {"request": request, "items": items})

# Issue #466 Step 4 Cleanup: Legacy endpoints removed - not used by current UI
# Use /api/reports/list and /api/reports/download endpoints instead

@router.get("/open")
def open_report(path: str):
    """Open a specific report file from local filesystem."""
    try:
        # Issue #466 Step 4 Cleanup: Local-only filesystem access
        p = _safe_join(path)
        return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Report not found: {path}")

@router.get("/preview", response_class=HTMLResponse)
def preview_report(request: Request, path: str):
    """Preview a report file from local filesystem."""
    try:
        # Issue #466 Step 4 Cleanup: Local-only filesystem access
        p = _safe_join(path)
        return _preview_local_file(request, p)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Report not found: {path}")

# Issue #466 Step 4 Cleanup: _preview_storage_content removed (GCS-specific, not needed for local-only)

def _preview_storage_content_archived(request: Request, filename: str, content: str) -> HTMLResponse:
    """Archived: Preview content loaded from storage (GCS-specific)."""
    ext = Path(filename).suffix.lower()
    
    if ext in {".html", ".htm"}:
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": filename, "html": content, "is_pdf": False, "is_csv": False})
    
    if ext == ".md":
        try:
            import pypandoc
            html = pypandoc.convert_text(content, "html")
        except Exception:
            import html as _ht
            html = "<pre>" + _ht.escape(content) + "</pre>"
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": filename, "html": html, "is_pdf": False, "is_csv": False})
    
    if ext == ".csv":
        import csv, html as _ht
        from io import StringIO
        rows = []
        reader = csv.reader(StringIO(content))
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 2000:
                break
        def td(cells, tag):
            return "".join(f"<{tag}>{_ht.escape(c)}</{tag}>" for c in cells)
        table_html = "<table class='table w-full'>"
        if rows:
            table_html += "<thead><tr>" + td(rows[0], "th") + "</tr></thead>"
            body = rows[1:] if len(rows) > 1 else []
            table_html += "<tbody>" + "".join("<tr>" + td(r, "td") + "</tr>" for r in body) + "</tbody>"
        table_html += "</table>"
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": filename, "html": table_html, "is_pdf": False, "is_csv": True,
             "download_url": f"/reports/open?path={filename}"})
    
    if ext == ".pdf":
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": filename, "html": "", "is_pdf": True, "is_csv": False,
             "pdf_url": f"/reports/open?path={filename}"})
    
    raise HTTPException(status_code=400, detail="Unsupported preview type")

def _preview_local_file(request: Request, p: Path) -> HTMLResponse:
    """Preview content from local file system (fallback)."""
    ext = p.suffix.lower()
    if ext in {".html", ".htm"}:
        html = p.read_text(encoding="utf-8", errors="ignore")
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": p.name, "html": html, "is_pdf": False, "is_csv": False})
    if ext == ".md":
        try:
            import pypandoc
            html = pypandoc.convert_file(str(p), "html")
        except Exception:
            import html as _ht
            html = "<pre>" + _ht.escape(p.read_text(encoding="utf-8", errors="ignore")) + "</pre>"
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": p.name, "html": html, "is_pdf": False, "is_csv": False})
    if ext == ".csv":
        import csv, html as _ht
        rows = []
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= 2000:
                    break
        def td(cells, tag):
            return "".join(f"<{tag}>{_ht.escape(c)}</{tag}>" for c in cells)
        table_html = "<table class='table w-full'>"
        if rows:
            table_html += "<thead><tr>" + td(rows[0], "th") + "</tr></thead>"
            body = rows[1:] if len(rows) > 1 else []
            table_html += "<tbody>" + "".join("<tr>" + td(r, "td") + "</tr>" for r in body) + "</tbody>"
        table_html += "</table>"
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": p.name, "html": table_html, "is_pdf": False, "is_csv": True,
             "download_url": f"/reports/open?path={p.relative_to(REPORTS_DIR)}"})
    if ext == ".pdf":
        return templates.TemplateResponse("_report_preview.html",
            {"request": request, "name": p.name, "html": "", "is_pdf": True, "is_csv": False,
             "pdf_url": f"/reports/open?path={p.relative_to(REPORTS_DIR)}"})
    raise HTTPException(status_code=400, detail="Unsupported preview type")
