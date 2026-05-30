"""
API routes for Race Configuration packages (config_id).

Issue #756: List, create, and resolve packages under runflow/config/{config_id}/.
Issue #757: GET/PUT course.json workspace per config_id.
Issue #758: Export segments.csv from course.json into config package.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config_package import (
    create_config_package,
    export_config_package_segments,
    import_runner_files_from_package,
    list_config_packages,
    load_config_course,
    load_config_manifest,
    package_readiness,
    resolve_config_package_path,
    save_config_course,
    update_config_package_metadata,
)
from app.core.config_package.storage import validate_config_id
from app.utils.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config-packages"])


class CreateConfigPackageRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=255)


class UpdateConfigPackageRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=255)


class ImportRunnersRequest(BaseModel):
    source_config_id: str = Field(..., min_length=1)


class SaveConfigCourseRequest(BaseModel):
    course: Dict[str, Any]


@router.get("/api/config/packages")
async def api_list_config_packages(request: Request) -> JSONResponse:
    """List race config packages (UUID + legacy slug folders)."""
    require_auth(request)
    try:
        packages = list_config_packages()
        return JSONResponse(content={"packages": packages})
    except Exception as e:
        logger.exception("Failed to list config packages")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list config packages: {e}",
        )


@router.post("/api/config/packages")
async def api_create_config_package(
    request: Request,
    body: CreateConfigPackageRequest,
) -> JSONResponse:
    """Create a new config package (UUID directory + config.json + course.json)."""
    require_auth(request)
    try:
        result = create_config_package(body.label, body.description)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"ok": True, **result},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create config package")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create config package: {e}",
        )


@router.get("/api/config/packages/{config_id}")
async def api_get_config_package(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Get package manifest and readiness."""
    require_auth(request)
    try:
        package_path = resolve_config_package_path(config_id)
        try:
            manifest = load_config_manifest(config_id)
        except FileNotFoundError:
            manifest = {
                "config_id": config_id,
                "label": config_id,
                "legacy": True,
            }
        manifest_editable = (package_path / "config.json").is_file()
        return JSONResponse(
            content={
                "ok": True,
                "config_id": config_id,
                "manifest": manifest,
                "manifest_editable": manifest_editable,
                "path": str(package_path),
                "readiness": package_readiness(package_path),
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/api/config/packages/{config_id}")
async def api_update_config_package(
    request: Request,
    config_id: str,
    body: UpdateConfigPackageRequest,
) -> JSONResponse:
    """Update package name and description in config.json."""
    require_auth(request)
    try:
        result = update_config_package_metadata(
            config_id, body.label, body.description
        )
        return JSONResponse(content={"ok": True, **result})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update config package")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update config package: {e}",
        )


@router.get("/api/config/packages/{config_id}/course")
async def api_load_config_course(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Load draw-first course workspace (course.json) for a config package."""
    require_auth(request)
    try:
        course = load_config_course(config_id)
        return JSONResponse(
            content={"ok": True, "config_id": config_id, "course": course}
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/api/config/packages/{config_id}/course")
async def api_save_config_course(
    request: Request,
    config_id: str,
    body: SaveConfigCourseRequest,
) -> JSONResponse:
    """Save course.json for a config package (validated workspace schema)."""
    require_auth(request)
    try:
        save_config_course(config_id, body.course)
        course = load_config_course(config_id)
        return JSONResponse(
            content={"ok": True, "config_id": config_id, "course": course}
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to save config package course")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save course: {e}",
        )


@router.post("/api/config/packages/{config_id}/export/segments")
async def api_export_config_package_segments(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Export segments.csv and locations.csv from package course.json."""
    require_auth(request)
    try:
        result = export_config_package_segments(config_id)
        return JSONResponse(content={"ok": True, **result})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to export config package segments")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export segments: {e}",
        )


@router.get("/api/config/packages/{config_id}/files")
async def api_list_package_files(
    request: Request,
    config_id: str,
    extension: Optional[str] = Query(None),
) -> JSONResponse:
    """List files in a config package (for Runners tab, etc.)."""
    require_auth(request)
    try:
        package_path = resolve_config_package_path(config_id)
        files: List[str] = []
        for path in sorted(package_path.iterdir()):
            if not path.is_file():
                continue
            if extension:
                ext = extension.lower().lstrip(".")
                if path.suffix.lower() != f".{ext}":
                    continue
            files.append(path.name)
        return JSONResponse(
            content={"ok": True, "config_id": config_id, "files": files}
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/import-runners")
async def api_import_runners(
    request: Request,
    config_id: str,
    body: ImportRunnersRequest,
) -> JSONResponse:
    """Copy *_runners.csv files from another config package into this package."""
    require_auth(request)
    try:
        copied = import_runner_files_from_package(config_id, body.source_config_id)
        package_path = resolve_config_package_path(config_id)
        return JSONResponse(
            content={
                "ok": True,
                "config_id": config_id,
                "source_config_id": body.source_config_id.strip(),
                "copied_files": copied,
                "readiness": package_readiness(package_path),
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to import runner files")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import runner files: {e}",
        )
