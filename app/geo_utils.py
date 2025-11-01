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

try:
    from .bin_analysis import SegmentBinData, BinData
    from .constants import DISTANCE_BIN_SIZE_KM, METERS_PER_KM
except ImportError:
    from bin_analysis import SegmentBinData, BinData
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

def generate_bins_geojson(segments_data: Dict[str, SegmentBinData]) -> Dict[str, Any]:
    """
    Generate GeoJSON for individual bins using real segment coordinates from GPX data.
    
    Args:
        segments_data: Dictionary mapping segment_id to SegmentBinData
    
    Returns:
        GeoJSON FeatureCollection with bin features
    """
    features = []
    
    # Load real segment coordinates from GPX data
    try:
        from .gpx_processor import load_all_courses, generate_segment_coordinates
        from .io.loader import load_segments
        
        # Load GPX courses
        courses = load_all_courses("data")
        
        # Load segments data to get segment definitions
        segments_df = load_segments("data/segments.csv")
        segments_list = segments_df.to_dict('records')
        
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
        logger.warning(f"Could not load GPX coordinates: {e}. Using fallback coordinates.")
        segment_coords_lookup = {}
    
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
            # Fallback to default coordinates
            logger.warning(f"No real coordinates found for segment {segment_id}, using defaults")
            start_lat, start_lon = DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON
            end_lat, end_lon = DEFAULT_CENTER_LAT + 0.01, DEFAULT_CENTER_LON + 0.01
            segment_length_km = 1.0
        
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

def validate_geojson(geojson: Dict[str, Any]) -> bool:
    """
    Validate GeoJSON structure.
    
    Args:
        geojson: GeoJSON data to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check basic structure
        if geojson.get("type") != "FeatureCollection":
            return False
        
        if "features" not in geojson:
            return False
        
        # Check features
        for feature in geojson["features"]:
            if feature.get("type") != "Feature":
                return False
            
            if "geometry" not in feature or "properties" not in feature:
                return False
            
            geometry = feature["geometry"]
            if geometry.get("type") not in ["Point", "LineString", "Polygon"]:
                return False
            
            if "coordinates" not in geometry:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"GeoJSON validation error: {e}")
        return False

def get_geojson_bounds(geojson: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """
    Calculate bounding box for GeoJSON data.
    
    Args:
        geojson: GeoJSON data
    
    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat) or None if invalid
    """
    try:
        if not validate_geojson(geojson):
            return None
        
        min_lon = min_lat = float('inf')
        max_lon = max_lat = float('-inf')
        
        for feature in geojson["features"]:
            geometry = feature["geometry"]
            coordinates = geometry["coordinates"]
            
            if geometry["type"] == "Point":
                lon, lat = coordinates
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
            elif geometry["type"] == "LineString":
                for lon, lat in coordinates:
                    min_lon = min(min_lon, lon)
                    max_lon = max(max_lon, lon)
                    min_lat = min(min_lat, lat)
                    max_lat = max(max_lat, lat)
            elif geometry["type"] == "Polygon":
                for ring in coordinates:
                    for lon, lat in ring:
                        min_lon = min(min_lon, lon)
                        max_lon = max(max_lon, lon)
                        min_lat = min(min_lat, lat)
                        max_lat = max(max_lat, lat)
        
        if min_lon == float('inf'):
            return None
        
        return (min_lon, min_lat, max_lon, max_lat)
        
    except Exception as e:
        logger.error(f"Error calculating GeoJSON bounds: {e}")
        return None
