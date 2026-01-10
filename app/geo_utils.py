"""
GeoJSON Utilities Module

This module provides utilities for generating GeoJSON data
for map visualization as outlined in Issue #146.

Features:
- Generate GeoJSON for segments with bin-level data
- Generate GeoJSON for individual bins
- Handle coordinate transformations and projections
- Support for different map projections and formats
"""

from __future__ import annotations
import logging
import math
from typing import Dict, List, Any, Optional, Tuple

from app.bin_analysis import SegmentBinData, BinData
from app.utils.constants import DISTANCE_BIN_SIZE_KM, METERS_PER_KM

logger = logging.getLogger(__name__)

# Default map center (Fredericton, NB)
DEFAULT_CENTER_LAT = 45.9620
DEFAULT_CENTER_LON = -66.6500

def calculate_bin_centroid(
    segment_start_lat: float,
    segment_start_lon: float,
    segment_end_lat: float,
    segment_end_lon: float,
    bin_start_km: float,
    bin_end_km: float,
    segment_length_km: float,
    line_coords: Optional[List[Tuple[float, float]]] = None
) -> Tuple[float, float]:
    """
    Calculate the centroid coordinates for a bin within a segment.
    
    Args:
        segment_start_lat: Starting latitude of the segment
        segment_start_lon: Starting longitude of the segment
        segment_end_lat: Ending latitude of the segment
        segment_end_lon: Ending longitude of the segment
        bin_start_km: Starting kilometer of the bin
        bin_end_km: Ending kilometer of the bin
        segment_length_km: Total length of the segment in km
        line_coords: Optional list of coordinates along the segment path
    
    Returns:
        Tuple of (latitude, longitude) for the bin centroid
    """
    if segment_length_km <= 0:
        return segment_start_lat, segment_start_lon
    
    # Calculate position along the segment (0.0 to 1.0)
    bin_center_km = (bin_start_km + bin_end_km) / 2.0
    position_ratio = bin_center_km / segment_length_km
    
    # If we have detailed line coordinates, use them for more accurate positioning
    if line_coords and len(line_coords) > 2:
        # Find the coordinate point closest to our bin center position
        target_index = int(position_ratio * (len(line_coords) - 1))
        target_index = max(0, min(target_index, len(line_coords) - 1))
        
        # Get the coordinate at the target position
        lon, lat = line_coords[target_index]
        
        # Check for NaN values and provide fallback
        if math.isnan(lat) or math.isnan(lon):
            logger.warning(f"NaN coordinates detected in line_coords[{target_index}], using fallback")
            lat = segment_start_lat + (segment_end_lat - segment_start_lat) * position_ratio
            lon = segment_start_lon + (segment_end_lon - segment_start_lon) * position_ratio
        
        return lat, lon
    else:
        # Fallback to simple linear interpolation
        lat = segment_start_lat + (segment_end_lat - segment_start_lat) * position_ratio
        lon = segment_start_lon + (segment_end_lon - segment_start_lon) * position_ratio
        
        # Check for NaN values and provide default
        if math.isnan(lat) or math.isnan(lon):
            logger.warning(f"NaN coordinates detected in interpolation, using defaults")
            lat, lon = DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON
        
        return lat, lon

def generate_segment_geometry(
    segment_id: str,
    segment_label: str,
    start_lat: float = DEFAULT_CENTER_LAT,
    start_lon: float = DEFAULT_CENTER_LON,
    end_lat: Optional[float] = None,
    end_lon: Optional[float] = None,
    segment_length_km: float = 1.0
) -> Dict[str, Any]:
    """
    Generate GeoJSON geometry for a segment.
    
    For now, this creates a simple line geometry. In a real implementation,
    this would use actual course GPS coordinates.
    """
    if end_lat is None:
        end_lat = start_lat + 0.01  # Small offset for demo
    if end_lon is None:
        end_lon = start_lon + 0.01  # Small offset for demo
    
    return {
        "type": "LineString",
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat]
        ]
    }

