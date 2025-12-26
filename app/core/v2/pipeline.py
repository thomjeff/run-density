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
from app.core.v2.performance import PerformanceMonitor, get_memory_usage_mb
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
        # Note: create_stubbed_pipeline doesn't have request/response, so pass None
        metadata = create_metadata_json(
            run_id=run_id,
            day=day_code,
            events=day_events,
            day_path=day_path,
            participants_by_event={},  # Empty for stubbed pipeline
            request_payload=None,
            response_payload=None
        )
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
    # Note: create_stubbed_pipeline doesn't have request/response, so pass None
    combined_metadata = create_combined_metadata(
        run_id=run_id,
        days=days_processed,
        per_day_metadata={day: {} for day in days_processed},  # Empty for stubbed pipeline
        request_payload=None,
        response_payload=None
    )
    
    # Update pointer files
    update_pointer_files(run_id, combined_metadata)
    
    return {
        "run_id": run_id,
        "days": days_processed,
        "output_paths": output_paths
    }


def _format_start_time(minutes_after_midnight: float) -> str:
    """Format start time minutes as HH:MM zero-padded."""
    try:
        mins = int(float(minutes_after_midnight))
        h = mins // 60
        m = mins % 60
        return f"{h:02d}:{m:02d}"
    except Exception:
        return ""


def _list_files_by_category(day_path: Path) -> Dict[str, List[str]]:
    """Build file lists for reports/bins/maps/heatmaps/ui (day-scoped)."""
    categories = {
        "reports": day_path / "reports",
        "bins": day_path / "bins",
        "maps": day_path / "maps",
        "ui": day_path / "ui",
        "heatmaps": day_path / "ui" / "heatmaps",
    }
    files_created: Dict[str, List[str]] = {}
    for cat, p in categories.items():
        if p.exists():
            files_created[cat] = sorted([f.name for f in p.iterdir() if f.is_file()])
        else:
            files_created[cat] = []
    return files_created


def _file_counts(files_created: Dict[str, List[str]]) -> Dict[str, int]:
    return {k: len(v) for k, v in files_created.items()}


def _verify_outputs(files_created: Dict[str, List[str]]) -> Dict[str, Any]:
    """Simple verification similar to v1 semantics."""
    critical = [
        ("reports", "Density.md"),
        ("reports", "Flow.csv"),
        ("reports", "Flow.md"),
        ("reports", "Locations.csv"),
        ("bins", "bins.parquet"),
        ("ui", "segment_metrics.json"),
        ("ui", "segments.geojson"),
    ]
    missing_critical = []
    for cat, fname in critical:
        if fname not in files_created.get(cat, []):
            missing_critical.append(f"{cat}/{fname}")
    # Heatmaps expected but not critical: at least one heatmap if bins exist
    missing_required = []
    if files_created.get("bins") and not files_created.get("heatmaps"):
        missing_required.append("heatmaps/*")
    status = "PASS"
    if missing_critical:
        status = "FAIL"
    elif missing_required:
        status = "PARTIAL"
    return {
        "status": status,
        "missing_critical": missing_critical,
        "missing_required": missing_required,
        "checks": {
            "reports": {"present": files_created.get("reports", [])},
            "bins": {"present": files_created.get("bins", [])},
            "ui": {"present": files_created.get("ui", [])},
            "heatmaps": {"present": files_created.get("heatmaps", [])},
        },
    }


