"""
API routes for Course Mapping: create, list, load, save under {data_dir}/courses/{id}.

Issue #732: Same data_dir as /analysis, /config, /baseline.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.course.storage import (
    create_course_directory,
    list_courses,
    load_course,
    save_course,
)
from app.core.v2.analysis_config import get_data_directory
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

    if not data_dir:
        data_dir = get_data_directory()
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
