"""
Map Data Generator

This module generates map-friendly JSON data from existing reports
for easy consumption by the map frontend.

Key Features:
- Finds latest reports in /reports/YYYY-MM-DD/ folders
- Generates simple JSON format for map visualization
- Supports both segment-level and bin-level data
- Integrates with existing density.py and flow.py modules
"""

from __future__ import annotations
import json
import logging
import os
import glob
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

try:
    from .density import analyze_density_segments
    from .flow import analyze_temporal_flow_segments
    from .io.loader import load_runners, load_segments
    from .constants import DISTANCE_BIN_SIZE_KM
except ImportError:
    from density import analyze_density_segments
    from flow import analyze_temporal_flow_segments
    from io.loader import load_runners, load_segments
    from constants import DISTANCE_BIN_SIZE_KM

logger = logging.getLogger(__name__)

def find_latest_map_dataset() -> Optional[str]:
    """
    Find the latest map dataset JSON file in /reports/ directory.
    
    Returns:
        Path to latest map dataset or None if not found
    """
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return None
    
    # Find all YYYY-MM-DD subdirectories
    date_dirs = [d for d in reports_dir.iterdir() if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2]
    
    if not date_dirs:
        return None
    
    # Sort by date (newest first)
    date_dirs.sort(key=lambda x: x.name, reverse=True)
    
    # Look for map dataset files in the latest directories
    all_map_files = []
    for date_dir in date_dirs:
        for file_path in date_dir.glob("map_data_*.json"):
            all_map_files.append(file_path)
    
    if all_map_files:
        # Sort by modification time (newest first)
        all_map_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_file = all_map_files[0]
        logger.info(f"Found latest map dataset: {latest_file}")
        return str(latest_file)
    
    logger.info("No map dataset found in any report directory")
    return None


def find_latest_bin_dataset() -> Optional[Dict[str, Any]]:
    """
    Find and load the latest bin dataset from /reports/ directory.
    
    Returns:
        Dict containing bin data or None if not found
    """
    try:
        bin_file_path = find_latest_bin_dataset_file()
        if bin_file_path:
            return _load_bin_dataset(bin_file_path)
        return None
    except Exception as e:
        logger.error(f"Error finding latest bin dataset: {e}")
        return None


def find_latest_bin_dataset_file() -> Optional[str]:
    """
    Find the latest bin dataset file in /reports/ directory.
    
    Returns:
        str: Path to the latest bin dataset file or None if not found
    """
    reports_dir = Path("reports")
    if not reports_dir.exists():
        logger.info("No reports directory found")
        return None
    
    all_bin_files = []
    
    # Search through all date subdirectories
    for date_dir in reports_dir.iterdir():
        if date_dir.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', date_dir.name):
            # Look for bin_data_*.json files
            for file_path in date_dir.glob("bin_data_*.json"):
                all_bin_files.append(file_path)
    
    if all_bin_files:
        # Sort by modification time (newest first)
        all_bin_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_file = all_bin_files[0]
        logger.info(f"Found latest bin dataset: {latest_file}")
        return str(latest_file)
    
    logger.info("No bin dataset found in any report directory")
    return None


def _load_bin_dataset(bin_dataset_path: str) -> Dict[str, Any]:
    """
    Load bin dataset from JSON file.
    
    Args:
        bin_dataset_path: Path to the bin dataset JSON file
        
    Returns:
        Dict containing the bin dataset
    """
    try:
        with open(bin_dataset_path, 'r', encoding='utf-8') as f:
            bin_data = json.load(f)
        
        logger.info(f"Successfully loaded bin dataset from {bin_dataset_path}")
        return bin_data
        
    except Exception as e:
        logger.error(f"Error loading bin dataset from {bin_dataset_path}: {e}")
        return {
            "ok": False,
            "error": str(e),
            "geojson": {"type": "FeatureCollection", "features": []},
            "metadata": {"total_segments": 0, "analysis_type": "bins"}
        }


