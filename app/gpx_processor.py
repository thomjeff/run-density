"""
GPX Processing Module for Race Course Coordinates

This module processes GPX files to extract real geographical coordinates
for race segments, enabling accurate map visualization.
"""

import xml.etree.ElementTree as ET
import math
import bisect
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
        seg_id = segment["seg_id"]
        from_km = segment["from_km"]
        to_km = segment["to_km"]
        label = segment["label"]
        
        # Try to get coordinates from the appropriate course
        # For segments with both events, use the first one
        event = segment.get("event", "10K")  # Default to 10K if not specified
        
        # Map event names to GPX files
        event_mapping = {
            "10K": "10K",
            "Half": "Half", 
            "Full": "Full"
        }
        
        gpx_event = event_mapping.get(event, "10K")
        course = courses.get(gpx_event)
        
        if course:
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
                    "course": gpx_event
                })
            else:
                # Fallback coordinates if slicing fails
                result.append({
                    "seg_id": seg_id,
                    "segment_label": label,
                    "from_km": from_km,
                    "to_km": to_km,
                    "line_coords": None,
                    "coord_issue": True,
                    "course": gpx_event,
                    "error": "Route slicing failed"
                })
        else:
            # Fallback if course not found
            result.append({
                "seg_id": seg_id,
                "segment_label": label,
                "from_km": from_km,
                "to_km": to_km,
                "line_coords": None,
                "coord_issue": True,
                "course": None,
                "error": "Course not found"
            })
    
    return result


def load_all_courses(gpx_dir: str = "data") -> Dict[str, GPXCourse]:
    """
    Load all GPX courses from the data directory
    
    Returns:
        Dictionary mapping event names to GPXCourse objects
    """
    import os
    
    courses = {}
    gpx_files = {
        "10K": os.path.join(gpx_dir, "10K.gpx"),
        "Half": os.path.join(gpx_dir, "Half.gpx"),
        "Full": os.path.join(gpx_dir, "Full.gpx")
    }
    
    for event, filepath in gpx_files.items():
        if os.path.exists(filepath):
            try:
                courses[event] = parse_gpx_file(filepath)
                print(f"✅ Loaded {event} course: {courses[event].total_distance_km:.2f} km")
            except Exception as e:
                print(f"❌ Failed to load {event} course: {e}")
        else:
            print(f"⚠️  GPX file not found: {filepath}")
    
    return courses


def create_geojson_from_segments(segments_with_coords: List[Dict]) -> Dict:
    """
    Convert segments with coordinates to GeoJSON format
    """
    features = []
    
    for seg in segments_with_coords:
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
                    "direction": "uni",  # Default, can be updated from overlaps.csv
                    "width_m": 10.0     # Default, can be updated from overlaps.csv
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
        courses = load_all_courses()
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

