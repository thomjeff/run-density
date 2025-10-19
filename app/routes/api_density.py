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

from app.storage import create_storage_from_env, load_latest_run_id

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


def load_density_metrics_from_bins():
    """
    Load and compute density metrics from bins.parquet.
    
    Returns:
        Dict with segment_id -> {utilization, worst_bin, bin_detail}
    """
    try:
        # Get latest run_id
        latest_path = Path("artifacts/latest.json")
        if not latest_path.exists():
            return {}
        
        with open(latest_path) as f:
            latest = json.load(f)
        run_id = latest.get("run_id")
        if not run_id:
            return {}
        
        # Load bins.parquet
        bins_path = Path(f"reports/{run_id}/bins.parquet")
        if not bins_path.exists():
            logger.warning(f"bins.parquet not found at {bins_path}")
            return {}
        
        bins_df = pd.read_parquet(bins_path)
        
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
        # Load segment metrics from artifacts
        segment_metrics = {}
        try:
            run_id = load_latest_run_id(storage)
            if run_id and storage.exists("segment_metrics.json"):
                segment_metrics = storage.read_json("segment_metrics.json")
            else:
                logger.warning("segment_metrics.json not found")
        except Exception as e:
            logger.warning(f"Could not load segment metrics: {e}")
        
        # Load segments geojson for labels
        segments_geojson = {}
        try:
            if run_id and storage.exists("segments.geojson"):
                segments_geojson = storage.read_json("segments.geojson")
            else:
                logger.warning("segments.geojson not found")
        except Exception as e:
            logger.warning(f"Could not load segments geojson: {e}")
        
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
            label_info = label_lookup.get(seg_id, {})
            
            # Build schema string (e.g., "0.9 km × 5.0 m")
            length = label_info.get("length_km", 0.0)
            width = label_info.get("width_m", 0.0)
            schema = f"{length:.1f} km × {width:.1f} m" if length > 0 else "N/A"
            
            # Events list
            events = label_info.get("events", [])
            events_str = ", ".join(events) if events else "N/A"
            
            # Get density metrics from bins.parquet
            bin_metrics = density_metrics.get(seg_id, {})
            utilization = bin_metrics.get("utilization", 0.0)
            worst_bin = bin_metrics.get("worst_bin")
            bin_detail = bin_metrics.get("bin_detail", {})
            
            # Format worst_bin for display
            worst_bin_display = "N/A"
            if worst_bin:
                time_str = worst_bin.get('time', '')
                if time_str:
                    worst_bin_display = f"Bin {worst_bin.get('bin_id', 'N/A')} {time_str} ({worst_bin.get('density', 0.0):.3f})"
                else:
                    worst_bin_display = f"Bin {worst_bin.get('bin_id', 'N/A')} ({worst_bin.get('density', 0.0):.3f})"
            
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
                "worst_bin": worst_bin_display,
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
    try:
        # Load segment metrics from artifacts
        segment_metrics = {}
        try:
            run_id = load_latest_run_id(storage)
            if run_id and storage.exists("segment_metrics.json"):
                segment_metrics = storage.read_json("segment_metrics.json")
        except Exception as e:
            logger.warning(f"Could not load segment metrics: {e}")
        
        if seg_id not in segment_metrics:
            raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found")
        
        metrics = segment_metrics[seg_id]
        
        # Load segments geojson for label
        label = seg_id
        length_km = 0.0
        width_m = 0.0
        direction = ""
        events = []
        
        try:
            if run_id and storage.exists("segments.geojson"):
                segments_geojson = storage.read_json("segments.geojson")
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
        
        # Check if flagged
        is_flagged = False
        try:
            if run_id and storage.exists("flags.json"):
                flags = storage.read_json("flags.json")
                if isinstance(flags, list):
                    is_flagged = any(f.get("seg_id") == seg_id for f in flags)
                elif isinstance(flags, dict):
                    is_flagged = any(f.get("seg_id") == seg_id for f in flags.get("flagged_segments", []))
        except Exception as e:
            logger.warning(f"Could not load flags: {e}")
        
        # Check for heatmap (if we add heatmap export later)
        heatmap_url = None
        # Future: check if artifacts/<run_id>/ui/heatmaps/<seg_id>.png exists
        
        detail = {
            "seg_id": seg_id,
            "name": label,
            "schema": f"{length_km:.1f} km × {width_m:.1f} m" if length_km > 0 else "N/A",
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
            "bin_detail": "absent" if not heatmap_url else "available"
        }
        
        return JSONResponse(content=detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting segment detail for {seg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load segment detail: {str(e)}")

