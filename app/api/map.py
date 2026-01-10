"""
Map API Module

This module provides API endpoints specifically for map visualization
as outlined in Issue #146 technical implementation strategy.

Endpoints:
- /api/segments.geojson - GeoJSON data for map segments
- /api/flow-bins - Bin-level flow data for visualization
- /api/export-bins - CSV/GeoJSON export functionality
"""

from __future__ import annotations
import json
import logging
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from app.bin_analysis import get_all_segment_bins, analyze_segment_bins, get_cache_stats
from app.geo_utils import generate_segments_geojson, generate_bins_geojson
from app.utils.constants import (
    DISTANCE_BIN_SIZE_KM,
    # DEFAULT_PACE_CSV and DEFAULT_SEGMENTS_CSV removed (Issue #553 Phase 6.1)
    # File paths now come from API request via analysis.json
    MAP_CENTER_LAT, MAP_CENTER_LON,
)
# DEFAULT_START_TIMES removed (Issue #512) - Start times must come from request
# Phase 3 cleanup: Removed get_global_cache_manager import (only used by removed cache endpoints)
# Phase 3 cleanup: app/cache_manager.py was removed entirely (unused, ~288 lines)
# from app.cache_manager import get_global_cache_manager
# map_data_generator.py removed in Phase 2B - fallback logic handles missing imports
# Issue #466 Step 2: Storage consolidated to app.storage

logger = logging.getLogger(__name__)

# Create router for map-specific endpoints
router = APIRouter(prefix="/api", tags=["map"])

# ============================================================================
# NEW ENDPOINTS FOR ISSUE #249: Map Bin-Level Visualization
# ============================================================================

