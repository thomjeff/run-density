"""Purpose-built Execute runtime (Issue #922).

Loads Execute routes only. Not app.main. No analysis engines.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.execute.db import init_schema, using_postgres
from app.core.execute.session_cookies import (
    rewrite_request_cookies,
    rewrite_response_cookies,
)
from app.routes.api_execute_gps import router as api_execute_gps_router
from app.routes.api_execute_runtime import router as api_execute_router
from app.routes.api_published_plans import router as api_published_plans_router
from app.routes.api_published_plans import templates as execute_plan_templates
from app.routes.execute_pages import router as execute_pages_router
from app.routes.execute_pages import templates as execute_page_templates
from app.version import get_version

logger = logging.getLogger(__name__)

os.environ.setdefault("RUNFLOW_EXECUTE_RUNTIME", "1")

app = FastAPI(title="Runflow Execute", version=get_version())
execute_page_templates.env.globals["execute_runtime"] = True
execute_plan_templates.env.globals["execute_runtime"] = True


@app.middleware("http")
async def isolate_execute_session_cookies(request, call_next):
    rewrite_request_cookies(request)
    response = await call_next(request)
    return rewrite_response_cookies(response)


app.include_router(execute_pages_router)
app.include_router(api_execute_router)
app.include_router(api_execute_gps_router)
app.include_router(api_published_plans_router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

if using_postgres():
    try:
        init_schema()
    except Exception as exc:
        logger.warning("Execute Postgres schema not ready: %s", exc)

logger.info("Execute runtime ready (not app.main).")
