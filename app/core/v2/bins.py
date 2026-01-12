"""
V2 Bin Generation Module

Wraps v1 bin generation logic to support day-partitioned output structure.
Also provides segment filtering utilities used by density and flow analysis.
"""

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

from app.density_report import (
    BinGenerationContext,
    _generate_bin_dataset_with_retry,
    _save_bin_artifacts_and_metadata,
    _process_segments_from_bins
)
from app.save_bins import save_bin_artifacts
from app.core.bin.summary import generate_bin_summary_artifact
from app.utils.constants import BIN_SCHEMA_VERSION
from app.core.v2.models import Day, Event
from app.config.loader import AnalysisContext as ConfigAnalysisContext, load_analysis_context
from app.utils.run_id import get_runflow_root

logger = logging.getLogger(__name__)


def filter_segments_by_events(segments_df: pd.DataFrame, events: List[Event]) -> pd.DataFrame:
    """
    Filter segments to those used by ANY of the requested events.
    
    This is used for density analysis to find all segments where at least one
    of the requested events is present. For flow analysis, use get_shared_segments()
    instead to find segments where BOTH events are present.
    
    Args:
        segments_df: Full segments DataFrame
        events: List of Event objects to filter by
        
    Returns:
        Filtered DataFrame containing only segments used by at least one event
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "A2", "B1"],
        ...     "full": ["y", "n", "y"],
        ...     "half": ["y", "n", "n"],
        ... })
        >>> events = [Event(name="full", day=Day.SUN, ...), Event(name="half", day=Day.SUN, ...)]
        >>> filtered = filter_segments_by_events(segments_df, events)
        >>> len(filtered) == 2  # A1 (both), B1 (full only)
        True
    """
    if segments_df.empty or not events:
        return segments_df.copy()
    
    # Build mask for segments used by any event
    combined_mask = pd.Series([False] * len(segments_df), index=segments_df.index)
    
    for event in events:
        event_name = event.name.lower()
        
        # Find column matching event name (case-insensitive)
        for col in segments_df.columns:
            if col.lower() == event_name:
                event_mask = segments_df[col].astype(str).str.lower().isin(['y', 'yes', 'true', '1'])
                combined_mask |= event_mask
                break
    
    filtered_segments = segments_df[combined_mask].copy()
    
    logger.debug(
        f"Filtered segments: {len(segments_df)} -> {len(filtered_segments)} "
        f"for {len(events)} events: {[e.name for e in events]}"
    )
    
    return filtered_segments


