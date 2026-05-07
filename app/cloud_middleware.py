"""
Session enforcement for Cloud Run (Issue #740).

All HTML and API routes require a valid password session except:
  GET /, POST /login, GET /logout, GET /static/*
"""
from __future__ import annotations

import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.utils.auth import is_session_valid
from app.utils.env import env_bool

logger = logging.getLogger(__name__)

_LOCSHEET_SHORT_RE = re.compile(r"^/locsheets/(fri|sat|sun|mon)/([A-Za-z0-9_-]+)$")
_LOCSHEET_FULL_RE = re.compile(r"^/locsheets/([A-Za-z0-9_-]+)/(fri|sat|sun|mon)/([A-Za-z0-9_-]+)$")


def _is_public_locsheet_path(path: str, method: str) -> bool:
    """Allow direct per-sheet loc-sheet HTML when explicitly enabled."""
    if method != "GET":
        return False
    if not env_bool("PUBLIC_LOCSHEETS", default=False):
        return False
    return bool(_LOCSHEET_SHORT_RE.match(path) or _LOCSHEET_FULL_RE.match(path))


class CloudSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        if path.startswith("/static/"):
            return await call_next(request)
        if path == "/" and method == "GET":
            return await call_next(request)
        if path == "/login" and method == "POST":
            return await call_next(request)
        if path == "/logout" and method == "GET":
            return await call_next(request)
        if _is_public_locsheet_path(path, method):
            return await call_next(request)

        if not is_session_valid(request):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse(url="/", status_code=303)

        return await call_next(request)
