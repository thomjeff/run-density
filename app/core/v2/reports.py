"""
Runflow v2 Reports Module

Generates day-partitioned reports (Density.md, Flow.md, Flow.csv, Locations.csv)
organized in runflow/{run_id}/{day}/reports/ structure.

Phase 6: Reports & Artifacts (Issue #500)
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.utils.run_id import get_runflow_root

logger = logging.getLogger(__name__)


def get_day_output_path(
    run_id: str,
    day: Day,
    category: str
) -> Path:
    """
    Generate day-partitioned output path for a specific category.
    
    Args:
        run_id: Unique run identifier (UUID)
        day: Day enum (fri, sat, sun, mon)
        category: Output category (reports, bins, maps, ui)
        
    Returns:
        Path object for the day-partitioned output directory
        
    Example:
        >>> path = get_day_output_path("abc123", Day.SUN, "reports")
        >>> str(path)
        'runflow/abc123/sun/reports'
    """
    runflow_root = get_runflow_root()
    day_path = runflow_root / run_id / day.value / category
    return day_path


def generate_reports_per_day(
    run_id: str,
    events: List[Event],
    timelines: List[DayTimeline],
    density_results: Dict[Day, Dict[str, Any]],
    flow_results: Dict[Day, Dict[str, Any]],
    segments_df: Any,  # pd.DataFrame
    all_runners_df: Any,  # pd.DataFrame
    locations_df: Optional[Any] = None,  # pd.DataFrame
    data_dir: str = "data"  # Data directory for loading runner files
) -> Dict[Day, Dict[str, str]]:
    """
    Generate all reports per day in day-partitioned structure.
    
    Main entry point for v2 report generation. Iterates over days and generates:
    - Density.md
    - Flow.md
    - Flow.csv
    - Locations.csv (if applicable)
    
    Args:
        run_id: Unique run identifier (UUID)
        events: List of Event objects from API payload
        timelines: List of DayTimeline objects from Phase 3
        density_results: Day-partitioned density analysis results from Phase 4
        flow_results: Day-partitioned flow analysis results from Phase 5
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame
        locations_df: Optional locations DataFrame
        
    Returns:
        Dictionary mapping Day to report file paths:
        {
            Day.SUN: {
                "density": "runflow/{run_id}/sun/reports/Density.md",
                "flow_md": "runflow/{run_id}/sun/reports/Flow.md",
                "flow_csv": "runflow/{run_id}/sun/reports/Flow.csv",
                "locations": "runflow/{run_id}/sun/reports/Locations.csv",
            },
            ...
        }
    """
    report_paths_by_day: Dict[Day, Dict[str, str]] = {}
    
    for timeline in timelines:
        day = timeline.day
        day_events = timeline.events
        
        # Get day output path for reports
        reports_path = get_day_output_path(run_id, day, "reports")
        reports_path.mkdir(parents=True, exist_ok=True)
        
        # Validate reports_path is for correct day
        expected_day_in_path = day.value
        if expected_day_in_path not in str(reports_path):
            logger.error(
                f"Reports path mismatch: expected day '{expected_day_in_path}' in path, "
                f"but got '{reports_path}'. This indicates a day-scoping bug."
            )
            raise ValueError(f"Reports path does not match day: {day.value}")
        
        day_report_paths: Dict[str, str] = {}
        
        # Filter segments by day events before report generation
        from app.core.v2.bins import filter_segments_by_events
        day_segments_df = filter_segments_by_events(segments_df, day_events)
        logger.info(
            f"Filtered segments for day {day.value}: {len(segments_df)} -> {len(day_segments_df)} "
            f"for events: {[e.name for e in day_events]}"
        )
        
        # Generate Density.md
        if day in density_results:
            density_path = generate_density_report_v2(
                run_id=run_id,
                day=day,
                day_events=day_events,
                density_results=density_results[day],
                reports_path=reports_path,
                segments_df=day_segments_df,
                data_dir=data_dir
            )
            if density_path:
                day_report_paths["density"] = str(density_path)
        
        # Generate Flow.md and Flow.csv
        if day in flow_results:
            try:
                flow_paths = generate_flow_report_v2(
                    run_id=run_id,
                    day=day,
                    day_events=day_events,
                    flow_results=flow_results[day],
                    reports_path=reports_path
                )
                day_report_paths.update(flow_paths)
            except Exception as e:
                logger.error(f"Failed to generate flow report for day {day.value}: {e}", exc_info=True)
                # Continue with other reports even if flow fails
        else:
            logger.warning(f"No flow results found for day {day.value}, skipping flow report generation")
        
        # Generate Locations.csv (if applicable)
        if locations_df is not None:
            locations_path = generate_locations_report_v2(
                run_id=run_id,
                day=day,
                day_events=day_events,
                locations_df=locations_df,
                all_runners_df=all_runners_df,
                reports_path=reports_path,
                segments_df=day_segments_df
            )
            if locations_path:
                day_report_paths["locations"] = str(locations_path)
        
        report_paths_by_day[day] = day_report_paths
        
        logger.info(
            f"Generated {len(day_report_paths)} reports for day {day.value} "
            f"in {reports_path}"
        )
    
    return report_paths_by_day


def generate_density_report_v2(
    run_id: str,
    day: Day,
    day_events: List[Event],
    density_results: Dict[str, Any],
    reports_path: Path,
    segments_df: Optional[Any] = None,  # pd.DataFrame - day-filtered segments
    data_dir: str = "data"  # Data directory for loading runner files
) -> Optional[Path]:
    """
    Generate day-scoped density report (Density.md).
    
    Uses generate_new_density_report_issue246 for Schema 1.0.0 format.
    Filters segments, bins, and segment_windows by day/events before report generation.
    
    Args:
        run_id: Unique run identifier
        day: Day enum
        day_events: List of events for this day
        density_results: Density analysis results for this day
        reports_path: Path to reports directory for this day
        segments_df: Optional day-filtered segments DataFrame (if None, will load and filter)
        
    Returns:
        Path to generated Density.md file, or None if generation failed
    """
    try:
        import pandas as pd
        import shutil
        from pathlib import Path as PathType
        from app.density_report import generate_new_density_report_issue246
        from app.new_density_report import load_parquet_sources
        from app.core.v2.bins import filter_segments_by_events
        from app.utils.run_id import get_runflow_root
        from app.utils.metadata import get_app_version
        
        # Get bins directory for this day
        runflow_root = get_runflow_root()
        bins_dir = runflow_root / run_id / day.value / "bins"
        
        # Copy bins files to reports directory if they exist (required for new format)
        source_bins_parquet = bins_dir / "bins.parquet"
        source_segment_windows = bins_dir / "segment_windows_from_bins.parquet"
        
        bins_parquet = reports_path / "bins.parquet"
        segment_windows_parquet = reports_path / "segment_windows_from_bins.parquet"
        
        if not source_bins_parquet.exists():
            logger.error(f"bins.parquet not found at {source_bins_parquet}, cannot generate new format report")
            raise FileNotFoundError(f"bins.parquet required for Schema 1.0.0 density report not found at {source_bins_parquet}")
        
        # Copy bins files to reports directory
        if source_bins_parquet.exists() and not bins_parquet.exists():
            shutil.copy2(source_bins_parquet, bins_parquet)
            logger.debug(f"Copied bins.parquet to reports directory")
        
        if source_segment_windows.exists() and not segment_windows_parquet.exists():
            shutil.copy2(source_segment_windows, segment_windows_parquet)
            logger.debug(f"Copied segment_windows_from_bins.parquet to reports directory")
        
        # Load and filter bins by day segments
        bins_df = pd.read_parquet(bins_parquet)
        segment_windows_df = pd.read_parquet(segment_windows_parquet) if segment_windows_parquet.exists() else pd.DataFrame()
        
        # Get day-filtered segments
        if segments_df is None:
            from app.io.loader import load_segments
            all_segments_df = load_segments("data/segments.csv")
            segments_df = filter_segments_by_events(all_segments_df, day_events)
        
        # Get list of day segment IDs
        day_segment_ids = set(segments_df['seg_id'].astype(str).unique())
        
        # Filter bins to only include day segments
        # bins.parquet has 'seg_id' column
        if 'seg_id' in bins_df.columns:
            bins_df_filtered = bins_df[bins_df['seg_id'].astype(str).isin(day_segment_ids)].copy()
            logger.info(f"Filtered bins: {len(bins_df)} -> {len(bins_df_filtered)} for day {day.value} segments")
        else:
            logger.warning(f"bins.parquet missing 'seg_id' column, cannot filter by day")
            bins_df_filtered = bins_df
        
        # Filter segment_windows to only include day segments
        if not segment_windows_df.empty and 'seg_id' in segment_windows_df.columns:
            segment_windows_df_filtered = segment_windows_df[
                segment_windows_df['seg_id'].astype(str).isin(day_segment_ids)
            ].copy()
            logger.info(f"Filtered segment_windows: {len(segment_windows_df)} -> {len(segment_windows_df_filtered)} for day {day.value} segments")
        else:
            segment_windows_df_filtered = segment_windows_df
        
        # Save filtered bins and segment_windows back to reports directory
        bins_df_filtered.to_parquet(bins_parquet, index=False)
        if not segment_windows_df_filtered.empty:
            segment_windows_df_filtered.to_parquet(segment_windows_parquet, index=False)
        
        # Save filtered segments to reports directory (for generate_new_density_report_issue246)
        segments_parquet = reports_path / "segments.parquet"
        # Ensure seg_id column exists (may be renamed to segment_id in some contexts)
        segments_for_report = segments_df.copy()
        if 'seg_id' in segments_for_report.columns and 'segment_id' not in segments_for_report.columns:
            segments_for_report = segments_for_report.rename(columns={'seg_id': 'segment_id'})
        segments_for_report.to_parquet(segments_parquet, index=False)
        logger.info(f"Saved {len(segments_for_report)} day-filtered segments to {segments_parquet}")
        
        # Generate new format report using filtered data
        try:
            app_version = get_app_version()
            
            # Extract event information for start times section
            # Get event names, start times, and runner counts from runner files
            event_info = {}
            for event in day_events:
                runner_count = 0
                try:
                    # Load runner file for this event to get count
                    from app.io.loader import load_runners
                    runner_file = Path(data_dir) / event.runners_file if hasattr(event, 'runners_file') else Path(data_dir) / f"{event.name}_runners.csv"
                    if runner_file.exists():
                        runners_df = load_runners(str(runner_file))
                        # Filter by day if day column exists
                        if 'day' in runners_df.columns:
                            runners_df = runners_df[runners_df['day'].str.lower() == day.value.lower()]
                        runner_count = len(runners_df)
                except Exception as e:
                    logger.debug(f"Could not get runner count for {event.name}: {e}")
                
                event_info[event.name] = {
                    'start_time': event.start_time,
                    'start_time_formatted': f"{int(event.start_time // 60):02d}:{int(event.start_time % 60):02d}",
                    'runner_count': runner_count
                }
            
            results = generate_new_density_report_issue246(
                reports_dir=str(reports_path),
                output_path=str(reports_path / "Density.md"),
                app_version=app_version,
                events=event_info  # Pass event info for dynamic start times
            )
            
            if results.get('success'):
                density_path = reports_path / "Density.md"
                logger.info(f"Generated Density.md (Schema 1.0.0) for day {day.value}: {density_path}")
                return density_path
            else:
                error_msg = f"New report format generation failed: {results.get('error', 'Unknown error')}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        except Exception as e:
            logger.error(f"Failed to generate new format report: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate Schema 1.0.0 density report: {e}") from e
        
    except (FileNotFoundError, RuntimeError):
        # Re-raise these errors (they're already logged)
        raise
    except Exception as e:
        logger.error(f"Failed to generate density report for day {day.value}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate Schema 1.0.0 density report for day {day.value}: {e}") from e


# Legacy format removed - v2 only uses Schema 1.0.0 format


def generate_flow_report_v2(
    run_id: str,
    day: Day,
    day_events: List[Event],
    flow_results: Dict[str, Any],
    reports_path: Path
) -> Dict[str, str]:
    """
    Generate day-scoped flow reports (Flow.md and Flow.csv).
    
    Args:
        run_id: Unique run identifier
        day: Day enum
        day_events: List of events for this day
        flow_results: Flow analysis results for this day
        reports_path: Path to reports directory for this day
        
    Returns:
        Dictionary with flow_md and flow_csv paths
    """
    flow_paths: Dict[str, str] = {}
    
    try:
        # Import here to avoid circular dependencies
        from app.flow_report import generate_temporal_flow_report
        
        # Extract start_times from day_events
        # generate_flow_markdown expects minutes (float), not datetime
        start_times: Dict[str, float] = {}
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",
            "open": "Open"
        }
        
        for event in day_events:
            v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
            # start_times expects minutes after midnight (already in Event.start_time)
            start_times[v1_event_name] = float(event.start_time)
        
        # Generate flow report using existing function
        # Note: analyze_temporal_flow_segments_v2 returns results with same structure as v1
        # (it calls analyze_temporal_flow_segments internally), so we can use it directly
        if not flow_results.get("ok", False):
            logger.warning(f"Flow analysis failed for day {day.value}, skipping report")
            return flow_paths
        
        # Convert v2 flow_results structure to v1 format for report generation
        # v2 structure: {"ok": True, "pairs": [...], "segments": {"pair_key": [...]}}
        # v1 structure: {"ok": True, "segments": [...]}
        # Note: v1 analyze_temporal_flow_segments returns segments as a list, not a dict
        v1_flow_results = {
            "ok": flow_results.get("ok", False),
            "engine": "temporal_flow",
            "segments": []
        }
        
        # Handle both list and dict structures for segments
        segments_data = flow_results.get("segments", [])
        if isinstance(segments_data, list):
            # Already in v1 format (list of segment dicts)
            v1_flow_results["segments"] = segments_data
        elif isinstance(segments_data, dict):
            # v2 format (dict with pair keys) - flatten into list
            for pair_key, pair_segments in segments_data.items():
                if isinstance(pair_segments, list):
                    v1_flow_results["segments"].extend(pair_segments)
                elif isinstance(pair_segments, dict):
                    v1_flow_results["segments"].append(pair_segments)
        
        from app.flow_report import generate_markdown_report as generate_flow_markdown
        
        # Generate flow markdown content
        flow_md_content = generate_flow_markdown(
            results=v1_flow_results,
            start_times=start_times
        )
        
        # Add day identifier to flow report header
        day_header = f"# Flow Analysis - {day.value.upper()}\n\n"
        day_header += f"**Run ID:** {run_id}\n"
        day_header += f"**Day:** {day.value}\n"
        day_header += f"**Events:** {', '.join([e.name for e in day_events])}\n\n"
        day_header += "---\n\n"
        
        flow_md_content = day_header + flow_md_content
        
        # Save Flow.md
        flow_md_path = reports_path / "Flow.md"
        flow_md_path.write_text(flow_md_content, encoding='utf-8')
        flow_paths["flow_md"] = str(flow_md_path)
        
        # Generate Flow.csv using v1 export function for consistency
        from app.flow_report import export_temporal_flow_csv
        flow_csv_path = reports_path / "Flow.csv"
        
        # export_temporal_flow_csv expects a directory path, not a file path
        # It will create Flow.csv inside that directory with timestamp
        try:
            export_temporal_flow_csv(
                results=v1_flow_results,
                output_path=str(reports_path),
                start_times=start_times,
                run_id=run_id
            )
            
            # Find the generated Flow.csv (might have timestamp in name)
            flow_csv_files = list(reports_path.glob("Flow*.csv"))
            if flow_csv_files:
                # Use the most recent one if multiple exist
                flow_csv_path = max(flow_csv_files, key=lambda p: p.stat().st_mtime)
                # Rename to standard Flow.csv if needed
                if flow_csv_path.name != "Flow.csv":
                    standard_path = reports_path / "Flow.csv"
                    flow_csv_path.rename(standard_path)
                    flow_csv_path = standard_path
            else:
                # Fallback: create empty CSV if export failed
                import pandas as pd
                pd.DataFrame().to_csv(flow_csv_path, index=False)
                logger.warning(f"export_temporal_flow_csv did not create file, created empty Flow.csv")
            
            flow_paths["flow_csv"] = str(flow_csv_path)
            logger.info(f"Generated Flow.csv for day {day.value}: {flow_csv_path}")
        except Exception as e:
            logger.error(f"Failed to export Flow.csv for day {day.value}: {e}", exc_info=True)
            # Create empty CSV as fallback
            import pandas as pd
            pd.DataFrame().to_csv(flow_csv_path, index=False)
            flow_paths["flow_csv"] = str(flow_csv_path)
        
        logger.info(f"Generated flow reports for day {day.value} at {reports_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate flow report for day {day.value}: {e}", exc_info=True)
    
    return flow_paths


def generate_locations_report_v2(
    run_id: str,
    day: Day,
    day_events: List[Event],
    locations_df: Any,  # pd.DataFrame
    all_runners_df: Any,  # pd.DataFrame
    reports_path: Path,
    segments_df: Optional[Any] = None  # pd.DataFrame - day-filtered segments
) -> Optional[Path]:
    """
    Generate day-scoped locations report (Locations.csv).
    
    Filters locations by day/events and uses location_report.py for proper generation.
    
    Args:
        run_id: Unique run identifier
        day: Day enum
        day_events: List of events for this day
        locations_df: Full locations DataFrame
        all_runners_df: Full runners DataFrame
        reports_path: Path to reports directory for this day
        segments_df: Optional day-filtered segments DataFrame
        
    Returns:
        Path to generated Locations.csv file, or None if generation failed
    """
    try:
        import pandas as pd
        from app.location_report import generate_location_report
        from app.core.v2.bins import filter_segments_by_events
        
        # Filter runners to this day
        day_event_names = {event.name.lower() for event in day_events}
        day_runners_df = all_runners_df[
            all_runners_df["event"].astype(str).str.lower().isin(day_event_names)
        ].copy()
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value}, skipping locations report")
            return None
        
        # Get day-filtered segments if not provided
        if segments_df is None:
            from app.io.loader import load_segments
            all_segments_df = load_segments("data/segments.csv")
            segments_df = filter_segments_by_events(all_segments_df, day_events)
        
        # Get day segment IDs
        day_segment_ids = set(segments_df['seg_id'].astype(str).unique())
        
        # Filter locations to those associated with day segments
        # locations.csv has 'seg_id' column (may be comma-separated list)
        # IMPORTANT: Include proxy locations (with proxy_loc_id) even if they don't match day segments
        # BUT only if they match the requested day (check 'day' column if present)
        # AND include their proxy source locations so proxy timing can be copied
        if 'seg_id' in locations_df.columns:
            def location_matches_day(row) -> bool:
                """Check if location's seg_ids overlap with day segments, or if it's a proxy location for this day."""
                # Include proxy locations ONLY if they match the requested day
                if 'proxy_loc_id' in row and pd.notna(row.get('proxy_loc_id')):
                    # Check if location has a 'day' column and it matches the requested day
                    if 'day' in row and pd.notna(row.get('day')):
                        return str(row.get('day')).lower() == day.value.lower()
                    # If no day column, include proxy locations (backward compatibility)
                    # but this should be avoided - locations should have day specified
                    return True
                
                # Check seg_id match
                loc_seg_ids = row.get('seg_id')
                if pd.isna(loc_seg_ids) or not loc_seg_ids:
                    return False
                # Handle comma-separated seg_ids
                loc_segs = [s.strip() for s in str(loc_seg_ids).split(',')]
                return any(seg in day_segment_ids for seg in loc_segs)
            
            location_mask = locations_df.apply(location_matches_day, axis=1)
            day_locations_df = locations_df[location_mask].copy()
            
            # Also include proxy source locations (locations that are referenced by proxy_loc_id)
            # This ensures proxy locations can find their source locations
            if 'proxy_loc_id' in day_locations_df.columns:
                proxy_source_ids = set(day_locations_df['proxy_loc_id'].dropna().astype(int).tolist())
                if proxy_source_ids:
                    # Find source locations that are referenced by proxy locations
                    source_locations = locations_df[locations_df['loc_id'].isin(proxy_source_ids)]
                    # Add source locations that aren't already included
                    missing_sources = source_locations[~source_locations['loc_id'].isin(day_locations_df['loc_id'])]
                    if not missing_sources.empty:
                        day_locations_df = pd.concat([day_locations_df, missing_sources], ignore_index=True)
                        logger.debug(
                            f"Added {len(missing_sources)} proxy source locations to day {day.value} report: "
                            f"{missing_sources['loc_id'].tolist()}"
                        )
            
            proxy_count = len(day_locations_df[day_locations_df['proxy_loc_id'].notna()]) if 'proxy_loc_id' in day_locations_df.columns else 0
            logger.info(
                f"Filtered locations for day {day.value}: {len(locations_df)} -> {len(day_locations_df)} "
                f"(including {proxy_count} proxy locations) matching segments: {sorted(day_segment_ids)}"
            )
        else:
            logger.warning(f"locations.csv missing 'seg_id' column, cannot filter by day")
            day_locations_df = locations_df
        
        if day_locations_df.empty:
            logger.warning(f"No locations found for day {day.value} segments, skipping locations report")
            return None
        
        # Use location_report.py to generate proper Locations.csv
        # Create temporary files for location_report (it expects CSV file paths)
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_runners_path = os.path.join(tmpdir, "runners.csv")
            tmp_segments_path = os.path.join(tmpdir, "segments.csv")
            tmp_locations_path = os.path.join(tmpdir, "locations.csv")
            
            # Save filtered data to temporary CSV files
            day_runners_df.to_csv(tmp_runners_path, index=False)
            segments_df.to_csv(tmp_segments_path, index=False)
            day_locations_df.to_csv(tmp_locations_path, index=False)
            
            # Extract start_times from day_events for location_report
            start_times: Dict[str, float] = {}
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
            
            # Generate location report using v1 function
            # location_report.py expects CSV file paths
            # NOTE: Do NOT pass run_id to generate_location_report when using v2 structure
            # because it will use get_runflow_category_path which creates runflow/{run_id}/reports
            # instead of runflow/{run_id}/{day}/reports. We pass output_dir directly instead.
            result = generate_location_report(
                locations_csv=tmp_locations_path,
                runners_csv=tmp_runners_path,
                segments_csv=tmp_segments_path,
                start_times=start_times,
                output_dir=str(reports_path),
                run_id=None  # Don't pass run_id - use output_dir directly for v2 day-partitioned structure
            )
            
            # location_report.py saves to output_dir/Locations.csv via get_report_paths
            locations_path = reports_path / "Locations.csv"
            if locations_path.exists():
                logger.info(f"Generated Locations.csv for day {day.value} at {locations_path}")
                return locations_path
            else:
                logger.warning(f"Location report generation did not create file at {locations_path}")
                return None
        
    except Exception as e:
        logger.error(f"Failed to generate locations report for day {day.value}: {e}", exc_info=True)
        return None


def copy_bin_artifacts(
    bins_dir: Path,
    target_bins_dir: Path
) -> None:
    """
    Copy bin artifacts from source to target directory.
    
    This is a no-op if source and target are the same (already in place).
    
    Args:
        bins_dir: Source bins directory
        target_bins_dir: Target bins directory
    """
    import shutil
    
    if bins_dir == target_bins_dir:
        logger.debug(f"Bin artifacts already in target location: {target_bins_dir}")
        return
    
    target_bins_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy bin artifacts
    artifacts = [
        "bins.parquet",
        "bins.geojson.gz",
        "bin_summary.json",
        "segment_windows_from_bins.parquet"
    ]
    
    for artifact in artifacts:
        source_path = bins_dir / artifact
        target_path = target_bins_dir / artifact
        
        if source_path.exists():
            if source_path != target_path:  # Avoid SameFileError
                shutil.copy2(source_path, target_path)
                logger.debug(f"Copied {artifact} to {target_path}")
        else:
            logger.debug(f"Bin artifact {artifact} not found at {source_path}, skipping")
    
    logger.info(f"Copied bin artifacts from {bins_dir} to {target_bins_dir}")

