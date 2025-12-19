"""
Bin Geometry Generation for Map Visualization

Generates route-aligned bin polygons from segment centerlines for map rendering.
Follows Issue #249 specification: linear-reference cut + buffer approach.

Key Principles (from ChatGPT guidance):
1. Work in metric CRS (UTM 19N, EPSG:32619) for accurate buffering
2. Reproject to Web Mercator (EPSG:3857) for web display
3. Route-aligned polygons only (no grid squares)
4. Time windows do not change geometry (same polygons, different colors)
5. Geometry is static, properties are time-varying

Dependencies: shapely, pyproj, geopandas
"""

import math
from typing import List, Dict, Tuple, Optional
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import transform
import pyproj
# Phase 3 cleanup: Removed unused imports (gpd, pd) - only used by removed functions

# Coordinate Reference Systems
WGS84 = pyproj.CRS("EPSG:4326")  # GPS coordinates (lat/lon)
UTM_19N = pyproj.CRS("EPSG:32619")  # UTM Zone 19N (Fredericton, NB area)
WEB_MERCATOR = pyproj.CRS("EPSG:3857")  # Web map standard

# Transformers
wgs84_to_utm = pyproj.Transformer.from_crs(WGS84, UTM_19N, always_xy=True)
utm_to_webmerc = pyproj.Transformer.from_crs(UTM_19N, WEB_MERCATOR, always_xy=True)
wgs84_to_webmerc = pyproj.Transformer.from_crs(WGS84, WEB_MERCATOR, always_xy=True)


def linear_reference_cut(
    centerline_coords: List[Tuple[float, float]],  # (lon, lat) in WGS84
    start_m: float,
    end_m: float
) -> Optional[List[Tuple[float, float]]]:
    """
    Cut a segment of a centerline by linear distance (meters).
    
    Args:
        centerline_coords: List of (lon, lat) coordinates in WGS84
        start_m: Start distance in meters from beginning of centerline
        end_m: End distance in meters from beginning of centerline
    
    Returns:
        List of (lon, lat) coordinates for the cut segment, or None if invalid
    """
    if not centerline_coords or len(centerline_coords) < 2:
        return None
    
    # Convert to UTM for accurate distance measurement
    utm_line = LineString([
        wgs84_to_utm.transform(lon, lat) for lon, lat in centerline_coords
    ])
    
    # Linear referencing: cut by distance
    if start_m >= utm_line.length or end_m <= 0:
        return None
    
    # Clamp to valid range
    start_m = max(0, start_m)
    end_m = min(utm_line.length, end_m)
    
    if start_m >= end_m:
        return None
    
    # Cut the line
    # shapely's interpolate: point at distance along line
    # We need to collect points between start_m and end_m
    cut_coords = []
    
    # Add start point
    start_point = utm_line.interpolate(start_m)
    cut_coords.append((start_point.x, start_point.y))
    
    # Add intermediate vertices that fall within [start_m, end_m]
    cumulative_distance = 0.0
    for i in range(1, len(utm_line.coords)):
        prev = Point(utm_line.coords[i-1])
        curr = Point(utm_line.coords[i])
        segment_length = prev.distance(curr)
        
        if cumulative_distance + segment_length >= start_m and cumulative_distance <= end_m:
            # This vertex is within our range
            if cumulative_distance >= start_m:  # Don't duplicate start point
                cut_coords.append(utm_line.coords[i])
        
        cumulative_distance += segment_length
        
        if cumulative_distance > end_m:
            break
    
    # Add end point
    end_point = utm_line.interpolate(end_m)
    if len(cut_coords) == 0 or (end_point.x, end_point.y) != cut_coords[-1]:
        cut_coords.append((end_point.x, end_point.y))
    
    # Convert back to WGS84
    transformer_back = pyproj.Transformer.from_crs(UTM_19N, WGS84, always_xy=True)
    wgs84_coords = [
        transformer_back.transform(x, y) for x, y in cut_coords
    ]
    
    return wgs84_coords if len(wgs84_coords) >= 2 else None


def buffer_to_polygon(
    centerline_coords: List[Tuple[float, float]],  # (lon, lat) in WGS84
    width_m: float,
    mitre_limit: float = 5.0
) -> Optional[Polygon]:
    """
    Buffer a centerline to create a polygon corridor.
    
    Args:
        centerline_coords: List of (lon, lat) coordinates in WGS84
        width_m: Total width of corridor in meters
        mitre_limit: Limit for sharp corners (default: 5.0)
    
    Returns:
        Polygon in Web Mercator (EPSG:3857), or None if invalid
    """
    if not centerline_coords or len(centerline_coords) < 2:
        return None
    
    # Convert to UTM for accurate buffering
    utm_line = LineString([
        wgs84_to_utm.transform(lon, lat) for lon, lat in centerline_coords
    ])
    
    # Buffer by half the width (radius)
    buffer_distance = width_m / 2.0
    polygon_utm = utm_line.buffer(
        buffer_distance,
        cap_style=2,  # flat cap
        join_style=2,  # mitre join
        mitre_limit=mitre_limit
    )
    
    # Convert to Web Mercator for web display
    polygon_webmerc = transform(utm_to_webmerc.transform, polygon_utm)
    
    return polygon_webmerc


def generate_bin_polygon(
    segment_centerline_coords: List[Tuple[float, float]],  # (lon, lat) in WGS84
    bin_start_km: float,
    bin_end_km: float,
    segment_width_m: float
) -> Optional[Polygon]:
    """
    Generate a single bin polygon from segment centerline.
    
    Args:
        segment_centerline_coords: Segment centerline coordinates (lon, lat) in WGS84
        bin_start_km: Bin start position in kilometers
        bin_end_km: Bin end position in kilometers
        segment_width_m: Segment width in meters
    
    Returns:
        Polygon in Web Mercator (EPSG:3857), or None if invalid
    """
    # Convert km to meters
    start_m = bin_start_km * 1000.0
    end_m = bin_end_km * 1000.0
    
    # Step 1: Linear-reference cut
    bin_centerline = linear_reference_cut(
        segment_centerline_coords,
        start_m,
        end_m
    )
    
    if not bin_centerline:
        return None
    
    # Step 2: Buffer to polygon
    polygon = buffer_to_polygon(
        bin_centerline,
        segment_width_m
    )
    
    return polygon


# Phase 3 cleanup: Removed unused functions (not imported anywhere):
# - generate_bin_polygons_for_segment() - Only used by generate_all_bin_polygons (also unused)
# - generate_all_bin_polygons() - Not imported
# - validate_bin_polygon() - Not imported
# - export_to_geojson() - Not imported

