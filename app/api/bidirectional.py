"""
API Routes for Bidirectional Overlap Data (Issue #720)
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Any, Dict, List, Optional
import csv
import logging

from app.storage import create_runflow_storage
from app.utils.constants import REPORTS_OVERLAPS_DIRNAME, REPORTS_OVERLAPS_SUMMARY_FILENAME

logger = logging.getLogger(__name__)

router = APIRouter()


def _empty_overlap_payload(selected_day: str, available_days: List[str]) -> JSONResponse:
    return JSONResponse(content={
        "selected_day": selected_day,
        "available_days": available_days,
        "overlaps": {
            "analyzed_count": 0,
            "overlap_count": 0,
            "segments": []
        }
    })


def _load_overlap_summary(storage, selected_day: str) -> Optional[Dict[str, Any]]:
    summary_path = f"{selected_day}/reports/{REPORTS_OVERLAPS_DIRNAME}/{REPORTS_OVERLAPS_SUMMARY_FILENAME}"
    if not storage.exists(summary_path):
        return None
    try:
        return storage.read_json(summary_path)
    except Exception as e:
        logger.warning(f"Failed to load overlaps_summary.json for {selected_day}: {e}")
        return None


@router.get("/api/bidirectional/segments")
async def get_bidirectional_segments(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    try:
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)

        summary = _load_overlap_summary(storage, selected_day)
        if not summary:
            return _empty_overlap_payload(selected_day, available_days)

        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "overlaps": {
                "analyzed_count": summary.get("analyzed_count", 0),
                "overlap_count": summary.get("overlap_count", 0),
                "segments": summary.get("segments", []),
            }
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading bidirectional segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load bidirectional segments: {str(e)}")


@router.get("/api/bidirectional/segment/{seg_id}")
async def get_bidirectional_segment_detail(
    seg_id: str,
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)"),
    event_a: Optional[str] = Query(None, description="Event A name"),
    event_b: Optional[str] = Query(None, description="Event B name"),
):
    try:
        from app.utils.run_id import get_latest_run_id, resolve_selected_day

        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)

        summary = _load_overlap_summary(storage, selected_day)
        if not summary:
            raise HTTPException(status_code=404, detail="No overlap summary available")

        segments = summary.get("segments", [])
        seg_matches = [
            seg for seg in segments
            if str(seg.get("seg_id")) == str(seg_id)
            and (event_a is None or str(seg.get("event_a")) == str(event_a))
            and (event_b is None or str(seg.get("event_b")) == str(event_b))
        ]
        if not seg_matches:
            raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found in overlap summary")
        if len(seg_matches) > 1 and (event_a is None or event_b is None):
            raise HTTPException(status_code=400, detail="event_a and event_b are required for this segment")

        segment = seg_matches[0]
        if not segment.get("event_a_label"):
            segment["event_a_label"] = segment.get("event_a")
        if not segment.get("event_b_label"):
            segment["event_b_label"] = segment.get("event_b")
        csv_filename = segment.get("csv_filename")
        if not csv_filename:
            raise HTTPException(status_code=404, detail="Overlap CSV not found for segment")

        csv_path = f"{selected_day}/reports/{REPORTS_OVERLAPS_DIRNAME}/{csv_filename}"
        if not storage.exists(csv_path):
            raise HTTPException(status_code=404, detail="Overlap CSV missing")

        csv_text = storage.read_text(csv_path)
        reader = csv.DictReader(csv_text.splitlines())
        rows = []
        for row in reader:
            parsed = dict(row)
            for key, value in row.items():
                if key.endswith("_count") or key.endswith("_entries") or key.endswith("_exits"):
                    try:
                        parsed[key] = int(value)
                    except Exception:
                        parsed[key] = 0
            rows.append(parsed)

        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "segment": segment,
            "rows": rows
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading bidirectional segment detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load bidirectional segment: {str(e)}")