@router.get("/map/manifest")
async def get_map_manifest():
    """
    Get map session metadata and configuration (Issue #249).
    
    Returns:
    - window_count: Total number of time windows
    - window_seconds: Duration of each window in seconds
    - segment_index: List of segments with metadata
    - lod: Level-of-detail zoom thresholds
    - Date and configuration metadata
    
    This endpoint provides everything the frontend needs to initialize
    the time slider and map layers.
    """
    try:
        # Load latest bin data to get window count
        import pandas as pd
        from pathlib import Path
        
        # Find latest bins.parquet file
        reports_dir = Path("reports")
        latest_date_dir = None
        if reports_dir.exists():
            date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
            for date_dir in date_dirs:
                bins_file = date_dir / "bins.parquet"
                if bins_file.exists():
                    latest_date_dir = date_dir
                    break
        
        if not latest_date_dir:
            raise HTTPException(status_code=404, detail="No bin data available. Generate density report first.")
        
        # Load bins to get window count and segment list
        bins_df = pd.read_parquet(latest_date_dir / "bins.parquet")
        
        # Calculate window count from unique time windows
        window_count = len(bins_df[['t_start', 't_end']].drop_duplicates())
        
        # Calculate window duration (in seconds)
        first_window = bins_df.iloc[0]
        t_start = pd.to_datetime(first_window['t_start'])
        t_end = pd.to_datetime(first_window['t_end'])
        window_seconds = int((t_end - t_start).total_seconds())
        
        from app.utils.run_id import get_latest_run_id
        from app.utils.run_id import get_runflow_root
        from app.config.loader import load_analysis_context

        run_id = get_latest_run_id()
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        analysis_context = load_analysis_context(run_path)
        segments_path = Path(analysis_context.segments_csv_path)

        if not segments_path.exists():
            raise HTTPException(status_code=404, detail=f"Segments metadata not found at {segments_path}")

        if segments_path.suffix == ".parquet":
            segments_df = pd.read_parquet(segments_path)
        else:
            segments_df = pd.read_csv(segments_path)
        
        # Build segment index
        segment_index = []
        for _, seg in segments_df.iterrows():
            segment_id = seg.get("segment_id") or seg.get("seg_id")
            if not segment_id:
                raise HTTPException(status_code=500, detail="Segments metadata missing segment_id")
            schema_key = seg.get("schema") or seg.get("schema_key")
            if not schema_key:
                raise HTTPException(status_code=500, detail=f"Segment {segment_id} missing schema")
            width_m = seg.get("width_m")
            if width_m is None:
                raise HTTPException(status_code=500, detail=f"Segment {segment_id} missing width_m")
            seg_label = seg.get("seg_label")
            if not seg_label:
                raise HTTPException(status_code=500, detail=f"Segment {segment_id} missing seg_label")
            segment_index.append({
                "segment_id": segment_id,
                "segment_label": seg_label,
                "schema_key": schema_key,
                "width_m": float(width_m)
            })
        
        # LOD thresholds (from ChatGPT's Issue #249 guidance)
        lod_thresholds = {
            "segments_only": 12,
            "flagged_bins": 14
        }
        
        # Get date from directory name
        date_str = latest_date_dir.name
        
        # Issue #254: Add rulebook version for consistency tracking
        try:
            from app.rulebook import version
            rb_version = version()
        except Exception:
            rb_version = "unknown"
        
        return JSONResponse(content={
            "ok": True,
            "date": date_str,
            "window_count": window_count,
            "window_seconds": window_seconds,
            "lod": lod_thresholds,
            "segments": segment_index,
            "rulebook_version": rb_version,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "source": "bins.parquet",
                "total_segments": len(segment_index),
                "rulebook_version": rb_version
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting map manifest: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map manifest: {e}")


@router.get("/map/segments")
async def get_map_segments():
    """
    Get segment corridors for map visualization (Issue #249 Phase 1.5).
    
    Returns segments as GeoJSON LineStrings with:
    - GPX centerline geometry
    - Segment metadata (label, schema, width)
    - Aggregated stats (peak density, worst window, etc.)
    
    Used for low-zoom overview and context layer at all zooms.
    """
    try:
        import pandas as pd
        from pathlib import Path
        from shapely.geometry import mapping
        
        # Find latest data
        reports_dir = Path("reports")
        latest_date_dir = None
        if reports_dir.exists():
            date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
            for date_dir in date_dirs:
                if (date_dir / "bins.parquet").exists():
                    latest_date_dir = date_dir
                    break
        
        if not latest_date_dir:
            raise HTTPException(status_code=404, detail="No segment data available")
        
        from app.utils.run_id import get_latest_run_id
        from app.utils.run_id import get_runflow_root
        from app.config.loader import load_analysis_context

        run_id = get_latest_run_id()
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        analysis_context = load_analysis_context(run_path)
        segments_path = Path(analysis_context.segments_csv_path)

        if not segments_path.exists():
            raise HTTPException(status_code=404, detail=f"Segments metadata not found at {segments_path}")

        segments_df = pd.read_csv(segments_path)
        
        # Load GPX centerlines
        try:
            from app.core.gpx.processor import load_all_courses, generate_segment_coordinates
            from app.io.loader import load_segments
        except ImportError:
            from gpx_processor import load_all_courses, generate_segment_coordinates
            from io.loader import load_segments
        
        events = analysis_context.analysis_config.get("events", [])
        if not events:
            raise HTTPException(status_code=500, detail="analysis.json missing events for GPX loading")
        gpx_paths = {}
        for event in events:
            event_name = event.get("name")
            if not event_name:
                raise HTTPException(status_code=500, detail="analysis.json events missing name for GPX loading")
            gpx_paths[event_name.lower()] = str(analysis_context.gpx_path(event_name))
        courses = load_all_courses(gpx_paths)
        
        # Convert to format for GPX processor
        segments_list = []
        for _, seg in segments_df.iterrows():
            seg_id = seg.get("seg_id")
            seg_label = seg.get("seg_label")
            if not seg_id:
                raise HTTPException(status_code=500, detail="Segments metadata missing seg_id")
            if not seg_label:
                raise HTTPException(status_code=500, detail=f"Segment {seg_id} missing seg_label")
            segments_list.append({
                "seg_id": seg_id,
                "segment_label": seg_label,
                "10k": seg.get('10k', seg.get('10K', 'n')),
                "half": seg.get('half', 'n'),
                "full": seg.get('full', 'n'),
                "10k_from_km": seg.get('10k_from_km') or seg.get('10K_from_km'),
                "10k_to_km": seg.get('10k_to_km') or seg.get('10K_to_km'),
                "half_from_km": seg.get('half_from_km'),
                "half_to_km": seg.get('half_to_km'),
                "full_from_km": seg.get('full_from_km'),
                "full_to_km": seg.get('full_to_km')
            })
        
        # Generate centerlines
        segments_with_coords = generate_segment_coordinates(courses, segments_list)
        
        logger.info(f"Generated {len(segments_with_coords)} segment centerlines")
        
        # Build GeoJSON features
        features = []
        for seg_coords in segments_with_coords:
            if not seg_coords.get('line_coords'):
                logger.warning(f"Segment {seg_coords.get('seg_id')}: No line_coords")
                continue
            if seg_coords.get('coord_issue'):
                logger.warning(f"Segment {seg_coords.get('seg_id')}: Coord issue - {seg_coords.get('error', 'unknown')}")
                continue
            
            seg_id = seg_coords['seg_id']
            seg_meta = segments_df[segments_df['seg_id'] == seg_id].iloc[0]
            
            # Convert coords to GeoJSON LineString
            coordinates = [list(coord) for coord in seg_coords['line_coords']]
            
            schema_key = seg_meta.get("schema") or seg_meta.get("schema_key")
            if not schema_key:
                raise HTTPException(status_code=500, detail=f"Segment {seg_id} missing schema")
            width_m = seg_meta.get("width_m")
            if width_m is None:
                raise HTTPException(status_code=500, detail=f"Segment {seg_id} missing width_m")
            feature = {
                "type": "Feature",
                "properties": {
                    "segment_id": seg_id,
                    "segment_label": seg_coords['segment_label'],
                    "schema_key": schema_key,
                    "width_m": float(width_m),
                    "from_km": seg_coords['from_km'],
                    "to_km": seg_coords['to_km'],
                    "length_km": seg_coords['to_km'] - seg_coords['from_km']
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            }
            features.append(feature)
        
        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count": len(features),
                "source": "gpx_processor"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting map segments: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map segments: {e}")


def _parse_bbox(bbox: str):
    """Parse bounding box string into Shapely geometry."""
    from shapely.geometry import box
    try:
        bbox_parts = bbox.split(",")
        if len(bbox_parts) != 4:
            raise ValueError
        minx, miny, maxx, maxy = map(float, bbox_parts)
        return box(minx, miny, maxx, maxy)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="bbox must be 'minX,minY,maxX,maxY'")


def _find_latest_bin_data_dir():
    """Find the latest directory containing bins.parquet."""
    from pathlib import Path
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return None
    
    date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
    for date_dir in date_dirs:
        bins_file = date_dir / "bins.parquet"
        if bins_file.exists():
            return date_dir
    return None


def _load_bin_geometries(data_dir):
    """Load bin geometries from bins.geojson.gz."""
    import json
    import gzip
    bin_geometries = {}
    
    try:
        bins_geojson_path = data_dir / "bins.geojson.gz"
        if bins_geojson_path.exists():
            with gzip.open(bins_geojson_path, 'rt', encoding='utf-8') as f:
                geojson_data = json.load(f)
                for feature in geojson_data.get('features', []):
                    props = feature.get('properties', {})
                    bin_id = props.get('bin_id')
                    geometry = feature.get('geometry')
                    if bin_id and geometry:
                        bin_geometries[bin_id] = geometry
            logger.info(f"Loaded {len(bin_geometries)} bin geometries from geojson.gz")
    except Exception as geom_error:
        logger.warning(f"Could not load bin geometries: {geom_error}")
    
    return bin_geometries


def _filter_bins_by_severity(window_bins, severity: str):
    """Filter bins by severity level."""
    severity_col = 'flag_severity' if 'flag_severity' in window_bins.columns else 'severity'
    
    if severity == "any":
        return window_bins, severity_col
    
    if severity_col in window_bins.columns:
        return window_bins[window_bins[severity_col] == severity], severity_col
    
    logger.warning("Severity filtering requested but severity column not in bins.parquet")
    return window_bins, severity_col


def _build_bin_feature(bin_row, window_idx: int, severity_col: str, bin_geometries: dict):
    """Build a GeoJSON feature from bin data."""
    import pandas as pd
    
    # Format times as HH:MM
    t_start = pd.to_datetime(bin_row['t_start'])
    t_end = pd.to_datetime(bin_row['t_end'])
    t_start_hhmm = t_start.strftime('%H:%M')
    t_end_hhmm = t_end.strftime('%H:%M')
    
    bin_id = bin_row['bin_id']
    
    return {
        "type": "Feature",
        "properties": {
            "segment_id": bin_row['segment_id'],
            "bin_id": bin_id,
            "start_km": float(bin_row['start_km']),
            "end_km": float(bin_row['end_km']),
            "window_idx": int(window_idx),
            "t_start_hhmm": t_start_hhmm,
            "t_end_hhmm": t_end_hhmm,
            "density": float(bin_row['density']),
            "rate": float(bin_row['rate']),
            "los_class": bin_row['los_class'],
            "severity": bin_row.get(severity_col, 'none'),
            "flag_reason": bin_row.get('flag_reason', 'none'),
            "rate_per_m_per_min": bin_row.get('rate_per_m_per_min', 0.0)
        },
        "geometry": bin_geometries.get(bin_id)
    }


@router.get("/map/bins")
async def get_map_bins(
    window_idx: int = Query(..., description="Time window index (0-based)"),
    bbox: str = Query(..., description="Bounding box: minX,minY,maxX,maxY (Web Mercator)"),
    severity: str = Query("any", description="Severity filter: any|watch|critical")
):
    """
    Get filtered bins for a specific time window and viewport (Issue #249).
    
    This endpoint returns bins as GeoJSON features with:
    - Static geometry (route-aligned polygons)
    - Dynamic properties for the requested window (density, rate, LOS, severity)
    
    Filtering:
    - window_idx: Only bins for this time window
    - bbox: Only bins intersecting the viewport
    - severity: Filter by operational severity
    
    Returns GeoJSON FeatureCollection with bin polygons.
    """
    import pandas as pd
    
    # Validate severity
    allowed_severity = {"any", "watch", "critical", "none"}
    if severity not in allowed_severity:
        raise HTTPException(status_code=400, detail=f"severity must be one of: {allowed_severity}")
    
    # Parse bounding box
    bbox_geom = _parse_bbox(bbox)
    
    # Find latest bin data
    latest_date_dir = _find_latest_bin_data_dir()
    if not latest_date_dir:
        raise HTTPException(status_code=404, detail="No bin data available")
    
    # Load bins.parquet
    bins_df = pd.read_parquet(latest_date_dir / "bins.parquet")
    
    # Filter by window_idx
    bins_df['t_start_dt'] = pd.to_datetime(bins_df['t_start'])
    min_time = bins_df['t_start_dt'].min()
    window_duration = pd.to_datetime(bins_df.iloc[0]['t_end']) - bins_df.iloc[0]['t_start_dt']
    bins_df['window_idx'] = ((bins_df['t_start_dt'] - min_time) / window_duration).astype(int)
    
    window_bins = bins_df[bins_df['window_idx'] == window_idx]
    
    if window_bins.empty:
        return JSONResponse(content={"type": "FeatureCollection", "features": []})
    
    # Load bin geometries
    bin_geometries = _load_bin_geometries(latest_date_dir)
    
    # Filter by severity
    window_bins, severity_col = _filter_bins_by_severity(window_bins, severity)
    
    # Build GeoJSON features
    features = [_build_bin_feature(bin_row, window_idx, severity_col, bin_geometries) 
                for _, bin_row in window_bins.iterrows()]
    
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "window_idx": window_idx,
            "count": len(features),
            "severity_filter": severity
        }
    })


