"""
Pre-flight validation for segment references in locations.csv.

Issue #559: Missing Segment Ranges for Referenced Locations

This module validates that all segments referenced in locations.csv
exist in segments.csv and have valid ranges for the events they're used with.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any, Set
from pathlib import Path
import pandas as pd

from app.io.loader import load_locations, load_segments

logger = logging.getLogger(__name__)


def validate_segment_references(
    locations_file: str,
    segments_file: str,
    data_dir: str
) -> Dict[str, Any]:
    """
    Validate that all segments referenced in locations.csv exist and have valid ranges.
    
    Args:
        locations_file: Path to locations CSV file (required)
        segments_file: Path to segments CSV file (required)
        data_dir: Data directory path
        
    Returns:
        Dict with validation results including:
        - total_locations: Total number of locations checked
        - missing_segments: List of segments referenced but not found
        - invalid_ranges: List of segments with invalid ranges per event
        - summary: Summary statistics
    """
    logger.info("Starting segment reference validation...")
    
    try:
        locations_df = load_locations(locations_file)
        segments_df = load_segments(segments_file)
    except Exception as e:
        logger.error(f"Failed to load data files: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total_locations": 0,
            "missing_segments": []
        }
    
    # Get all segment IDs from segments.csv
    valid_segment_ids = set(segments_df['seg_id'].astype(str).unique())
    
    # Track issues
    missing_segments: Set[str] = set()
    invalid_ranges: List[Dict[str, Any]] = []
    total_references = 0
    
    # Process each location
    for _, location in locations_df.iterrows():
        loc_id = location.get('loc_id')
        
        # Get segments_list from location (may be comma-separated string or list)
        segments_str = location.get('seg_id', '')
        if pd.isna(segments_str):
            continue
        
        # Parse segments (handle comma-separated string)
        if isinstance(segments_str, str):
            segments_list = [s.strip() for s in segments_str.split(',') if s.strip()]
        elif isinstance(segments_str, list):
            segments_list = [str(s).strip() for s in segments_str if s]
        else:
            continue
        
        # Get events this location applies to
        events = []
        for event_col in ['full', 'half', '10k', 'elite', 'open']:
            if str(location.get(event_col, '')).lower() in ['y', 'yes', 'true', '1']:
                events.append(event_col.lower())
        
        for seg_id in segments_list:
            total_references += 1
            
            # Check if segment exists
            if seg_id not in valid_segment_ids:
                missing_segments.add(seg_id)
                logger.warning(
                    f"Location {loc_id}: Segment {seg_id} referenced but not found in segments.csv"
                )
                continue
            
            # Check segment ranges for each event
            seg_row = segments_df[segments_df['seg_id'] == seg_id]
            if seg_row.empty:
                missing_segments.add(seg_id)
                continue
            
            row = seg_row.iloc[0]
            
            for event in events:
                event_col = event.lower()
                from_col = f"{event_col}_from_km"
                to_col = f"{event_col}_to_km"
                
                # Check if columns exist
                if from_col not in segments_df.columns or to_col not in segments_df.columns:
                    invalid_ranges.append({
                        "loc_id": loc_id,
                        "seg_id": seg_id,
                        "event": event,
                        "issue": f"Missing columns {from_col}/{to_col} in segments.csv"
                    })
                    continue
                
                # Check if segment is used by this event
                event_flag = str(row.get(event_col, '')).lower()
                if event_flag != 'y':
                    invalid_ranges.append({
                        "loc_id": loc_id,
                        "seg_id": seg_id,
                        "event": event,
                        "issue": f"Segment not marked as used by event {event} (flag={event_flag})"
                    })
                    continue
                
                # Check if ranges are valid
                from_km = row.get(from_col)
                to_km = row.get(to_col)
                
                if pd.isna(from_km) or pd.isna(to_km):
                    invalid_ranges.append({
                        "loc_id": loc_id,
                        "seg_id": seg_id,
                        "event": event,
                        "issue": f"Missing or invalid distance ranges (from_km={from_km}, to_km={to_km})"
                    })
                elif from_km == to_km:
                    invalid_ranges.append({
                        "loc_id": loc_id,
                        "seg_id": seg_id,
                        "event": event,
                        "issue": f"Invalid range: from_km == to_km ({from_km})"
                    })
    
    # Generate summary
    summary = {
        "total_segment_references": total_references,
        "missing_segments_count": len(missing_segments),
        "invalid_ranges_count": len(invalid_ranges),
        "validation_passed": len(missing_segments) == 0 and len(invalid_ranges) == 0
    }
    
    result = {
        "status": "complete",
        "total_locations": len(locations_df),
        "missing_segments": sorted(list(missing_segments)),
        "invalid_ranges": invalid_ranges,
        "summary": summary
    }
    
    if missing_segments or invalid_ranges:
        logger.warning(
            f"Validation found {len(missing_segments)} missing segments and {len(invalid_ranges)} invalid ranges. "
            f"These segments will be skipped during analysis."
        )
    else:
        logger.info(f"All {total_references} segment references validated successfully")
    
    return result
