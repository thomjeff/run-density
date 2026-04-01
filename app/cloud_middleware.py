"""
Session enforcement for Cloud Run (Issue #740).

All HTML and API routes require a valid password session except:
  GET /, POST /login, GET /logout, GET /static/*
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.utils.auth import is_session_valid

logger = logging.getLogger(__name__)


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

        if not is_session_valid(request):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse(url="/", status_code=303)

        return await call_next(request)