def find_latest_reports() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Find the latest report files in /reports/ directory.
    
    Returns:
        Tuple of (density_md_path, flow_md_path, flow_csv_path) or (None, None, None) if not found
    """
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return None, None, None
    
    # Find all YYYY-MM-DD subdirectories
    date_dirs = [d for d in reports_dir.iterdir() if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2]
    
    if not date_dirs:
        return None, None, None
    
    # Sort by date (newest first)
    date_dirs.sort(key=lambda x: x.name, reverse=True)
    latest_dir = date_dirs[0]
    
    # Look for report files in the latest directory
    density_md = None
    flow_md = None
    flow_csv = None
    
    for file_path in latest_dir.glob("*.md"):
        if "Density" in file_path.name:
            density_md = str(file_path)
        elif "Flow" in file_path.name:
            flow_md = str(file_path)
    
    for file_path in latest_dir.glob("*.csv"):
        if "Flow" in file_path.name:
            flow_csv = str(file_path)
    
    logger.info(f"Found latest reports in {latest_dir}: density={density_md}, flow={flow_md}, flow_csv={flow_csv}")
    return density_md, flow_md, flow_csv

def generate_map_data(
    pace_csv: str = "data/runners.csv",
    segments_csv: str = "data/segments.csv", 
    start_times: Dict[str, int] = None
) -> Dict[str, Any]:
    """
    Generate map-friendly data from latest map dataset or run new analysis.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments data CSV
        start_times: Event start times in minutes from midnight
    
    Returns:
        Dictionary with map visualization data
    """
    if start_times is None:
        start_times = {"Full": 420, "10K": 440, "Half": 460}
    
    # Try to find existing map dataset first
    map_dataset_path = find_latest_map_dataset()
    
    if map_dataset_path:
        logger.info(f"Using existing map dataset: {map_dataset_path}")
        return _load_map_dataset(map_dataset_path)
    else:
        logger.info("No existing map dataset found, running new analysis")
        return _generate_from_analysis(pace_csv, segments_csv, start_times)

def _load_map_dataset(map_dataset_path: str) -> Dict[str, Any]:
    """Load map data from existing map dataset JSON file."""
    try:
        logger.info(f"Loading map dataset from {map_dataset_path}")
        
        with open(map_dataset_path, 'r', encoding='utf-8') as f:
            map_data = json.load(f)
        
        # Validate the loaded data
        is_valid, errors = validate_map_data(map_data)
        if not is_valid:
            logger.error(f"Map dataset validation failed: {errors}")
            return {"ok": False, "error": f"Invalid map dataset: {errors}"}
        
        logger.info(f"Successfully loaded map dataset with {len(map_data.get('segments', {}))} segments")
        return map_data
        
    except Exception as e:
        logger.error(f"Error loading map dataset: {e}")
        return {"ok": False, "error": str(e)}

def _generate_from_reports(density_md_path: str, flow_csv_path: str) -> Dict[str, Any]:
    """Generate map data from existing report files."""
    try:
        logger.info("Parsing existing reports for map data")
        
        # For now, we need to run a quick analysis to get the actual data
        # In the future, we could parse the MD/CSV files directly
        logger.info("Running quick analysis to extract data from reports")
        
        # Load data and run analysis to get the actual segment data
        pace_data = load_runners("data/runners.csv")
        segments_df = load_segments("data/segments.csv")
        
        # Convert start times to datetime objects
        from datetime import datetime, timedelta
        start_times = {"Full": 420, "10K": 440, "Half": 460}
        start_times_dt = {}
        for event, minutes in start_times.items():
            start_times_dt[event] = datetime(2024, 1, 1) + timedelta(minutes=minutes)
        
        # Run density analysis to get segment data
        density_results = analyze_density_segments(
            pace_data=pace_data,
            start_times=start_times_dt,
            density_csv_path="data/segments.csv"
        )
        
        # Generate map-friendly data structure
        map_data = {
            "ok": True,
            "source": "reports",
            "density_md": density_md_path,
            "flow_csv": flow_csv_path,
            "timestamp": datetime.now().isoformat(),
            "segments": {},
            "metadata": {
                "total_segments": len(density_results.get("segments", {})),
                "analysis_type": "density_from_reports"
            }
        }
        
        # Process density data for segments
        segment_count = 0
        for segment_id, segment_data in density_results.get("segments", {}).items():
            if isinstance(segment_data, dict):
                # Extract data from the segment dictionary
                peak_areal_density = segment_data.get('peak_areal_density', 0.0)
                peak_crowd_density = segment_data.get('peak_crowd_density', 0.0)
                
                map_data["segments"][segment_id] = {
                    "segment_id": segment_id,
                    "segment_label": segment_data.get('seg_label', segment_id),
                    "peak_areal_density": peak_areal_density,
                    "peak_crowd_density": peak_crowd_density,
                    "zone": _determine_zone(peak_areal_density),
                    "flow_type": segment_data.get('flow_type', 'none'),
                    "width_m": segment_data.get('width_m', 3.0)
                }
                segment_count += 1
        
        # Validate the data
        if segment_count == 0:
            logger.warning("No segments found in density analysis results")
            return {"ok": False, "error": "No segments found in density analysis results"}
        
        logger.info(f"Successfully extracted {segment_count} segments from reports")
        return map_data
        
    except Exception as e:
        logger.error(f"Error parsing reports: {e}")
        return {"ok": False, "error": str(e)}

def _generate_from_analysis(pace_csv: str, segments_csv: str, start_times: Dict[str, int]) -> Dict[str, Any]:
    """Generate map data by running new analysis."""
    try:
        logger.info("Running new analysis for map data")
        
        # Load data
        pace_data = load_runners(pace_csv)
        segments_df = load_segments(segments_csv)
        
        # Convert start times to datetime objects
        from datetime import datetime, timedelta
        start_times_dt = {}
        for event, minutes in start_times.items():
            start_times_dt[event] = datetime(2024, 1, 1) + timedelta(minutes=minutes)
        
        # Run density analysis
        density_results = analyze_density_segments(
            pace_data=pace_data,
            start_times=start_times_dt,
            density_csv_path=segments_csv
        )
        
        # Run flow analysis
        flow_results = analyze_temporal_flow_segments(
            pace_csv=pace_csv,
            segments_csv=segments_csv,
            start_times=start_times
        )
        
        # Generate map-friendly data structure
        map_data = {
            "ok": True,
            "source": "analysis",
            "timestamp": datetime.now().isoformat(),
            "segments": {},
            "flow_data": flow_results.get("segments", {}),
            "metadata": {
                "total_segments": len(density_results.get("segments", {})),
                "analysis_type": "density_and_flow"
            }
        }
        
        # Process density data for segments
        for segment_id, segment_data in density_results.get("segments", {}).items():
            if isinstance(segment_data, dict):
                # Extract data from the segment dictionary
                peak_areal_density = segment_data.get('peak_areal_density', 0.0)
                peak_crowd_density = segment_data.get('peak_crowd_density', 0.0)
                
                map_data["segments"][segment_id] = {
                    "segment_id": segment_id,
                    "segment_label": segment_data.get('seg_label', segment_id),
                    "peak_areal_density": peak_areal_density,
                    "peak_crowd_density": peak_crowd_density,
                    "zone": _determine_zone(peak_areal_density),
                    "flow_type": segment_data.get('flow_type', 'none'),
                    "width_m": segment_data.get('width_m', 3.0)
                }
        
        return map_data
        
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        return {"ok": False, "error": str(e)}

def _determine_zone(density: float) -> str:
    """Determine zone color based on density value."""
    if density < 0.36:
        return "green"
    elif density < 0.54:
        return "yellow"
    elif density < 0.72:
        return "orange"
    elif density < 1.08:
        return "red"
    else:
        return "dark-red"

def validate_map_data(map_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate map data for correctness and completeness.
    
    Args:
        map_data: Map data dictionary to validate
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check basic structure
    if not map_data.get("ok", False):
        errors.append("Map data indicates failure")
        return False, errors
    
    if "segments" not in map_data:
        errors.append("Missing 'segments' key in map data")
        return False, errors
    
    segments = map_data["segments"]
    if not isinstance(segments, dict):
        errors.append("'segments' must be a dictionary")
        return False, errors
    
    if len(segments) == 0:
        errors.append("No segments found in map data")
        return False, errors
    
    # Validate each segment
    required_fields = ["segment_id", "segment_label", "peak_areal_density", "peak_crowd_density", "zone"]
    for segment_id, segment_data in segments.items():
        if not isinstance(segment_data, dict):
            errors.append(f"Segment {segment_id} data must be a dictionary")
            continue
            
        for field in required_fields:
            if field not in segment_data:
                errors.append(f"Segment {segment_id} missing required field: {field}")
        
        # Validate density values
        areal_density = segment_data.get("peak_areal_density", 0)
        crowd_density = segment_data.get("peak_crowd_density", 0)
        
        if not isinstance(areal_density, (int, float)) or areal_density < 0:
            errors.append(f"Segment {segment_id} has invalid areal_density: {areal_density}")
        
        if not isinstance(crowd_density, (int, float)) or crowd_density < 0:
            errors.append(f"Segment {segment_id} has invalid crowd_density: {crowd_density}")
        
        # Validate zone
        zone = segment_data.get("zone", "")
        valid_zones = ["green", "yellow", "orange", "red", "dark-red"]
        if zone not in valid_zones:
            errors.append(f"Segment {segment_id} has invalid zone: {zone}")
    
    # Check metadata
    metadata = map_data.get("metadata", {})
    if "total_segments" not in metadata:
        errors.append("Missing 'total_segments' in metadata")
    elif metadata["total_segments"] != len(segments):
        errors.append(f"Metadata total_segments ({metadata['total_segments']}) doesn't match actual segments ({len(segments)})")
    
    is_valid = len(errors) == 0
    return is_valid, errors

def test_map_data_generator() -> bool:
    """
    Test the map data generator to ensure it produces correct data.
    
    Returns:
        True if test passes, False otherwise
    """
    try:
        logger.info("Testing map data generator...")
        
        # Generate map data
        map_data = generate_map_data()
        
        # Validate the data
        is_valid, errors = validate_map_data(map_data)
        
        if not is_valid:
            logger.error(f"Map data validation failed: {errors}")
            return False
        
        # Log success details
        segment_count = len(map_data.get("segments", {}))
        logger.info(f"✅ Map data generator test PASSED")
        logger.info(f"   - Generated {segment_count} segments")
        logger.info(f"   - Source: {map_data.get('source', 'unknown')}")
        logger.info(f"   - Timestamp: {map_data.get('timestamp', 'unknown')}")
        
        # Log sample segment data
        if segment_count > 0:
            sample_segment = list(map_data["segments"].values())[0]
            logger.info(f"   - Sample segment: {sample_segment.get('segment_id', 'unknown')} - {sample_segment.get('segment_label', 'unknown')}")
            logger.info(f"     Zone: {sample_segment.get('zone', 'unknown')}, Areal: {sample_segment.get('peak_areal_density', 0):.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Map data generator test FAILED: {e}")
        return False

def save_map_data(map_data: Dict[str, Any], filename: str = None) -> str:
    """
    Save map data to a JSON file for easy consumption.
    
    Args:
        map_data: Map data dictionary
        filename: Optional filename (defaults to timestamp-based name)
    
    Returns:
        Path to saved file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        filename = f"map_data_{timestamp}.json"
    
    # Ensure reports directory exists
    reports_dir = Path("reports") / datetime.now().strftime("%Y-%m-%d")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = reports_dir / filename
    
    with open(file_path, 'w') as f:
        json.dump(map_data, f, indent=2, default=str)
    
    logger.info(f"Map data saved to {file_path}")
    return str(file_path)
