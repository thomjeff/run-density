"""
API Routes for Density Data (RF-FE-002)

Provides density analysis endpoints for the density page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging
import pandas as pd
from pathlib import Path
import json

# Issue #466 Step 2: Storage consolidated to app.storage


# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)


def load_density_metrics_from_bins(run_id: Optional[str] = None, day: Optional[str] = None):
    """
    Load and compute density metrics from bins.parquet.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped paths
    
    Returns:
        Dict with segment_id -> {utilization, worst_bin, bin_detail}
    """
    try:
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        if not run_id:
            run_id = get_latest_run_id()
        
        storage = create_runflow_storage(run_id)
        
        # Resolve day for day-scoped paths
        if day:
            selected_day, _ = resolve_selected_day(run_id, day)
            bins_path = f"{selected_day}/bins/bins.parquet"
        else:
            bins_path = "bins/bins.parquet"
        
        # Load bins.parquet from runflow structure
        bins_df = storage.read_parquet(bins_path)
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
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Failed to parse time range '{t_start}-{t_end}': {e}. Using raw values.")
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


def _load_and_normalize_segment_metrics(storage_service) -> Dict[str, Dict[str, Any]]:
    """Load segment metrics from storage and normalize to dict format."""
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
    return segment_metrics


def _build_label_lookup_from_geojson(segments_geojson: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build label lookup dictionary from segments geojson."""
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
    return label_lookup


def _enrich_label_lookup_from_csv(label_lookup: Dict[str, Dict[str, Any]], segments_csv_path: str = "data/segments.csv") -> Dict[str, Dict[str, Any]]:
    """Enrich label lookup with data from segments.csv (e.g., length_km if missing from geojson)."""
    try:
        from app.io.loader import load_segments
        from pathlib import Path
        
        segments_df = load_segments(segments_csv_path)
        
        for _, row in segments_df.iterrows():
            seg_id = str(row.get("seg_id", "")).strip()
            if not seg_id:
                continue
            
            # Initialize if not present
            if seg_id not in label_lookup:
                label_lookup[seg_id] = {
                    "label": seg_id,
                    "length_km": 0.0,
                    "width_m": 0.0,
                    "direction": "",
                    "events": []
                }
            
            # Update length_km from CSV if missing or 0 in geojson
            # Try event-specific length columns (full_length, half_length, 10k_length, etc.)
            if label_lookup[seg_id].get("length_km", 0.0) == 0.0:
                # Try full_length first, then half_length, then 10k_length
                length_km = None
                for col in ["full_length", "half_length", "10k_length", "elite_length", "open_length"]:
                    if col in row and pd.notna(row[col]) and row[col] > 0:
                        length_km = float(row[col])
                        break
                
                # Fallback: calculate from full_to_km - full_from_km
                if length_km is None or length_km == 0.0:
                    full_from = row.get("full_from_km")
                    full_to = row.get("full_to_km")
                    if pd.notna(full_from) and pd.notna(full_to):
                        length_km = float(full_to) - float(full_from)
                
                if length_km and length_km > 0:
                    label_lookup[seg_id]["length_km"] = length_km
            
            # Update other fields if missing
            if not label_lookup[seg_id].get("label") or label_lookup[seg_id]["label"] == seg_id:
                name = row.get("name")
                if pd.notna(name):
                    label_lookup[seg_id]["label"] = str(name)
            
            if label_lookup[seg_id].get("width_m", 0.0) == 0.0:
                width_m = row.get("width_m")
                if pd.notna(width_m):
                    label_lookup[seg_id]["width_m"] = float(width_m)
        
        logger.info(f"Enriched label lookup with {len(segments_df)} segments from CSV")
    except Exception as e:
        logger.warning(f"Could not enrich label lookup from CSV: {e}")
    
    return label_lookup


def _load_flagged_segment_ids(storage_service) -> set:
    """Load flagged segment IDs from flags.json."""
    flagged_seg_ids = set()
    try:
        flags = storage_service.load_ui_artifact("flags.json")
        if flags:
            if isinstance(flags, list):
                flagged_seg_ids = {f.get("seg_id") for f in flags if f.get("seg_id")}
            elif isinstance(flags, dict):
                flagged_seg_ids = {f.get("seg_id") for f in flags.get("flagged_segments", []) if f.get("seg_id")}
            logger.info(f"Loaded {len(flagged_seg_ids)} flagged segments from flags.json")
        else:
            logger.warning("flags.json not found in storage service")
    except Exception as e:
        logger.warning(f"Could not load flags: {e}")
    return flagged_seg_ids


