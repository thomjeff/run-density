"""
Runflow v2 Pipeline Module

Provides pipeline functions for creating day-partitioned directory structure and running analysis.
Phase 4: Integrates density analysis (Issue #498)

Phase 2: API Route (Issue #496)
Phase 4: Density Pipeline Integration (Issue #498)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.core.v2.models import Day, Event
from app.core.v2.timeline import generate_day_timelines
from app.core.v2.density import (
    load_all_runners_for_events,
    analyze_density_segments_v2,
    filter_runners_by_day,
)
from app.core.v2.flow import analyze_temporal_flow_segments_v2
from app.core.v2.reports import generate_reports_per_day
from app.core.v2.bins import generate_bins_v2
from app.io.loader import load_segments
from app.utils.run_id import generate_run_id, get_runflow_root
from app.utils.metadata import update_latest_pointer, append_to_run_index
import logging

logger = logging.getLogger(__name__)


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


def create_full_analysis_pipeline(
    events: List[Event],
    segments_file: str = "segments.csv",
    locations_file: str = "locations.csv",
    flow_file: str = "flow.csv",
    data_dir: str = "data",
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create day-partitioned directory structure and run full analysis (Phase 4 + 5).
    
    This function integrates Phase 4 (density) and Phase 5 (flow) analysis:
    1. Creates directory structure
    2. Generates day timelines
    3. Loads segments and runners
    4. Runs density analysis per day
    5. Runs flow analysis per day
    6. Returns results with density and flow data
    
    Args:
        events: List of Event objects from validated payload
        segments_file: Name of segments CSV file (default: "segments.csv")
        locations_file: Name of locations CSV file (default: "locations.csv")
        flow_file: Name of flow CSV file (default: "flow.csv")
        data_dir: Base directory for data files (default: "data")
        run_id: Optional run ID (generates new one if not provided)
        
    Returns:
        Dictionary with run_id, days processed, output paths, density results, and flow results
    """
    # Generate run_id if not provided
    if not run_id:
        run_id = generate_run_id()
        days_count = len(set(e.day for e in events))
        event_names = [e.name for e in events]
        logger.info(f"Generated new run_id: {run_id} for {len(events)} events ({', '.join(event_names)}) across {days_count} day(s)")
    else:
        days_count = len(set(e.day for e in events))
        event_names = [e.name for e in events]
        logger.info(f"Using provided run_id: {run_id} for {len(events)} events ({', '.join(event_names)}) across {days_count} day(s)")
    
    runflow_root = get_runflow_root()
    run_path = runflow_root / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created run directory: {run_path}")
    
    # Group events by day
    from app.core.v2.loader import group_events_by_day
    events_by_day = group_events_by_day(events)
    
    # Generate day timelines (Phase 3)
    timelines = generate_day_timelines(events)
    logger.info(f"Generated {len(timelines)} day timelines")
    
    # Load segments DataFrame
    segments_path = Path(data_dir) / segments_file
    segments_df = load_segments(str(segments_path))
    logger.info(f"Loaded {len(segments_df)} segments from {segments_path}")
    
    # Load all runners for events (Phase 4)
    all_runners_df = load_all_runners_for_events(events, data_dir)
    logger.info(f"Loaded {len(all_runners_df)} total runners from {len(events)} events")
    
    # Run density analysis (Phase 4)
    density_results = analyze_density_segments_v2(
        events=events,
        timelines=timelines,
        segments_df=segments_df,
        all_runners_df=all_runners_df,
        density_csv_path=str(segments_path)
    )
    
    # Run flow analysis (Phase 5)
    flow_results = analyze_temporal_flow_segments_v2(
        events=events,
        timelines=timelines,
        segments_df=segments_df,
        all_runners_df=all_runners_df,
        flow_file=flow_file,
        data_dir=data_dir
    )
    
    # Generate bins per day (after density analysis, before reports)
    bins_by_day = {}
    for day, day_events in events_by_day.items():
        # Get density results for this day
        day_density = density_results.get(day.value, {})
        if not day_density:
            logger.warning(f"No density results for day {day.value}, skipping bin generation")
            continue
        
        # Filter runners to this day
        # Use combine_runners_for_events() for proper per-event file loading
        from app.core.v2.density import combine_runners_for_events
        event_names = [e.name.lower() for e in day_events]
        day_runners_df = combine_runners_for_events(event_names, day.value, data_dir)
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value} events {event_names}, using fallback")
            day_runners_df = filter_runners_by_day(all_runners_df, day, day_events)
        
        # Filter segments to this day's events (Issue #515: Fix bin scoping)
        from app.core.v2.bins import filter_segments_by_events
        day_segments_df = filter_segments_by_events(segments_df, day_events)
        logger.info(f"Filtered segments for day {day.value}: {len(segments_df)} -> {len(day_segments_df)} segments")
        
        # Prepare start_times for bin generation (minutes as float)
        start_times = {}
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",
            "open": "Open"
        }
        for event in day_events:
            v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
            start_times[v1_event_name] = float(event.start_time)
        
        # Generate bins for this day (Issue #515: Use day-filtered segments)
        bins_dir = generate_bins_v2(
            density_results=day_density,
            start_times=start_times,
            segments_df=day_segments_df,  # ✅ Filtered by day events
            runners_df=day_runners_df,
            run_id=run_id,
            day=day,
            events=day_events,
            data_dir=data_dir
        )
        
        if bins_dir:
            bins_by_day[day.value] = str(bins_dir)
            logger.info(f"Generated bins for day {day.value}: {bins_dir}")
        else:
            logger.warning(f"Bin generation skipped or failed for day {day.value}")
    
    # Load locations DataFrame if locations_file is provided
    locations_df = None
    if locations_file:
        from app.io.loader import load_locations
        locations_path = Path(data_dir) / locations_file
        if locations_path.exists():
            locations_df = load_locations(str(locations_path))
            logger.info(f"Loaded {len(locations_df)} locations from {locations_path}")
        else:
            logger.warning(f"Locations file not found: {locations_path}")
    
    # Generate reports (Phase 6)
    # Use day-partitioned bins directories
    reports_by_day = generate_reports_per_day(
        run_id=run_id,
        events=events,
        timelines=timelines,
        density_results=density_results,
        flow_results=flow_results,
        segments_df=segments_df,
        all_runners_df=all_runners_df,
        locations_df=locations_df,
        data_dir=data_dir
    )
    
    # Generate map_data.json per day (for density page map visualization)
    from app.core.v2.reports import get_day_output_path
    from app.density_report import generate_map_dataset
    import json
    maps_by_day = {}
    for day, day_events in events_by_day.items():
        try:
            maps_dir = get_day_output_path(run_id, day, "maps")
            maps_dir.mkdir(parents=True, exist_ok=True)
            
            # Get density results for this day
            day_density = density_results.get(day.value, {})
            if not day_density:
                logger.warning(f"No density results for day {day.value}, skipping map_data.json")
                continue
            
            # Prepare start_times dict for map generation (v1 format: "Full", "10K", etc.)
            event_name_mapping = {
                "full": "Full",
                "half": "Half",
                "10k": "10K",
                "elite": "Elite",
                "open": "Open"
            }
            start_times_for_map = {}
            for event in day_events:
                v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
                start_times_for_map[v1_event_name] = float(event.start_time)
            
            # Generate map dataset from density results
            map_data = generate_map_dataset(day_density, start_times_for_map)
            
            # Save to day-scoped maps directory
            map_data_path = maps_dir / "map_data.json"
            with open(map_data_path, 'w', encoding='utf-8') as f:
                json.dump(map_data, f, indent=2, default=str)
            
            maps_by_day[day.value] = str(maps_dir)
            logger.info(f"Generated map_data.json for day {day.value}: {map_data_path}")
        except Exception as e:
            logger.warning(f"Could not generate map_data.json for day {day.value}: {e}", exc_info=True)
    
    # Generate UI artifacts (Phase 7 - Issue #501)
    # Generate artifacts per day with full run scope data
    from app.core.v2.ui_artifacts import generate_ui_artifacts_per_day
    artifacts_by_day = {}
    for day, day_events in events_by_day.items():
        try:
            artifacts_path = generate_ui_artifacts_per_day(
                run_id=run_id,
                day=day,
                events=events,  # Pass all events for full run scope
                density_results=density_results,
                flow_results=flow_results,
                segments_df=segments_df,
                all_runners_df=all_runners_df,
                data_dir=data_dir,
                environment="local"
            )
            if artifacts_path:
                artifacts_by_day[day.value] = str(artifacts_path)
                logger.info(f"Generated UI artifacts for day {day.value}: {artifacts_path}")
            else:
                logger.warning(f"UI artifact generation returned None for day {day.value}")
        except Exception as e:
            logger.error(f"Failed to generate UI artifacts for day {day.value}: {e}", exc_info=True)
    
    # Create day-partitioned structure
    output_paths = {}
    days_processed = []
    density_summary = {}
    flow_summary_by_day = {}
    
    for day, day_events in events_by_day.items():
        day_code = day.value
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
        
        # Store density results summary
        day_density = density_results.get(day, {})
        density_summary[day_code] = {
            "processed_segments": day_density.get("summary", {}).get("processed_segments", 0),
            "skipped_segments": day_density.get("summary", {}).get("skipped_segments", 0),
            "total_segments": day_density.get("summary", {}).get("total_segments", 0),
            "has_error": "error" in day_density.get("summary", {})
        }
        
        # Store flow results summary
        day_flow = flow_results.get(day, {})
        flow_summary_by_day[day_code] = {
            "ok": day_flow.get("ok", False),
            "total_segments": day_flow.get("total_segments", 0),
            "segments_with_convergence": day_flow.get("segments_with_convergence", 0),
            "has_error": "error" in day_flow or not day_flow.get("ok", False)
        }
        
        # Create metadata.json per day
        metadata = create_metadata_json(run_id, day_code, day_events)
        metadata["density"] = density_summary[day_code]
        metadata["flow"] = flow_summary_by_day[day_code]
        metadata_path = day_path / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Store output paths
        output_paths[day_code] = {
            "day": day_code,
            "reports": f"runflow/{run_id}/{day_code}/reports",
            "bins": f"runflow/{run_id}/{day_code}/bins",
            "maps": f"runflow/{run_id}/{day_code}/maps",
            "ui": f"runflow/{run_id}/{day_code}/ui",
            "metadata": f"runflow/{run_id}/{day_code}/metadata.json"
        }
    
    # Create combined metadata
    combined_metadata = create_combined_metadata(run_id, days_processed, events)
    combined_metadata["density"] = density_summary
    combined_metadata["flow"] = flow_summary_by_day
    
    # Update pointer files
    update_pointer_files(run_id, combined_metadata)
    
    return {
        "run_id": run_id,
        "days": days_processed,
        "output_paths": output_paths,
        "density_results": density_results,
        "density_summary": density_summary,
        "flow_results": flow_results,
        "reports_by_day": reports_by_day
    }


# Alias for backward compatibility
def create_density_pipeline(
    events: List[Event],
    segments_file: str = "segments.csv",
    data_dir: str = "data",
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Alias for create_full_analysis_pipeline for backward compatibility.
    
    This function now runs both density and flow analysis.
    """
    return create_full_analysis_pipeline(
        events=events,
        segments_file=segments_file,
        data_dir=data_dir,
        run_id=run_id
    )

