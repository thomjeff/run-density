"""
GPX Processing Module for Race Course Coordinates

This module processes GPX files to extract real geographical coordinates
for race segments, enabling accurate map visualization.
"""

import xml.etree.ElementTree as ET
import math
import bisect
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class GPXPoint:
    """Represents a GPS point with coordinates and distance"""
    lat: float
    lon: float
    distance_km: float = 0.0


# --- distance + slicing helpers ---

EARTH_R = 6371000.0  # metres

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters"""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlon/2)**2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def cumulative_km(course_points: List[Tuple[float, float]]) -> List[float]:
    """
    course_points: [(lat, lon), ...] in order along the course.
    Returns cum distance in km for each vertex, starting at 0.0.
    """
    if not course_points:
        return []
    out = [0.0]
    acc = 0.0
    for i in range(1, len(course_points)):
        lat0, lon0 = course_points[i-1]
        lat1, lon1 = course_points[i]
        acc += haversine_m(lat0, lon0, lat1, lon1) / 1000.0
        out.append(acc)
    return out


def _interp_vertex(course_points: List[Tuple[float, float]], cum_km: List[float], target_km: float) -> Tuple[float, float]:
    """
    Returns (lon, lat) at the exact target_km along the course (linear along segment).
    """
    if not course_points:
        return (0.0, 0.0)
    # clamp
    if target_km <= cum_km[0]:
        lat, lon = course_points[0]
        return (lon, lat)
    if target_km >= cum_km[-1]:
        lat, lon = course_points[-1]
        return (lon, lat)

    j = max(0, bisect.bisect_left(cum_km, target_km) - 1)
    j2 = min(j + 1, len(cum_km) - 1)
    d0, d1 = cum_km[j], cum_km[j2]
    lat0, lon0 = course_points[j]
    lat1, lon1 = course_points[j2]
    if d1 <= d0:
        return (lon0, lat0)
    t = (target_km - d0) / (d1 - d0)
    lat = lat0 + t * (lat1 - lat0)
    lon = lon0 + t * (lon1 - lon0)
    return (lon, lat)


def slice_polyline_by_km(
    course_points: List[Tuple[float, float]],
    cum_km: List[float],
    km_a: float,
    km_b: float,
) -> List[Tuple[float, float]]:
    """
    Returns a dense LineString ([(lon,lat), ...]) for the route section between km_a and km_b.
    Works even if the endpoints are spatially coincident due to loops.
    """
    if not course_points or not cum_km or len(course_points) != len(cum_km):
        return []

    a, b = (km_a, km_b) if km_a <= km_b else (km_b, km_a)

    # start/end exact points
    coords: List[Tuple[float, float]] = [_interp_vertex(course_points, cum_km, a)]

    # include all intermediate vertices strictly between a..b
    i0 = max(0, bisect.bisect_left(cum_km, a) - 1)
    i1 = min(len(cum_km) - 1, bisect.bisect_right(cum_km, b))
    for k in range(i0 + 1, i1):
        if a <= cum_km[k] <= b:
            lat, lon = course_points[k]
            coords.append((lon, lat))

    coords.append(_interp_vertex(course_points, cum_km, b))

    # drop duplicate consecutive points
    dedup: List[Tuple[float, float]] = []
    last = None
    for c in coords:
        if c != last:
            dedup.append(c)
        last = c
    return dedup


def metres_between(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Calculate distance between two coordinate tuples in meters"""
    (lon1, lat1), (lon2, lat2) = a, b
    return haversine_m(lat1, lon1, lat2, lon2)