def create_metadata_json(
    run_id: str,
    day: str,
    events: List[Event],
    day_path: Path,
    participants_by_event: Dict[str, int],
    request_payload: Optional[Dict[str, Any]] = None,
    response_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create metadata.json for a specific day with v1 parity + v2 day/event details.
    
    Issue #553: Enhanced to include request and response payloads.
    
    Args:
        run_id: Run identifier
        day: Day code (fri, sat, sun, mon)
        events: List of Event objects for this day
        day_path: Path to day directory
        participants_by_event: Dictionary mapping event names to participant counts
        request_payload: Optional full request payload (Issue #553)
        response_payload: Optional full response payload (Issue #553)
    """
    from app.utils.metadata import (
        get_app_version, get_git_sha,
        detect_runtime_environment, detect_storage_target
    )
    
    files_created = _list_files_by_category(day_path)
    verification = _verify_outputs(files_created)
    event_entries = {}
    for ev in events:
        name = ev.name.lower()
        event_entries[name] = {
            "start_time": _format_start_time(ev.start_time),
            "participants": int(participants_by_event.get(name, 0))
        }
    
    metadata = {
        "run_id": run_id,
        "day": day,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": verification["status"],
        "events": event_entries,
        "runtime_env": detect_runtime_environment(),
        "storage_target": detect_storage_target(),
        "app_version": get_app_version(),
        "git_sha": get_git_sha(),
        "files_created": files_created,
        "file_counts": _file_counts(files_created),
        "output_verification": verification,
    }
    
    # Issue #553: Add request and response payloads if provided
    if request_payload is not None:
        metadata["request"] = request_payload
    if response_payload is not None:
        metadata["response"] = response_payload
    
    return metadata


def create_combined_metadata(
    run_id: str,
    days: List[str],
    per_day_metadata: Dict[str, Dict[str, Any]],
    request_payload: Optional[Dict[str, Any]] = None,
    response_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create run-level metadata with v1 parity + day awareness.
    
    Issue #553: Enhanced to include request and response payloads.
    
    Args:
        run_id: Run identifier
        days: List of day codes processed
        per_day_metadata: Dictionary mapping day codes to day metadata
        request_payload: Optional full request payload (Issue #553)
        response_payload: Optional full response payload (Issue #553)
    """
    from app.utils.metadata import (
        get_app_version, get_git_sha,
        detect_runtime_environment, detect_storage_target
    )
    
    # Aggregate status: FAIL if any fail; PARTIAL if none fail but any partial; else PASS
    statuses = [md.get("status", "PASS") for md in per_day_metadata.values()]
    agg_status = "PASS"
    if any(s == "FAIL" for s in statuses):
        agg_status = "FAIL"
    elif any(s == "PARTIAL" for s in statuses):
        agg_status = "PARTIAL"
    
    # Aggregate files/counts
    files_created = {}
    file_counts = {}
    for day, md in per_day_metadata.items():
        for cat, files in md.get("files_created", {}).items():
            files_created.setdefault(cat, []).extend([f"{day}/{cat}/{fn}" for fn in files])
        for cat, cnt in md.get("file_counts", {}).items():
            file_counts[cat] = file_counts.get(cat, 0) + cnt
    
    # Aggregate verification (simple: list missing across days)
    missing_critical = []
    missing_required = []
    for day, md in per_day_metadata.items():
        ov = md.get("output_verification", {})
        for m in ov.get("missing_critical", []):
            missing_critical.append(f"{day}/{m}")
        for m in ov.get("missing_required", []):
            missing_required.append(f"{day}/{m}")
    
    metadata = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": agg_status,
        "days": days,
        "day_paths": {day: f"runflow/{run_id}/{day}" for day in days},
        "runtime_env": detect_runtime_environment(),
        "storage_target": detect_storage_target(),
        "app_version": get_app_version(),
        "git_sha": get_git_sha(),
        "files_created": files_created,
        "file_counts": file_counts,
        "output_verification": {
            "status": agg_status,
            "missing_critical": missing_critical,
            "missing_required": missing_required,
        },
    }
    
    # Issue #553: Add request and response payloads if provided
    if request_payload is not None:
        metadata["request"] = request_payload
    if response_payload is not None:
        metadata["response"] = response_payload
    
    return metadata


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
    run_id: Optional[str] = None,
    request_payload: Optional[Dict[str, Any]] = None,
    response_payload: Optional[Dict[str, Any]] = None
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
    # Issue #553: Run directory may already exist if analysis.json was generated
    run_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Using run directory: {run_path}")
    
    # Issue #553 Phase 7.1: Load analysis.json at pipeline start (single source of truth)
    # If analysis.json exists, use it; otherwise, use provided parameters (backward compatibility)
    analysis_config = None
    analysis_json_path = run_path / "analysis.json"
    if analysis_json_path.exists():
        from app.core.v2.analysis_config import load_analysis_json
        analysis_config = load_analysis_json(run_path)
        logger.info(f"Loaded analysis.json from {analysis_json_path}")
        
        # Override parameters with values from analysis.json (single source of truth)
        data_dir = analysis_config.get("data_dir", data_dir)
        segments_file = analysis_config.get("segments_file", segments_file)
        locations_file = analysis_config.get("locations_file", locations_file)
        flow_file = analysis_config.get("flow_file", flow_file)
    else:
        logger.warning(
            f"analysis.json not found at {analysis_json_path}. "
            f"Using provided parameters. This may indicate analysis.json was not generated."
        )
    
    # Issue #527: Set up run-level file logging
    from app.utils.run_logging import RunLogHandler
    run_log_handler = None
    
    # Issue #503: Initialize performance monitoring
    perf_monitor = PerformanceMonitor(run_id=run_id)
    perf_monitor.total_memory_mb = get_memory_usage_mb()
    
    try:
        run_log_handler = RunLogHandler(run_id, runflow_root)
        run_log_handler.__enter__()
        
        # Group events by day
        from app.core.v2.loader import group_events_by_day
        events_by_day = group_events_by_day(events)
        
        # Phase: Timeline Generation
        timeline_metrics = perf_monitor.start_phase("timeline_generation")
        timelines = generate_day_timelines(events)
        timeline_metrics.finish(event_count=len(events))
        logger.info(f"Generated {len(timelines)} day timelines")
        
        # Phase: Data Loading
        data_loading_metrics = perf_monitor.start_phase("data_loading")
        
        # Load segments DataFrame
        # Issue #553 Phase 7.1: Use file path from analysis.json if available
        if analysis_config:
            from app.core.v2.analysis_config import get_segments_file
            segments_path_str = get_segments_file(analysis_config=analysis_config)
        else:
            segments_path_str = str(Path(data_dir) / segments_file)
        segments_df = load_segments(segments_path_str)
        logger.info(f"Loaded {len(segments_df)} segments from {segments_path_str}")
        
        # Load all runners for events (Phase 4)
        all_runners_df = load_all_runners_for_events(events, data_dir)
        data_loading_metrics.finish(
            segment_count=len(segments_df),
            runner_count=len(all_runners_df),
            event_count=len(events),
            memory_mb=get_memory_usage_mb()
        )
        logger.info(f"Loaded {len(all_runners_df)} total runners from {len(events)} events")
        
        # Phase: Density Analysis
        density_metrics = perf_monitor.start_phase("density_analysis")
        density_results = analyze_density_segments_v2(
            events=events,
            timelines=timelines,
            segments_df=segments_df,
            all_runners_df=all_runners_df,
            density_csv_path=segments_path_str
        )
        # Count segments processed per day
        total_segments_processed = sum(
            len(day_result.get("segments", [])) 
            for day_result in density_results.values()
        )
        density_metrics.finish(
            segment_count=total_segments_processed,
            memory_mb=get_memory_usage_mb()
        )
        
        # Phase: Flow Analysis
        flow_metrics = perf_monitor.start_phase("flow_analysis")
        # Issue #553 Phase 7.1: Use file path from analysis.json if available
        if analysis_config:
            from app.core.v2.analysis_config import get_flow_file
            flow_file_path = get_flow_file(analysis_config=analysis_config)
        else:
            flow_file_path = flow_file
        flow_results = analyze_temporal_flow_segments_v2(
            events=events,
            timelines=timelines,
            segments_df=segments_df,
            all_runners_df=all_runners_df,
            flow_file=flow_file_path,
            data_dir=data_dir
        )
        flow_metrics.finish(memory_mb=get_memory_usage_mb())
        
        # Phase: Bin Generation (per day)
        bins_by_day = {}
        for day, day_events in events_by_day.items():
            bin_metrics = perf_monitor.start_phase(f"bin_generation_{day.value}")
            
            # Get density results for this day
            day_density = density_results.get(day.value, {})
            if not day_density:
                logger.warning(f"No density results for day {day.value}, skipping bin generation")
                bin_metrics.finish()
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
            # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
            start_times = {}
            for event in day_events:
                start_times[event.name.lower()] = float(event.start_time)
            
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
            
            # Try to get feature count from bins if available
            feature_count = None
            if bins_dir:
                try:
                    import pandas as pd
                    bins_parquet = Path(bins_dir) / "bins.parquet"
                    if bins_parquet.exists():
                        bins_df = pd.read_parquet(bins_parquet)
                        feature_count = len(bins_df)
                except Exception:
                    pass
            
            bin_metrics.finish(
                feature_count=feature_count,
                segment_count=len(day_segments_df),
                runner_count=len(day_runners_df),
                memory_mb=get_memory_usage_mb()
            )
            
            # Check guardrails for this day's bin generation
            guardrails = perf_monitor.check_guardrails(bin_metrics)
            if guardrails["warnings"]:
                for warning in guardrails["warnings"]:
                    logger.warning(f"⚠️  {warning}")
                if guardrails["suggestions"]:
                    for suggestion in guardrails["suggestions"]:
                        logger.info(f"💡 {suggestion}")
            
            if bins_dir:
                bins_by_day[day.value] = str(bins_dir)
                logger.info(f"Generated bins for day {day.value}: {bins_dir}")
            else:
                logger.warning(f"Bin generation skipped or failed for day {day.value}")
        
        # Load locations DataFrame if locations_file is provided
        # Issue #553 Phase 7.1: Use file path from analysis.json if available
        locations_df = None
        if locations_file:
            if analysis_config:
                from app.core.v2.analysis_config import get_locations_file
                locations_path_str = get_locations_file(analysis_config=analysis_config)
            else:
                locations_path_str = str(Path(data_dir) / locations_file)
            
            locations_path = Path(locations_path_str)
            if locations_path.exists():
                from app.io.loader import load_locations
                locations_df = load_locations(locations_path_str)
                logger.info(f"Loaded {len(locations_df)} locations from {locations_path_str}")
            else:
                logger.warning(f"Locations file not found at {locations_path_str}, skipping locations report")
        
        # Phase: Report Generation
        report_metrics = perf_monitor.start_phase("report_generation")
        
        # Use day-partitioned bins directories
        # Issue #553 Phase 7.1: Use file paths from analysis.json (already loaded at pipeline start)
        if analysis_config:
            segments_file_path = analysis_config.get("data_files", {}).get("segments", segments_path_str)
            flow_file_path = analysis_config.get("data_files", {}).get("flow", flow_file_path)
            locations_file_path = analysis_config.get("data_files", {}).get("locations", locations_path_str) if locations_file else None
        else:
            # Fallback to constructed paths if analysis.json not available
            segments_file_path = segments_path_str
            flow_file_path = flow_file_path
            locations_file_path = str(Path(data_dir) / locations_file) if locations_file else None
        
        reports_by_day = generate_reports_per_day(
            run_id=run_id,
            events=events,
            timelines=timelines,
            density_results=density_results,
            flow_results=flow_results,
            segments_df=segments_df,
            all_runners_df=all_runners_df,
            locations_df=locations_df,
            data_dir=data_dir,
            segments_file_path=segments_file_path,  # Issue #553 Phase 6.2
            flow_file_path=flow_file_path,  # Issue #553 Phase 6.2
            locations_file_path=locations_file_path  # Issue #553 Phase 6.2
        )
        report_metrics.finish(memory_mb=get_memory_usage_mb())
        
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
                
                # Prepare start_times dict for map generation
                # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
                start_times_for_map = {}
                for event in day_events:
                    start_times_for_map[event.name.lower()] = float(event.start_time)
                
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
        day_metadata_map: Dict[str, Dict[str, Any]] = {}
        
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
            
            # Participants per event for this day (re-use combine_runners_for_events)
            participants_by_event: Dict[str, int] = {}
            try:
                from app.core.v2.density import combine_runners_for_events
                event_names = [e.name.lower() for e in day_events]
                day_runners_df = combine_runners_for_events(event_names, day_code, data_dir)
                if not day_runners_df.empty:
                    # event column should be lowercase
                    participants_by_event = (
                        day_runners_df['event'].str.lower().value_counts().to_dict()
                    )
            except Exception as e:
                logger.warning(f"Could not compute participants per event for {day_code}: {e}")
            
            # Create metadata.json per day with v1 parity + events
            metadata = create_metadata_json(
                run_id=run_id,
                day=day_code,
                events=day_events,
                day_path=day_path,
                participants_by_event=participants_by_event,
                request_payload=request_payload,
                response_payload=response_payload
            )
            metadata["density"] = density_summary[day_code]
            metadata["flow"] = flow_summary_by_day[day_code]
            metadata_path = day_path / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            day_metadata_map[day_code] = metadata
            
            # Store output paths
            output_paths[day_code] = {
                "day": day_code,
                "reports": f"runflow/{run_id}/{day_code}/reports",
                "bins": f"runflow/{run_id}/{day_code}/bins",
                "maps": f"runflow/{run_id}/{day_code}/maps",
                "ui": f"runflow/{run_id}/{day_code}/ui",
                "metadata": f"runflow/{run_id}/{day_code}/metadata.json"
            }
        
        # Create combined metadata (run-level)
        combined_metadata = create_combined_metadata(
            run_id=run_id,
            days=days_processed,
            per_day_metadata=day_metadata_map,
            request_payload=request_payload,
            response_payload=response_payload
        )
        combined_metadata["density"] = density_summary
        combined_metadata["flow"] = flow_summary_by_day
        
        # Issue #503: Add performance metrics to metadata
        perf_monitor.total_memory_mb = get_memory_usage_mb()
        combined_metadata["performance"] = perf_monitor.get_summary()
        
        # Write run-level metadata.json
        run_metadata_path = run_path / "metadata.json"
        with open(run_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        
        # Issue #503: Log performance summary
        perf_monitor.log_summary()
        
        # Check overall guardrails
        total_elapsed = perf_monitor.get_total_elapsed()
        if total_elapsed > 300:  # 5 minutes
            logger.warning(
                f"⚠️  Total runtime ({total_elapsed/60:.1f} min) exceeds target (5 min). "
                f"Consider optimization opportunities."
            )
        
        # Issue #527: Add log file path to metadata
        if run_log_handler:
            log_path = run_log_handler.get_log_path()
            if log_path:
                # Add logs reference to combined metadata
                combined_metadata["logs"] = {
                    "app_log": f"logs/app.log"
                }
                # Re-write metadata.json with logs reference
                with open(run_metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        
        # Update pointer files
        update_pointer_files(run_id, combined_metadata)
        
    finally:
        # Issue #527: Clean up run logging
        if run_log_handler:
            try:
                run_log_handler.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing run log handler: {e}")
    
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

