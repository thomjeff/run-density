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
import geopandas as gpd
import pandas as pd

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


def generate_bin_polygons_for_segment(
    segment_id: str,
    segment_centerline_coords: List[Tuple[float, float]],
    bins_df: pd.DataFrame,
    segment_width_m: float
) -> gpd.GeoDataFrame:
    """
    Generate bin polygons for a single segment.
    
    Args:
        segment_id: Segment identifier (e.g., "A1")
        segment_centerline_coords: Segment centerline coordinates (lon, lat)
        bins_df: DataFrame of bins for this segment (from bins.parquet)
        segment_width_m: Segment width in meters
    
    Returns:
        GeoDataFrame with bin polygons and properties
    """
    geometries = []
    bin_ids = []
    start_kms = []
    end_kms = []
    
    # Group by unique spatial bins (start_km, end_km)
    # Bins repeat across time windows, we only need one polygon per spatial bin
    spatial_bins = bins_df[['start_km', 'end_km']].drop_duplicates()
    
    for _, bin_row in spatial_bins.iterrows():
        start_km = bin_row['start_km']
        end_km = bin_row['end_km']
        
        polygon = generate_bin_polygon(
            segment_centerline_coords,
            start_km,
            end_km,
            segment_width_m
        )
        
        if polygon and polygon.is_valid:
            geometries.append(polygon)
            bin_ids.append(f"{segment_id}:{start_km:.3f}-{end_km:.3f}")
            start_kms.append(start_km)
            end_kms.append(end_km)
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({
        'segment_id': [segment_id] * len(geometries),
        'bin_id': bin_ids,
        'start_km': start_kms,
        'end_km': end_kms
    }, geometry=geometries, crs=WEB_MERCATOR)
    
    return gdf


def generate_all_bin_polygons(
    segments_df: pd.DataFrame,  # From segments.csv/parquet
    bins_df: pd.DataFrame,      # From bins.parquet
    segment_geometries: Dict[str, List[Tuple[float, float]]]  # From gpx_processor
) -> gpd.GeoDataFrame:
    """
    Generate bin polygons for all segments.
    
    Args:
        segments_df: DataFrame with segment metadata (segment_id, seg_label, width_m, etc.)
        bins_df: DataFrame with all bins (from bins.parquet)
        segment_geometries: Dict mapping segment_id to centerline coords (lon, lat)
    
    Returns:
        GeoDataFrame with all bin polygons
    """
    all_gdfs = []
    
    for _, segment in segments_df.iterrows():
        segment_id = segment['segment_id']
        width_m = float(segment.get('width_m', 5.0))  # Default to 5m if missing
        
        # Get centerline geometry
        centerline_coords = segment_geometries.get(segment_id)
        if not centerline_coords:
            print(f"⚠️  No centerline geometry for segment {segment_id}, skipping")
            continue
        
        # Get bins for this segment
        segment_bins = bins_df[bins_df['segment_id'] == segment_id]
        if segment_bins.empty:
            print(f"⚠️  No bins for segment {segment_id}, skipping")
            continue
        
        # Generate polygons
        gdf = generate_bin_polygons_for_segment(
            segment_id,
            centerline_coords,
            segment_bins,
            width_m
        )
        
        if not gdf.empty:
            all_gdfs.append(gdf)
            print(f"✅ Generated {len(gdf)} bin polygons for {segment_id}")
    
    # Combine all segments
    if all_gdfs:
        result = gpd.GeoDataFrame(pd.concat(all_gdfs, ignore_index=True), crs=WEB_MERCATOR)
        return result
    else:
        # Return empty GeoDataFrame with correct schema
        return gpd.GeoDataFrame({
            'segment_id': [],
            'bin_id': [],
            'start_km': [],
            'end_km': []
        }, geometry=[], crs=WEB_MERCATOR)


def validate_bin_polygon(
    polygon: Polygon,
    expected_length_m: float,
    expected_width_m: float,
    centerline_coords: List[Tuple[float, float]],
    tolerance: float = 0.15
) -> Tuple[bool, List[str]]:
    """
    Validate a bin polygon against guardrails from Issue #249.
    
    Guardrails (must pass):
    1. Polygon centroid within corridor buffer
    2. area_m² ≈ (length_m × width_m) ± tolerance
    3. Polygon is valid (no self-intersections)
    
    Args:
        polygon: Polygon in Web Mercator
        expected_length_m: Expected bin length in meters
        expected_width_m: Expected bin width in meters
        centerline_coords: Centerline coords (lon, lat) for centroid check
        tolerance: Area tolerance (default: 15%)
    
    Returns:
        Tuple of (is_valid: bool, issues: List[str])
    """
    issues = []
    
    # Check 1: Polygon is valid
    if not polygon.is_valid:
        issues.append("Polygon is not valid (self-intersecting or degenerate)")
        return False, issues
    
    # Check 2: Area validation
    # Convert to UTM for accurate area measurement
    transformer_to_utm = pyproj.Transformer.from_crs(WEB_MERCATOR, UTM_19N, always_xy=True)
    polygon_utm = transform(transformer_to_utm.transform, polygon)
    
    actual_area_m2 = polygon_utm.area
    expected_area_m2 = expected_length_m * expected_width_m
    
    if expected_area_m2 > 0:
        area_ratio = actual_area_m2 / expected_area_m2
        if area_ratio < (1.0 - tolerance) or area_ratio > (1.0 + tolerance):
            issues.append(
                f"Area mismatch: actual={actual_area_m2:.1f}m², "
                f"expected={expected_area_m2:.1f}m² (ratio={area_ratio:.2f})"
            )
    
    # Check 3: Centroid within corridor buffer
    centroid = polygon.centroid
    
    # Convert centerline to UTM and buffer
    utm_centerline = LineString([
        wgs84_to_utm.transform(lon, lat) for lon, lat in centerline_coords
    ])
    corridor_buffer = utm_centerline.buffer(expected_width_m / 2.0 + 10.0)  # +10m margin
    
    # Convert centroid to UTM
    transformer_webmerc_to_utm = pyproj.Transformer.from_crs(WEB_MERCATOR, UTM_19N, always_xy=True)
    centroid_utm = transform(transformer_webmerc_to_utm.transform, centroid)
    
    if not corridor_buffer.contains(centroid_utm):
        issues.append("Centroid not within corridor buffer (floating square detected)")
    
    is_valid = len(issues) == 0
    return is_valid, issues


def export_to_geojson(
    gdf: gpd.GeoDataFrame,
    output_path: str,
    compress: bool = True
) -> None:
    """
    Export bin polygons to GeoJSON file.
    
    Args:
        gdf: GeoDataFrame with bin polygons
        output_path: Output file path (e.g., "bins_geometry.geojson")
        compress: Whether to gzip compress (default: True)
    """
    import json
    import gzip
    
    # Convert to GeoJSON
    geojson = json.loads(gdf.to_json())
    
    if compress:
        output_path = output_path.replace('.geojson', '.geojson.gz')
        with gzip.open(output_path, 'wt', encoding='utf-8') as f:
            json.dump(geojson, f)
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)
    
    print(f"✅ Exported {len(gdf)} bin polygons to {output_path}")