class MapRequest(BaseModel):
    """Request model for map API endpoints."""
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    binSizeKm: Optional[float] = None

class FlowBinsRequest(BaseModel):
    """Request model for flow bins endpoint."""
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    segmentId: Optional[str] = None
    binSizeKm: Optional[float] = None


@router.get("/bins-data")
async def get_bins_data(
    forceRefresh: bool = Query(False, description="Force refresh by running new analysis"),
    startTimes: Optional[str] = Query(None, description="JSON string of start times (required if forceRefresh=true - Issue #512)")
):
    """
    Get bin-level visualization data for map display.
    
    This endpoint provides bin-level data for the map visualization:
    - Uses existing analysis data if available and forceRefresh=False
    - Runs new bin analysis if no data found or forceRefresh=True
    - Returns GeoJSON data for bin-level visualization
    """
    try:
        if forceRefresh:
            logger.info("Force refresh requested - running new bin analysis")
            # Issue #512: Start times must come from request, not constants
            if startTimes is None:
                raise HTTPException(
                    status_code=400,
                    detail="startTimes query parameter required when forceRefresh=true. (Issue #512)"
                )
            
            import json
            start_times = json.loads(startTimes)
            raise HTTPException(
                status_code=400,
                detail=(
                    "forceRefresh is no longer supported without analysis.json paths. "
                    "Provide a run-specific analysis.json and use the v2 pipeline."
                )
            )
            
            # Run new bin analysis (removed: forceRefresh requires analysis.json paths)
        else:
            # map_data_generator.py removed in Phase 2B - return empty data
            logger.info("No existing bin data found - returning empty data")
            return JSONResponse(content={
                "ok": True,
                "source": "placeholder",
                "timestamp": datetime.now().isoformat(),
                "geojson": {
                    "type": "FeatureCollection",
                    "features": []
                },
                "metadata": {
                    "total_segments": 0,
                    "analysis_type": "bins",
                    "bin_size_km": DISTANCE_BIN_SIZE_KM,
                    "message": "No bin data available - run analysis first"
                }
            })
        
    except Exception as e:
        logger.error(f"Error getting bins data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting bins data: {e}")