def _format_bin_detail_display(bin_detail: Dict[str, Any]) -> str:
    """Format bin detail for display."""
    if bin_detail and bin_detail.get("total_bins", 0) > 0:
        return f"{bin_detail['total_bins']} bins"
    return "absent"


def _build_segment_record(
    seg_id: str,
    metrics: Dict[str, Any],
    label_lookup: Dict[str, Dict[str, Any]],
    flagged_seg_ids: set,
    density_metrics: Dict[str, Any],
    segment_metrics: Dict[str, Dict[str, Any]],
    segments_csv_path: str
) -> Dict[str, Any]:
    """Build segment record from metrics and metadata."""
    label_info = label_lookup.get(seg_id, {})
    
    # Issue #285: Use operational schema tag instead of geometry metadata
    schema = _get_segment_operational_schema(seg_id, segment_metrics, segments_csv_path)
    
    # Events list
    events = label_info.get("events", [])
    events_str = ", ".join(events) if events else "N/A"
    
    # Get density metrics from bins.parquet
    bin_metrics = density_metrics.get(seg_id, {})
    utilization = bin_metrics.get("utilization", 0.0)
    worst_bin = bin_metrics.get("worst_bin")
    bin_detail = bin_metrics.get("bin_detail", {})
    
    return {
        "seg_id": seg_id,
        "name": label_info.get("label", seg_id),
        "schema": schema,
        "length_km": label_info.get("length_km", 0.0),  # Issue #652: Add segment length
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
        "bin_detail": _format_bin_detail_display(bin_detail)
    }


def _get_segments_csv_path_for_run(run_id: str) -> str:
    from app.utils.run_id import get_runflow_root
    from app.core.v2.analysis_config import get_segments_file

    runflow_root = get_runflow_root()
    run_path = runflow_root / run_id
    return get_segments_file(run_path=run_path)


