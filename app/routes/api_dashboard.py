"""
API Routes for Dashboard Data (RF-FE-002)

Provides summary data for dashboard KPI tiles.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 6
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import logging
from datetime import datetime

from app.common.config import load_rulebook, load_reporting
from app.utils.run_id import get_latest_run_id, resolve_selected_day
from app.storage import create_runflow_storage

# Issue #283: Import SSOT for flagging logic parity
from app import flagging as ssot_flagging

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage_service singleton (not needed)

# Phase 3 cleanup: Removed unused helper functions:
# - count_runners_for_events() - Replaced by reading from metadata.json
# - load_bins_flagged_count() - Replaced by reading from flags.json


def calculate_peak_density_los(peak_density: float) -> str:
    """
    Calculate LOS for peak density using rulebook thresholds.
    
    Args:
        peak_density: Peak density value (persons/m²)
        
    Returns:
        LOS grade (A-F)
    """
    try:
        rulebook = load_rulebook()
        thresholds = rulebook.get("globals", {}).get("los_thresholds", {})
        
        # Get density thresholds (assuming they're in order A->F)
        density_thresholds = thresholds.get("density", [])
        
        if not density_thresholds:
            # Fallback to hardcoded thresholds if YAML missing
            density_thresholds = [0.2, 0.4, 0.6, 0.8, 1.0]
        
        # Find appropriate LOS grade
        los_grades = ["A", "B", "C", "D", "E", "F"]
        
        for i, threshold in enumerate(density_thresholds):
            if peak_density < threshold:
                return los_grades[i]
        
        # If above all thresholds, return F
        return "F"
        
    except Exception as e:
        logger.error(f"Error calculating peak density LOS: {e}")
        # Fallback to simple threshold
        if peak_density < 0.2:
            return "A"
        elif peak_density < 0.4:
            return "B"
        elif peak_density < 0.6:
            return "C"
        elif peak_density < 0.8:
            return "D"
        elif peak_density < 1.0:
            return "E"
        else:
            return "F"


def _load_ui_artifact_safe(storage, path: str, warnings: list):
    """Load UI artifact with safe exception handling."""
    try:
        return storage.read_json(path)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        warnings.append(f"missing: {path.split('/')[-1]}")
        return None


def _calculate_flags_metrics(flags) -> tuple:
    """Calculate segments_flagged and bins_flagged from flags data."""
    if isinstance(flags, dict):
        segments_flagged = len(flags.get("flagged_segments", []))
        bins_flagged = flags.get("total_bins_flagged", 0)
    elif isinstance(flags, list):
        segments_flagged = len(flags)
        bins_flagged = sum(f.get("flagged_bins", 0) for f in flags)
        logger.info(f"Calculated bins_flagged: {bins_flagged} from {len(flags)} flag entries")
    else:
        segments_flagged = 0
        bins_flagged = 0
    return segments_flagged, bins_flagged


def _calculate_peak_metrics(segment_metrics: dict) -> tuple:
    """Calculate peak density and rate from segment metrics."""
    peak_density = 0.0
    peak_rate = 0.0
    
    for seg_id, metrics in segment_metrics.items():
        if isinstance(metrics, dict):
            peak_density = max(peak_density, metrics.get("peak_density", 0.0))
            peak_rate = max(peak_rate, metrics.get("peak_rate", 0.0))
    
    return peak_density, peak_rate


@router.get("/api/dashboard/summary")
async def get_dashboard_summary(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get dashboard summary data for KPI tiles.
    
    Returns:
        JSON with aggregated metrics from all data sources
        
    Sources:
        - meta.json → run_timestamp, environment
        - segment_metrics.json → segments_total, peak_density, peak_rate, segments_overtaking, segments_copresence
        - flags.json → bins_flagged, segments_flagged
        - runners.csv → total_runners, cohorts
    """
    try:
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Track missing files for warnings
        warnings = []
        
        # Load meta data
        meta = _load_ui_artifact_safe(storage, f"{selected_day}/ui/meta.json", warnings) or {}
        timestamp = meta.get("run_timestamp", datetime.now().isoformat() + "Z")
        environment = meta.get("environment", "local")
        
        # Load day metadata for events (canonical source for event tiles)
        events_detail: List[Dict[str, Any]] = []
        day_events_map: Dict[str, Dict[str, Any]] = {}
        try:
            day_meta_path = storage._full_local(f"{selected_day}/metadata.json")
            if day_meta_path.exists():
                day_meta = json.loads(day_meta_path.read_text())
                events_obj = day_meta.get("events", {}) if isinstance(day_meta.get("events"), dict) else {}
                for ev_name, ev_info in events_obj.items():
                    if not isinstance(ev_info, dict):
                        continue
                    participants = int(ev_info.get("participants", 0))
                    start_time = ev_info.get("start_time", "")
                    events_detail.append({
                        "name": ev_name,
                        "start_time": start_time,
                        "participants": participants
                    })
                    day_events_map[ev_name] = {
                        "count": participants,
                        "start_time": start_time
                    }
        except Exception as e:
            logger.warning(f"Could not read day metadata for events: {e}")
        
        # Load segment metrics
        # Issue #485: Extract summary fields BEFORE filtering segment-level data
        raw_segment_metrics = _load_ui_artifact_safe(storage, f"{selected_day}/ui/segment_metrics.json", warnings) or {}
        
        # Extract summary-level fields (these are top-level keys, not segment IDs)
        summary_fields = ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins', 
                         'overtaking_segments', 'co_presence_segments']
        segments_overtaking = raw_segment_metrics.get("overtaking_segments", 0)
        segments_copresence = raw_segment_metrics.get("co_presence_segments", 0)
        
        # Filter out summary fields to get only segment-level data
        # Segment-level data has segment IDs as keys (not in summary_fields list)
        segment_metrics = {k: v for k, v in raw_segment_metrics.items() 
                          if k not in summary_fields}
        segments_total = len(segment_metrics)
        
        logger.info(f"Loaded flow metrics from segment_metrics.json: overtaking={segments_overtaking}, co-presence={segments_copresence}")
        
        # Calculate peak density and rate from segment-level data
        peak_density, peak_rate = _calculate_peak_metrics(segment_metrics)
        peak_density_los = calculate_peak_density_los(peak_density)
        
        # Load flags data
        flags = _load_ui_artifact_safe(storage, f"{selected_day}/ui/flags.json", warnings)
        if flags is None:
            flags = []
        
        logger.info(f"Loaded flags data: {type(flags)}, length: {len(flags) if flags else 0}")
        segments_flagged, bins_flagged = _calculate_flags_metrics(flags)
        
        # Runners data: prefer metadata events map; fallback to empty
        total_runners = sum((v.get("count", 0) for v in day_events_map.values()), 0)
        cohorts = day_events_map  # cohorts keyed by event name with count/start_time
        
        # Determine status
        status = "normal"
        if peak_density_los in ["E", "F"] or segments_flagged > 0:
            status = "action_required"
        
        # Build response
        summary = {
            "run_id": run_id,  # Issue #470: Include run_id in response
            "selected_day": selected_day,
            "available_days": available_days,
            "timestamp": timestamp,
            "environment": environment,
            "total_runners": total_runners,
            "cohorts": cohorts,
            "events_detail": events_detail,
            "segments_total": segments_total,
            "segments_flagged": segments_flagged,
            "bins_flagged": bins_flagged,
            "peak_density": round(peak_density, 4),
            "peak_density_los": peak_density_los,
            "peak_rate": round(peak_rate, 2),
            "segments_overtaking": segments_overtaking,
            "segments_copresence": segments_copresence,
            "status": status,
            "warnings": warnings
        }
        
        logger.info(f"Dashboard summary: {segments_total} segments, {total_runners} runners, status={status}")
        
        return JSONResponse(
            content=summary,
            headers={"Cache-Control": "public, max-age=60"}
        )
        
    except Exception as e:
        logger.error(f"Error generating dashboard summary: {e}")
        
        # Return safe defaults
        fallback_summary = {
            "timestamp": datetime.now().isoformat() + "Z",
            "environment": "local",
            "total_runners": 0,
            "cohorts": {},
            "segments_total": 0,
            "segments_flagged": 0,
            "bins_flagged": 0,
            "peak_density": 0.0,
            "peak_density_los": "A",
            "peak_rate": 0.0,
            "segments_overtaking": 0,
            "segments_copresence": 0,
            "status": "normal",
            "warnings": ["error: failed to load dashboard data"]
        }
        
        return JSONResponse(
            content=fallback_summary,
            headers={"Cache-Control": "public, max-age=60"}
        )
