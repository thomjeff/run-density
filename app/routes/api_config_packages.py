"""
API routes for Race Configuration packages (config_id).

Issue #756: List, create, and resolve packages under runflow/config/{config_id}/.
Issue #757: GET/PUT course.json workspace per config_id.
Issue #758: Export segments.csv from course.json into config package.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.core.config_package import (
    create_config_package,
    delete_config_package,
    export_config_package_segments,
    import_runner_files_from_package,
    list_config_packages,
    load_config_course,
    load_config_manifest,
    package_readiness,
    resolve_config_package_path,
    save_config_course,
    save_config_package_resources,
    update_config_package_metadata,
)
from app.core.config_package.legs import (
    create_package_leg,
    delete_package_leg,
    export_all_package_legs_zip,
    export_package_leg_zip,
    get_leg_line_geojson,
    reconcile_leg_locations_to_course,
    remove_leg_location_from_manifest,
    sync_leg_metadata_into_course,
    sync_leg_locations_if_applied,
    update_package_leg,
    update_package_leg_geometry,
)
from app.core.config_package.segment_recipes import (
    apply_package_recipes,
    get_event_route_preview,
    get_package_segment_library_state,
    import_gpx_files_to_library,
    save_package_recipes,
    seed_reference_segment_library,
)
from app.core.config_package.storage import validate_config_id
from app.core.locations.suggest_events import suggest_location_events
from app.utils.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config-packages"])


class CreateConfigPackageRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=255)
    event_day: str = Field("", max_length=16)
    package_events: List[str] = Field(
        ...,
        min_length=1,
        description="Event ids for this package (e.g. full, half, 10k)",
    )


class UpdateConfigPackageRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=255)
    event_day: str = Field("", max_length=16)


class ImportRunnersRequest(BaseModel):
    source_config_id: str = Field(..., min_length=1)


class SaveConfigCourseRequest(BaseModel):
    course: Dict[str, Any]


class PackageResourceEntry(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)
    label: str = Field(..., min_length=1, max_length=64)


class SavePackageResourcesRequest(BaseModel):
    resources: List[PackageResourceEntry]


class SuggestLocationEventsRequest(BaseModel):
    location_index: Optional[int] = Field(None, ge=0)
    location: Optional[Dict[str, Any]] = None


class UpdateLegRequest(BaseModel):
    leg_label: Optional[str] = None
    start_label: Optional[str] = None
    end_label: Optional[str] = None
    width_m: Optional[float] = None
    schema: Optional[str] = None
    direction: Optional[str] = None
    flow_type: Optional[str] = None
    flow_notes: Optional[str] = None
    description: Optional[str] = None
    locations: Optional[List[Dict[str, Any]]] = None


class UpdateLegGeometryRequest(BaseModel):
    coordinates: List[List[float]] = Field(
        ...,
        min_length=2,
        description="Track vertices as [lon, lat] in order",
    )


class RemoveLegLocationRequest(BaseModel):
    leg_loc_key: str = Field(..., min_length=3, description="Leg location key, e.g. 01:0")


class SaveSegmentRecipesRequest(BaseModel):
    order_by_event: Dict[str, Dict[str, Optional[int]]] = Field(
        default_factory=dict,
        description="Per event, leg id -> 1-based order (omit or null if unused)",
    )
    export_csv: bool = Field(
        True,
        description="After save, apply recipes to course.json and write segments.csv",
    )


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
        result = create_config_package(
            body.label,
            body.description,
            event_day=body.event_day,
            package_events=body.package_events,
        )
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
            config_id, body.label, body.description, body.event_day
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


@router.delete("/api/config/packages/{config_id}")
async def api_delete_config_package(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Permanently delete a config package directory."""
    require_auth(request)
    try:
        result = delete_config_package(config_id)
        return JSONResponse(content={"ok": True, **result})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to delete config package")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete config package: {e}",
        )


