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

def _scan_reports(limit: int = 20) -> List[Dict]:
    """Scan for reports using storage service (Cloud Storage or local fallback)."""
    rows = []
    
    try:
        # Try storage service first (Cloud Storage or local)
        storage_service = get_storage_service()
        
        # Get files from storage service
        storage_files = storage_service.list_files()
        
        for filename in storage_files:
            if not filename:
                continue
                
            # Check if file has allowed extension
            file_path = Path(filename)
            if file_path.suffix.lower() not in ALLOWED_EXTS:
                continue
                
            # Determine report kind
            lower = filename.lower()
            if "density" in lower:
                kind = "density"
            elif "flow" in lower:
                kind = "flow"
            else:
                kind = "other"
                
            # For now, use current time as timestamp (storage service returns filenames only)
            ts = datetime.now()
            
            rows.append({
                "name": filename,
                "kind": kind,
                "ext": file_path.suffix.lower(),
                "mtime": ts,
                "rel": filename,  # Use filename as relative path for storage
                "source": "storage"
            })
            
    except Exception as e:
        print(f"⚠️ Storage service failed, falling back to local files: {e}")
        
        # Fallback to local file system
        if not REPORTS_DIR.exists():
            return []
            
        for p in REPORTS_DIR.rglob("*"):
            if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
                lower = p.name.lower()
                if "density" in lower:
                    kind = "density"
                elif "flow" in lower:
                    kind = "flow"
                else:
                    kind = "other"
                try:
                    ts = datetime.fromtimestamp(p.stat().st_mtime)
                except Exception:
                    ts = None
                rows.append({
                    "name": p.name,
                    "kind": kind,
                    "ext": p.suffix.lower(),
                    "mtime": ts,
                    "rel": str(p.relative_to(REPORTS_DIR)),
                    "source": "local"
                })
    
    # Sort by modification time (newest first)
    rows.sort(key=lambda r: (r["mtime"] or datetime.min), reverse=True)
    return rows[:limit]

def _latest(kind: str) -> Optional[Dict]:
    """Get the latest report of a specific kind from storage or local files."""
    items = [r for r in _scan_reports(200) if r["kind"] == kind]
    if not items:
        return None
    return items[0]  # Return the file info dict instead of Path

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
        content = storage_service.load_file(file_info["name"])
        if content is None:
            raise HTTPException(status_code=404, detail="Density report not found in storage")
        
        # Return content as response
        from fastapi.responses import Response
        media_type = mimetypes.guess_type(file_info["name"])[0] or "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_info['name']}"}
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
        content = storage_service.load_file(file_info["name"])
        if content is None:
            raise HTTPException(status_code=404, detail="Flow report not found in storage")
        
        # Return content as response
        from fastapi.responses import Response
        media_type = mimetypes.guess_type(file_info["name"])[0] or "text/plain"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_info['name']}"}
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
