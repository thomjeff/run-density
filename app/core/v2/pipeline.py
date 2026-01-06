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
from dataclasses import is_dataclass, asdict

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


def _convert_dataclasses_to_dicts(obj: Any) -> Any:
    """
    Recursively convert dataclass objects to dictionaries for JSON serialization.
    
    Issue #612: Properly serialize ConvergencePoint and ConflictZone dataclasses
    instead of using default=str which converts them to strings.
    
    Args:
        obj: Object that may contain dataclass instances (dict, list, dataclass, or primitive)
        
    Returns:
        Object with all dataclasses converted to dicts
    """
    # Handle dataclass objects
    if is_dataclass(obj):
        # Convert dataclass to dict and recursively process its fields
        return _convert_dataclasses_to_dicts(asdict(obj))
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: _convert_dataclasses_to_dicts(value) for key, value in obj.items()}
    
    # Handle lists
    if isinstance(obj, list):
        return [_convert_dataclasses_to_dicts(item) for item in obj]
    
    # Handle tuples (convert to lists for JSON compatibility)
    if isinstance(obj, tuple):
        return [_convert_dataclasses_to_dicts(item) for item in obj]
    
    # Return primitives as-is (str, int, float, bool, None, etc.)
    return obj


# Issue #581: Phase mapping for Issue #574 pipeline structure
PHASE_MAPPING = {
    "phase_1_pre_analysis": {"number": "Phase 1", "description": "Pre-Analysis & Validation"},
    "phase_2_data_loading": {"number": "Phase 2", "description": "Data Loading"},
    "phase_3_1_computation": {"number": "Phase 3.1", "description": "Core Computation"},
    "phase_3_2_persistence": {"number": "Phase 3.2", "description": "Computation Persistence"},
    "phase_4_1_ui_artifacts": {"number": "Phase 4.1", "description": "UI Artifacts Generation"},
    "phase_4_2_derived_metrics": {"number": "Phase 4.2", "description": "Derived Metrics Calculation"},
    "phase_5_reports": {"number": "Phase 5", "description": "Report Generation"},
    "phase_6_metadata": {"number": "Phase 6", "description": "Metadata & Cleanup"},
}


def compute_operational_status(los_letter: str, flow_utilization: Optional[float] = None) -> str:
    """
    Compute operational status based on LOS and flow utilization.
    
    Issue #569: Implements the same logic as density_report.py::_render_key_takeaways_v2
    
    Args:
        los_letter: LOS grade (A-F)
        flow_utilization: Optional flow utilization percentage (None if not available)
        
    Returns:
        Operational status string: "Stable", "Moderate", "Critical", or "Overload"
    """
    # Determine status based on LOS and flow
    if los_letter in ["A", "B"]:
        if flow_utilization and flow_utilization > 200:
            return "Overload"  # Flow utilization exceeds 200% - consider flow management
        else:
            return "Stable"  # Density and flow within acceptable ranges
    elif los_letter in ["C", "D"]:
        return "Moderate"  # Density approaching comfort limits - monitor closely
    else:  # E, F
        return "Critical"  # High density detected - immediate action required