@router.post("/flow-bins")
async def get_flow_bins(request: FlowBinsRequest):
    """
    Get bin-level flow data for visualization.
    
    This endpoint provides detailed bin-level data including:
    - Density metrics per bin
    - Overtake counts per bin
    - Co-presence data per bin
    - RSI scores and convergence points
    """
    try:
        if request.segmentId:
            # Get data for specific segment
            segment_bins = analyze_segment_bins(
                segment_id=request.segmentId,
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=request.startTimes,
                bin_size_km=request.binSizeKm
            )
            
            # Convert to API response format
            bins_data = []
            for bin_data in segment_bins.bins:
                bins_data.append({
                    "bin_index": bin_data.bin_index,
                    "start_km": bin_data.start_km,
                    "end_km": bin_data.end_km,
                    "density": bin_data.density,
                    "density_level": bin_data.density_level,
                    "overtakes": bin_data.overtakes,
                    "co_presence": bin_data.co_presence,
                    "rsi_score": bin_data.rsi_score,
                    "convergence_point": bin_data.convergence_point,
                    "centroid_lat": bin_data.centroid_lat,
                    "centroid_lon": bin_data.centroid_lon
                })
            
            return JSONResponse(content={
                "ok": True,
                "segment_id": request.segmentId,
                "segment_label": segment_bins.segment_label,
                "bins": bins_data,
                "total_bins": segment_bins.total_bins,
                "bin_size_m": segment_bins.bin_size_m,
                "generated_at": segment_bins.generated_at.isoformat()
            })
        else:
            # Get data for all segments
            all_bins = get_all_segment_bins(
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=request.startTimes,
                bin_size_km=request.binSizeKm
            )
            
            # Convert to API response format
            segments_data = {}
            for segment_id, segment_bins in all_bins.items():
                bins_data = []
                for bin_data in segment_bins.bins:
                    bins_data.append({
                        "bin_index": bin_data.bin_index,
                        "start_km": bin_data.start_km,
                        "end_km": bin_data.end_km,
                        "density": bin_data.density,
                        "density_level": bin_data.density_level,
                        "overtakes": bin_data.overtakes,
                        "co_presence": bin_data.co_presence,
                        "rsi_score": bin_data.rsi_score,
                        "convergence_point": bin_data.convergence_point,
                        "centroid_lat": bin_data.centroid_lat,
                        "centroid_lon": bin_data.centroid_lon
                    })
                
                segments_data[segment_id] = {
                    "segment_label": segment_bins.segment_label,
                    "bins": bins_data,
                    "total_bins": segment_bins.total_bins,
                    "bin_size_m": segment_bins.bin_size_m,
                    "generated_at": segment_bins.generated_at.isoformat()
                }
            
            return JSONResponse(content={
                "ok": True,
                "segments": segments_data,
                "total_segments": len(segments_data)
            })
            
    except Exception as e:
        logger.error(f"Error getting flow bins: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting flow bins: {e}")

