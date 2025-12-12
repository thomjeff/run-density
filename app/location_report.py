"""
Location Report Module

Issue #277: Course Resource Timing Overview

Generates arrival modeling and operational timing windows for fixed point locations
on the course (traffic control points, water stops, turnarounds).

Author: Cursor AI Assistant
Epic: Issue #277
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from shapely.geometry import LineString, Point
from pyproj import Transformer

from app.io.loader import load_locations, load_runners, load_segments
from app.core.gpx.processor import load_all_courses, GPXCourse
from app.utils.constants import (
    LOCATION_SNAP_THRESHOLD_M,
    LOCATION_SETUP_BUFFER_MINUTES,
    SECONDS_PER_MINUTE,
    METERS_PER_KM,
    TIME_FORMAT_HOURS
)

# Configure logging
logger = logging.getLogger(__name__)

# Coordinate transformers
WGS84_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32619", always_xy=True)
UTM_TO_WGS84 = Transformer.from_crs("EPSG:32619", "EPSG:4326", always_xy=True)


def round_to_interval(value_minutes: float, interval_minutes: float) -> float:
    """
    Round value up to nearest interval.
    
    Issue #277: Used for loc_end rounding.
    
    Args:
        value_minutes: Value to round (in minutes)
        interval_minutes: Rounding interval (in minutes)
        
    Returns:
        Rounded value (in minutes)
    """
    if interval_minutes <= 0:
        return value_minutes
    
    return np.ceil(value_minutes / interval_minutes) * interval_minutes


def format_time_hhmmss(seconds: float) -> str:
    """
    Format seconds to hh:mm:ss string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string (hh:mm:ss)
    """
    if pd.isna(seconds) or seconds is None:
        return "NA"
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_segment_ranges_for_event(
    segments_df: pd.DataFrame,
    segment_ids: List[str],
    event: str
) -> List[Tuple[str, float, float]]:
    """
    Get distance ranges (from_km, to_km) for listed segments for a specific event.
    
    Args:
        segments_df: DataFrame from segments.csv
        segment_ids: List of segment IDs to check
        event: Event name ("Full", "Half", "10K")
        
    Returns:
        List of (seg_id, from_km, to_km) tuples
    """
    ranges = []
    event_col = event.lower() if event != "10K" else "10K"
    from_col = f"{event_col}_from_km"
    to_col = f"{event_col}_to_km"
    
    for seg_id in segment_ids:
        seg_row = segments_df[segments_df["seg_id"] == seg_id]
        if seg_row.empty:
            logger.warning(f"Segment {seg_id} not found in segments.csv")
            continue
        
        row = seg_row.iloc[0]
        from_km = row.get(from_col)
        to_km = row.get(to_col)
        
        # Check if segment is used by this event
        event_flag = row.get(event_col, "").lower() if event_col in row.index else ""
        if event_flag != "y":
            logger.debug(f"Segment {seg_id} not used by event {event} (flag={event_flag})")
            continue
        
        if pd.notna(from_km) and pd.notna(to_km) and from_km != to_km:
            # Only add if segment is actually used by this event
            if event_flag == "y":
                ranges.append((
                    seg_id,
                    float(from_km),
                    float(to_km)
                ))
            else:
                logger.debug(
                    f"Segment {seg_id} has range [{from_km}, {to_km}] but not used by event {event} (flag={event_flag})"
                )
        else:
            logger.warning(
                f"Segment {seg_id} missing or invalid {from_col}/{to_col} for event {event} "
                f"(from_km={from_km}, to_km={to_km})"
            )
    
    return ranges


def project_point_to_course(
    location_point_utm: Point,
    course_polyline_utm: LineString
) -> Optional[float]:
    """
    Project a location point onto a course polyline and return distance along line.
    
    Args:
        location_point_utm: Location point in UTM coordinates
        course_polyline_utm: Course polyline in UTM coordinates
        
    Returns:
        Distance along course in kilometers, or None if projection fails
    """
    try:
        # Project point onto line (returns distance along line in meters)
        distance_m = course_polyline_utm.project(location_point_utm)
        distance_km = distance_m / METERS_PER_KM
        return distance_km
    except Exception as e:
        logger.warning(f"Failed to project point to course: {e}")
        return None


def find_nearest_segment(
    location_point_utm: Point,
    segments_df: pd.DataFrame,
    courses: Dict[str, GPXCourse],
    event: str
) -> Optional[Tuple[str, float]]:
    """
    Find nearest segment to location point (fallback when segments field is empty).
    
    Args:
        location_point_utm: Location point in UTM
        segments_df: DataFrame from segments.csv
        courses: Dictionary of GPX courses
        event: Event name
        
    Returns:
        Tuple of (seg_id, distance_km) or None if no segment within threshold
    """
    from app.core.gpx.processor import generate_segment_coordinates
    
    course = courses.get(event)
    if not course:
        return None
    
    # Convert course to UTM LineString
    course_points_utm = [
        WGS84_TO_UTM.transform(p.lon, p.lat) for p in course.points
    ]
    course_line_utm = LineString(course_points_utm)
    
    # Project location onto full course
    distance_km = project_point_to_course(location_point_utm, course_line_utm)
    if distance_km is None:
        return None
    
    # Find which segment this distance falls within
    event_col = event.lower() if event != "10K" else "10K"
    from_col = f"{event_col}_from_km"
    to_col = f"{event_col}_to_km"
    
    for _, seg_row in segments_df.iterrows():
        if seg_row.get(event_col, "").lower() == "y":
            from_km = seg_row.get(from_col)
            to_km = seg_row.get(to_col)
            
            if pd.notna(from_km) and pd.notna(to_km):
                if from_km <= distance_km <= to_km:
                    # Check distance from location to segment centerline
                    seg_id = seg_row["seg_id"]
                    
                    # Get segment centerline
                    segments_list = [{
                        "seg_id": seg_id,
                        event_col: "y",
                        f"{event_col}_from_km": from_km,
                        f"{event_col}_to_km": to_km
                    }]
                    seg_coords = generate_segment_coordinates(courses, segments_list)
                    
                    if seg_coords and seg_coords[0].get("line_coords"):
                        seg_line_coords = seg_coords[0]["line_coords"]
                        seg_points_utm = [
                            WGS84_TO_UTM.transform(lon, lat) for lon, lat in seg_line_coords
                        ]
                        seg_line_utm = LineString(seg_points_utm)
                        
                        # Calculate distance from point to segment
                        distance_to_seg_m = location_point_utm.distance(seg_line_utm)
                        
                        if distance_to_seg_m <= LOCATION_SNAP_THRESHOLD_M:
                            return (seg_id, distance_km)
    
    return None


def calculate_arrival_times_for_location(
    location: pd.Series,
    runners_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    courses: Dict[str, GPXCourse],
    start_times: Dict[str, float]
) -> List[float]:
    """
    Calculate arrival times for all eligible runners at a location.
    
    Issue #277: Supports multiple crossings (e.g., A1 and G1 for loc_id=8).
    Issue #480: Processes ALL listed segments independently to capture all crossings
                (e.g., B1 outbound, B3 return, D1 outbound, D2 return).
    
    Args:
        location: Location row from locations.csv
        runners_df: DataFrame from runners.csv
        segments_df: DataFrame from segments.csv
        courses: Dictionary of GPX courses
        start_times: Dictionary of event start times in minutes
        
    Returns:
        List of arrival times in seconds (may include duplicates for multiple crossings).
        Same runner may appear multiple times (once per segment crossing).
    """
    arrival_times = []
    
    # Get eligible events (where flag is 'y')
    eligible_events = []
    for event in ["full", "half", "10K"]:
        if location.get(event, "").lower() == "y":
            event_name = "Full" if event == "full" else ("Half" if event == "half" else "10K")
            eligible_events.append(event_name)
    
    if not eligible_events:
        logger.warning(f"Location {location.get('loc_id')}: No eligible events (full={location.get('full')}, half={location.get('half')}, 10K={location.get('10K')})")
        return arrival_times
    
    logger.debug(f"Location {location.get('loc_id')}: Processing {len(eligible_events)} eligible events: {eligible_events}")
    
    # Convert location point to UTM
    lat = location.get("lat")
    lon = location.get("lon")
    if pd.isna(lat) or pd.isna(lon):
        logger.warning(f"Location {location.get('loc_id')} has invalid coordinates")
        return arrival_times
    
    location_point_utm = Point(WGS84_TO_UTM.transform(lon, lat))
    
    # Get listed segments (if any)
    segments_list = location.get("segments_list", [])
    
    # Process each eligible event
    for event in eligible_events:
        course = courses.get(event)
        if not course:
            continue
        
        # Convert course to UTM LineString
        course_points_utm = [
            WGS84_TO_UTM.transform(p.lon, p.lat) for p in course.points
        ]
        course_line_utm = LineString(course_points_utm)
        
        # Project location onto course
        distance_km = project_point_to_course(location_point_utm, course_line_utm)
        if distance_km is None:
            logger.warning(f"Location {location.get('loc_id')} ({event}): Projection failed - could not project point to course")
            continue
        
        logger.debug(f"Location {location.get('loc_id')} ({event}): Projected distance = {distance_km:.3f}km")
        
        # Issue #480: Process ALL listed segments independently for multiple crossings
        if segments_list:
            from app.core.gpx.processor import generate_segment_coordinates
            
            segment_ranges = get_segment_ranges_for_event(segments_df, segments_list, event)
            if not segment_ranges:
                logger.warning(
                    f"Location {location.get('loc_id')} ({event}): No valid segment ranges found for segments {segments_list}"
                )
                continue
            
            # Get runners for this event
            event_runners = runners_df[runners_df["event"] == event].copy()
            
            if event_runners.empty:
                logger.warning(f"Location {location.get('loc_id')} ({event}): No runners found for event {event}")
                continue
            
            event_start_sec = start_times.get(event, 0) * SECONDS_PER_MINUTE
            event_col_gpx = event.lower() if event != "10K" else "10K"
            
            # Issue #480: Process ALL listed segments independently
            # This ensures we capture all crossings (e.g., B1 outbound, B3 return, D1 outbound, D2 return)
            processed_segments = []
            
            for seg_id, from_km, to_km in segment_ranges:
                logger.debug(f"Location {location.get('loc_id')} ({event}): Processing segment {seg_id} [{from_km:.3f}, {to_km:.3f}]km")
                
                # Get segment centerline for this event
                segments_for_gpx = [{
                    "seg_id": seg_id,
                    event_col_gpx: "y",
                    f"{event_col_gpx}_from_km": from_km,
                    f"{event_col_gpx}_to_km": to_km
                }]
                seg_coords = generate_segment_coordinates(courses, segments_for_gpx)
                
                # Determine distance along segment for this location
                seg_distance_km = None
                
                if seg_coords and seg_coords[0].get("line_coords"):
                    # Project location onto segment centerline
                    seg_line_coords = seg_coords[0]["line_coords"]
                    seg_points_utm = [
                        WGS84_TO_UTM.transform(lon, lat) for lon, lat in seg_line_coords
                    ]
                    seg_line_utm = LineString(seg_points_utm)
                    
                    # Check distance from location to segment centerline
                    distance_to_seg_m = location_point_utm.distance(seg_line_utm)
                    
                    if distance_to_seg_m <= LOCATION_SNAP_THRESHOLD_M:
                        # Project onto segment centerline to get distance along segment
                        seg_distance_m = seg_line_utm.project(location_point_utm)
                        seg_distance_relative_km = seg_distance_m / METERS_PER_KM
                        
                        # Convert to absolute course distance: from_km + distance_along_segment
                        absolute_distance_km = from_km + seg_distance_relative_km
                        
                        # Verify it's within segment bounds
                        if from_km <= absolute_distance_km <= to_km:
                            seg_distance_km = absolute_distance_km
                            logger.info(
                                f"Location {location.get('loc_id')} ({event}): Projected onto segment {seg_id} centerline: {absolute_distance_km:.3f}km (from_km={from_km:.3f} + seg_dist={seg_distance_relative_km:.3f}km)"
                            )
                        else:
                            logger.debug(
                                f"Location {location.get('loc_id')} ({event}): Segment {seg_id} centerline distance {absolute_distance_km:.3f}km outside range [{from_km:.3f}, {to_km:.3f}], trying fallback"
                            )
                
                # Fallback: use full course projection if centerline projection failed or unavailable
                if seg_distance_km is None:
                    if (from_km - 0.1) <= distance_km <= (to_km + 0.1):
                        seg_distance_km = max(from_km, min(distance_km, to_km))
                        logger.info(
                            f"Location {location.get('loc_id')} ({event}): Using full course distance {distance_km:.3f}km for segment {seg_id} (clamped to {seg_distance_km:.3f}km)"
                        )
                    else:
                        # Segment is listed but location doesn't match full course projection
                        # This can happen when same physical location is at different distances on different segments
                        # Use segment midpoint as reasonable approximation for arrival time calculation
                        seg_distance_km = (from_km + to_km) / 2.0
                        logger.warning(
                            f"Location {location.get('loc_id')} ({event}): Segment {seg_id} [{from_km:.3f}, {to_km:.3f}]km listed but "
                            f"centerline projection failed and full course distance {distance_km:.3f}km doesn't match. "
                            f"Using segment midpoint {seg_distance_km:.3f}km for arrival calculations."
                        )
                
                # Calculate arrival times for ALL runners at this segment distance
                # Issue #480: Same runner can contribute multiple arrival times (once per segment)
                for _, runner in event_runners.iterrows():
                    start_offset = runner.get("start_offset", 0)
                    if pd.isna(start_offset):
                        start_offset = 0
                    # start_offset is in seconds, not minutes
                    
                    pace_min_per_km = runner.get("pace", 0)
                    if pd.isna(pace_min_per_km) or pace_min_per_km <= 0:
                        continue
                    
                    pace_sec_per_km = pace_min_per_km * SECONDS_PER_MINUTE
                    
                    # Arrival time = start_time + offset (seconds) + pace * distance
                    arrival_time = event_start_sec + start_offset + pace_sec_per_km * seg_distance_km
                    arrival_times.append(arrival_time)
                
                processed_segments.append(seg_id)
            
            logger.info(
                f"Location {location.get('loc_id')} ({event}): Processed {len(processed_segments)} segments: {processed_segments}, "
                f"calculated arrival times for {len(event_runners)} runners across {len(processed_segments)} segments"
            )
            continue  # Skip the single-segment calculation below
        else:
            # Fallback: find nearest segment
            nearest = find_nearest_segment(location_point_utm, segments_df, courses, event)
            if not nearest:
                logger.warning(f"Location {location.get('loc_id')} ({event}): No nearest segment found")
                continue
            # distance_km already set from projection
            logger.debug(f"Location {location.get('loc_id')} ({event}): Using nearest segment distance {distance_km:.3f}km")
        
        # Get runners for this event
        # Note: runners.csv uses capitalized event names ("Full", "Half", "10K")
        event_runners = runners_df[runners_df["event"] == event].copy()
        
        logger.debug(f"Location {location.get('loc_id')} ({event}): Found {len(event_runners)} runners for event {event}")
        
        if event_runners.empty:
            logger.warning(f"Location {location.get('loc_id')} ({event}): No runners found for event {event}")
            continue
        
        # Calculate arrival times
        event_start_sec = start_times.get(event, 0) * SECONDS_PER_MINUTE
        
        for _, runner in event_runners.iterrows():
            start_offset = runner.get("start_offset", 0)
            if pd.isna(start_offset):
                start_offset = 0
            # start_offset is in seconds, not minutes
            
            pace_min_per_km = runner.get("pace", 0)
            if pd.isna(pace_min_per_km) or pace_min_per_km <= 0:
                continue
            
            pace_sec_per_km = pace_min_per_km * SECONDS_PER_MINUTE
            
            # Arrival time = start_time + offset (seconds) + pace * distance
            arrival_time = event_start_sec + start_offset + pace_sec_per_km * distance_km
            arrival_times.append(arrival_time)
        
        logger.debug(f"Location {location.get('loc_id')} ({event}): Calculated {len(arrival_times)} arrival times for {len(event_runners)} runners at distance {distance_km:.3f}km")
    
    return arrival_times


def generate_location_report(
    locations_csv: str = "data/locations.csv",
    runners_csv: str = "data/runners.csv",
    segments_csv: str = "data/segments.csv",
    start_times: Optional[Dict[str, float]] = None,
    output_dir: str = "reports",
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate locations report with arrival modeling and operational timing.
    
    Issue #277: Main entry point for location report generation.
    
    Args:
        locations_csv: Path to locations.csv
        runners_csv: Path to runners.csv
        segments_csv: Path to segments.csv
        start_times: Dictionary of event start times in minutes (default: from constants)
        output_dir: Output directory for report
        run_id: Optional run ID for runflow structure
        
    Returns:
        Dictionary with report results and file path
    """
    from app.report_utils import get_report_paths, get_runflow_category_path
    
    # Issue #512: Start times must be provided, not from constants
    if start_times is None:
        raise ValueError(
            "start_times parameter is required. Start times must come from API request, "
            "not from hardcoded constants. (Issue #512)"
        )
    
    logger.info("Starting location report generation...")
    
    # Load data
    try:
        locations_df = load_locations(locations_csv)
        runners_df = load_runners(runners_csv)
        segments_df = load_segments(segments_csv)
        courses = load_all_courses("data")
    except FileNotFoundError as e:
        logger.error(f"Required input file not found: {e}")
        return {"ok": False, "error": str(e), "error_type": "file_not_found"}
    except Exception as e:
        logger.error(f"Failed to load input data: {e}")
        return {"ok": False, "error": str(e), "error_type": "load_error"}
    
    if locations_df.empty:
        logger.warning("No locations found in locations.csv")
        return {"ok": False, "error": "No locations to process"}
    
    # Determine output path
    if run_id:
        output_dir = get_runflow_category_path(run_id, "reports")
    
    # Calculate earliest start time for loc_start calculation
    earliest_start_min = min(start_times.values()) if start_times else 0
    loc_start_base_sec = (earliest_start_min - LOCATION_SETUP_BUFFER_MINUTES) * SECONDS_PER_MINUTE
    
    # Process each location
    report_rows = []
    # Build lookup dictionary for proxy locations (will be populated as we process)
    locations_by_id = {}
    
    for _, location in locations_df.iterrows():
        loc_id = location.get("loc_id")
        loc_label = location.get("loc_label", "")
        loc_type = location.get("loc_type", "").lower()
        
        logger.info(f"Processing location {loc_id}: {loc_label}")
        
        # Initialize report row
        report_row = {
            "loc_id": loc_id,
            "loc_label": loc_label,
            "loc_type": loc_type,
            "zone": location.get("zone", ""),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
            "first_runner": None,
            "peak_start": None,
            "peak_end": None,
            "last_runner": None,
            "loc_start": format_time_hhmmss(loc_start_base_sec),
            "loc_end": None,
            "duration": None,
            "timing_source": "modeled",  # Default to modeled, will be updated for proxy-based traffic locations
            "notes": location.get("notes", "")
        }
        
        # Check if timing_source is set to proxy:n in input locations.csv
        # This handles locations that should copy timing from another location
        timing_source = location.get("timing_source", "")
        if pd.notna(timing_source) and isinstance(timing_source, str) and timing_source.startswith("proxy:"):
            try:
                proxy_id = int(timing_source.split(":")[1])
                logger.info(
                    f"Location {loc_id} ({loc_label}): timing_source={timing_source}, "
                    f"will copy timing from location {proxy_id}"
                )
                
                # Look up proxy location (must be processed first, so check if it exists)
                # If not yet processed, we'll handle it in a second pass
                proxy_location = locations_by_id.get(proxy_id)
                
                if proxy_location:
                    # Copy operational timing from proxy location (loc_start, loc_end, duration)
                    # Note: first_runner, peak_start, peak_end, last_runner are NOT copied
                    # because proxy locations don't have runners at that physical location
                    report_row["loc_start"] = proxy_location.get("loc_start")
                    report_row["loc_end"] = proxy_location.get("loc_end")
                    report_row["duration"] = proxy_location.get("duration")
                    report_row["timing_source"] = timing_source
                    report_row["notes"] = f"{location.get('notes', '')} (Proxy to location {proxy_id})".strip()
                    
                    logger.info(
                        f"Location {loc_id} ({loc_label}): Copied timing from proxy location {proxy_id}: "
                        f"loc_end={report_row['loc_end']}, duration={report_row['duration']}"
                    )
                    
                    # Add to report_rows and continue (skip arrival time calculation)
                    report_rows.append(report_row)
                    locations_by_id[loc_id] = report_row
                    continue
                else:
                    # Proxy location not yet processed - defer to second pass
                    logger.debug(
                        f"Location {loc_id} ({loc_label}): Proxy location {proxy_id} not yet processed, "
                        f"will handle in second pass"
                    )
                    # Continue with normal processing for now, will update in second pass
            except (ValueError, IndexError) as e:
                logger.error(
                    f"Location {loc_id} ({loc_label}): Invalid timing_source format '{timing_source}': {e}"
                )
                report_row["timing_source"] = "error:invalid_proxy_format"
        
        # Validate proxy_loc_id usage (Issue #479)
        proxy_loc_id = location.get("proxy_loc_id")
        if pd.notna(proxy_loc_id) and proxy_loc_id != "" and loc_type != "traffic":
            logger.warning(
                f"Location {loc_id} ({loc_label}): proxy_loc_id={proxy_loc_id} provided but loc_type={loc_type} is not 'traffic'. "
                f"Ignoring proxy_loc_id for non-traffic locations."
            )
        
        # Skip arrival modeling for traffic locations
        # Note: timing_source will be updated later in proxy processing loop
        if loc_type == "traffic":
            report_rows.append(report_row)
            locations_by_id[loc_id] = report_row
            continue
        
        # Calculate arrival times
        arrival_times = calculate_arrival_times_for_location(
            location, runners_df, segments_df, courses, start_times
        )
        
        if not arrival_times:
            loc_row = locations_df[locations_df['loc_id'] == loc_id]
            if not loc_row.empty:
                loc = loc_row.iloc[0]
                logger.warning(
                    f"No arrival times calculated for location {loc_id} ({loc.get('loc_label', 'unknown')}). "
                    f"Event flags: full={loc.get('full')}, half={loc.get('half')}, 10K={loc.get('10K')}, "
                    f"seg_id={loc.get('seg_id')}"
                )
            else:
                logger.warning(f"No arrival times calculated for location {loc_id}")
            report_rows.append(report_row)
            locations_by_id[loc_id] = report_row
            continue
        
        # Calculate statistics
        arrival_times_sorted = sorted(arrival_times)
        report_row["first_runner"] = format_time_hhmmss(arrival_times_sorted[0])
        report_row["last_runner"] = format_time_hhmmss(arrival_times_sorted[-1])
        
        # Percentiles
        if len(arrival_times_sorted) > 1:
            p25_idx = int(len(arrival_times_sorted) * 0.25)
            p75_idx = int(len(arrival_times_sorted) * 0.75)
            report_row["peak_start"] = format_time_hhmmss(arrival_times_sorted[p25_idx])
            report_row["peak_end"] = format_time_hhmmss(arrival_times_sorted[p75_idx])
        else:
            report_row["peak_start"] = report_row["first_runner"]
            report_row["peak_end"] = report_row["last_runner"]
        
        # Calculate loc_end (last_runner + buffer, rounded to interval)
        if report_row["last_runner"] != "NA":
            last_runner_sec = arrival_times_sorted[-1]
            buffer_minutes = location.get("buffer", 0)
            if pd.isna(buffer_minutes):
                buffer_minutes = 0
            
            interval_minutes = location.get("interval", 5)
            if pd.isna(interval_minutes):
                interval_minutes = 5
            
            loc_end_minutes = (last_runner_sec / SECONDS_PER_MINUTE) + buffer_minutes
            loc_end_minutes_rounded = round_to_interval(loc_end_minutes, interval_minutes)
            report_row["loc_end"] = format_time_hhmmss(loc_end_minutes_rounded * SECONDS_PER_MINUTE)
            
            # Calculate duration
            duration_minutes = loc_end_minutes_rounded - (loc_start_base_sec / SECONDS_PER_MINUTE)
            report_row["duration"] = int(duration_minutes) if duration_minutes > 0 else 0
        
        report_rows.append(report_row)
        locations_by_id[loc_id] = report_row
    
    # Second pass: Handle locations with timing_source="proxy:n" that referenced locations not yet processed
    # This ensures proxy locations are available when needed
    for i, report_row in enumerate(report_rows):
        loc_id = report_row["loc_id"]
        location_row = locations_df[locations_df['loc_id'] == loc_id]
        
        if location_row.empty:
            continue
        
        location = location_row.iloc[0]
        timing_source = location.get("timing_source", "")
        
        # Check if this location needs proxy timing and wasn't handled in first pass
        if (pd.notna(timing_source) and isinstance(timing_source, str) and 
            timing_source.startswith("proxy:") and 
            report_row.get("timing_source") == "modeled"):  # Only process if not already handled
            
            try:
                proxy_id = int(timing_source.split(":")[1])
                proxy_location = locations_by_id.get(proxy_id)
                
                if proxy_location:
                    # Copy operational timing from proxy location (loc_start, loc_end, duration)
                    # Note: first_runner, peak_start, peak_end, last_runner are NOT copied
                    # because proxy locations don't have runners at that physical location
                    report_row["loc_start"] = proxy_location.get("loc_start")
                    report_row["loc_end"] = proxy_location.get("loc_end")
                    report_row["duration"] = proxy_location.get("duration")
                    report_row["timing_source"] = timing_source
                    
                    original_notes = report_row.get("notes", "")
                    proxy_note = f"Proxy to location {proxy_id}"
                    if original_notes:
                        report_row["notes"] = f"{original_notes} ({proxy_note})"
                    else:
                        report_row["notes"] = proxy_note
                    
                    logger.info(
                        f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                        f"Copied timing from proxy location {proxy_id} in second pass: "
                        f"loc_end={report_row['loc_end']}, duration={report_row['duration']}"
                    )
                else:
                    logger.error(
                        f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                        f"Proxy location {proxy_id} not found in processed locations."
                    )
                    report_row["timing_source"] = "error:proxy_not_found"
            except (ValueError, IndexError) as e:
                logger.error(
                    f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                    f"Invalid timing_source format '{timing_source}': {e}"
                )
                report_row["timing_source"] = "error:invalid_proxy_format"
    
    # Issue #479: Process proxy_loc_id for traffic locations
    # Build lookup dictionary for all processed locations (refresh after second pass)
    locations_by_id = {row["loc_id"]: row for row in report_rows}
    
    # Iterate through report_rows to update traffic locations with proxy data
    for report_row in report_rows:
        if report_row["loc_type"] != "traffic":
            continue
        
        # Get original location data to access proxy_loc_id
        loc_id = report_row["loc_id"]
        location_row = locations_df[locations_df['loc_id'] == loc_id]
        
        if location_row.empty:
            continue
        
        location = location_row.iloc[0]
        proxy_loc_id = location.get("proxy_loc_id")
        
        # Debug logging for proxy_loc_id
        logger.debug(
            f"Traffic location {loc_id}: proxy_loc_id={proxy_loc_id}, type={type(proxy_loc_id)}, "
            f"isna={pd.isna(proxy_loc_id) if hasattr(pd, 'isna') else 'N/A'}"
        )
        
        # Skip if no proxy_loc_id provided
        # Handle both pandas NaN and empty string cases
        if pd.isna(proxy_loc_id) or (isinstance(proxy_loc_id, str) and proxy_loc_id.strip() == ""):
            # Traffic location without proxy should keep default "modeled" or could be set to something else
            # For now, keep as "modeled" to indicate it wasn't proxy-based
            logger.debug(f"Traffic location {loc_id}: No proxy_loc_id, keeping timing_source as 'modeled'")
            continue
        
        # Convert proxy_loc_id to int for lookup (handle string/numeric)
        try:
            proxy_id = int(proxy_loc_id)
        except (ValueError, TypeError):
            logger.error(
                f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                f"Invalid proxy_loc_id value '{proxy_loc_id}'. Expected numeric loc_id."
            )
            report_row["timing_source"] = "error:proxy_not_found"
            continue
        
        # Look up proxy location
        proxy_location = locations_by_id.get(proxy_id)
        
        if not proxy_location:
            logger.error(
                f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                f"Proxy location {proxy_id} not found in processed locations."
            )
            report_row["timing_source"] = "error:proxy_not_found"
            continue
        
        # Check if proxy location has loc_end
        proxy_loc_end = proxy_location.get("loc_end")
        if not proxy_loc_end or proxy_loc_end == "NA" or pd.isna(proxy_loc_end):
            logger.error(
                f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                f"Proxy location {proxy_id} ({proxy_location.get('loc_label', 'unknown')}) has no loc_end value."
            )
            report_row["timing_source"] = "error:proxy_not_found"
            continue
        
        # Copy loc_end from proxy location
        report_row["loc_end"] = proxy_loc_end
        
        # Calculate duration: loc_end - loc_start (in minutes)
        # Parse loc_end time string (hh:mm:ss) to seconds
        try:
            loc_end_parts = proxy_loc_end.split(":")
            loc_end_sec = (
                int(loc_end_parts[0]) * 3600 +
                int(loc_end_parts[1]) * 60 +
                int(loc_end_parts[2])
            )
            
            # Calculate duration in minutes
            duration_minutes = (loc_end_sec - loc_start_base_sec) / SECONDS_PER_MINUTE
            report_row["duration"] = int(duration_minutes) if duration_minutes > 0 else 0
            
            # Set timing_source
            report_row["timing_source"] = f"proxy:{proxy_id}"
            
            logger.info(
                f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                f"Set loc_end={proxy_loc_end} and duration={report_row['duration']} from proxy location {proxy_id}"
            )
        except (ValueError, IndexError) as e:
            logger.error(
                f"Location {loc_id} ({report_row.get('loc_label', 'unknown')}): "
                f"Failed to parse proxy loc_end '{proxy_loc_end}': {e}"
            )
            report_row["timing_source"] = "error:proxy_not_found"
            report_row["loc_end"] = None
            report_row["duration"] = None
    
    # Create DataFrame and save
    report_df = pd.DataFrame(report_rows)
    
    # Get output path
    full_path, relative_path = get_report_paths("Locations", "csv", output_dir)
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)
    
    report_df.to_csv(full_path, index=False)
    logger.info(f"Location report saved to: {full_path}")
    
    return {
        "ok": True,
        "file_path": full_path,
        "relative_path": relative_path,
        "locations_processed": len(report_df),
        "timestamp": datetime.now().isoformat()
    }

