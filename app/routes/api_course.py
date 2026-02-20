"""
API routes for Course Mapping: create, list, load, save under {data_dir}/courses/{id}.

Issue #732: Same data_dir as /analysis, /config, /baseline.
Snap-to-road: proxy to OSRM (public or configurable) to avoid CORS.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.core.course.export import export_course_zip

# OSRM public demo (driving). Override with OSRM_ROUTE_URL env for self-hosted.
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"

from app.core.course.storage import (
    create_course_directory,
    list_courses,
    load_course,
    save_course,
)
from app.utils.run_id import get_runflow_root

router = APIRouter(prefix="/api/courses", tags=["course"])
logger = logging.getLogger(__name__)


def resolve_course_data_dir(
    data_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> Path:
    """
    Resolve data directory for course storage. Same logic as baseline.
    """
    if config_dir:
        normalized = config_dir.strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="config_dir must not be empty",
            )
        if Path(normalized).name != normalized or "/" in normalized or "\\" in normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid config_dir: {config_dir}",
            )
        config_root = get_runflow_root() / "config"
        if not config_root.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Config root not found: {config_root}",
            )
        config_path = config_root / normalized
        if not config_path.exists() or not config_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Config directory not found: {normalized}",
            )
        return config_path

    # Issue #732: When no data_dir/config_dir provided, use runflow root from constants (same as analysis/baseline).
    if not data_dir:
        data_dir = str(get_runflow_root())
    data_path = Path(data_dir)
    if not data_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data directory does not exist: {data_dir}",
        )
    if not data_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data directory path is not a directory: {data_dir}",
        )
    return data_path


class CreateCourseRequest(BaseModel):
    """Request body for creating a new course."""

    data_dir: Optional[str] = None
    config_dir: Optional[str] = None


class SaveCourseRequest(BaseModel):
    """Request body for saving course state."""

    data_dir: Optional[str] = None
    config_dir: Optional[str] = None
    course: Dict[str, Any]


@router.get("")
async def api_list_courses(
    data_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> JSONResponse:
    """
    List courses under data_dir/courses/. Same data_dir as analysis/baseline.
    """
    try:
        root = resolve_course_data_dir(data_dir=data_dir, config_dir=config_dir)
        courses = list_courses(root)
        return JSONResponse(content={"ok": True, "data_dir": str(root), "courses": courses})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("List courses failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("")
async def api_create_course(request: CreateCourseRequest) -> JSONResponse:
    """
    Create a new course under data_dir/courses/{id}. Returns course id and full course state.
    """
    try:
        root = resolve_course_data_dir(
            data_dir=request.data_dir,
            config_dir=request.config_dir,
        )
        course_dir = create_course_directory(root)
        course_id = course_dir.name
        course_data = load_course(root, course_id)
        return JSONResponse(
            content={
                "ok": True,
                "id": course_id,
                "path": str(course_dir),
                "course": course_data,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Create course failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/route/segment")
async def api_route_segment(
    from_ll: str = Query(..., description="lon,lat of start"),
    to_ll: str = Query(..., description="lon,lat of end"),
) -> JSONResponse:
    """
    Snap-to-road: return road geometry between two points (OSRM driving profile).
    Returns GeoJSON coordinates [[lon, lat], ...] or error. Issue #732.
    """
    try:
        parts_from = [x.strip() for x in from_ll.split(",") if x.strip()]
        parts_to = [x.strip() for x in to_ll.split(",") if x.strip()]
        if len(parts_from) != 2 or len(parts_to) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_ll and to_ll must be 'lon,lat'",
            )
        lon1, lat1 = float(parts_from[0]), float(parts_from[1])
        lon2, lat2 = float(parts_to[0]), float(parts_to[1])
        url = f"{OSRM_BASE}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return JSONResponse(
                content={"ok": False, "detail": data.get("message", data.get("code", "No route"))}
            )
        coords = data["routes"][0].get("geometry", {}).get("coordinates")
        if not coords:
            return JSONResponse(content={"ok": False, "detail": "No geometry"})
        return JSONResponse(content={"ok": True, "coordinates": coords})
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Route segment failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Routing service error",
        )


@router.get("/{course_id}/export")
async def api_export_course(
    course_id: str,
    data_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> Response:
    """Export course as zip (segments.csv, flow.csv, locations.csv, course.gpx). Issue #732."""
    try:
        root = resolve_course_data_dir(data_dir=data_dir, config_dir=config_dir)
        course_data = load_course(root, course_id)
        course_name = (course_data.get("name") or "").strip() or course_id
        zip_bytes = export_course_zip(course_data, course_id, course_name)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="course_{course_id}_export.zip"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Export course failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{course_id}")
async def api_load_course(
    course_id: str,
    data_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> JSONResponse:
    """Load course.json by id."""
    try:
        root = resolve_course_data_dir(data_dir=data_dir, config_dir=config_dir)
        course_data = load_course(root, course_id)
        return JSONResponse(content={"ok": True, "course": course_data})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Load course failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{course_id}")
async def api_save_course(course_id: str, request: SaveCourseRequest) -> JSONResponse:
    """Save course state to course.json."""
    try:
        root = resolve_course_data_dir(
            data_dir=request.data_dir,
            config_dir=request.config_dir,
        )
        save_course(root, course_id, request.course)
        course_data = load_course(root, course_id)
        return JSONResponse(content={"ok": True, "course": course_data})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Save course failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