@router.get("/api/density/segments")
async def get_density_segments(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get density analysis data for all segments.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
    
    Returns:
        Array of segment density records with:
        - seg_id, name, schema, active, peak_density, worst_los, peak_rate
        - utilization, flagged, worst_bin, watch, mitigation
    """
    try:
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Load segment metrics from day-scoped path (Issue #580: Updated path to metrics/ subdirectory)
        segment_metrics_raw = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json")
        if not segment_metrics_raw:
            return JSONResponse(
                content={"detail": "No segment metrics available"},
                status_code=404
            )
        
        # Extract per-segment data (skip summary fields)
        segment_metrics = {k: v for k, v in segment_metrics_raw.items() 
                          if isinstance(v, dict) and k not in ["peak_density", "peak_rate", "segments_with_flags", "flagged_bins"]}
        
        # Load segments geojson for labels from day-scoped path (Issue #580: Updated path to geospatial/ subdirectory)
        segments_geojson = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson")
        if not segments_geojson:
            logger.warning(f"segments.geojson not found for day {selected_day}")
        
        # Build label lookup
        label_lookup = _build_label_lookup_from_geojson(segments_geojson or {})
        
        # Issue #652: Enrich with data from segments.csv (especially length_km)
        # Issue #616: Require segments_csv_path from analysis.json (no hardcoded fallback)
        try:
            segments_csv_path_for_api = _get_segments_csv_path_for_run(run_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"segments_csv_path not found in analysis.json for run {run_id}: {e}"
            )
        
        label_lookup = _enrich_label_lookup_from_csv(label_lookup, segments_csv_path_for_api)
        
        # Load flags from day-scoped path (Issue #580: Updated path to metrics/ subdirectory)
        flags_data = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
        flagged_seg_ids = set()
        if flags_data and isinstance(flags_data, list):
            flagged_seg_ids = {flag.get("segment_id") or flag.get("seg_id") for flag in flags_data}
        
        # Load density metrics from bins.parquet (day-scoped)
        density_metrics = load_density_metrics_from_bins(run_id, selected_day)
        
        # Build segments list
        segments_list = []
        for seg_id, metrics in segment_metrics.items():
            # Issue #308: Validate that metrics is a dictionary before calling .get()
            if not isinstance(metrics, dict):
                logger.warning(f"⚠️ Skipping invalid segment {seg_id}: {type(metrics).__name__}")
                continue
            
            segment_record = _build_segment_record(
                seg_id, metrics, label_lookup, flagged_seg_ids,
                density_metrics, segment_metrics, segments_csv_path_for_api
            )
            segments_list.append(segment_record)
        
        # Sort by seg_id
        segments_list.sort(key=lambda x: x["seg_id"])
        
        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "segments": segments_list
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating density segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load density data: {str(e)}")


def _load_segment_metrics_from_storage(storage_service) -> Dict[str, Dict[str, Any]]:
    """Load segment metrics from storage service."""
    segment_metrics = {}
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
    return segment_metrics


def _load_segment_metadata_from_geojson(storage_service, seg_id: str) -> Dict[str, Any]:
    """Load segment metadata (label, length, width, direction, events) from geojson."""
    metadata = {
        "label": seg_id,
        "length_km": 0.0,
        "width_m": 0.0,
        "direction": "",
        "events": []
    }
    
    try:
        segments_geojson = storage_service.load_ui_artifact("segments.geojson")
        if segments_geojson:
            for feature in segments_geojson.get("features", []):
                props = feature.get("properties", {})
                if props.get("seg_id") == seg_id:
                    metadata["label"] = props.get("label", seg_id)
                    metadata["length_km"] = props.get("length_km", 0.0)
                    metadata["width_m"] = props.get("width_m", 0.0)
                    metadata["direction"] = props.get("direction", "")
                    metadata["events"] = props.get("events", [])
                    break
    except Exception as e:
        logger.warning(f"Could not load segments geojson: {e}")
    
    return metadata


def _check_segment_flagged(storage_service, seg_id: str) -> bool:
    """Check if segment is flagged using storage service."""
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
    return is_flagged


def _load_heatmap_and_caption(storage_service, seg_id: str):
    """Load heatmap URL and caption for segment."""
    heatmap_url = None
    caption = None
    
    try:
        # Use StorageService for heatmap URL generation
        storage = get_storage_service()
        logger.info(f"Storage mode: {storage.mode}, bucket: {storage.bucket}")
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
    
    return heatmap_url, caption


def _build_segment_detail_response(
    seg_id: str,
    metrics: Dict[str, Any],
    metadata: Dict[str, Any],
    is_flagged: bool,
    heatmap_url: Optional[str],
    caption: Optional[str],
    segment_metrics: Dict[str, Dict[str, Any]],
    segments_csv_path: str
) -> Dict[str, Any]:
    """Build segment detail response dictionary."""
    return {
        "seg_id": seg_id,
        "name": metadata["label"],
        "schema": _get_segment_operational_schema(seg_id, segment_metrics, segments_csv_path),
        "active": metrics.get("active_window", "N/A"),
        "peak_density": metrics.get("peak_density", 0.0),
        "worst_los": metrics.get("worst_los", "Unknown"),
        "peak_rate": metrics.get("peak_rate", 0.0),
        "flagged": is_flagged,
        "events": ", ".join(metadata["events"]) if metadata["events"] else "N/A",
        "direction": metadata["direction"],
        "length_km": metadata["length_km"],
        "width_m": metadata["width_m"],
        "heatmap_url": heatmap_url,
        "caption": caption,
        "bin_detail": "absent" if not heatmap_url else "available"
    }


@router.get("/api/density/segment/{seg_id}")
async def get_density_segment_detail(
    seg_id: str,
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get detailed density analysis for a specific segment.
    
    Args:
        seg_id: Segment identifier
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
        
    Returns:
        Detailed segment record with heatmap availability
    """
    logger.info(f"=== UPDATED CODE LOADED === Processing segment detail for {seg_id}")
    try:
        # Issue #460 Phase 5: Use runflow structure
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Load segment metrics from day-scoped path (Issue #580: Updated path to metrics/ subdirectory)
        segment_metrics_raw = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json")
        if not segment_metrics_raw:
            raise HTTPException(status_code=404, detail="Segment metrics not found")
        
        # Extract per-segment data
        segment_metrics = {k: v for k, v in segment_metrics_raw.items() 
                          if isinstance(v, dict) and k not in ["peak_density", "peak_rate", "segments_with_flags", "flagged_bins"]}
        
        if seg_id not in segment_metrics:
            raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found")
        
        metrics = segment_metrics[seg_id]
        
        # Issue #616: Require segments_csv_path from analysis.json (no hardcoded fallback)
        try:
            segments_csv_path_for_api = _get_segments_csv_path_for_run(run_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"segments_csv_path not found in analysis.json for run {run_id}: {e}"
            )

        # Load segment metadata from day-scoped geojson
        segments_geojson = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson")
        metadata = {}
        if segments_geojson and "features" in segments_geojson:
            for feature in segments_geojson["features"]:
                props = feature.get("properties", {})
                if props.get("seg_id") == seg_id:
                    metadata = props
                    break
        
        # Check if flagged from day-scoped path
        flags_data = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
        is_flagged = False
        if flags_data and isinstance(flags_data, list):
            is_flagged = any(f.get("segment_id") == seg_id or f.get("seg_id") == seg_id for f in flags_data)
        
        # Load heatmap URL and caption from day-scoped captions.json (Issue #580: Updated path to visualizations/ subdirectory)
        captions = storage.read_json(f"{selected_day}/ui/visualizations/captions.json")
        heatmap_url = None
        caption = ""
        if captions and seg_id in captions:
            caption_data = captions[seg_id]
            # Build heatmap URL for day-scoped runflow structure (Issue #580: Updated path to visualizations/)
            # Files are at: runflow/<run_id>/<day>/ui/visualizations/<seg_id>.png
            # Mounted as: /heatmaps -> /app/runflow
            # URL path: /heatmaps/<run_id>/<day>/ui/visualizations/<seg_id>.png
            heatmap_url = f"/heatmaps/{run_id}/{selected_day}/ui/visualizations/{seg_id}.png"
            caption = caption_data.get("summary", "")
        
        # Issue #596: Load density metrics (utilization, worst_bin) from bins.parquet
        density_metrics = load_density_metrics_from_bins(run_id, selected_day)
        bin_metrics = density_metrics.get(seg_id, {})
        utilization = bin_metrics.get("utilization", 0.0)
        worst_bin = bin_metrics.get("worst_bin")
        
        # Build detail response
        detail = _build_segment_detail_response(
            seg_id, metrics, metadata, is_flagged, heatmap_url,
            caption, segment_metrics, segments_csv_path_for_api
        )
        
        # Issue #596: Add utilization and worst_bin to detail response
        detail["utilization"] = utilization
        detail["worst_bin"] = worst_bin
        
        return JSONResponse(content=detail)
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting segment detail for {seg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load segment detail: {str(e)}")


def _get_segment_operational_schema(
    seg_id: str,
    segment_metrics: Dict[str, Dict[str, Any]],
    segments_csv_path: str
) -> str:
    """
    Get the operational schema tag for a specific segment.
    
    Issue #285: Returns operational schema tag (e.g., start_corral, on_course_open, on_course_narrow)
    instead of density data schema.
    
    Issue #648: Uses schema_resolver.resolve_schema() as SSOT (loads from segments.csv).
    Prefers schema from segment_metrics if available (should already be resolved from CSV),
    otherwise resolves directly from CSV.
    
    Args:
        seg_id: Segment identifier
        segment_metrics: Dictionary of segment metrics (may contain pre-resolved schema)
        
    Returns:
        String with operational schema tag
    """
    from app.schema_resolver import resolve_schema as resolve_schema_from_csv
    
    try:
        # Try to get schema from segment_metrics first (should already be resolved from CSV)
        if seg_id in segment_metrics:
            metrics = segment_metrics[seg_id]
            # Issue #308: Validate that metrics is a dictionary before calling .get()
            if isinstance(metrics, dict):
                schema_tag = metrics.get("schema", None)
                if schema_tag:
                    return schema_tag
            else:
                logger.warning(f"⚠️ Invalid metrics type for segment {seg_id}: {type(metrics).__name__}")
        
        # Fallback: resolve directly from CSV (Issue #648: CSV is SSOT)
        return resolve_schema_from_csv(seg_id, None, segments_csv_path)
            
    except Exception as e:
        logger.warning(f"Could not get operational schema for {seg_id}: {e}")
        # Fallback: resolve directly from CSV (Issue #648: CSV is SSOT)
        return resolve_schema_from_csv(seg_id, None, segments_csv_path)
