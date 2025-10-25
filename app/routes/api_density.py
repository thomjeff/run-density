"""
API Routes for Density Data (RF-FE-002)

Provides density analysis endpoints for the density page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging
import pandas as pd
from pathlib import Path
import json

from app.storage import create_storage_from_env
from app.storage_service import get_storage_service
from app.storage_service import StorageService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()
storage_service = StorageService()


def load_density_metrics_from_bins():
    """
    Load and compute density metrics from bins.parquet.
    
    Returns:
        Dict with segment_id -> {utilization, worst_bin, bin_detail}
    """
    try:
        # Get latest run_id via StorageService (GCS-aware)
        from app.storage_service import get_storage_service
        storage = get_storage_service()
        run_id = storage.get_latest_run_id()
        
        if not run_id:
            return {}
        
        # Load bins.parquet (GCS-aware via StorageService)
        bins_df = storage.read_parquet(f"reports/{run_id}/bins.parquet")
        if bins_df is None:
            return {}
        
        # Normalize column names
        if "seg_id" in bins_df.columns and "segment_id" not in bins_df.columns:
            bins_df = bins_df.rename(columns={"seg_id": "segment_id"})
        
        # Group by segment and compute metrics
        segment_metrics = {}
        logger.info(f"Processing {len(bins_df)} bins for {bins_df['segment_id'].nunique()} segments")
        
        for seg_id, group in bins_df.groupby("segment_id"):
            # Utilization: average density across all bins
            utilization = group["density"].mean() if len(group) > 0 else 0.0
            
            # Worst bin: bin with highest density
            worst_bin_idx = group["density"].idxmax() if len(group) > 0 else None
            worst_bin = None
            if worst_bin_idx is not None:
                worst_bin_row = group.loc[worst_bin_idx]
                # Format time from t_start and t_end
                t_start = worst_bin_row.get("t_start", "")
                t_end = worst_bin_row.get("t_end", "")
                time_str = ""
                if t_start and t_end:
                    try:
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(t_start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(t_end.replace('Z', '+00:00'))
                        time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
                    except:
                        time_str = f"{t_start}-{t_end}"
                
                worst_bin = {
                    "bin_id": worst_bin_row.get("bin_id", "N/A"),
                    "density": float(worst_bin_row["density"]),
                    "rate": float(worst_bin_row["rate"]),
                    "start_km": float(worst_bin_row.get("start_km", 0.0)),
                    "end_km": float(worst_bin_row.get("end_km", 0.0)),
                    "time": time_str
                }
            
            # Bin detail: summary of all bins for this segment
            bin_detail = {
                "total_bins": len(group),
                "density_range": {
                    "min": float(group["density"].min()),
                    "max": float(group["density"].max()),
                    "mean": float(group["density"].mean())
                },
                "rate_range": {
                    "min": float(group["rate"].min()),
                    "max": float(group["rate"].max()),
                    "mean": float(group["rate"].mean())
                }
            }
            
            segment_metrics[seg_id] = {
                "utilization": float(utilization),
                "worst_bin": worst_bin,
                "bin_detail": bin_detail
            }
        
        logger.info(f"Computed density metrics for {len(segment_metrics)} segments")
        return segment_metrics
        
    except Exception as e:
        logger.error(f"Error loading density metrics from bins: {e}")
        return {}


@router.get("/api/density/segments")
async def get_density_segments():
    """
    Get density analysis data for all segments.
    
    Returns:
        Array of segment density records with:
        - seg_id, name, schema, active, peak_density, worst_los, peak_rate
        - utilization, flagged, worst_bin, watch, mitigation
    """
    try:
        # Load segment metrics from UI artifacts using storage service
        segment_metrics = {}
        try:
            raw_data = storage_service.load_ui_artifact("segment_metrics.json")
            if raw_data:
                # Handle different formats: direct dict vs {'items': [...]}
                if isinstance(raw_data, dict) and 'items' in raw_data:
                    # Convert items list to dict format expected by API
                    segment_metrics = {item['segment_id']: item for item in raw_data['items']}
                elif isinstance(raw_data, list):
                    # Array format from new artifact exporter
                    segment_metrics = {item['segment_id']: item for item in raw_data}
                elif isinstance(raw_data, dict):
                    # Direct dict format (from artifact exporter) - filter out summary fields
                    segment_metrics = {k: v for k, v in raw_data.items() if k not in ['peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins', 'overtaking_segments', 'co_presence_segments']}
                else:
                    # Fallback
                    segment_metrics = raw_data
                logger.info(f"Loaded {len(segment_metrics)} segment metrics from storage service")
            else:
                logger.warning("segment_metrics.json not found in storage service")
        except Exception as e:
            logger.warning(f"Could not load segment metrics from storage service: {e}")
        
        # Load segments geojson for labels using storage service
        segments_geojson = {}
        try:
            segments_geojson = storage_service.load_ui_artifact("segments.geojson")
            if not segments_geojson:
                logger.warning("segments.geojson not found in storage service")
        except Exception as e:
            logger.warning(f"Could not load segments geojson from storage service: {e}")
        
        # Build label lookup from geojson
        label_lookup = {}
        for feature in segments_geojson.get("features", []):
            props = feature.get("properties", {})
            seg_id = props.get("seg_id")
            if seg_id:
                label_lookup[seg_id] = {
                    "label": props.get("label", seg_id),
                    "length_km": props.get("length_km", 0.0),
                    "width_m": props.get("width_m", 0.0),
                    "direction": props.get("direction", ""),
                    "events": props.get("events", [])
                }
        
        # Load flags
        flagged_seg_ids = set()
        if storage.exists("flags.json"):
            try:
                flags = storage.read_json("flags.json")
                if isinstance(flags, list):
                    flagged_seg_ids = {f.get("seg_id") for f in flags if f.get("seg_id")}
                elif isinstance(flags, dict):
                    flagged_seg_ids = {f.get("seg_id") for f in flags.get("flagged_segments", []) if f.get("seg_id")}
            except Exception as e:
                logger.warning(f"Could not read flags: {e}")
        
        # Load density metrics from bins.parquet
        density_metrics = load_density_metrics_from_bins()
        
        
        # Build segments list
        segments_list = []
        for seg_id, metrics in segment_metrics.items():
            # Issue #308: Validate that metrics is a dictionary before calling .get()
            if not isinstance(metrics, dict):
                logger.warning(f"⚠️ Skipping invalid segment {seg_id}: {type(metrics).__name__}")
                continue
                
            label_info = label_lookup.get(seg_id, {})
            
            # Issue #285: Use operational schema tag instead of geometry metadata
            schema = _get_segment_operational_schema(seg_id, segment_metrics)
            
            # Events list
            events = label_info.get("events", [])
            events_str = ", ".join(events) if events else "N/A"
            
            # Get density metrics from bins.parquet
            bin_metrics = density_metrics.get(seg_id, {})
            utilization = bin_metrics.get("utilization", 0.0)
            worst_bin = bin_metrics.get("worst_bin")
            bin_detail = bin_metrics.get("bin_detail", {})
            
            # Format bin_detail for display
            bin_detail_display = "absent"
            if bin_detail and bin_detail.get("total_bins", 0) > 0:
                bin_detail_display = f"{bin_detail['total_bins']} bins"
            
            segment_record = {
                "seg_id": seg_id,
                "name": label_info.get("label", seg_id),
                "schema": schema,
                "active": metrics.get("active_window", "N/A"),
                "peak_density": metrics.get("peak_density", 0.0),
                "worst_los": metrics.get("worst_los", "Unknown"),
                "peak_rate": metrics.get("peak_rate", 0.0),
                "utilization": utilization,
                "flagged": seg_id in flagged_seg_ids,
                "worst_bin": worst_bin,  # Issue #286: Send raw object for frontend formatting
                "watch": metrics.get("worst_los") in ["D", "E", "F"],
                "mitigation": "Monitor" if seg_id in flagged_seg_ids else "None",
                "events": events_str,
                "bin_detail": bin_detail_display
            }
            
            segments_list.append(segment_record)
        
        # Sort by seg_id
        segments_list.sort(key=lambda x: x["seg_id"])
        
        response = JSONResponse(content=segments_list)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error generating density segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load density data: {str(e)}")


@router.get("/api/density/segment/{seg_id}")
async def get_density_segment_detail(seg_id: str):
    """
    Get detailed density analysis for a specific segment.
    
    Args:
        seg_id: Segment identifier
        
    Returns:
        Detailed segment record with heatmap availability
    """
    logger.info(f"=== UPDATED CODE LOADED === Processing segment detail for {seg_id}")
    try:
        # Load segment metrics from artifacts using storage service (same as segments API)
        segment_metrics = {}
        storage_service = get_storage_service()
        try:
            raw_data = storage_service.load_ui_artifact("segment_metrics.json")
            if raw_data and isinstance(raw_data, dict):
                # Direct dict format: keys are segment IDs, values are metrics
                segment_metrics = raw_data
                logger.info(f"Loaded {len(segment_metrics)} segment metrics from storage service")
            else:
                logger.warning("segment_metrics.json not found or invalid format")
        except Exception as e:
            logger.warning(f"Could not load segment metrics from storage service: {e}")
        
        if seg_id not in segment_metrics:
            raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found")
        
        metrics = segment_metrics[seg_id]
        
        # Load segments geojson for label using storage service
        label = seg_id
        length_km = 0.0
        width_m = 0.0
        direction = ""
        events = []
        
        try:
            segments_geojson = storage_service.load_ui_artifact("segments.geojson")
            if segments_geojson:
                for feature in segments_geojson.get("features", []):
                    props = feature.get("properties", {})
                    if props.get("seg_id") == seg_id:
                        label = props.get("label", seg_id)
                        length_km = props.get("length_km", 0.0)
                        width_m = props.get("width_m", 0.0)
                        direction = props.get("direction", "")
                        events = props.get("events", [])
                        break
        except Exception as e:
            logger.warning(f"Could not load segments geojson: {e}")
        
        # Check if flagged using storage service
        is_flagged = False
        try:
            flags = storage_service.load_ui_artifact("flags.json")
            if flags:
                if isinstance(flags, list):
                    is_flagged = any(f.get("seg_id") == seg_id for f in flags)
                elif isinstance(flags, dict):
                    is_flagged = any(f.get("seg_id") == seg_id for f in flags.get("flagged_segments", []))
        except Exception as e:
            logger.warning(f"Could not load flags: {e}")
        
        # Check for heatmap and caption
        heatmap_url = None
        caption = None
        
        try:
            from app.storage import create_storage_from_env
            # Use environment-aware storage for heatmap URL generation
            storage = create_storage_from_env()
            heatmap_url = storage.get_heatmap_signed_url(seg_id)
            logger.info(f"Heatmap URL for {seg_id}: {heatmap_url}")
        except Exception as e:
            logger.warning(f"Could not get heatmap URL for {seg_id}: {e}")
        
        try:
            captions = storage_service.load_ui_artifact("captions.json")
            if captions and seg_id in captions:
                caption = captions[seg_id].get("summary")
        except Exception as e:
            logger.warning(f"Could not load captions for {seg_id}: {e}")
        
        detail = {
            "seg_id": seg_id,
            "name": label,
            "schema": _get_segment_operational_schema(seg_id, segment_metrics),
            "active": metrics.get("active_window", "N/A"),
            "peak_density": metrics.get("peak_density", 0.0),
            "worst_los": metrics.get("worst_los", "Unknown"),
            "peak_rate": metrics.get("peak_rate", 0.0),
            "flagged": is_flagged,
            "events": ", ".join(events) if events else "N/A",
            "direction": direction,
            "length_km": length_km,
            "width_m": width_m,
            "heatmap_url": heatmap_url,
            "caption": caption,
            "bin_detail": "absent" if not heatmap_url else "available"
        }
        
        return JSONResponse(content=detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting segment detail for {seg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load segment detail: {str(e)}")


def _get_segment_operational_schema(seg_id: str, segment_metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    Get the operational schema tag for a specific segment.
    
    Issue #285: Returns operational schema tag (e.g., start_corral, on_course_open, on_course_narrow)
    instead of density data schema.
    
    Args:
        seg_id: Segment identifier
        segment_metrics: Dictionary of segment metrics
        
    Returns:
        String with operational schema tag
    """
    try:
        if seg_id in segment_metrics:
            metrics = segment_metrics[seg_id]
            # Issue #308: Validate that metrics is a dictionary before calling .get()
            if isinstance(metrics, dict):
                schema_tag = metrics.get("schema", "on_course_open")
                return schema_tag
            else:
                logger.warning(f"⚠️ Invalid metrics type for segment {seg_id}: {type(metrics).__name__}")
                return "on_course_open"  # Default fallback
        else:
            return "on_course_open"  # Default fallback
            
    except Exception as e:
        logger.warning(f"Could not get operational schema for {seg_id}: {e}")
        return "on_course_open"

