"""
Queue a v2 analysis run (shared by /runflow/v2/analyze and config package UI).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Union

from fastapi import BackgroundTasks, status
from fastapi.responses import JSONResponse

from app.api.models.v2 import V2AnalyzeResponse, V2ErrorResponse, V2OutputPaths
from app.core.v2.analysis_config import generate_analysis_json, get_data_directory
from app.core.v2.loader import load_events_from_payload
from app.core.v2.pipeline import create_full_analysis_pipeline
from app.core.v2.validation import ValidationError, validate_api_payload
from app.utils.run_id import generate_run_id, get_run_directory

logger = logging.getLogger(__name__)


def map_data_dir_for_runtime(data_dir: str) -> str:
    """Map host runflow paths to container paths when running in Docker."""
    from app.utils.path_mapper import to_runtime_path

    return to_runtime_path(data_dir)


def run_analysis_background(
    events,
    segments_file: str,
    locations_file: str,
    flow_file: str,
    data_dir: str,
    run_id: str,
    request_payload: Dict[str, Any],
):
    """Background task to run the full analysis pipeline."""
    try:
        logger.info("Starting background analysis for run_id: %s", run_id)
        enable_audit = request_payload.get("enableAudit", "n").lower()
        pipeline_result = create_full_analysis_pipeline(
            events=events,
            segments_file=segments_file,
            locations_file=locations_file,
            flow_file=flow_file,
            data_dir=data_dir,
            run_id=run_id,
            request_payload=request_payload,
            enable_audit=enable_audit,
        )

        run_path = get_run_directory(run_id)
        response_payload = {
            "status": "success",
            "code": 200,
            "run_id": pipeline_result["run_id"],
            "days": pipeline_result["days"],
            "output_paths": {
                day: {
                    "day": paths["day"],
                    "reports": paths["reports"],
                    "bins": paths["bins"],
                    "maps": paths["maps"],
                    "ui": paths["ui"],
                    "metadata": paths["metadata"],
                }
                for day, paths in pipeline_result["output_paths"].items()
            },
        }

        run_metadata_path = run_path / "metadata.json"
        if run_metadata_path.exists():
            with open(run_metadata_path, "r", encoding="utf-8") as fh:
                run_metadata = json.load(fh)
            run_metadata["response"] = response_payload
            with open(run_metadata_path, "w", encoding="utf-8") as fh:
                json.dump(run_metadata, fh, indent=2, ensure_ascii=False)

        for day_code in pipeline_result["days"]:
            day_metadata_path = run_path / day_code / "metadata.json"
            if day_metadata_path.exists():
                with open(day_metadata_path, "r", encoding="utf-8") as fh:
                    day_metadata = json.load(fh)
                day_metadata["response"] = response_payload
                with open(day_metadata_path, "w", encoding="utf-8") as fh:
                    json.dump(day_metadata, fh, indent=2, ensure_ascii=False)

        logger.info("Background analysis completed for run_id: %s", run_id)
    except Exception as e:
        logger.error("Error in background analysis for run_id %s: %s", run_id, e, exc_info=True)


def submit_v2_analysis(
    payload_dict: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Union[V2AnalyzeResponse, JSONResponse]:
    """Validate payload, write analysis.json, and queue the background pipeline."""
    data_dir = payload_dict.get("data_dir") or get_data_directory()
    data_dir = map_data_dir_for_runtime(str(data_dir))
    payload_dict = dict(payload_dict)
    payload_dict["data_dir"] = data_dir

    data_path = Path(data_dir)
    if not data_path.exists():
        error_response = V2ErrorResponse(
            status="ERROR",
            code=404,
            error=f"Data directory not found: {data_dir}",
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response.model_dump(),
        )
    if not data_path.is_dir():
        error_response = V2ErrorResponse(
            status="ERROR",
            code=400,
            error=f"Data directory path is not a directory: {data_dir}",
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(),
        )

    try:
        validate_api_payload(payload_dict, data_dir)
    except ValidationError as e:
        error_response = V2ErrorResponse(status="ERROR", code=e.code, error=e.message)
        return JSONResponse(status_code=e.code, content=error_response.model_dump())

    run_id = generate_run_id()
    run_path = get_run_directory(run_id)
    run_path.mkdir(parents=True, exist_ok=True)

    try:
        analysis_config = generate_analysis_json(
            request_payload=payload_dict,
            run_id=run_id,
            run_path=run_path,
            data_dir=data_dir,
        )
        logger.info("Generated analysis.json for run_id: %s", run_id)
    except Exception as e:
        logger.error("Failed to generate analysis.json: %s", e, exc_info=True)
        error_response = V2ErrorResponse(
            status="ERROR",
            code=500,
            error=f"Failed to generate analysis configuration: {str(e)}",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )

    data_dir = analysis_config.get("data_dir")
    if not data_dir:
        error_response = V2ErrorResponse(
            status="ERROR",
            code=500,
            error="analysis.json missing required field: data_dir",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )

    segments_file = analysis_config.get("segments_file")
    locations_file = analysis_config.get("locations_file")
    flow_file = analysis_config.get("flow_file")
    events = load_events_from_payload(payload_dict, data_dir)
    event_days: List[str] = list(
        {str(event.get("day") or "").strip().lower() for event in payload_dict.get("events", [])}
    )
    event_days = [d for d in event_days if d]

    output_paths_dict = {}
    for day_code in event_days:
        output_paths_dict[day_code] = V2OutputPaths(
            day=day_code,
            reports=f"runflow/analysis/{run_id}/{day_code}/reports",
            bins=f"runflow/analysis/{run_id}/{day_code}/bins",
            maps=f"runflow/analysis/{run_id}/{day_code}/maps",
            ui=f"runflow/analysis/{run_id}/{day_code}/ui",
            metadata=f"runflow/analysis/{run_id}/{day_code}/metadata.json",
        )

    background_tasks.add_task(
        run_analysis_background,
        events=events,
        segments_file=segments_file,
        locations_file=locations_file,
        flow_file=flow_file,
        data_dir=data_dir,
        run_id=run_id,
        request_payload=payload_dict,
    )

    logger.info("Analysis request accepted for run_id: %s", run_id)
    return V2AnalyzeResponse(
        run_id=run_id,
        status="success",
        days=event_days,
        output_paths=output_paths_dict,
    )
