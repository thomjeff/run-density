"""
Cloud-mode entrypoint for the skinny, read-only Locations UI.
"""
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.cloud_ui import router as cloud_ui_router
from app.routes.api_locations import router as locations_router
from app.routes.api_segments import router as segments_router
from app.utils.env import env_str
from app.utils.run_id import get_available_days, get_run_directory

logger = logging.getLogger(__name__)


def _validate_cloud_config() -> None:
    run_id = env_str("CLOUD_RUN_ID", "").strip()
    if not run_id:
        raise RuntimeError("CLOUD_RUN_ID must be set for cloud mode")

    password = env_str("DASHBOARD_PASSWORD", "")
    if not password:
        raise RuntimeError("DASHBOARD_PASSWORD must be set for cloud mode")

    run_dir = get_run_directory(run_id)
    if not run_dir.exists():
        raise RuntimeError(f"Run directory not found for run_id={run_id}")

    available_days = get_available_days(run_id)
    if not available_days:
        raise RuntimeError(f"No day folders found for run_id={run_id}")

    os.environ.setdefault("CLOUD_MODE", "true")
    logger.info("Cloud mode config validated.")


_validate_cloud_config()

app = FastAPI(title="Runflow Cloud UI")

app.include_router(cloud_ui_router)
app.include_router(locations_router)
app.include_router(segments_router)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