@router.get("/api/config/packages/{config_id}/course")
async def api_load_config_course(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Load draw-first course workspace (course.json) for a config package."""
    require_auth(request)
    try:
        reconcile_leg_locations_to_course(config_id)
        sync_leg_metadata_into_course(config_id)
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
        from app.core.config_package.legs import sync_leg_location_metadata_from_course

        save_config_course(config_id, body.course)
        sync_leg_metadata_into_course(config_id)
        sync_leg_location_metadata_from_course(config_id)
        reconcile_leg_locations_to_course(config_id)
        sync_leg_metadata_into_course(config_id)
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


@router.get("/api/config/packages/{config_id}/segment-library")
async def api_get_segment_library(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Load segment library legs, recipes, and per-event km totals."""
    require_auth(request)
    try:
        state = get_package_segment_library_state(config_id)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/segment-library/legs")
async def api_create_package_leg(
    request: Request,
    config_id: str,
    file: UploadFile = File(...),
    leg_label: str = Form(""),
    start_label: str = Form(""),
    end_label: str = Form(""),
    width_m: float = Form(3.0),
    schema: str = Form("on_course_open"),
    direction: str = Form("uni"),
    flow_type: str = Form("none"),
    flow_notes: str = Form(""),
    description: str = Form(""),
) -> JSONResponse:
    """Create a course leg from an uploaded GPX file."""
    require_auth(request)
    try:
        data = await file.read()
        if not data:
            raise ValueError("GPX file is empty")
        state = create_package_leg(
            config_id,
            data,
            file.filename or "leg.gpx",
            leg_label=leg_label,
            start_label=start_label,
            end_label=end_label,
            width_m=width_m,
            schema=schema,
            direction=direction,
            flow_type=flow_type,
            flow_notes=flow_notes,
            description=description,
        )
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/api/config/packages/{config_id}/segment-library/legs/{leg_id}/geometry")
async def api_update_package_leg_geometry(
    request: Request,
    config_id: str,
    leg_id: str,
    body: UpdateLegGeometryRequest,
) -> JSONResponse:
    """Save reshaped leg route (GPX track from edited coordinates)."""
    require_auth(request)
    try:
        state = update_package_leg_geometry(config_id, leg_id, body.coordinates)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/config/packages/{config_id}/segment-library/export-legs")
async def api_export_all_package_legs(
    request: Request,
    config_id: str,
) -> Response:
    """Download a zip with every leg GPX track and JSON metadata."""
    require_auth(request)
    try:
        zip_bytes, filename = export_all_package_legs_zip(config_id)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/config/packages/{config_id}/segment-library/legs/{leg_id}/export")
async def api_export_package_leg(
    request: Request,
    config_id: str,
    leg_id: str,
) -> Response:
    """Download a zip with the leg GPX track and JSON metadata (including locations)."""
    require_auth(request)
    try:
        zip_bytes, filename = export_package_leg_zip(config_id, leg_id)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/config/packages/{config_id}/segment-library/legs/{leg_id}/geometry")
async def api_get_package_leg_geometry(
    request: Request,
    config_id: str,
    leg_id: str,
) -> JSONResponse:
    """GeoJSON LineString for one leg (map display)."""
    require_auth(request)
    try:
        feature = get_leg_line_geojson(config_id, leg_id)
        return JSONResponse(content={"ok": True, "feature": feature})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/segment-library/sync-leg-locations")
async def api_sync_leg_locations_to_course(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Merge leg map placements into course.json."""
    require_auth(request)
    try:
        from app.core.config_package.legs import merge_leg_locations_into_course

        merge_leg_locations_into_course(config_id)
        synced = True
        course = load_config_course(config_id)
        return JSONResponse(
            content={
                "ok": True,
                "synced": synced,
                "config_id": config_id,
                "course": course,
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/segment-library/leg-locations/remove")
async def api_remove_leg_location_from_manifest(
    request: Request,
    config_id: str,
    body: RemoveLegLocationRequest,
) -> JSONResponse:
    """Remove a leg placement from the library when deleted on the Course tab."""
    require_auth(request)
    try:
        remove_leg_location_from_manifest(config_id, body.leg_loc_key)
        reconcile_leg_locations_to_course(config_id)
        course = load_config_course(config_id)
        state = get_package_segment_library_state(config_id)
        return JSONResponse(
            content={
                "ok": True,
                "config_id": config_id,
                "course": course,
                "library": state,
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/api/config/packages/{config_id}/segment-library/legs/{leg_id}")
async def api_update_package_leg(
    request: Request,
    config_id: str,
    leg_id: str,
    body: UpdateLegRequest,
) -> JSONResponse:
    """Update leg metadata and optional locations."""
    require_auth(request)
    try:
        fields = body.model_dump(exclude_unset=True)
        if "leg_label" in fields and fields["leg_label"] is not None:
            fields["seg_label"] = fields.pop("leg_label")
        state = update_package_leg(config_id, leg_id, fields)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/api/config/packages/{config_id}/segment-library/legs/{leg_id}/gpx")
async def api_replace_package_leg_gpx(
    request: Request,
    config_id: str,
    leg_id: str,
    file: UploadFile = File(...),
) -> JSONResponse:
    """Replace GPX geometry for an existing leg."""
    require_auth(request)
    try:
        data = await file.read()
        if not data:
            raise ValueError("GPX file is empty")
        state = update_package_leg(
            config_id,
            leg_id,
            {},
            gpx_bytes=data,
            gpx_filename=file.filename or "leg.gpx",
        )
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/api/config/packages/{config_id}/segment-library/legs/{leg_id}")
async def api_delete_package_leg(
    request: Request,
    config_id: str,
    leg_id: str,
) -> JSONResponse:
    """Delete a leg and remove it from recipes."""
    require_auth(request)
    try:
        state = delete_package_leg(config_id, leg_id)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/segment-library/seed-reference")
async def api_seed_reference_segment_library(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Copy built-in reference leg library into the package (dev / bootstrap)."""
    require_auth(request)
    try:
        state = seed_reference_segment_library(config_id)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/config/packages/{config_id}/segment-library/upload")
async def api_upload_segment_library_gpx(
    request: Request,
    config_id: str,
    files: List[UploadFile] = File(...),
) -> JSONResponse:
    """Upload GPX files and optional runflow leg export JSON (locations + metadata)."""
    require_auth(request)
    try:
        uploads = []
        for uf in files:
            data = await uf.read()
            uploads.append((uf.filename or "leg.gpx", data))
        state = import_gpx_files_to_library(config_id, uploads)
        return JSONResponse(content={"ok": True, **state})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/api/config/packages/{config_id}/segment-library/recipes")
async def api_save_segment_recipes(
    request: Request,
    config_id: str,
    body: SaveSegmentRecipesRequest,
) -> JSONResponse:
    """Save recipe order grid; optionally apply to course and export segments.csv."""
    require_auth(request)
    try:
        state = save_package_recipes(config_id, {}, order_by_event=body.order_by_event)
        result: Dict[str, Any] = {"ok": True, "library": state}
        if body.export_csv:
            apply_result = apply_package_recipes(config_id, export_csv=True)
            result["apply"] = apply_result
            course = load_config_course(config_id)
            result["course"] = course
        return JSONResponse(content=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to save segment recipes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save recipes: {e}",
        )


@router.post("/api/config/packages/{config_id}/segment-library/apply")
async def api_apply_segment_recipes(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Apply saved recipes to course.json and export segments.csv."""
    require_auth(request)
    try:
        result = apply_package_recipes(config_id, export_csv=True)
        course = load_config_course(config_id)
        return JSONResponse(
            content={"ok": True, **result, "course": course}
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to apply segment recipes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply recipes: {e}",
        )


@router.get("/api/config/packages/{config_id}/segment-library/events/{event_id}/preview")
async def api_event_route_preview(
    request: Request,
    config_id: str,
    event_id: str,
) -> JSONResponse:
    """Stitched GPX route for one event (Course tab map preview)."""
    require_auth(request)
    try:
        preview = get_event_route_preview(config_id, event_id)
        return JSONResponse(content={"ok": True, **preview})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to load event route preview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load route preview: {e}",
        )


@router.post("/api/config/packages/{config_id}/export/segments")
async def api_export_config_package_segments(
    request: Request,
    config_id: str,
) -> JSONResponse:
    """Export segments.csv, locations.csv, flow.csv, and per-event GPX from package."""
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


@router.put("/api/config/packages/{config_id}/resources")
async def api_save_package_resources(
    request: Request,
    config_id: str,
    body: SavePackageResourcesRequest,
) -> JSONResponse:
    """Update schedulable resource types for this config package (FPF, YSSR, etc.)."""
    require_auth(request)
    try:
        payload = [r.model_dump() for r in body.resources]
        result = save_config_package_resources(config_id, payload)
        return JSONResponse(content={"ok": True, **result})
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to save package resources")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save resources: {e}",
        )


@router.post("/api/config/packages/{config_id}/locations/suggest-events")
async def api_suggest_location_events(
    request: Request,
    config_id: str,
    body: SuggestLocationEventsRequest,
) -> JSONResponse:
    """Suggest full/half/10k/elite/open flags from seg_id and course segments."""
    require_auth(request)
    try:
        course = load_config_course(config_id)
        segments = course.get("segments") or []
        loc: Optional[Dict[str, Any]] = body.location
        if loc is None:
            if body.location_index is None:
                raise ValueError("location_index or location is required")
            locations = course.get("locations") or []
            if body.location_index >= len(locations):
                raise ValueError("location_index out of range")
            loc = locations[body.location_index]
        flags, rationale = suggest_location_events(loc, segments)
        return JSONResponse(
            content={
                "ok": True,
                "events": flags,
                "rationale": rationale,
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to suggest location events")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suggest events: {e}",
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
