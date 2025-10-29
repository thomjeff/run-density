# app/routes/reports.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from pathlib import Path
from typing import List, Dict, Optional
import os, mimetypes
from datetime import datetime

# Import storage service for Cloud Storage integration
try:
    from ..storage_service import get_storage_service
except ImportError:
    from storage_service import get_storage_service

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


def _scan_cloud_reports(storage_service, limit: int) -> List[Dict]:
    """Scan reports from cloud storage."""
    rows = []
    from datetime import timedelta
    
    today = datetime.now().date()
    for days_back in range(7):  # Check last 7 days
        check_date = today - timedelta(days=days_back)
        date_str = check_date.strftime("%Y-%m-%d")
        
        # List files for this date
        files = storage_service.list_files(date=date_str)
        
        for file_path in files:
            file_name = file_path.split('/')[-1]  # Get just the filename
            if any(file_name.lower().endswith(ext) for ext in ALLOWED_EXTS):
                ts = _extract_timestamp_from_filename(file_name, check_date)
                row = _build_report_row(file_name, file_path, ts, storage_service.use_cloud_storage)
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
        storage_service = get_storage_service()
        rows = _scan_cloud_reports(storage_service, limit)
    except Exception as e:
        # Fallback to local file system
        rows = _scan_local_reports(limit)
    
    # Sort by modification time (newest first)
    rows.sort(key=lambda r: (r["mtime"] or datetime.min), reverse=True)
    return rows[:limit]

def _latest(kind: str) -> Optional[Dict]:
    """Get the latest report of a specific kind from storage or local files."""
    try:
        from datetime import datetime, timedelta
        from app.storage_service import get_storage_service
        
        storage_service = get_storage_service()
        today = datetime.now().date()
        
        # Check the last 7 days for reports
        for days_back in range(7):
            check_date = today - timedelta(days=days_back)
            date_str = check_date.strftime("%Y-%m-%d")
            
            # List files for this date - files are saved directly in YYYY-MM-DD/ not reports/YYYY-MM-DD/
            if storage_service._detect_environment():
                # For Cloud Storage, we need to call the private method with the correct path
                files = storage_service._list_gcs_files(date_str)
            else:
                # For local, use the public interface
                files = storage_service.list_files(date=date_str)
            print(f"DEBUG: _latest() checking date {date_str}, found {len(files)} files: {files}")
            
            # Find the latest file of the requested kind
            matching_files = []
            print(f"DEBUG: _latest() looking for kind '{kind}' in {len(files)} files")
            for file_path in files:
                file_name = file_path.split('/')[-1]  # Get just the filename
                if any(file_name.lower().endswith(ext) for ext in ALLOWED_EXTS):
                    lower = file_name.lower()
                    print(f"DEBUG: _latest() checking file '{file_name}' (lower: '{lower}')")
                    if kind == "density" and "density" in lower:
                        print(f"DEBUG: _latest() found density match: {file_name}")
                        matching_files.append((date_str, file_name))
                    elif kind == "flow" and "flow" in lower:
                        print(f"DEBUG: _latest() found flow match: {file_name}")
                        matching_files.append((date_str, file_name))
            
            if matching_files:
                # Sort by filename to get the latest
                matching_files.sort(key=lambda x: x[1], reverse=True)
                latest_date, latest_filename = matching_files[0]
                
                print(f"DEBUG: _latest() storage_service.config.use_cloud_storage = {storage_service.config.use_cloud_storage}")
                result = {
                    "rel": latest_filename,
                    "kind": kind,
                    "date": latest_date,
                    "source": "cloud" if storage_service.config.use_cloud_storage else "local"
                }
                print(f"DEBUG: _latest() returning: {result}")
                return result
        
        return None
        
    except Exception as e:
        print(f"Error in _latest: {e}")
        return None

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

@router.get("/density/latest")
def density_latest():
    file_info = _latest("density")
    if not file_info:
        raise HTTPException(status_code=404, detail="No density report found")
    
    try:
        storage_service = get_storage_service()
        
        # Load content from storage service (Cloud Storage or local)
        if file_info["source"] == "cloud":
            # Files are saved directly in YYYY-MM-DD/ not reports/YYYY-MM-DD/
            file_path = f"{file_info.get('date')}/{file_info['rel']}"
            print(f"DEBUG: density_latest() loading file from path: {file_path}")
            content = storage_service._load_from_gcs(file_path)
            if content is None:
                raise HTTPException(status_code=404, detail="Density report file not found in storage")
        else:
            # Local file system fallback - construct full path with date directory
            file_path = REPORTS_DIR / file_info["date"] / file_info["rel"]
            print(f"DEBUG: density_latest() loading local file from path: {file_path}")
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"Density report file not found at {file_path}")
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        
        # Return content as response
        from fastapi.responses import Response
        media_type = mimetypes.guess_type(file_info["rel"])[0] or "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_info['rel']}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading density report: {str(e)}")

@router.get("/flow/latest")
def flow_latest():
    file_info = _latest("flow")
    if not file_info:
        raise HTTPException(status_code=404, detail="No flow report found")
    
    try:
        storage_service = get_storage_service()
        
        # Load content from storage service (Cloud Storage or local)
        if file_info["source"] == "cloud":
            # Files are saved directly in YYYY-MM-DD/ not reports/YYYY-MM-DD/
            file_path = f"{file_info.get('date')}/{file_info['rel']}"
            print(f"DEBUG: flow_latest() loading file from path: {file_path}")
            content = storage_service._load_from_gcs(file_path)
            if content is None:
                raise HTTPException(status_code=404, detail="Flow report file not found in storage")
        else:
            # Local file system fallback - construct full path with date directory
            file_path = REPORTS_DIR / file_info["date"] / file_info["rel"]
            print(f"DEBUG: flow_latest() loading local file from path: {file_path}")
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"Flow report file not found at {file_path}")
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        
        # Return content as response
        from fastapi.responses import Response
        media_type = mimetypes.guess_type(file_info["rel"])[0] or "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_info['rel']}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading flow report: {str(e)}")

@router.get("/open")
def open_report(path: str):
    """Open a specific report file from storage or local files."""
    try:
        storage_service = get_storage_service()
        content = storage_service.load_file(path)
        if content is None:
            # Fallback to local file system
            p = _safe_join(path)
            return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])
        
        # Return content from storage
        from fastapi.responses import Response
        media_type = mimetypes.guess_type(path)[0] or "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={path}"}
        )
    except Exception as e:
        # Fallback to local file system
        p = _safe_join(path)
        return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])

@router.get("/preview", response_class=HTMLResponse)
def preview_report(request: Request, path: str):
    """Preview a report file from storage or local files."""
    try:
        storage_service = get_storage_service()
        content = storage_service.load_file(path)
        if content is None:
            # Fallback to local file system
            p = _safe_join(path)
            return _preview_local_file(request, p)
        
        # Preview content from storage
        return _preview_storage_content(request, path, content)
        
    except Exception as e:
        # Fallback to local file system
        p = _safe_join(path)
        return _preview_local_file(request, p)

def _preview_storage_content(request: Request, filename: str, content: str) -> HTMLResponse:
    """Preview content loaded from storage."""
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
