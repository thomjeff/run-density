"""
Runflow v2 Pipeline Module

Provides stubbed pipeline functions for creating day-partitioned directory structure.
Actual analysis pipeline will be implemented in Phases 3-7.

Phase 2: API Route (Issue #496)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.core.v2.models import Day, Event
from app.utils.run_id import generate_run_id, get_runflow_root
from app.utils.metadata import update_latest_pointer, append_to_run_index


def create_stubbed_pipeline(
    events: List[Event],
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create day-partitioned directory structure for v2 analysis.
    
    This is a stubbed implementation that creates the directory structure
    and placeholder metadata files. Actual analysis happens in Phases 3-7.
    
    Args:
        events: List of Event objects from validated payload
        run_id: Optional run ID (generates new one if not provided)
        
    Returns:
        Dictionary with run_id, days processed, and output paths
    """
    # Generate run_id if not provided
    if not run_id:
        run_id = generate_run_id()
    
    runflow_root = get_runflow_root()
    run_path = runflow_root / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    
    # Group events by day
    from app.core.v2.loader import group_events_by_day
    events_by_day = group_events_by_day(events)
    
    # Create day-partitioned structure
    output_paths = {}
    days_processed = []
    
    for day, day_events in events_by_day.items():
        day_code = day.value  # Get string value from Day enum
        days_processed.append(day_code)
        
        # Create day directory
        day_path = run_path / day_code
        day_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        reports_dir = day_path / "reports"
        bins_dir = day_path / "bins"
        maps_dir = day_path / "maps"
        ui_dir = day_path / "ui"
        
        reports_dir.mkdir(exist_ok=True)
        bins_dir.mkdir(exist_ok=True)
        maps_dir.mkdir(exist_ok=True)
        ui_dir.mkdir(exist_ok=True)
        
        # Create metadata.json per day
        metadata = create_metadata_json(run_id, day_code, day_events)
        metadata_path = day_path / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Store output paths (relative to runflow root for API response)
        output_paths[day_code] = {
            "day": day_code,
            "reports": f"runflow/{run_id}/{day_code}/reports",
            "bins": f"runflow/{run_id}/{day_code}/bins",
            "maps": f"runflow/{run_id}/{day_code}/maps",
            "ui": f"runflow/{run_id}/{day_code}/ui",
            "metadata": f"runflow/{run_id}/{day_code}/metadata.json"
        }
    
    # Create combined metadata for index.json (includes all days)
    combined_metadata = create_combined_metadata(run_id, days_processed, events)
    
    # Update pointer files
    update_pointer_files(run_id, combined_metadata)
    
    return {
        "run_id": run_id,
        "days": days_processed,
        "output_paths": output_paths
    }


def create_metadata_json(
    run_id: str,
    day: str,
    events: List[Event]
) -> Dict[str, Any]:
    """
    Create metadata.json for a specific day.
    
    Args:
        run_id: Run identifier
        day: Day code (fri, sat, sun, mon)
        events: List of events for this day
        
    Returns:
        Metadata dictionary
    """
    from app.utils.metadata import (
        get_app_version, get_git_sha,
        detect_runtime_environment, detect_storage_target
    )
    
    event_names = [event.name for event in events]
    
    return {
        "run_id": run_id,
        "day": day,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending",  # Will be updated to "complete" when pipeline finishes
        "events": event_names,
        "runtime_env": detect_runtime_environment(),
        "storage_target": detect_storage_target(),
        "app_version": get_app_version(),
        "git_sha": get_git_sha(),
        "file_counts": {
            "reports": 0,
            "bins": 0,
            "maps": 0,
            "ui": 0
        }
    }


def create_combined_metadata(
    run_id: str,
    days: List[str],
    all_events: List[Event]
) -> Dict[str, Any]:
    """
    Create combined metadata for index.json (includes all days).
    
    Args:
        run_id: Run identifier
        days: List of day codes processed
        all_events: List of all events across all days
        
    Returns:
        Combined metadata dictionary
    """
    from app.utils.metadata import (
        get_app_version, get_git_sha,
        detect_runtime_environment, detect_storage_target
    )
    
    event_names = [event.name for event in all_events]
    
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending",
        "days": days,
        "events": event_names,
        "runtime_env": detect_runtime_environment(),
        "storage_target": detect_storage_target(),
        "app_version": get_app_version(),
        "git_sha": get_git_sha(),
        "file_counts": {}  # Will be populated when pipeline completes
    }


def update_pointer_files(run_id: str, metadata: Dict[str, Any]) -> None:
    """
    Update latest.json and index.json pointer files.
    
    Args:
        run_id: Run identifier
        metadata: Metadata dictionary (from first day processed)
    """
    # Update latest.json to point to this run
    update_latest_pointer(run_id)
    
    # Append to index.json
    # Note: For v2, we create one index entry per run (not per day)
    # The metadata includes all days processed
    append_to_run_index(metadata)

