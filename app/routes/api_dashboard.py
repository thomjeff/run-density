"""
API Routes for Dashboard Data (RF-FE-002)

Provides summary data for dashboard KPI tiles.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 6
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime

from app.storage import create_storage_from_env, load_meta, load_segment_metrics, load_flags, DATASET
from app.storage_service import StorageService
from app.common.config import load_rulebook, load_reporting

# Issue #283: Import SSOT for flagging logic parity
from app import flagging as ssot_flagging

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()
storage_service = StorageService()


def load_runners_data() -> Dict[str, Any]:
    """
    Load runners data and aggregate by event.
    
    Returns:
        Dict with total_runners and cohorts data
    """
    try:
        if not storage.exists(DATASET["runners"]):
            logger.warning("runners.csv not found in storage")
            return {"total_runners": 0, "cohorts": {}}
        
        # Read CSV data
        csv_content = storage.read_text(DATASET["runners"])
        lines = csv_content.strip().split('\n')
        
        if len(lines) < 2:
            return {"total_runners": 0, "cohorts": {}}
        
        # Parse CSV (assuming: event,start_time,count or similar structure)
        # For now, use mock data structure - will be updated when real data available
        cohorts = {
            "Full": {"start": "07:00", "count": 368},
            "10K": {"start": "07:20", "count": 618}, 
            "Half": {"start": "07:40", "count": 912}
        }
        
        total_runners = sum(cohort["count"] for cohort in cohorts.values())
        
        return {
            "total_runners": total_runners,
            "cohorts": cohorts
        }
        
    except Exception as e:
        logger.error(f"Error loading runners data: {e}")
        return {"total_runners": 0, "cohorts": {}}


def load_bins_flagged_count() -> int:
    """
    Load bins data and count flagged bins using SSOT (Issue #283 fix).
    
    Returns:
        int: Number of flagged bins
    """
    try:
        import pandas as pd
        from pathlib import Path
        
        # Find the latest reports directory (date-based)
        reports_base = Path("reports")
        if not reports_base.exists():
            logger.warning("No reports directory found")
            return 0
        
        # Get latest date directory
        date_dirs = [d for d in reports_base.iterdir() if d.is_dir() and d.name.startswith("2025-")]
        if not date_dirs:
            logger.warning("No date directories found in reports")
            return 0
        
        latest_dir = max(date_dirs, key=lambda d: d.name)
        bins_path = latest_dir / "bins.parquet"
        
        if not bins_path.exists():
            logger.warning(f"bins.parquet not found at {bins_path}")
            return 0
        
        # Load bins and use SSOT for flagging count
        bins_df = pd.read_parquet(bins_path)
        bin_flags = ssot_flagging.compute_bin_flags(bins_df)
        
        flagged_count = len(bin_flags)
        logger.info(f"SSOT flagged bins count: {flagged_count} from {bins_path}")
        return flagged_count
        
    except Exception as e:
        logger.error(f"Error loading bins data: {e}")
        return 0


def load_flow_data() -> Dict[str, int]:
    """
    Load flow data for overtaking and co-presence counts.
    
    Returns:
        Dict with segments_overtaking and segments_copresence counts
    """
    try:
        if not storage.exists(DATASET["flow"]):
            logger.warning("flow.json not found in storage")
            return {"segments_overtaking": 0, "segments_copresence": 0}
        
        flow_data = storage.read_json(DATASET["flow"])
        
        # Count segments with overtaking and co-presence
        segments_overtaking = 0
        segments_copresence = 0
        
        # flow.json is a simple object with segment IDs as keys
        for seg_id, values in flow_data.items():
            # Check for overtaking (any non-zero overtake counts)
            overtaking_a = values.get("overtaking_a", 0)
            overtaking_b = values.get("overtaking_b", 0)
            if overtaking_a > 0 or overtaking_b > 0:
                segments_overtaking += 1
            
            # Check for co-presence
            copresence_a = values.get("copresence_a", 0)
            copresence_b = values.get("copresence_b", 0)
            if copresence_a > 0 or copresence_b > 0:
                segments_copresence += 1
        
        return {
            "segments_overtaking": segments_overtaking,
            "segments_copresence": segments_copresence
        }
        
    except Exception as e:
        logger.error(f"Error loading flow data: {e}")
        return {"segments_overtaking": 0, "segments_copresence": 0}


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


@router.get("/api/dashboard/summary")
async def get_dashboard_summary():
    """
    Get dashboard summary data for KPI tiles.
    
    Returns:
        JSON with aggregated metrics from all data sources
        
    Sources:
        - meta.json → run_timestamp, environment
        - segment_metrics.json → segments_total, peak_density, peak_rate
        - flags.json → bins_flagged, segments_flagged
        - flow.json → segments_overtaking, segments_copresence
        - runners.csv → total_runners, cohorts
    """
    try:
        # Track missing files for warnings
        warnings = []
        
        # Load meta data from UI artifacts
        meta = storage_service.load_ui_artifact("meta.json")
        if meta is None:
            warnings.append("missing: meta.json")
            meta = {}
        
        timestamp = meta.get("run_timestamp", datetime.now().isoformat() + "Z")
        environment = meta.get("environment", "local")
        
        # Load segment metrics from UI artifacts
        segment_metrics = storage_service.load_ui_artifact("segment_metrics.json")
        if segment_metrics is None:
            warnings.append("missing: segment_metrics.json")
            segment_metrics = {}
        
        segments_total = len(segment_metrics)
        
        # Calculate peak density and rate across all segments
        peak_density = 0.0
        peak_rate = 0.0
        
        for seg_id, metrics in segment_metrics.items():
            if isinstance(metrics, dict):
                peak_density = max(peak_density, metrics.get("peak_density", 0.0))
                peak_rate = max(peak_rate, metrics.get("peak_rate", 0.0))
        
        # Calculate peak density LOS
        peak_density_los = calculate_peak_density_los(peak_density)
        
        # Load flags data from UI artifacts
        flags = storage_service.load_ui_artifact("flags.json")
        logger.info(f"Loaded flags data: {type(flags)}, length: {len(flags) if flags else 0}")
        if flags is None:
            warnings.append("missing: flags.json")
            flags = []
        
        # Handle both old dict format and new array format
        if isinstance(flags, dict):
            # Old format: {"flagged_segments": [...], "total_bins_flagged": N}
            segments_flagged = len(flags.get("flagged_segments", []))
            bins_flagged = flags.get("total_bins_flagged", 0)
        elif isinstance(flags, list):
            # New format: [{seg_id, type, severity, ...}]
            segments_flagged = len(flags)
            # Calculate bins_flagged from flags data
            bins_flagged = sum(f.get("flagged_bins", 0) for f in flags)
            logger.info(f"Calculated bins_flagged: {bins_flagged} from {len(flags)} flag entries")
        else:
            segments_flagged = 0
            bins_flagged = 0
        
        # Load runners data
        if not storage.exists(DATASET["runners"]):
            warnings.append("missing: runners.csv")
        
        runners_data = load_runners_data()
        total_runners = runners_data["total_runners"]
        cohorts = runners_data["cohorts"]
        
        # Load flow data from UI artifacts
        flow_data = storage_service.load_ui_artifact("flow.json")
        if flow_data is None:
            warnings.append("missing: flow.json")
            segments_overtaking = 0
            segments_copresence = 0
        else:
            # Calculate overtaking and co-presence from flow data
            segments_overtaking = 0
            segments_copresence = 0
            
            if isinstance(flow_data, list):
                for item in flow_data:
                    if item.get("overtaking_a", 0) > 0 or item.get("overtaking_b", 0) > 0:
                        segments_overtaking += 1
                    if item.get("copresence_a", 0) > 0 or item.get("copresence_b", 0) > 0:
                        segments_copresence += 1
        
        # Determine status
        status = "normal"
        if peak_density_los in ["E", "F"] or segments_flagged > 0:
            status = "action_required"
        
        # Build response
        summary = {
            "timestamp": timestamp,
            "environment": environment,
            "total_runners": total_runners,
            "cohorts": cohorts,
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
