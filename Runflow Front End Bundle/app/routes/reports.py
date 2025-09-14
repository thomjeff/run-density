# app/routes/reports.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from pathlib import Path
from typing import List, Dict, Optional
import os, mimetypes
from datetime import datetime

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")

REPORTS_DIR = Path(os.getenv("RUNFLOW_REPORTS_DIR", "reports")).resolve()
ALLOWED_EXTS = {".html", ".htm", ".md", ".pdf", ".csv"}

def _scan_reports(limit: int = 20) -> List[Dict]:
    if not REPORTS_DIR.exists():
        return []
    rows = []
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
            })
    rows.sort(key=lambda r: (r["mtime"] or datetime.min), reverse=True)
    return rows[:limit]

def _latest(kind: str) -> Optional[Path]:
    items = [r for r in _scan_reports(200) if r["kind"] == kind]
    if not items:
        return None
    return (REPORTS_DIR / items[0]["rel"]).resolve()

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
    p = _latest("density")
    if not p:
        raise HTTPException(status_code=404, detail="No density report found")
    return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])

@router.get("/flow/latest")
def flow_latest():
    p = _latest("flow")
    if not p:
        raise HTTPException(status_code=404, detail="No flow report found")
    return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])

@router.get("/open")
def open_report(path: str):
    p = _safe_join(path)
    return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0])

@router.get("/preview", response_class=HTMLResponse)
def preview_report(request: Request, path: str):
    p = _safe_join(path)
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