@dataclass
class GPXCourse:
    """Represents a complete GPX course with points and metadata"""
    name: str
    points: List[GPXPoint]
    total_distance_km: float = 0.0
    
    def __post_init__(self):
        """Cache route data for efficient slicing"""
        # Extract raw coordinates for slicing
        self.course_points = [(p.lat, p.lon) for p in self.points]
        # Calculate cumulative distances for slicing
        self.cum_km = cumulative_km(self.course_points)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth
    Returns distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def parse_gpx_file(filepath: str) -> GPXCourse:
    """
    Parse a GPX file and extract track points with calculated distances
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Handle different GPX namespaces
        namespaces = {
            'gpx': 'http://www.topografix.com/GPX/1/1',
            'gpx11': 'http://www.topografix.com/GPX/1/1',
            'gpx10': 'http://www.topografix.com/GPX/1/0'
        }
        
        # Find the track name
        track_name = "Unknown Course"
        for track in root.findall('.//gpx:trk', namespaces):
            name_elem = track.find('gpx:name', namespaces)
            if name_elem is not None:
                track_name = name_elem.text
                break
        
        # Extract track points
        points = []
        for trkpt in root.findall('.//gpx:trkpt', namespaces):
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
            points.append(GPXPoint(lat=lat, lon=lon))
        
        # Calculate cumulative distances with better precision
        total_distance = 0.0
        for i in range(1, len(points)):
            prev_point = points[i-1]
            curr_point = points[i]
            segment_distance = haversine_distance(
                prev_point.lat, prev_point.lon,
                curr_point.lat, curr_point.lon
            )
            total_distance += segment_distance
            curr_point.distance_km = total_distance
            
            # Debug: log every 100th point
            if i % 100 == 0:
                print(f"  Point {i}: {total_distance:.3f} km")
        
        print(f"  Final distance: {total_distance:.3f} km")
        
        return GPXCourse(
            name=track_name,
            points=points,
            total_distance_km=total_distance
        )
        
    except Exception as e:
        raise ValueError(f"Failed to parse GPX file {filepath}: {e}")


def find_coordinates_at_distance(course: GPXCourse, target_distance_km: float) -> Optional[Tuple[float, float]]:
    """
    Find the coordinates at a specific distance along the course
    Returns (lat, lon) or None if distance is out of range
    """
    if not course.points or target_distance_km < 0:
        return None
    
    # Debug logging for problematic distances
    if target_distance_km > 10:
        print(f"  Looking for coordinates at {target_distance_km}km (course total: {course.total_distance_km:.2f}km)")
    
    # Find the two points that bracket the target distance
    for i in range(len(course.points) - 1):
        point1 = course.points[i]
        point2 = course.points[i + 1]
        
        if point1.distance_km <= target_distance_km <= point2.distance_km:
            # Interpolate between the two points
            ratio = (target_distance_km - point1.distance_km) / (point2.distance_km - point1.distance_km)
            lat = point1.lat + ratio * (point2.lat - point1.lat)
            lon = point1.lon + ratio * (point2.lon - point1.lon)
            
            # Debug logging for interpolation
            if target_distance_km > 10:
                print(f"    Interpolated {target_distance_km}km between points {i} ({point1.distance_km:.2f}km) and {i+1} ({point2.distance_km:.2f}km)")
                print(f"    Result: ({lat:.6f}, {lon:.6f})")
            
            return (lat, lon)
    
    # If target distance is beyond the course, return the last point
    if target_distance_km >= course.total_distance_km:
        last_point = course.points[-1]
        print(f"  Distance {target_distance_km}km beyond course, using last point at {last_point.distance_km:.2f}km")
        return (last_point.lat, last_point.lon)
    
    # If target distance is before the course, return the first point
    if target_distance_km <= 0:
        first_point = course.points[0]
        print(f"  Distance {target_distance_km}km before course, using first point")
        return (first_point.lat, first_point.lon)
    
    print(f"  Distance {target_distance_km}km not found in course range [0, {course.total_distance_km:.2f}]")
    return None


def generate_segment_coordinates(
    courses: Dict[str, GPXCourse],
    segments: List[Dict]
) -> List[Dict]:
    """
    Generate real coordinates for race segments based on GPX courses
    
    Args:
        courses: Dictionary mapping event names to GPXCourse objects
        segments: List of segment dictionaries from overlaps.csv
    
    Returns:
        List of segments with real coordinates
    """
    result = []
    
    for segment in segments:
        seg_id = segment.get("seg_id")
        if not seg_id:
            raise ValueError("Segment missing required seg_id for GPX coordinate generation.")
        label = segment.get("segment_label")
        if not label:
            raise ValueError(f"Segment {seg_id} missing required segment_label for GPX coordinate generation.")
        
        # Determine which event to use based on which events use this segment
        # Priority: elite, open, 10k, half, full (covering sat/sun events)
        # Issue #655: Only check for events that exist in the courses dict to avoid
        # failures when segments reference events not in the current analysis
        # Note: column names are lowercase in CSV
        gpx_event = None
        available_events = set(courses.keys())  # Only check events we have GPX data for
        for event in ["elite", "open", "10k", "half", "full"]:
            if event in available_events and segment.get(event, "").lower() == "y":
                gpx_event = event
                break
        
        if gpx_event is None:
            # Issue #655: Skip segments that don't match any available event instead of failing
            # This can happen when segments.csv has events not in the current analysis
            continue  # Skip this segment - it's not part of the current analysis events
        
        # Lookup course (courses dict uses lowercase keys)
        course = courses.get(gpx_event)
        if course is None:
            # This should not happen since we filtered above, but be defensive
            continue  # Skip this segment
        
        # Get event-specific from_km and to_km fields
        from_km_key = f"{gpx_event}_from_km"
        to_km_key = f"{gpx_event}_to_km"
        
        from_km = segment.get(from_km_key)
        to_km = segment.get(to_km_key)
        
        # Skip if we don't have the required fields for this event or if they're NaN
        if from_km is None or to_km is None or pd.isna(from_km) or pd.isna(to_km):
            result.append({
                "seg_id": seg_id,
                "segment_label": label,
                "from_km": None,
                "to_km": None,
                "line_coords": None,
                "coord_issue": True,
                "course": gpx_event,
                "error": f"Missing or NaN {from_km_key} or {to_km_key} fields"
            })
            continue
        
        # Use route slicing instead of just endpoints
        line_coords = slice_polyline_by_km(
            course.course_points,
            course.cum_km,
            from_km,
            to_km
        )
        
        if line_coords and len(line_coords) >= 2:
            # Check for suspicious segments (endpoints within 25m and too few vertices)
            coord_issue = False
            if len(line_coords) <= 2 and metres_between(line_coords[0], line_coords[-1]) < 25.0:
                coord_issue = True
                print(f"⚠️ [map] warning: {seg_id} endpoints are nearly identical; using route slice.")
            
            result.append({
                "seg_id": seg_id,
                "segment_label": label,
                "from_km": from_km,
                "to_km": to_km,
                "line_coords": line_coords,
                "coord_issue": coord_issue,
                "course": gpx_event,
                "direction": segment.get("direction"),
                "width_m": segment.get("width_m"),
            })
        else:
            raise ValueError(f"Route slicing failed for segment {seg_id} in GPX course '{gpx_event}'.")
    
    return result


def load_all_courses(gpx_files: Dict[str, str]) -> Dict[str, GPXCourse]:
    """
    Load all GPX courses from the data directory
    
    Returns:
        Dictionary mapping event names to GPXCourse objects
    """
    import os
    from pathlib import Path
    
    if not gpx_files:
        raise ValueError("gpx_files is required to load GPX courses.")
    courses: Dict[str, GPXCourse] = {}
    for event, filepath_str in gpx_files.items():
        filepath = Path(filepath_str)
        if filepath.suffix.lower() != ".gpx":
            raise ValueError(f"GPX file for event '{event}' must have .gpx extension: {filepath}")
        if not filepath.exists():
            raise FileNotFoundError(f"GPX file not found for event '{event}': {filepath}")
        try:
            course = parse_gpx_file(str(filepath))
            courses[event.lower()] = course
            print(f"✅ Loaded {event} course: {course.total_distance_km:.2f} km")
        except Exception as e:
            raise ValueError(f"Failed to load {event} course from {filepath}: {e}") from e
    
    return courses


def create_geojson_from_segments(segments_with_coords: List[Dict]) -> Dict:
    """
    Convert segments with coordinates to GeoJSON format
    """
    features = []
    
    for seg in segments_with_coords:
        direction = seg.get("direction")
        width_m = seg.get("width_m")
        if direction in (None, ""):
            raise ValueError(f"Segment {seg.get('seg_id')} missing direction for GeoJSON export.")
        if width_m is None or (isinstance(width_m, float) and pd.isna(width_m)):
            raise ValueError(f"Segment {seg.get('seg_id')} missing width_m for GeoJSON export.")
        if seg.get("line_coords") and len(seg["line_coords"]) >= 2:
            features.append({
                "type": "Feature",
                "properties": {
                    "seg_id": seg["seg_id"],
                    "segment_label": seg["segment_label"],
                    "from_km": seg["from_km"],
                    "to_km": seg["to_km"],
                    "course": seg["course"],
                    "coord_issue": seg.get("coord_issue", False),
                    "direction": direction,
                    "width_m": float(width_m),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": seg["line_coords"]  # Already in [lon, lat] format
                }
            })
        else:
            # Log segments without coordinates for debugging
            print(f"⚠️  Segment {seg['seg_id']} missing coordinates: {seg.get('error', 'Unknown error')}")
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


if __name__ == "__main__":
    # Test the GPX processing
    print("Testing GPX processing...")
    
    try:
        if len(sys.argv) < 2:
            raise SystemExit("Usage: python -m app.core.gpx.processor event=path [event=path ...]")
        gpx_paths = {}
        for arg in sys.argv[1:]:
            if "=" not in arg:
                raise SystemExit("Each GPX argument must be in the form event=path")
            event, path = arg.split("=", 1)
            gpx_paths[event.strip().lower()] = path.strip()
        courses = load_all_courses(gpx_paths)
        print(f"\nLoaded {len(courses)} courses")
        
        for event, course in courses.items():
            print(f"{event}: {course.total_distance_km:.2f} km, {len(course.points)} points")
            
            # Test coordinate finding
            test_distances = [0.0, 1.0, 5.0, 10.0]
            for dist in test_distances:
                coord = find_coordinates_at_distance(course, dist)
                if coord:
                    print(f"  {dist}km: {coord[0]:.6f}, {coord[1]:.6f}")
                else:
                    print(f"  {dist}km: Not found")
                    
    except Exception as e:
        print(f"Error: {e}")
