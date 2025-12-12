"""
V2 Bin Generation Module

Wraps v1 bin generation logic to support day-partitioned output structure.
Also provides segment filtering utilities used by density and flow analysis.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

from app.density_report import (
    AnalysisContext,
    _generate_bin_dataset_with_retry,
    _save_bin_artifacts_and_metadata,
    _process_segments_from_bins
)
from app.save_bins import save_bin_artifacts
from app.core.bin.summary import generate_bin_summary_artifact
from app.utils.constants import BIN_SCHEMA_VERSION
from app.core.v2.models import Day, Event

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
    data_dir: str = "data"
) -> Optional[Path]:
    """
    Generate bin artifacts for a specific day using v1 bin generation logic.
    
    This function wraps the v1 bin generation to:
    1. Create AnalysisContext with v2 data
    2. Temporarily provide combined runners CSV for build_runner_window_mapping()
    3. Call v1 bin generation functions
    4. Save artifacts to day-partitioned structure: runflow/{run_id}/{day}/bins/
    
    Args:
        density_results: Density analysis results from analyze_density_segments_v2()
        start_times: Dictionary mapping event names to start times in minutes (float)
        segments_df: Segments DataFrame
        runners_df: Runners DataFrame (filtered to day)
        run_id: Run identifier
        day: Day enum
        events: List of events for this day
        data_dir: Base directory for data files
        
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
        
        # Map event names to v1 format
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",
            "open": "Open"
        }
        
        # Get segments CSV path
        segments_csv_path = str(Path(data_dir) / "segments.csv")
        
        # CRITICAL FIX: build_runner_window_mapping() hardcodes reading from "data/runners.csv"
        # We need to temporarily replace it with our day-filtered runners
        # However, build_runner_window_mapping() expects event names like 'Full', '10K', 'Half'
        # So we need to map our lowercase event names to uppercase for the legacy function
        import tempfile
        import shutil
        
        # Create temp combined runners CSV with v1 event names (uppercase for legacy compatibility)
        temp_runners_df = runners_df.copy()
        if 'event' in temp_runners_df.columns:
            # Map v2 lowercase event names to v1 uppercase format for build_runner_window_mapping()
            temp_runners_df['event'] = temp_runners_df['event'].str.lower().map(
                lambda x: event_name_mapping.get(x, x.capitalize())
            )
        
        # Create temp file
        temp_runners_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_runners_df.to_csv(temp_runners_csv.name, index=False)
        temp_runners_csv.close()
        temp_runners_path = temp_runners_csv.name
        
        # Temporarily replace "data/runners.csv" with our temp file
        original_runners_path = Path(data_dir) / "runners.csv"
        backup_runners_path = None
        runners_was_replaced = False
        
        try:
            # If "data/runners.csv" exists, back it up
            if original_runners_path.exists():
                backup_runners_path = str(original_runners_path) + ".backup"
                shutil.copy2(original_runners_path, backup_runners_path)
            
            # Copy our temp file to "data/runners.csv"
            shutil.copy2(temp_runners_path, original_runners_path)
            runners_was_replaced = True
            logger.debug(f"Temporarily replaced data/runners.csv with day-filtered runners ({len(temp_runners_df)} runners)")
            
        except Exception as e:
            logger.warning(f"Failed to temporarily replace data/runners.csv: {e}")
            # Continue anyway - bin generation might still work
        
        # Create AnalysisContext
        analysis_context = AnalysisContext(
            course_id="fredericton_marathon",
            segments=segments_df,
            runners=runners_df,
            params={"start_times": start_times},
            code_version="v2.0.0",
            schema_version=BIN_SCHEMA_VERSION,
            pace_csv_path=str(original_runners_path),
            segments_csv_path=segments_csv_path
        )
        
        # Call v1 bin generation with retry logic
        start_time = time.monotonic()
        temp_output_dir = tempfile.mkdtemp()
        
        try:
            daily_folder_path, bin_metadata, bin_data = _generate_bin_dataset_with_retry(
                density_results, start_times, temp_output_dir, analysis_context
            )
            
            if not daily_folder_path:
                logger.error(f"Bin generation returned no folder path for day {day.value}")
                return None
            
            # Move bin artifacts from temp location to day-partitioned bins directory
            temp_bins_dir = Path(daily_folder_path)
            if temp_bins_dir.exists():
                # Copy bin artifacts to day-partitioned location
                bin_files = [
                    "bins.parquet",
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
                
                # Also copy any other parquet/json files
                for src_file in temp_bins_dir.glob("*.parquet"):
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
            
            return bins_dir
            
        finally:
            # Restore original "data/runners.csv" if we replaced it
            if runners_was_replaced:
                try:
                    if backup_runners_path and os.path.exists(backup_runners_path):
                        shutil.copy2(backup_runners_path, original_runners_path)
                        os.unlink(backup_runners_path)
                        logger.debug(f"Restored original data/runners.csv")
                    elif original_runners_path.exists():
                        # Remove our temp file (only if we created it)
                        try:
                            os.unlink(original_runners_path)
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to restore original data/runners.csv: {e}")
            
            # Clean up temp files
            try:
                shutil.rmtree(temp_output_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_output_dir}: {e}")
            
            # Clean up temp runners CSV
            try:
                if os.path.exists(temp_runners_path):
                    os.unlink(temp_runners_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp runners CSV {temp_runners_path}: {e}")
        
    except Exception as e:
        logger.error(f"Failed to generate bins for day {day.value}: {e}", exc_info=True)
        return None
