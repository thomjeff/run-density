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

from app.common.config import load_rulebook, load_reporting

# Issue #283: Import SSOT for flagging logic parity
from app import flagging as ssot_flagging

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage_service singleton (not needed)


def load_runners_data() -> Dict[str, Any]:
    """
    Load runners data and aggregate by event.
    
    Returns:
        Dict with total_runners and cohorts data
    """
    try:
        # Read runners.csv directly from local filesystem (Docker image includes data/)
        import pandas as pd
        from app.utils.constants import DEFAULT_START_TIMES
        df = pd.read_csv("data/runners.csv")
        
        # Count runners by event
        cohorts = {}
        for event in df['event'].unique():
            event_runners = df[df['event'] == event]
            # Get start time from constants (in minutes, convert to HH:MM format)
            start_minutes = DEFAULT_START_TIMES.get(event, 0)
            hours = start_minutes // 60
            minutes = start_minutes % 60
            start_time = f"{hours:02d}:{minutes:02d}"
            
            cohorts[event] = {
                "start": start_time,
                "count": len(event_runners)
            }
        
        total_runners = len(df)
        
        return {
            "total_runners": total_runners,
            "cohorts": cohorts
        }
        
    except Exception as e:
        logger.warning(f"Could not read runners.csv: {e}")
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
        # Use StorageService to load flow data
        storage = get_storage_service()
        flow_data = storage.load_ui_artifact("flow.json")
        
        if not flow_data:
            logger.warning("flow.json not found in storage")
            return {"segments_overtaking": 0, "segments_copresence": 0}
        
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
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        from app.utils.metadata import get_latest_run_id
        from app.storage import create_runflow_storage
        
        run_id = get_latest_run_id()
        storage = create_runflow_storage(run_id)
        
        # Track missing files for warnings
        warnings = []
        
        # Load meta data
        meta = _load_ui_artifact_safe(storage, "ui/meta.json", warnings) or {}
        timestamp = meta.get("run_timestamp", datetime.now().isoformat() + "Z")
        environment = meta.get("environment", "local")
        
        # Load segment metrics
        segment_metrics = _load_ui_artifact_safe(storage, "ui/segment_metrics.json", warnings) or {}
        segments_total = len(segment_metrics)
        
        # Calculate peak density and rate
        peak_density, peak_rate = _calculate_peak_metrics(segment_metrics)
        peak_density_los = calculate_peak_density_los(peak_density)
        
        # Load flags data
        flags = _load_ui_artifact_safe(storage, "ui/flags.json", warnings)
        if flags is None:
            flags = []
        
        logger.info(f"Loaded flags data: {type(flags)}, length: {len(flags) if flags else 0}")
        segments_flagged, bins_flagged = _calculate_flags_metrics(flags)
        
        # Load runners data (from local data/ directory)
        from pathlib import Path
        if not Path("data/runners.csv").exists():
            warnings.append("missing: runners.csv")
        
        runners_data = load_runners_data()
        total_runners = runners_data["total_runners"]
        cohorts = runners_data["cohorts"]
        
        # Issue #304: Load flow metrics from segment_metrics.json
        # Summary-level metrics are now in segment_metrics.json alongside per-segment data
        segments_overtaking = 0
        segments_copresence = 0
        
        # Extract from segment_metrics if available
        if segment_metrics:
            segments_overtaking = segment_metrics.get("overtaking_segments", 0)
            segments_copresence = segment_metrics.get("co_presence_segments", 0)
            logger.info(f"Loaded flow metrics from segment_metrics.json: overtaking={segments_overtaking}, co-presence={segments_copresence}")
        else:
            logger.warning("segment_metrics.json not available, flow metrics will be zero")
        
        # Determine status
        status = "normal"
        if peak_density_los in ["E", "F"] or segments_flagged > 0:
            status = "action_required"
        
        # Build response
        summary = {
            "run_id": run_id,  # Issue #470: Include run_id in response
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