def calculate_peak_density_los(peak_density: float) -> str:
    """
    Calculate LOS for peak density using rulebook thresholds.
    
    Issue #569: Replicates logic from app/routes/api_dashboard.py
    
    Args:
        peak_density: Peak density value (persons/m²)
        
    Returns:
        LOS grade (A-F)
    """
    try:
        from app.common.config import load_rulebook
        rulebook = load_rulebook()
        thresholds = rulebook.get("globals", {}).get("los_thresholds", {})
        
        # Get density thresholds (assuming they're in order A->F)
        density_thresholds = thresholds.get("density", [])
        
        if not density_thresholds:
            # Fallback to hardcoded thresholds if YAML missing
            density_thresholds = [0.2, 0.4, 0.6, 0.8, 1.0]
        
        # Find appropriate LOS grade
        los_grades = ["A", "B", "C", "D", "E", "F"]
        
        for i, threshold in enumerate(density_thresholds):
            if peak_density < threshold:
                return los_grades[i]
        
        # If above all thresholds, return F
        return "F"
    except Exception as e:
        logger.warning(f"Error calculating LOS from rulebook: {e}, using fallback")
        # Fallback logic
        if peak_density < 0.36:
            return "A"
        elif peak_density < 0.54:
            return "B"
        elif peak_density < 0.72:
            return "C"
        elif peak_density < 1.08:
            return "D"
        elif peak_density < 1.63:
            return "E"
        else:
            return "F"


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
        "heatmaps": day_path / "ui" / "visualizations",  # Issue #574: heatmaps now in visualizations/
    }
    files_created: Dict[str, List[str]] = {}
    for cat, p in categories.items():
        if p.exists():
            # Issue #574: For ui category, also include files from subdirectories
            if cat == "ui":
                files_list = []
                # List files directly in ui/
                files_list.extend([f.name for f in p.iterdir() if f.is_file()])
                # List files in subdirectories (metadata/, metrics/, geospatial/, visualizations/)
                for subdir in ["metadata", "metrics", "geospatial", "visualizations"]:
                    subdir_path = p / subdir
                    if subdir_path.exists():
                        files_list.extend([f"{subdir}/{f.name}" for f in subdir_path.iterdir() if f.is_file()])
                files_created[cat] = sorted(files_list)
            else:
                files_created[cat] = sorted([f.name for f in p.iterdir() if f.is_file()])
        else:
            files_created[cat] = []
    return files_created


def _file_counts(files_created: Dict[str, List[str]]) -> Dict[str, int]:
    return {k: len(v) for k, v in files_created.items()}