@router.post("/export-bins")
async def export_bins(
    request: MapRequest,
    format: str = Query("csv", description="Export format: csv or geojson")
):
    """
    Export bin-level data in CSV or GeoJSON format.
    
    This endpoint provides export functionality for bin-level data
    as specified in Issue #146 acceptance criteria.
    """
    try:
        # Get all segment bin data
        all_bins = get_all_segment_bins(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            bin_size_km=request.binSizeKm
        )
        
        if format.lower() == "geojson":
            # Generate GeoJSON export
            from app.config.loader import load_analysis_context
            from app.utils.run_id import get_latest_run_id, get_runflow_root
            run_id = get_latest_run_id()
            if not run_id:
                raise HTTPException(status_code=404, detail="No run_id available for analysis.json lookup.")
            analysis_context = load_analysis_context(get_runflow_root() / run_id)
            geojson = generate_bins_geojson(all_bins, analysis_context=analysis_context)
            return JSONResponse(content=geojson)
        else:
            # Generate CSV export
            csv_data = []
            for segment_id, segment_bins in all_bins.items():
                for bin_data in segment_bins.bins:
                    # Flatten overtakes and co-presence data
                    overtakes_str = "; ".join([f"{k}:{v}" for k, v in bin_data.overtakes.items()])
                    co_presence_str = "; ".join([f"{k}:{v}" for k, v in bin_data.co_presence.items()])
                    
                    csv_data.append({
                        "segment_id": segment_id,
                        "bin_index": bin_data.bin_index,
                        "start_f": bin_data.start_km,
                        "end_f": bin_data.end_km,
                        "density": bin_data.density,
                        "overtakes": overtakes_str,
                        "co_presence": co_presence_str,
                        "rsi": bin_data.rsi_score,
                        "convergence_point": bin_data.convergence_point
                    })
            
            return JSONResponse(content={
                "ok": True,
                "format": "csv",
                "data": csv_data,
                "total_records": len(csv_data)
            })
            
    except Exception as e:
        logger.error(f"Error exporting bins: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting bins: {e}")