def generate_bin_geometry(
    segment_start_lat: float,
    segment_start_lon: float,
    segment_end_lat: float,
    segment_end_lon: float,
    bin_start_km: float,
    bin_end_km: float,
    segment_length_km: float,
    bin_size_m: float,
    line_coords: Optional[List[Tuple[float, float]]] = None
) -> Dict[str, Any]:
    """
    Generate GeoJSON geometry for a bin.
    
    Creates a rectangular polygon representing the bin area.
    """
    # Calculate bin center
    center_lat, center_lon = calculate_bin_centroid(
        segment_start_lat, segment_start_lon,
        segment_end_lat, segment_end_lon,
        bin_start_km, bin_end_km, segment_length_km,
        line_coords
    )
    
    # Calculate bin width in degrees (approximate)
    # This is a simplified calculation - in practice, you'd use proper projection
    bin_width_deg = (bin_size_m / METERS_PER_KM) * 0.01  # Rough conversion
    
    # Create rectangular polygon
    half_width = bin_width_deg / 2
    
    return {
        "type": "Polygon",
        "coordinates": [[
            [center_lon - half_width, center_lat - half_width],
            [center_lon + half_width, center_lat - half_width],
            [center_lon + half_width, center_lat + half_width],
            [center_lon - half_width, center_lat + half_width],
            [center_lon - half_width, center_lat - half_width]
        ]]
    }

def generate_segments_geojson(segments_data: Dict[str, SegmentBinData]) -> Dict[str, Any]:
    """
    Generate GeoJSON for segments with bin-level data.
    
    Args:
        segments_data: Dictionary mapping segment_id to SegmentBinData
    
    Returns:
        GeoJSON FeatureCollection with segment features
    """
    features = []
    
    for segment_id, segment_bins in segments_data.items():
        # Generate segment geometry (simplified for now)
        geometry = generate_segment_geometry(
            segment_id=segment_id,
            segment_label=segment_bins.segment_label
        )
        
        # Calculate segment properties
        total_density = sum(bin_data.density for bin_data in segment_bins.bins)
        avg_density = total_density / len(segment_bins.bins) if segment_bins.bins else 0.0
        
        # Count convergence points
        convergence_points = sum(1 for bin_data in segment_bins.bins if bin_data.convergence_point)
        
        # Calculate total overtakes
        total_overtakes = {}
        for bin_data in segment_bins.bins:
            for event_pair, count in bin_data.overtakes.items():
                total_overtakes[event_pair] = total_overtakes.get(event_pair, 0) + count
        
        # Create feature properties
        properties = {
            "seg_id": segment_id,
            "segment_label": segment_bins.segment_label,
            "total_bins": segment_bins.total_bins,
            "bin_size_m": segment_bins.bin_size_m,
            "avg_density": round(avg_density, 3),
            "convergence_points": convergence_points,
            "total_overtakes": total_overtakes,
            "generated_at": segment_bins.generated_at.isoformat()
        }
        
        # Add bin-level summary data
        bin_summary = []
        for bin_data in segment_bins.bins:
            bin_summary.append({
                "bin_index": bin_data.bin_index,
                "start_km": bin_data.start_km,
                "end_km": bin_data.end_km,
                "density": round(bin_data.density, 3),
                "density_level": bin_data.density_level,
                "rsi_score": round(bin_data.rsi_score, 3),
                "convergence_point": bin_data.convergence_point
            })
        
        properties["bins"] = bin_summary
        
        # Create feature
        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        }
        
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "total_segments": len(features),
            "generated_at": segments_data[list(segments_data.keys())[0]].generated_at.isoformat() if segments_data else None
        }
    }

