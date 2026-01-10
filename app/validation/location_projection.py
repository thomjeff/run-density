"""
Pre-flight validation for location projection failures.

Issue #558: Segment Projection Failures During Location Mapping

This module provides validation functions to identify projection failures
before running the full model, enabling early detection of data issues.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import pandas as pd

from app.io.loader import load_locations, load_segments
from app.core.gpx.processor import load_all_courses, generate_segment_coordinates
from app.location_report import project_point_to_course
from shapely.geometry import LineString, Point
from pyproj import Transformer

from app.utils.constants import LOCATION_SNAP_THRESHOLD_M, METERS_PER_KM

logger = logging.getLogger(__name__)

# Coordinate transformers
WGS84_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32619", always_xy=True)


def validate_location_projections(
    locations_file: str,
    segments_file: str,
    data_dir: str,
    output_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate location projections before full model run.
    
    This function performs a dry-run validation to identify projection failures
    that would cause fallback to segment midpoint during actual analysis.
    
    Args:
        locations_file: Path to locations CSV file (required)
        segments_file: Path to segments CSV file (required)
        data_dir: Data directory path
        output_file: Optional path to save bad_segments.json export
        
    Returns:
        Dict with validation results including:
        - total_locations: Total number of locations checked
        - projection_failures: List of failed projections
        - summary: Summary statistics
    """
    logger.info("Starting location projection validation...")
    
    try:
        locations_df = load_locations(locations_file)
        segments_df = load_segments(segments_file)
        courses = load_all_courses(data_dir)
    except Exception as e:
        logger.error(f"Failed to load data files: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total_locations": 0,
            "projection_failures": []
        }
    
    projection_failures = []
    total_checked = 0
    
    # Process each location
    for _, location in locations_df.iterrows():
        loc_id = location.get('loc_id')
        loc_label = location.get('loc_label', loc_id)
        lat = location.get('lat')
        lon = location.get('lon')
        
        if pd.isna(lat) or pd.isna(lon):
            continue
        
        # Convert location to UTM (once, reuse for all events)
        location_point_utm = Point(WGS84_TO_UTM.transform(lon, lat))
        
        # Get segments for this location
        seg_ids = str(location.get('seg_id', '')).split(',')
        seg_ids = [s.strip() for s in seg_ids if s.strip()]
        
        # Check each event this location applies to
        events = []
        for event_col in ['full', 'half', '10k', 'elite', 'open']:
            if location.get(event_col, '').lower() in ['y', 'yes', 'true', '1']:
                events.append(event_col)
        
        for event in events:
            course = courses.get(event.lower())
            if not course:
                continue
            
            # Get full course distance for this location using location_report function
            try:
                # Get course line coordinates
                course_points = [(p.lat, p.lon) for p in course.points]
                if not course_points:
                    continue
                
                course_points_utm = [WGS84_TO_UTM.transform(lon, lat) for lat, lon in course_points]
                course_line_utm = LineString(course_points_utm)
                
                distance_km = project_point_to_course(location_point_utm, course_line_utm)
                if distance_km is None:
                    continue
            except Exception as e:
                logger.debug(f"Failed to project location {loc_id} to {event} course: {e}")
                continue
            
            for seg_id in seg_ids:
                total_checked += 1
                
                # Get segment range for this event
                from_key = f"{event}_from_km"
                to_key = f"{event}_to_km"
                
                if from_key not in segments_df.columns or to_key not in segments_df.columns:
                    continue
                
                seg_row = segments_df[segments_df['seg_id'] == seg_id]
                if seg_row.empty:
                    continue
                
                from_km = seg_row[from_key].iloc[0]
                to_km = seg_row[to_key].iloc[0]
                
                if pd.isna(from_km) or pd.isna(to_km):
                    continue
                
                # Try to project onto segment centerline
                segments_for_gpx = [{
                    'seg_id': seg_id,
                    f"{event}_from_km": from_km,
                    f"{event}_to_km": to_km
                }]
                seg_coords = generate_segment_coordinates(courses, segments_for_gpx)
                
                projection_success = False
                projection_error_km = None
                distance_to_seg_m = None
                
                if seg_coords and seg_coords[0].get("line_coords"):
                    seg_line_coords = seg_coords[0]["line_coords"]
                    seg_points_utm = [
                        WGS84_TO_UTM.transform(lon, lat) for lon, lat in seg_line_coords
                    ]
                    seg_line_utm = LineString(seg_points_utm)
                    
                    distance_to_seg_m = location_point_utm.distance(seg_line_utm)
                    
                    if distance_to_seg_m <= LOCATION_SNAP_THRESHOLD_M:
                        seg_distance_m = seg_line_utm.project(location_point_utm)
                        seg_distance_relative_km = seg_distance_m / METERS_PER_KM
                        absolute_distance_km = from_km + seg_distance_relative_km
                        
                        if from_km <= absolute_distance_km <= to_km:
                            projection_success = True
                        else:
                            projection_error_km = abs(absolute_distance_km - (from_km + to_km) / 2.0)
                    else:
                        projection_error_km = distance_to_seg_m / 1000.0  # Convert to km
                
                # Check if full course distance matches
                if not projection_success:
                    segment_length_km = to_km - from_km
                    midpoint_km = (from_km + to_km) / 2.0
                    
                    if not ((from_km - 0.1) <= distance_km <= (to_km + 0.1)):
                        projection_error_km = abs(distance_km - midpoint_km)
                        
                        projection_failures.append({
                            "loc_id": loc_id,
                            "loc_label": loc_label,
                            "event": event,
                            "seg_id": seg_id,
                            "segment_range_km": [from_km, to_km],
                            "segment_length_km": segment_length_km,
                            "full_course_distance_km": distance_km,
                            "projection_error_km": projection_error_km,
                            "distance_to_seg_m": distance_to_seg_m,
                            "will_use_midpoint": True,
                            "midpoint_km": midpoint_km
                        })
    
    # Generate summary
    summary = {
        "total_locations_checked": total_checked,
        "projection_failures_count": len(projection_failures),
        "failure_rate": len(projection_failures) / total_checked if total_checked > 0 else 0.0
    }
    
    result = {
        "status": "complete",
        "total_locations": len(locations_df),
        "total_checked": total_checked,
        "projection_failures": projection_failures,
        "summary": summary
    }
    
    # Export bad_segments.json if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Exported projection failures to {output_file}")
    
    if projection_failures:
        logger.warning(
            f"Found {len(projection_failures)} projection failures out of {total_checked} checks "
            f"({summary['failure_rate']*100:.1f}% failure rate)"
        )
    else:
        logger.info(f"All {total_checked} location projections validated successfully")
    
    return result