@router.get("/map-config")
async def get_map_config():
    """
    Get map configuration for frontend.
    
    This endpoint provides configuration constants for the frontend
    to avoid hardcoded values in JavaScript.
    """
    try:
        from app.utils.constants import (
            MAP_CENTER_LAT, MAP_CENTER_LON, MAP_DEFAULT_ZOOM,
            MAP_TILE_URL, MAP_TILE_ATTRIBUTION, MAP_MAX_ZOOM,
            MAP_DENSITY_THRESHOLDS, MAP_ZONE_COLORS
        )
        
        # Issue #512: startTimes removed from config - must come from request
        return JSONResponse(content={
            "ok": True,
            "config": {
                # Issue #616: File paths come from analysis.json (no hardcoded defaults)
                "mapCenter": [MAP_CENTER_LAT, MAP_CENTER_LON],
                "mapZoom": MAP_DEFAULT_ZOOM,
                "tileUrl": MAP_TILE_URL,
                "tileAttribution": MAP_TILE_ATTRIBUTION,
                "maxZoom": MAP_MAX_ZOOM,
                "densityThresholds": MAP_DENSITY_THRESHOLDS,
                "zoneColors": MAP_ZONE_COLORS
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting map config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map config: {e}")

@router.get("/map-status")
async def get_map_status():
    """
    Get map system status and cache information.
    
    This endpoint provides status information for the map system,
    including cache statistics and system health.
    """
    try:
        cache_stats = get_cache_stats()
        
        return JSONResponse(content={
            "ok": True,
            "status": "healthy",
            "cache_stats": cache_stats,
            "bin_size_km": DISTANCE_BIN_SIZE_KM,
            "endpoints": [
                "/api/segments.geojson",
                "/api/flow-bins", 
                "/api/export-bins",
                "/api/map-status",
                "/api/map-config"
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting map status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map status: {e}")

# Phase 3 cleanup: Removed unused endpoints (not used by frontend or E2E tests):
# - /historical-trends - Only 3.4% coverage for analyze_historical_trends(), never called
# - /compare-segments - Only 2.9% coverage for compare_segments(), never called
# - /export-advanced - Only 5.3% coverage for export_bin_data(), never called
# - POST /api/clear-cache - Admin endpoint, not used
# - GET /api/cache-management - Admin endpoint, not used
# - POST /api/invalidate-segment - Admin endpoint, not used
# - GET /api/cache-status - Admin endpoint, not used
# - GET /api/cached-analysis - Admin endpoint, not used

# REMOVED: /api/force-refresh endpoint - causes Cloud Run timeouts
# Maps are now visualization-only and read from existing reports

# Phase 3 cleanup: Removed broken /api/map-data endpoint
# - Called undefined get_storage_service() function (NameError at runtime)
# - Not used by frontend (frontend uses /api/segments/geojson from app/routes/api_segments.py)
# - Maps are visualization-only and read from existing reports via other endpoints

# Phase 3 cleanup: Removed unused cache management endpoints (not used by frontend or E2E tests):
# - POST /api/clear-cache - Admin endpoint, not used
# - GET /api/cache-management - Admin endpoint, not used
# - POST /api/invalidate-segment - Admin endpoint, not used
# - GET /api/cache-status - Admin endpoint, not used
# - GET /api/cached-analysis - Admin endpoint, not used
# - POST /api/cleanup-cache - Admin endpoint, not used

# Phase 3 cleanup: Removed POST /api/cleanup-cache endpoint
# - Admin endpoint, not used by frontend or E2E tests