def _update_metadata_verification(day_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata verification by re-checking files on disk.
    
    This should be called after reports are generated to ensure verification
    reflects the actual files that exist.
    
    Args:
        day_path: Path to day directory
        metadata: Existing metadata dictionary to update
        
    Returns:
        Updated metadata dictionary with corrected verification
    """
    files_created = _list_files_by_category(day_path)
    verification = _verify_outputs(files_created)
    
    # Update metadata with new file lists and verification
    metadata["files_created"] = files_created
    metadata["file_counts"] = _file_counts(files_created)
    metadata["output_verification"] = verification
    metadata["status"] = verification["status"]
    
    return metadata


def _verify_outputs(files_created: Dict[str, List[str]]) -> Dict[str, Any]:
    """Simple verification similar to v1 semantics."""
    critical = [
        ("reports", "Density.md"),
        ("reports", "Flow.csv"),
        # Issue #600: Flow.md removed from critical files (deprecated, only Flow.csv used)
        ("reports", "Locations.csv"),
        ("bins", "bins.parquet"),
        ("ui", "metrics/segment_metrics.json"),  # Issue #574: Now in metrics/ subdirectory
        ("ui", "geospatial/segments.geojson"),  # Issue #574: Now in geospatial/ subdirectory
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
    response_payload: Optional[Dict[str, Any]] = None,
    enable_audit: str = 'n'
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
        
        # Phase 1: Pre-Analysis & Validation (Issue #581: Enhanced logging)
        phase_1_metrics = perf_monitor.start_phase(
            "phase_1_pre_analysis",
            phase_number="Phase 1",
            phase_description="Pre-Analysis & Validation"
        )
        # Validation already done above (analysis.json loading, file existence checks)
        event_count = len(events)
        days_count = len(events_by_day)
        data_files_count = sum([
            1 if analysis_config.get("segments_file") else 0,
            1 if analysis_config.get("flow_file") else 0,
            1 if analysis_config.get("locations_file") else 0,
        ])
        # Timeline Generation (part of Phase 1)
        timelines = generate_day_timelines(events)
        logger.info(f"[Phase 1] Generated {len(timelines)} day timelines")
        
        perf_monitor.complete_phase(
            phase_1_metrics,
            phase_number="Phase 1",
            phase_description="Pre-Analysis & Validation",
            summary_stats={"events": event_count, "days": days_count, "data_files": data_files_count, "timelines": len(timelines)}
        )
        
        # Phase 2: Data Loading (Issue #581: Enhanced logging)
        data_loading_metrics = perf_monitor.start_phase(
            "phase_2_data_loading",
            phase_number="Phase 2",
            phase_description="Data Loading"
        )
        
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
        runner_count = len(all_runners_df)
        segment_count = len(segments_df)
        locations_count = 0  # Will be updated if locations are loaded
        
        data_loading_metrics.finish(
            segment_count=segment_count,
            runner_count=runner_count,
            event_count=len(events),
            memory_mb=get_memory_usage_mb()
        )
        logger.info(f"Loaded {runner_count} total runners from {len(events)} events")
        
        perf_monitor.complete_phase(
            data_loading_metrics,
            phase_number="Phase 2",
            phase_description="Data Loading",
            summary_stats={"segments": segment_count, "runners": runner_count, "events": len(events)}
        )
        
        # Phase 3.1: Core Computation (Density, Flow, Locations) - Issue #581: Enhanced logging
        computation_metrics = perf_monitor.start_phase(
            "phase_3_1_computation",
            phase_number="Phase 3.1",
            phase_description="Core Computation"
        )
        
        # Density Analysis
        logger.info("[Phase 3.1] Processing density analysis...")
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
        density_days = len(density_results)
        logger.info(f"[Phase 3.1] Density analysis complete: {density_days} days, {total_segments_processed} segments")
        
        # Flow Analysis
        logger.info("[Phase 3.1] Processing flow analysis...")
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
            data_dir=data_dir,
            enable_audit=enable_audit,
            run_id=run_id,
            run_path=run_path
        )
        flow_days = len(flow_results)
        logger.info(f"[Phase 3.1] Flow analysis complete: {flow_days} days")
        
        computation_metrics.finish(
            segment_count=total_segments_processed,
            memory_mb=get_memory_usage_mb()
        )
        
        perf_monitor.complete_phase(
            computation_metrics,
            phase_number="Phase 3.1",
            phase_description="Core Computation",
            summary_stats={"density_days": density_days, "flow_days": flow_days, "segments": total_segments_processed}
        )
        
        # Phase 3.2: Persist Computation Results (Issue #574, #581: Enhanced logging)
        persistence_metrics = perf_monitor.start_phase(
            "phase_3_2_persistence",
            phase_number="Phase 3.2",
            phase_description="Computation Persistence"
        )
        
        # Create computation directory per day and persist results
        persisted_files = []
        for day, day_events in events_by_day.items():
            day_code = day.value
            logger.info(f"[Phase 3.2] Processing day: {day_code}")
            day_path = run_path / day_code
            computation_dir = day_path / "computation"
            computation_dir.mkdir(parents=True, exist_ok=True)
            
            # Persist density_results.json
            day_density = density_results.get(day, {})
            if day_density:
                density_json_path = computation_dir / "density_results.json"
                # Convert Day enum keys to strings for JSON serialization
                density_for_json = {
                    "day": day_code,
                    "events": day_density.get("events", []),
                    "summary": day_density.get("summary", {}),
                    "segments": day_density.get("segments", {})
                }
                with open(density_json_path, 'w', encoding='utf-8') as f:
                    json.dump(density_for_json, f, indent=2, default=str)
                logger.info(f"  → Persisted density_results.json: {density_json_path}")
                persisted_files.append(f"density_results.json ({day_code})")
            
            # Persist flow_results.json
            day_flow = flow_results.get(day, {})
            if day_flow:
                flow_json_path = computation_dir / "flow_results.json"
                # Convert Day enum keys to strings for JSON serialization
                # Issue #612: Convert dataclasses (ConvergencePoint, ConflictZone) to dicts before JSON serialization
                flow_for_json = {
                    "day": day_code,
                    "events": day_flow.get("events", []),
                    "ok": day_flow.get("ok", False),
                    "total_segments": day_flow.get("total_segments", 0),
                    "segments_with_convergence": day_flow.get("segments_with_convergence", 0),
                    "segments": _convert_dataclasses_to_dicts(day_flow.get("segments", {}))
                }
                with open(flow_json_path, 'w', encoding='utf-8') as f:
                    json.dump(flow_for_json, f, indent=2)
                logger.info(f"  → Persisted flow_results.json: {flow_json_path}")
                persisted_files.append(f"flow_results.json ({day_code})")
        
        persistence_metrics.finish(memory_mb=get_memory_usage_mb())
        perf_monitor.complete_phase(
            persistence_metrics,
            phase_number="Phase 3.2",
            phase_description="Computation Persistence",
            summary_stats={"json_files": len(persisted_files)}
        )
        
        # Bin Generation (per day) - part of Phase 3.1, no separate phase tracking
        bins_by_day = {}
        for day, day_events in events_by_day.items():
            logger.info(f"[Phase 3.1] Processing bin generation for day: {day.value}")
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
        
        # Persist locations_results.json if locations_df exists (Issue #574, #581: Enhanced logging)
        # Issue #591: Compute resources_available per day
        if locations_df is not None:
            import pandas as pd
            from app.core.v2.bins import filter_segments_by_events
            
            locations_count = len(locations_df)
            logger.info(f"[Phase 3.2] Processing locations persistence...")
            for day, day_events in events_by_day.items():
                day_code = day.value
                logger.info(f"[Phase 3.2] Processing day: {day_code}")
                day_path = run_path / day_code
                computation_dir = day_path / "computation"
                computation_dir.mkdir(parents=True, exist_ok=True)
                
                # Issue #591: Filter locations by day to compute day-specific resources_available
                # Filter segments for this day
                day_segments_df = filter_segments_by_events(segments_df, day_events)
                day_segment_ids = set(day_segments_df['seg_id'].astype(str).unique())
                
                # Filter locations to those associated with day segments (similar to generate_locations_report_v2)
                if 'seg_id' in locations_df.columns:
                    def location_matches_day(row) -> bool:
                        """Check if location's seg_ids overlap with day segments, or if it's a proxy location for this day."""
                        # Check 'day' column first (if present) for all locations
                        if 'day' in row and pd.notna(row.get('day')):
                            loc_day = str(row.get('day')).lower()
                            if loc_day != day_code.lower():
                                return False
                        
                        # Include proxy locations ONLY if they match the requested day
                        if 'proxy_loc_id' in row and pd.notna(row.get('proxy_loc_id')):
                            return True
                        
                        # Check seg_id match for regular locations
                        loc_seg_ids = row.get('seg_id')
                        if pd.isna(loc_seg_ids) or not loc_seg_ids:
                            return False
                        loc_segs = [s.strip().strip('"').strip("'") for s in str(loc_seg_ids).split(',')]
                        return any(seg in day_segment_ids for seg in loc_segs)
                    
                    location_mask = locations_df.apply(location_matches_day, axis=1)
                    day_locations_df = locations_df[location_mask].copy()
                    
                    # Also include proxy source locations (locations that are referenced by proxy_loc_id)
                    if 'proxy_loc_id' in day_locations_df.columns:
                        proxy_source_ids = set(day_locations_df['proxy_loc_id'].dropna().astype(int).tolist())
                        if proxy_source_ids:
                            source_locations = locations_df[locations_df['loc_id'].isin(proxy_source_ids)]
                            missing_sources = source_locations[~source_locations['loc_id'].isin(day_locations_df['loc_id'])]
                            if not missing_sources.empty:
                                day_locations_df = pd.concat([day_locations_df, missing_sources], ignore_index=True)
                else:
                    day_locations_df = locations_df.copy()
                
                # Issue #591: Compute resources_available for this day
                # Detect all columns ending with "_count"
                count_columns = [col for col in day_locations_df.columns if col.endswith("_count")]
                
                # Find resources where at least one location has count > 0
                resources_available = []
                for count_col in count_columns:
                    # Check if any location has count > 0 for this resource
                    if not day_locations_df.empty:
                        # Convert to numeric, filling NaN with 0
                        numeric_counts = pd.to_numeric(day_locations_df[count_col], errors='coerce').fillna(0)
                        if (numeric_counts > 0).any():
                            # Extract prefix (e.g., "fpf" from "fpf_count")
                            resource_prefix = count_col.replace("_count", "")
                            resources_available.append(resource_prefix)
                
                # Sort for consistent output
                resources_available = sorted(resources_available)
                
                logger.info(f"  → Day {day_code}: Found {len(resources_available)} resources with count > 0: {resources_available}")
                
                # Persist all locations (locations are not day-partitioned in the data)
                # But resources_available IS day-specific
                locations_json_path = computation_dir / "locations_results.json"
                locations_for_json = {
                    "day": day_code,
                    "locations_count": locations_count,
                    "resources_available": resources_available,  # Issue #591: Day-specific resource list
                    "locations": locations_df.to_dict('records') if not locations_df.empty else []
                }
                with open(locations_json_path, 'w', encoding='utf-8') as f:
                    json.dump(locations_for_json, f, indent=2, default=str)
                logger.info(f"  → Persisted locations_results.json: {locations_json_path}")
                persisted_files.append(f"locations_results.json ({day_code})")
        
        # Phase 4.1: UI Artifacts Generation (Issue #574, #581: Enhanced logging)
        artifacts_metrics = perf_monitor.start_phase(
            "phase_4_1_ui_artifacts",
            phase_number="Phase 4.1",
            phase_description="UI Artifacts Generation"
        )
        from app.core.v2.ui_artifacts import generate_ui_artifacts_per_day
        artifacts_by_day = {}
        artifacts_count = 0
        for day, day_events in events_by_day.items():
            logger.info(f"[Phase 4.1] Processing day: {day.value}")
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
                    # Count artifacts (typically 8 per day: meta.json, segment_metrics.json, flags.json, etc.)
                    ui_dir = Path(artifacts_path)
                    if ui_dir.exists():
                        # Count files in subdirectories
                        metadata_count = len(list((ui_dir / "metadata").glob("*"))) if (ui_dir / "metadata").exists() else 0
                        metrics_count = len(list((ui_dir / "metrics").glob("*"))) if (ui_dir / "metrics").exists() else 0
                        geospatial_count = len(list((ui_dir / "geospatial").glob("*"))) if (ui_dir / "geospatial").exists() else 0
                        viz_count = len(list((ui_dir / "visualizations").glob("*.png"))) if (ui_dir / "visualizations").exists() else 0
                        day_artifacts = metadata_count + metrics_count + geospatial_count + viz_count
                        artifacts_count += day_artifacts
                        logger.info(f"  → Generated {day_artifacts} artifacts in 4 subdirectories: {artifacts_path}")
                    else:
                        logger.info(f"  → Generated UI artifacts: {artifacts_path}")
                else:
                    logger.warning(f"  → UI artifact generation returned None for day {day.value}")
            except Exception as e:
                logger.error(f"[Phase 4.1] ❌ ERROR: UI artifacts generation failed for day {day.value}")
                logger.error(f"  → Phase: UI Artifacts Generation")
                logger.error(f"  → Day: {day.value}")
                logger.error(f"  → Action: Generating UI artifacts with new subdirectory structure")
                logger.error(f"  → Exception: {type(e).__name__}: {e}", exc_info=True)
                raise  # Re-raise to fail the pipeline
        artifacts_metrics.finish(memory_mb=get_memory_usage_mb())
        perf_monitor.complete_phase(
            artifacts_metrics,
            phase_number="Phase 4.1",
            phase_description="UI Artifacts Generation",
            summary_stats={"artifacts": artifacts_count, "days": len(artifacts_by_day), "subdirectories": 4}
        )
        
        # Phase 4.2: Calculate Derived Metrics (RES, operational status) - Issue #574, #581: Enhanced logging
        # This happens AFTER UI artifacts (which generates segment_metrics.json) but BEFORE reports
        derived_metrics_phase = perf_monitor.start_phase(
            "phase_4_2_derived_metrics",
            phase_number="Phase 4.2",
            phase_description="Derived Metrics Calculation"
        )
        
        # Create day directories first (needed for metadata.json)
        for day, day_events in events_by_day.items():
            day_code = day.value
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
        
        # Calculate derived metrics per day
        derived_metrics_by_day = {}
        for day, day_events in events_by_day.items():
            day_code = day.value
            day_path = run_path / day_code
            ui_path = day_path / "ui"
            
            # Load segment_metrics.json (generated in Phase 4.1, Issue #574: now in metrics/ subdirectory)
            segment_metrics_path = ui_path / "metrics" / "segment_metrics.json"
            if not segment_metrics_path.exists():
                logger.warning(f"segment_metrics.json not found for {day_code}, skipping derived metrics")
                continue
            
            segment_metrics_data = json.loads(segment_metrics_path.read_text())
            
            # Calculate operational status
            peak_density = segment_metrics_data.get("peak_density", 0.0)
            max_flow_utilization = None
            
            # Find max flow_utilization from segment-level data
            for seg_id, seg_data in segment_metrics_data.items():
                if seg_id not in ["peak_density", "peak_rate", "segments_with_flags", 
                                 "flagged_bins", "overtaking_segments", "co_presence_segments"]:
                    if isinstance(seg_data, dict):
                        flow_util = seg_data.get("flow_utilization")
                        if flow_util is not None:
                            if max_flow_utilization is None or flow_util > max_flow_utilization:
                                max_flow_utilization = flow_util
            
            # Compute LOS and operational status
            los_letter = calculate_peak_density_los(peak_density)
            operational_status = compute_operational_status(los_letter, max_flow_utilization)
            
            # Calculate RES per event group
            event_groups_res = {}
            event_group_config = analysis_config.get("event_group") if analysis_config else None
            
            if event_group_config:
                # Filter segment_metrics to segment-level data only
                segment_metrics = {
                    seg_id: seg_data
                    for seg_id, seg_data in segment_metrics_data.items()
                    if seg_id not in ["peak_density", "peak_rate", "segments_with_flags", 
                                     "flagged_bins", "overtaking_segments", "co_presence_segments"]
                    and isinstance(seg_data, dict)
                }
                
                # Get event names for this day
                day_event_names = {e.name.lower() for e in day_events}
                
                # Calculate RES for each event group
                for group_id, group_events_str in event_group_config.items():
                    group_event_names = [
                        name.strip().lower() 
                        for name in group_events_str.split(",") 
                        if name.strip()
                    ]
                    
                    # Filter to only groups that have events for this day
                    day_group_events = [
                        event_name for event_name in group_event_names
                        if event_name in day_event_names
                    ]
                    
                    if len(day_group_events) == 0:
                        continue
                    
                    try:
                        from app.core.v2.res import calculate_res_per_event_group
                        res_score = calculate_res_per_event_group(
                            event_group_id=group_id,
                            event_names=day_group_events,
                            segment_metrics=segment_metrics,
                            segments_df=segments_df,
                            analysis_config=analysis_config
                        )
                        event_groups_res[group_id] = {
                            "events": day_group_events,
                            "res": round(res_score, 2)
                        }
                        logger.info(
                            f"Issue #574: Calculated RES for group '{group_id}' on {day_code}: "
                            f"{res_score:.2f} (events: {day_group_events})"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Issue #574: Failed to calculate RES for group '{group_id}' on {day_code}: {e}",
                            exc_info=True
                        )
            
            # Store derived metrics
            derived_metrics_by_day[day_code] = {
                "operational_status": operational_status,
                "los": los_letter,
                "peak_density": peak_density,
                "max_flow_utilization": max_flow_utilization,
                "event_groups": event_groups_res if event_groups_res else None
            }
            
            logger.info(
                f"Issue #574: Calculated derived metrics for {day_code}: "
                f"operational_status={operational_status}, los={los_letter}, "
                f"peak_density={peak_density:.3f}, res_groups={len(event_groups_res) if event_groups_res else 0}"
            )
        
        derived_metrics_phase.finish(memory_mb=get_memory_usage_mb())
        res_groups_count = sum(len(day_metrics.get("event_groups", {}) or {}) for day_metrics in derived_metrics_by_day.values())
        perf_monitor.complete_phase(
            derived_metrics_phase,
            phase_number="Phase 4.2",
            phase_description="Derived Metrics Calculation",
            summary_stats={"RES_groups": res_groups_count, "operational_status": len(derived_metrics_by_day), "days": len(derived_metrics_by_day)}
        )
        
        # Generate map_data.json per day (for density page map visualization)
        from app.core.v2.reports import get_day_output_path
        from app.density_report import generate_map_dataset
        maps_by_day = {}
        for day, day_events in events_by_day.items():
            try:
                maps_dir = get_day_output_path(run_id, day, "maps")
                maps_dir.mkdir(parents=True, exist_ok=True)
                
                # Get density results for this day
                day_density = density_results.get(day, {})
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
                logger.warning(f"[Phase 4.1] Could not generate map_data.json for day {day.value}: {e}", exc_info=True)
        
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
            
            # Issue #574: Use pre-calculated derived metrics from Phase 4.2
            derived_metrics = derived_metrics_by_day.get(day_code, {})
            if derived_metrics:
                metadata["operational_status"] = derived_metrics.get("operational_status", "Unknown")
                if derived_metrics.get("event_groups"):
                    metadata["event_groups"] = derived_metrics["event_groups"]
                logger.info(
                    f"Issue #574: Added derived metrics to metadata for {day_code}: "
                    f"operational_status={derived_metrics.get('operational_status')}, "
                    f"res_groups={len(derived_metrics.get('event_groups', {}))}"
                )
            else:
                metadata["operational_status"] = "Unknown"
                logger.warning(f"Issue #574: No derived metrics found for {day_code}, using defaults")
            
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
        
        # Phase 5: Report Generation (Issue #574, #581: Enhanced logging)
        # Reports are generated AFTER all metrics are calculated and persisted
        # Reports load from JSON artifacts (pure templating, no inline calculations)
        report_metrics = perf_monitor.start_phase(
            "phase_5_reports",
            phase_number="Phase 5",
            phase_description="Report Generation"
        )
        
        # Issue #574: Load computation results from JSON artifacts
        # This ensures reports use persisted data, not in-memory copies
        density_results_from_json = {}
        flow_results_from_json = {}
        locations_df_from_json = None
        
        for day, day_events in events_by_day.items():
            day_code = day.value
            day_path = run_path / day_code
            computation_dir = day_path / "computation"
            
            # Load density_results.json
            density_json_path = computation_dir / "density_results.json"
            if density_json_path.exists():
                try:
                    density_data = json.loads(density_json_path.read_text())
                    # Convert day string back to Day enum for compatibility
                    # Note: density_data has "day" as string, but we need Day enum key
                    # The report generation expects Day enum keys, so we'll keep using in-memory for now
                    # but this shows the structure is ready
                    logger.debug(f"Loaded density_results.json for {day_code} from {density_json_path}")
                except Exception as e:
                    logger.warning(f"Could not load density_results.json for {day_code}: {e}, using in-memory")
            
            # Load flow_results.json
            flow_json_path = computation_dir / "flow_results.json"
            if flow_json_path.exists():
                try:
                    flow_data = json.loads(flow_json_path.read_text())
                    logger.debug(f"Loaded flow_results.json for {day_code} from {flow_json_path}")
                except Exception as e:
                    logger.warning(f"Could not load flow_results.json for {day_code}: {e}, using in-memory")
        
        # Load locations_results.json (if exists)
        if locations_file:
            for day, day_events in events_by_day.items():
                day_code = day.value
                day_path = run_path / day_code
                computation_dir = day_path / "computation"
                locations_json_path = computation_dir / "locations_results.json"
                if locations_json_path.exists():
                    try:
                        import pandas as pd
                        locations_data = json.loads(locations_json_path.read_text())
                        locations_df_from_json = pd.DataFrame(locations_data.get("locations", []))
                        logger.debug(f"Loaded locations_results.json for {day_code} from {locations_json_path}")
                        break  # Locations are not day-partitioned, so load once
                    except Exception as e:
                        logger.warning(f"Could not load locations_results.json for {day_code}: {e}, using in-memory")
        
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
        
        # Generate reports
        # Issue #574: Reports now load from JSON artifacts where available, with fallback to in-memory
        # Note: Reports have access to RES data in metadata.json (calculated in Phase 4.2)
        # TODO: Full refactor to load from JSON only (remove in-memory fallback in future)
        try:
            reports_by_day = generate_reports_per_day(
                run_id=run_id,
                events=events,
                timelines=timelines,
                density_results=density_results,  # Issue #600: Still using in-memory for now (will be removed when Density fully refactored)
                segments_df=segments_df,
                all_runners_df=all_runners_df,
                data_dir=data_dir,
                segments_file_path=segments_file_path,
                flow_file_path=flow_file_path,
                locations_file_path=locations_file_path
            )
            
            # Count reports generated
            report_counts = {"Density.md": 0, "Flow.csv": 0, "Locations.csv": 0}
            for day_code, day_reports in reports_by_day.items():
                if day_reports.get("density_report"):
                    report_counts["Density.md"] += 1
                if day_reports.get("flow_report"):
                    report_counts["Flow.csv"] += 1
                if day_reports.get("locations_report"):
                    report_counts["Locations.csv"] += 1
            
            total_reports = sum(report_counts.values())
            report_metrics.finish(memory_mb=get_memory_usage_mb())
            perf_monitor.complete_phase(
                report_metrics,
                phase_number="Phase 5",
                phase_description="Report Generation",
                summary_stats={"reports": total_reports, "Density.md": report_counts["Density.md"], 
                              "Flow.csv": report_counts["Flow.csv"], "Locations.csv": report_counts["Locations.csv"]}
            )
            
            # Update metadata verification after reports are generated
            # Bug fix: Metadata was created before reports, causing false FAIL status
            logger.info("[Phase 5] Updating metadata verification after report generation")
            for day_code, day_metadata in day_metadata_map.items():
                day_path = run_path / day_code
                updated_metadata = _update_metadata_verification(day_path, day_metadata)
                day_metadata_map[day_code] = updated_metadata
                
                # Write updated metadata.json to disk
                metadata_path = day_path / "metadata.json"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(updated_metadata, f, indent=2, ensure_ascii=False)
                logger.info(f"[Phase 5] Updated metadata.json for {day_code}: status={updated_metadata['status']}")
        except Exception as e:
            logger.error(f"[Phase 5] ❌ ERROR: Report generation failed: {e}", exc_info=True)
            logger.error(f"  → Phase: Report Generation")
            logger.error(f"  → Action: Generating reports from persisted data")
            report_metrics.finish(memory_mb=get_memory_usage_mb())
            # Set empty reports dict to allow pipeline to continue
            reports_by_day = {}
            raise  # Re-raise to fail the pipeline
        
        # Phase 6: Metadata & Cleanup (Issue #574, #581: Enhanced logging)
        metadata_metrics = perf_monitor.start_phase(
            "phase_6_metadata",
            phase_number="Phase 6",
            phase_description="Metadata & Cleanup"
        )
        
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
        
        # Phase 6: Metadata & Cleanup (Issue #574, #581: Enhanced logging)
        metadata_metrics = perf_monitor.start_phase(
            "phase_6_metadata",
            phase_number="Phase 6",
            phase_description="Metadata & Cleanup"
        )
        
        # Issue #503: Add performance metrics to metadata
        perf_monitor.total_memory_mb = get_memory_usage_mb()
        combined_metadata["performance"] = perf_monitor.get_summary()
        
        # Write run-level metadata.json
        run_metadata_path = run_path / "metadata.json"
        with open(run_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"[Phase 6] Created metadata.json: {run_metadata_path}")
        
        # Issue #527: Add log file path to metadata (part of Phase 6)
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
        
        # Update pointer files (latest.json, index.json)
        update_pointer_files(run_id, combined_metadata)
        logger.info(f"[Phase 6] Updated pointer files (latest.json, index.json)")
        
        metadata_metrics.finish(memory_mb=get_memory_usage_mb())
        perf_monitor.complete_phase(
            metadata_metrics,
            phase_number="Phase 6",
            phase_description="Metadata & Cleanup",
            summary_stats={"metadata_files": len(days_processed), "pointers": 2}
        )
        
        # Issue #503: Log performance summary with phase mapping
        perf_monitor.log_summary(phase_mapping=PHASE_MAPPING)
        
        # Check overall guardrails
        total_elapsed = perf_monitor.get_total_elapsed()
        if total_elapsed > 300:  # 5 minutes
            logger.warning(
                f"⚠️  Total runtime ({total_elapsed/60:.1f} min) exceeds target (5 min). "
                f"Consider optimization opportunities."
            )
        
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