def generate_bins_v2(
    density_results: Dict[str, Any],
    start_times: Dict[str, float],
    segments_df: pd.DataFrame,
    runners_df: pd.DataFrame,
    run_id: str,
    day: Day,
    events: List[Event],
    data_dir: str,
    segments_csv_path: Optional[str] = None,  # Issue #616: Use segments_file from analysis.json
    analysis_context: Optional[ConfigAnalysisContext] = None
) -> Optional[Path]:
    """
    Generate bin artifacts for a specific day using v1 bin generation logic.
    
    This function wraps the v1 bin generation to:
    1. Create AnalysisContext with v2 data
    2. Temporarily provide combined runners CSV for build_runner_window_mapping()
    3. Call v1 bin generation functions
    4. Save artifacts to day-partitioned structure: runflow/analysis/{run_id}/{day}/bins/
    
    Args:
        density_results: Density analysis results from analyze_density_segments_v2()
        start_times: Dictionary mapping event names to start times in minutes (float)
        segments_df: Segments DataFrame
        runners_df: Runners DataFrame (filtered to day)
        run_id: Run identifier
        day: Day enum
        events: List of events for this day
        data_dir: Base directory for data files (used as fallback)
        segments_csv_path: Path to segments CSV file (from analysis.json).
        analysis_context: Optional analysis context loaded from analysis.json to avoid reloading config.
        
    Returns:
        Path to bins directory if successful, None otherwise
    """
    # Check if bin generation is enabled
    enable_bins = os.getenv('ENABLE_BIN_DATASET', 'true').lower() == 'true'
    if not enable_bins:
        logger.info(f"Bin dataset generation disabled (ENABLE_BIN_DATASET=false) for day {day.value}")
        return None
    
    logger.info(f"Generating bin artifacts for day {day.value}")
    
    try:
        # Get day-partitioned bins directory
        from app.core.v2.reports import get_day_output_path
        bins_dir = get_day_output_path(run_id, day, "bins")
        bins_dir.mkdir(parents=True, exist_ok=True)
        
        if segments_csv_path is None:
            raise ValueError(
                "segments_csv_path must be provided to generate_bins_v2 from analysis.json."
            )
        logger.info(f"Issue #616: Using segments_csv_path={segments_csv_path} from analysis.json")
        
        # Issue #616: build_runner_window_mapping uses per-event runner files; no temp data/runners.csv needed
        
        # Issue #553 Phase 4.2 & 4.3: Load event configuration from analysis.json (SSOT)
        # This must happen BEFORE creating BinGenerationContext to avoid overwriting the SSOT context
        event_durations = {}
        event_names = []
        config_analysis_context = analysis_context  # Keep SSOT context separate
        try:
            if config_analysis_context is None:
                runflow_root = get_runflow_root()
                run_path = runflow_root / run_id
                config_analysis_context = load_analysis_context(run_path)
            analysis_config = config_analysis_context.analysis_config
            
            # Extract event names and durations from analysis.json
            events_list = analysis_config.get("events", [])
            for event in events_list:
                event_name = event.get("name", "")
                duration = event.get("event_duration_minutes")
                if event_name:
                    event_names.append(event_name.lower())
                    if duration:
                        # Support both original case and lowercase for lookup
                        event_durations[event_name] = duration
                        event_durations[event_name.lower()] = duration
            
            logger.debug(f"Loaded event names from analysis.json: {event_names}")
            logger.debug(f"Loaded event durations from analysis.json: {event_durations}")
        except Exception as e:
            logger.error(f"Failed to load event configuration from analysis.json: {e}")
            # Issue #553: Fail fast - event configuration is required
            raise ValueError(
                f"Cannot generate bins without event configuration from analysis.json: {e}"
            )
        
        # Issue #655: Create BinGenerationContext (legacy dataclass for bin generation parameters)
        # Note: This is different from ConfigAnalysisContext (SSOT config loader from app.config.loader)
        # Use a different variable name to avoid overwriting the SSOT context
        bin_gen_context = BinGenerationContext(
            course_id="fredericton_marathon",
            segments=segments_df,
            runners=runners_df,
            params={"start_times": start_times},
            code_version="v2.0.0",
            schema_version=BIN_SCHEMA_VERSION,
            pace_csv_path="",
            segments_csv_path=segments_csv_path
        )
        
        # Issue #519: Filter density_results to only include day-specific segments
        # This prevents bin generation from creating bins for all segments
        # and eliminates the need for duplicate filtering later
        filtered_density_results = density_results.copy()
        if "segments" in filtered_density_results and isinstance(filtered_density_results["segments"], dict):
            # Get day segment IDs (check both seg_id and segment_id columns)
            seg_id_col = None
            if "seg_id" in segments_df.columns:
                seg_id_col = "seg_id"
            elif "segment_id" in segments_df.columns:
                seg_id_col = "segment_id"
            
            if seg_id_col:
                day_segment_ids = set(segments_df[seg_id_col].astype(str).unique().tolist())
                
                # Normalize sub-segments to base segments (e.g., N2a, N2b -> N2)
                normalized_day_segment_ids = set()
                for seg_id in day_segment_ids:
                    normalized_day_segment_ids.add(seg_id)
                    # Add base segment (strip trailing letters)
                    base_seg = seg_id.rstrip('abcdefghijklmnopqrstuvwxyz')
                    if base_seg != seg_id:
                        normalized_day_segment_ids.add(base_seg)
                
                # Filter segments dictionary to only include day segments
                original_segments = filtered_density_results["segments"]
                filtered_segments = {}
                
                for seg_id, seg_data in original_segments.items():
                    seg_id_str = str(seg_id)
                    # Check exact match
                    if seg_id_str in normalized_day_segment_ids:
                        filtered_segments[seg_id] = seg_data
                    else:
                        # Check if segment is a sub-segment of a day segment
                        base_seg = seg_id_str.rstrip('abcdefghijklmnopqrstuvwxyz')
                        if base_seg in normalized_day_segment_ids:
                            filtered_segments[seg_id] = seg_data
                
                filtered_density_results["segments"] = filtered_segments
                
                logger.info(
                    f"Filtered density_results for day {day.value}: "
                    f"{len(original_segments)} -> {len(filtered_segments)} segments "
                    f"(day segments: {sorted(day_segment_ids)})"
                )
                
                # Update summary counts if present
                if "summary" in filtered_density_results:
                    summary = filtered_density_results["summary"]
                    summary["total_segments"] = len(filtered_segments)
                    # Recalculate processed_segments count
                    processed_count = sum(
                        1 for seg_data in filtered_segments.values()
                        if isinstance(seg_data, dict) and seg_data.get("summary", {}).get("processed", False)
                    )
                    summary["processed_segments"] = processed_count
                    summary["skipped_segments"] = len(filtered_segments) - processed_count
            else:
                logger.warning(f"segments_df missing 'seg_id' or 'segment_id' column, cannot filter density_results")
        else:
            logger.warning(f"density_results missing 'segments' dict, cannot filter by day")
        
        # Issue #553 Phase 4.3: Filter event_durations to match current day's events
        # start_times only contains events for the current day, so filter event_durations accordingly
        day_event_durations = {}
        for event_name in start_times.keys():
            event_name_lower = event_name.lower()
            # Try both original case and lowercase
            if event_name in event_durations:
                day_event_durations[event_name] = event_durations[event_name]
            if event_name_lower in event_durations:
                day_event_durations[event_name_lower] = event_durations[event_name_lower]
        
        logger.debug(f"Filtered event_durations for day {day.value}: {day_event_durations}")
        
        # Call v1 bin generation with retry logic
        start_time = time.monotonic()
        temp_output_dir = tempfile.mkdtemp()
        
        try:
            # Issue #655: Pass SSOT ConfigAnalysisContext to _generate_bin_dataset_with_retry
            # instead of BinGenerationContext, because build_runner_window_mapping expects
            # the SSOT context with runners_csv_path() method
            daily_folder_path, bin_metadata, bin_data = _generate_bin_dataset_with_retry(
                filtered_density_results, start_times, temp_output_dir, config_analysis_context, 
                day_event_durations, event_names
            )
            
            if not daily_folder_path:
                logger.error(f"Bin generation returned no folder path for day {day.value}")
                return None
            
            # Move bin artifacts from temp location to day-partitioned bins directory
            temp_bins_dir = Path(daily_folder_path)
            bins_successfully_copied = False
            if temp_bins_dir.exists():
                # Safety check: Filter bins.parquet by day segments before copying
                # After Issue #519, this should be a no-op since density_results is filtered
                # before bin generation, but we keep it as a safety check
                bins_parquet_src = temp_bins_dir / "bins.parquet"
                if bins_parquet_src.exists():
                    import pandas as pd
                    bins_df = pd.read_parquet(bins_parquet_src)
                    
                    # Get day segment IDs (check both seg_id and segment_id columns)
                    seg_id_col = None
                    if "seg_id" in segments_df.columns:
                        seg_id_col = "seg_id"
                    elif "segment_id" in segments_df.columns:
                        seg_id_col = "segment_id"
                    
                    if not seg_id_col:
                        logger.warning(f"segments_df missing 'seg_id' or 'segment_id' column, cannot filter bins by day")
                        logger.warning(f"segments_df columns: {list(segments_df.columns)}")
                        shutil.copy2(bins_parquet_src, bins_dir / "bins.parquet")
                        bins_successfully_copied = True
                    else:
                        day_segment_ids = set(segments_df[seg_id_col].astype(str).unique().tolist())
                        logger.debug(f"Day {day.value} segments_df has {len(segments_df)} segments with IDs: {sorted(day_segment_ids)}")
                        
                        # Normalize sub-segments to base segments (e.g., N2a, N2b -> N2)
                        # Also include sub-segments that start with base segment IDs
                        normalized_day_segment_ids = set()
                        for seg_id in day_segment_ids:
                            normalized_day_segment_ids.add(seg_id)
                            # Add base segment (strip trailing letters)
                            base_seg = seg_id.rstrip('abcdefghijklmnopqrstuvwxyz')
                            if base_seg != seg_id:
                                normalized_day_segment_ids.add(base_seg)
                        
                        # Filter bins by day segments (check both segment_id and seg_id columns)
                        segment_col = None
                        if "segment_id" in bins_df.columns:
                            segment_col = "segment_id"
                        elif "seg_id" in bins_df.columns:
                            segment_col = "seg_id"
                        
                        if segment_col:
                            # Normalize bin segment IDs to base segments for comparison
                            def normalize_seg_id(seg_id_str):
                                """Normalize segment ID: N2a -> N2, N2 -> N2"""
                                return seg_id_str.rstrip('abcdefghijklmnopqrstuvwxyz')
                            
                            # Check if bin segment matches any day segment (base or sub-segment)
                            def matches_day_segment(bin_seg_id):
                                bin_seg_str = str(bin_seg_id)
                                # Check exact match
                                if bin_seg_str in normalized_day_segment_ids:
                                    return True
                                # Check if bin segment is a sub-segment of a day segment
                                bin_base = normalize_seg_id(bin_seg_str)
                                return bin_base in normalized_day_segment_ids
                            
                            bins_df_filtered = bins_df[bins_df[segment_col].astype(str).apply(matches_day_segment)].copy()
                            
                            # Debug: Check what segments are actually in bins before/after filtering
                            before_segments = set(bins_df[segment_col].astype(str).unique().tolist())
                            after_segments = set(bins_df_filtered[segment_col].astype(str).unique().tolist())
                            
                            logger.info(
                                f"Filtered bins for day {day.value}: {len(bins_df)} -> {len(bins_df_filtered)} "
                                f"(day segments: {sorted(day_segment_ids)}, "
                                f"before: {len(before_segments)} segments, after: {len(after_segments)} segments)"
                            )
                            
                            if len(bins_df_filtered) == 0:
                                logger.warning(
                                    f"No bins matched day segments for {day.value}. "
                                    f"Day segments: {sorted(day_segment_ids)}, "
                                    f"Bin segments before filter: {sorted(before_segments)[:10]}..."
                                )
                            # Save filtered bins.parquet
                            bins_parquet_dst = bins_dir / "bins.parquet"
                            bins_df_filtered.to_parquet(bins_parquet_dst, compression="zstd", compression_level=3)
                            logger.debug(f"Saved filtered bins.parquet to {bins_parquet_dst}")
                            bins_successfully_copied = True
                        else:
                            # Fallback: copy without filtering if segment column not found
                            logger.warning(f"bins.parquet missing 'segment_id' or 'seg_id' column, cannot filter by day")
                            shutil.copy2(bins_parquet_src, bins_dir / "bins.parquet")
                            bins_successfully_copied = True
                
                # Copy other bin artifacts
                bin_files = [
                    "bins.geojson.gz",
                    "bin_summary.json",
                    "segment_windows_from_bins.parquet"
                ]
                
                for bin_file in bin_files:
                    src = temp_bins_dir / bin_file
                    if src.exists():
                        dst = bins_dir / bin_file
                        shutil.copy2(src, dst)
                        logger.debug(f"Copied {bin_file} to {dst}")
                
                # Also copy any other parquet/json files (skip bins.parquet - already filtered and saved above)
                for src_file in temp_bins_dir.glob("*.parquet"):
                    if src_file.name == "bins.parquet":
                        continue  # Skip - already filtered and saved above
                    dst = bins_dir / src_file.name
                    shutil.copy2(src_file, dst)
                    logger.debug(f"Copied {src_file.name} to {dst}")
                
                for src_file in temp_bins_dir.glob("*.json"):
                    dst = bins_dir / src_file.name
                    shutil.copy2(src_file, dst)
                    logger.debug(f"Copied {src_file.name} to {dst}")
            
            # Log summary
            elapsed = time.monotonic() - start_time
            final_features = len(bin_data.get("geojson", {}).get("features", [])) if bin_data else 0
            occupied_bins = bin_data.get("geojson", {}).get("metadata", {}).get("occupied_bins", 0) if bin_data else 0
            logger.info(
                f"Generated {final_features} bin features for day {day.value} in {elapsed:.1f}s "
                f"(occupied: {occupied_bins})"
            )
            
            if occupied_bins == 0:
                logger.warning(f"⚠️ No occupied bins found for day {day.value} - runner mapping may have failed")
            
            # Issue #655: Verify bins.parquet was successfully created before returning
            bins_parquet_final = bins_dir / "bins.parquet"
            if not bins_parquet_final.exists():
                error_msg = (
                    f"CRITICAL: bins.parquet was not created at {bins_parquet_final} "
                    f"despite bin generation completing. This indicates a file copy/save failure."
                )
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            logger.info(f"✅ Bin generation completed successfully for day {day.value}: {bins_parquet_final}")
            return bins_dir
            
        finally:
            # Clean up temp files (non-critical - don't fail if cleanup fails)
            try:
                shutil.rmtree(temp_output_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_output_dir}: {e}")
                # Note: Cleanup failure is non-critical - bins are already saved, so we don't re-raise
        
    except Exception as e:
        # Issue #655: Only return None if bins were not successfully created
        # Check if bins.parquet exists despite the exception (e.g., copy succeeded but cleanup failed)
        bins_parquet_check = bins_dir / "bins.parquet"
        if bins_parquet_check.exists():
            logger.warning(
                f"Exception occurred during bin generation for day {day.value}: {e}, "
                f"but bins.parquet exists at {bins_parquet_check}. "
                f"Continuing with existing bins file."
            )
            return bins_dir
        else:
            logger.error(f"Failed to generate bins for day {day.value}: {e}", exc_info=True)
            return None