def generate_bins_geojson(segments_data: Dict[str, SegmentBinData], analysis_context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Generate GeoJSON for individual bins using real segment coordinates from GPX data.
    
    Issue #616: Accept analysis_context to resolve paths instead of hardcoded defaults.
    
    Args:
        segments_data: Dictionary mapping segment_id to SegmentBinData
        analysis_context: Analysis context with resolved data_files paths.
    
    Returns:
        GeoJSON FeatureCollection with bin features
    """
    features = []
    
    # Load real segment coordinates from GPX data
    try:
        from app.core.gpx.processor import load_all_courses, generate_segment_coordinates
        from app.io.loader import load_segments

        if not analysis_context:
            raise ValueError("analysis_context is required for generate_bins_geojson.")
        segments_csv_path = getattr(analysis_context, "segments_csv_path", None)
        if not segments_csv_path:
            raise ValueError(
                "analysis_context.segments_csv_path is required for generate_bins_geojson."
            )

        events = analysis_context.analysis_config.get("events", [])
        if not events:
            raise ValueError("analysis.json missing events for GPX loading in generate_bins_geojson.")
        gpx_paths = {}
        for event in events:
            event_name = event.get("name")
            if not event_name:
                raise ValueError("analysis.json events missing name for GPX loading in generate_bins_geojson.")
            gpx_paths[event_name.lower()] = str(analysis_context.gpx_path(event_name))

        # Load GPX courses
        courses = load_all_courses(gpx_paths)

        # Load segments data to get segment definitions
        segments_df = load_segments(segments_csv_path)
        segments_list = []
        for _, seg in segments_df.iterrows():
            seg_id = seg.get("seg_id")
            seg_label = seg.get("seg_label")
            if not seg_id:
                raise ValueError("segments.csv missing seg_id for generate_bins_geojson.")
            if not seg_label:
                raise ValueError(f"Segment {seg_id} missing seg_label for generate_bins_geojson.")
            segments_list.append({
                "seg_id": seg_id,
                "segment_label": seg_label,
                "10k": seg.get("10k", seg.get("10K", "n")),
                "half": seg.get("half", "n"),
                "full": seg.get("full", "n"),
                "10k_from_km": seg.get("10k_from_km") or seg.get("10K_from_km"),
                "10k_to_km": seg.get("10k_to_km") or seg.get("10K_to_km"),
                "half_from_km": seg.get("half_from_km"),
                "half_to_km": seg.get("half_to_km"),
                "full_from_km": seg.get("full_from_km"),
                "full_to_km": seg.get("full_to_km"),
                "direction": seg.get("direction"),
                "width_m": seg.get("width_m"),
            })

        # Generate real coordinates for all segments
        segments_with_coords = generate_segment_coordinates(courses, segments_list)

        # Create a lookup dictionary for segment coordinates
        segment_coords_lookup = {}
        for seg in segments_with_coords:
            if seg.get("line_coords") and len(seg["line_coords"]) >= 2:
                segment_coords_lookup[seg["seg_id"]] = {
                    "line_coords": seg["line_coords"],
                    "from_km": seg["from_km"],
                    "to_km": seg["to_km"]
                }

        logger.info(f"Loaded coordinates for {len(segment_coords_lookup)} segments")

    except Exception as e:
        logger.error(f"Could not load GPX coordinates for bin geojson: {e}")
        raise
    
    for segment_id, segment_bins in segments_data.items():
        # Get real coordinates for this segment
        segment_coords = segment_coords_lookup.get(segment_id)
        
        if segment_coords and segment_coords["line_coords"]:
            # Use real segment coordinates
            line_coords = segment_coords["line_coords"]
            from_km = segment_coords["from_km"]
            to_km = segment_coords["to_km"]
            segment_length_km = to_km - from_km
            
            # Calculate segment start and end points
            start_lon, start_lat = line_coords[0]
            end_lon, end_lat = line_coords[-1]
            
            logger.info(f"Using real coordinates for segment {segment_id}: {len(line_coords)} points, {segment_length_km:.2f}km")
            
        else:
            raise ValueError(f"No real coordinates found for segment {segment_id} in GPX data.")
        
        # Generate bin features
        for bin_data in segment_bins.bins:
            # Calculate bin centroid using real segment coordinates
            center_lat, center_lon = calculate_bin_centroid(
                start_lat, start_lon, end_lat, end_lon,
                bin_data.start_km, bin_data.end_km, segment_length_km,
                line_coords if segment_coords else None
            )
            
            # Generate bin geometry using real segment coordinates
            geometry = generate_bin_geometry(
                start_lat, start_lon, end_lat, end_lon,
                bin_data.start_km, bin_data.end_km, segment_length_km,
                segment_bins.bin_size_m,
                line_coords if segment_coords else None
            )
            
            # Create bin properties with NaN safety checks
            properties = {
                "segment_id": segment_id,
                "segment_label": segment_bins.segment_label,
                "bin_index": bin_data.bin_index,
                "start_km": bin_data.start_km,
                "end_km": bin_data.end_km,
                "density": round(bin_data.density, 3) if not math.isnan(bin_data.density) else 0.0,
                "density_level": bin_data.density_level,
                "overtakes": bin_data.overtakes,
                "co_presence": bin_data.co_presence,
                "rsi_score": round(bin_data.rsi_score, 3) if not math.isnan(bin_data.rsi_score) else 0.0,
                "convergence_point": bin_data.convergence_point,
                "centroid_lat": round(center_lat, 6) if not math.isnan(center_lat) else round(DEFAULT_CENTER_LAT, 6),
                "centroid_lon": round(center_lon, 6) if not math.isnan(center_lon) else round(DEFAULT_CENTER_LON, 6)
            }
            
            # Create feature
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties
            }
            
            features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "total_bins": len(features),
            "generated_at": segments_data[list(segments_data.keys())[0]].generated_at.isoformat() if segments_data else None
        }
    }

# Phase 3 cleanup: Removed unused functions (not imported anywhere):
# - validate_geojson() - Only 5.0% coverage, only used by get_geojson_bounds (also unused)
# - get_geojson_bounds() - Only 2.9% coverage, never imported or called
