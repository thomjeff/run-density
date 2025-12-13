"""
Runflow v2 UI Artifacts Module

Generates UI-facing artifacts (JSON files, heatmaps, captions) for the dashboard.
Artifacts are stored per-day in runflow/{run_id}/{day}/ui/ but contain full run scope data.

Phase 7: UI & API Surface Updates (Issue #501)
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import pandas as pd

from app.core.v2.models import Day, Event
from app.utils.run_id import get_runflow_root
from app.core.artifacts.frontend import (
    export_ui_artifacts,
    calculate_flow_segment_counts
)

logger = logging.getLogger(__name__)


def get_ui_artifacts_path(run_id: str, day: Day) -> Path:
    """
    Get the UI artifacts directory path for a specific day.
    
    Args:
        run_id: Unique run identifier (UUID)
        day: Day enum (fri, sat, sun, mon)
        
    Returns:
        Path object for the UI artifacts directory
        
    Example:
        >>> path = get_ui_artifacts_path("abc123", Day.SUN)
        >>> str(path)
        'runflow/abc123/sun/ui'
    """
    runflow_root = get_runflow_root()
    ui_path = runflow_root / run_id / day.value / "ui"
    return ui_path


def aggregate_full_run_data(
    events: List[Event],
    density_results: Dict[str, Any],
    flow_results: Dict[str, Any],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Aggregate data from all days/events to create full run scope for artifacts.
    
    This function collects data from all days and events to ensure artifacts
    contain complete context (all segments, all events) even though they're
    stored per-day.
    
    Args:
        events: All events from the run (across all days)
        density_results: Density results dict keyed by day
        flow_results: Flow results dict keyed by day
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events)
        
    Returns:
        Dictionary with aggregated data for artifact generation
    """
    # Aggregate density results from all days
    aggregated_density = {}
    for day_results in density_results.values():
        if isinstance(day_results, dict):
            aggregated_density.update(day_results)
    
    # Aggregate flow results from all days
    aggregated_flow = {}
    for day_results in flow_results.values():
        if isinstance(day_results, dict):
            aggregated_flow.update(day_results)
    
    return {
        "events": events,
        "density_results": aggregated_density,
        "flow_results": aggregated_flow,
        "segments_df": segments_df,
        "runners_df": all_runners_df
    }


def generate_ui_artifacts_per_day(
    run_id: str,
    day: Day,
    events: List[Event],
    density_results: Dict[str, Any],
    flow_results: Dict[str, Any],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame,
    data_dir: str = "data",
    environment: str = "local"
) -> Optional[Path]:
    """
    Generate UI artifacts for a specific day with day-scoped data.
    
    CRITICAL: Artifacts must only contain segments for the specified day, not all segments.
    This function filters all data (bins, metrics, geojson, heatmaps) by day segments.
    
    Args:
        run_id: Unique run identifier (UUID)
        day: Day enum for path organization
        events: All events from the run (across all days)
        density_results: Density results dict keyed by day
        flow_results: Flow results dict keyed by day
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events)
        data_dir: Base directory for data files
        environment: Environment name ("local" or "cloud")
        
    Returns:
        Path to UI artifacts directory, or None if generation failed
        
    Note:
        Artifacts are stored in runflow/{run_id}/{day}/ui/ and contain
        ONLY segments for that specific day (day-scoped).
    """
    try:
        logger.info(f"Generating UI artifacts for day {day.value} (day-scoped)")
        
        # Get UI artifacts path for this day
        ui_path = get_ui_artifacts_path(run_id, day)
        ui_path.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL: Get day-specific events and segments
        from app.core.v2.bins import filter_segments_by_events
        day_events = [e for e in events if e.day == day]
        day_segments_df = filter_segments_by_events(segments_df, day_events)
        day_segment_ids = set(day_segments_df['seg_id'].astype(str).unique())
        
        logger.info(
            f"Day {day.value}: Filtering artifacts to {len(day_segment_ids)} segments: "
            f"{sorted(list(day_segment_ids))[:10]}{'...' if len(day_segment_ids) > 10 else ''}"
        )
        
        # Calculate flow segment counts from day-specific flow results only
        overtaking_segments = 0
        co_presence_segments = 0
        
        try:
            # Only count segments from this day's flow results
            day_flow = flow_results.get(day.value, {})
            if isinstance(day_flow, dict):
                overtaking_segments_set = set()
                copresence_segments_set = set()
                
                for seg_id, flow_data in day_flow.items():
                    if isinstance(flow_data, dict):
                        # Check for overtaking activity
                        if flow_data.get("overtaking_a", 0) > 0 or flow_data.get("overtaking_b", 0) > 0:
                            overtaking_segments_set.add(seg_id)
                        # Check for co-presence activity
                        if flow_data.get("copresence_a", 0) > 0 or flow_data.get("copresence_b", 0) > 0:
                            copresence_segments_set.add(seg_id)
                
                overtaking_segments = len(overtaking_segments_set)
                co_presence_segments = len(copresence_segments_set)
            
            logger.info(
                f"Day {day.value} flow segment counts: {overtaking_segments} overtaking, "
                f"{co_presence_segments} co-presence"
            )
        except Exception as e:
            logger.warning(f"Could not calculate flow segment counts: {e}")
        
        # Call the internal function with day-scoped data
        try:
            artifacts_dir = _export_ui_artifacts_v2(
                run_id=run_id,
                day=day,
                day_events=day_events,
                day_segment_ids=day_segment_ids,
                density_results=density_results,
                flow_results=flow_results,
                segments_df=segments_df,
                all_runners_df=all_runners_df,
                overtaking_segments=overtaking_segments,
                co_presence_segments=co_presence_segments,
                environment=environment
            )
            
            if artifacts_dir:
                logger.info(f"✅ UI artifacts generated for day {day.value}: {artifacts_dir}")
                return artifacts_dir
            else:
                logger.warning(f"UI artifact generation returned None for day {day.value}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating UI artifacts for day {day.value}: {e}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Failed to generate UI artifacts for day {day.value}: {e}", exc_info=True)
        return None


def _export_ui_artifacts_v2(
    run_id: str,
    day: Day,
    day_events: List[Event],
    day_segment_ids: set,
    density_results: Dict[str, Any],
    flow_results: Dict[str, Any],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame,
    overtaking_segments: int,
    co_presence_segments: int,
    environment: str
) -> Optional[Path]:
    """
    Internal wrapper for v1 artifact generation functions adapted for v2 structure.
    
    CRITICAL: This function filters all artifacts by day segments to ensure day-scoping.
    
    This function calls v1 artifact generation functions directly, but:
    1. Filters bins by day segments before generating artifacts
    2. Filters segment_metrics by day segments
    3. Filters segments.geojson by day segments
    4. Filters heatmaps by day segments
    5. Writes artifacts to v2 day-scoped path structure
    
    Args:
        run_id: Unique run identifier
        day: Day enum for path organization
        reports_dir: Path to reports directory (day-scoped, used as base)
        full_run_data: Aggregated data from all days/events
        overtaking_segments: Count of segments with overtaking (full run)
        co_presence_segments: Count of segments with co-presence (full run)
        environment: Environment name
        
    Returns:
        Path to UI artifacts directory
    """
    import json
    from app.core.artifacts.frontend import (
        generate_meta_json,
        generate_segment_metrics_json,
        generate_flags_json,
        generate_flow_json,
        generate_segments_geojson,
        generate_density_schema_json,
        generate_health_json
    )
    from app.core.artifacts.heatmaps import export_heatmaps_and_captions
    
    # Get UI artifacts path
    ui_path = get_ui_artifacts_path(run_id, day)
    ui_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Generating UI artifacts in {ui_path} (day-scoped to {len(day_segment_ids)} segments)")
    
    # Aggregate bins.parquet from all days, then filter by day segments
    aggregated_bins = None
    temp_reports = None
    
    try:
        # Aggregate bins from all days first
        aggregated_bins = _aggregate_bins_from_all_days(run_id)
        if aggregated_bins is not None and not aggregated_bins.empty:
            # Normalize column names for v1 functions
            # v1 expects 'rate_p_s' but v2 bins.parquet has 'rate'
            if 'rate' in aggregated_bins.columns and 'rate_p_s' not in aggregated_bins.columns:
                aggregated_bins = aggregated_bins.rename(columns={'rate': 'rate_p_s'})
            # v1 expects 'segment_id' but v2 might have 'seg_id'
            segment_col = None
            if 'seg_id' in aggregated_bins.columns and 'segment_id' not in aggregated_bins.columns:
                aggregated_bins = aggregated_bins.rename(columns={'seg_id': 'segment_id'})
                segment_col = 'segment_id'
            elif 'segment_id' in aggregated_bins.columns:
                segment_col = 'segment_id'
            
            # CRITICAL FIX: Filter bins to only include day segments
            if segment_col:
                bins_before = len(aggregated_bins)
                aggregated_bins = aggregated_bins[
                    aggregated_bins[segment_col].astype(str).isin(day_segment_ids)
                ].copy()
                logger.info(
                    f"   ✅ Filtered bins: {bins_before} -> {len(aggregated_bins)} rows "
                    f"for day {day.value} ({len(day_segment_ids)} segments)"
                )
            
            # Create temporary reports structure for v1 functions
            temp_reports = ui_path.parent / "reports_temp"
            temp_bins_dir = temp_reports / "bins"
            temp_bins_dir.mkdir(parents=True, exist_ok=True)
            aggregated_bins.to_parquet(temp_bins_dir / "bins.parquet", index=False)
            logger.info(f"   ✅ Saved {len(aggregated_bins)} day-scoped bins to temp_reports")
        else:
            logger.warning("   ⚠️  No bins data available from any day")
    except Exception as e:
        logger.warning(f"   ⚠️  Could not aggregate/filter bins: {e}")
    
    try:
        # 1. Generate meta.json
        logger.info("1️⃣  Generating meta.json...")
        meta = generate_meta_json(run_id, environment)
        # Add day information for v2
        meta["day"] = day.value
        (ui_path / "meta.json").write_text(json.dumps(meta, indent=2))
        logger.info(f"   ✅ meta.json: run_id={meta['run_id']}, day={day.value}")
        
                # 2. Generate segment_metrics.json (day-scoped)
                logger.info("2️⃣  Generating segment_metrics.json...")
                try:
                    if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                        segment_metrics = generate_segment_metrics_json(temp_reports)
                        # Compute peak_rate from day-filtered bins
                        from app.core.artifacts.frontend import _compute_peak_rate_per_segment
                        peak_rate_map = _compute_peak_rate_per_segment(aggregated_bins)
                        
                        # CRITICAL FIX: Filter segment_metrics to only include day segments
                        segment_metrics_filtered = {
                            seg_id: metrics for seg_id, metrics in segment_metrics.items()
                            if str(seg_id) in day_segment_ids
                        }
                        
                        # Merge peak_rate data for filtered segments
                        for seg_id, seg_metrics in segment_metrics_filtered.items():
                            if seg_id in peak_rate_map:
                                seg_metrics["peak_rate"] = peak_rate_map[seg_id]["peak_rate"]
                                seg_metrics["peak_rate_time"] = peak_rate_map[seg_id]["peak_rate_time"]
                                seg_metrics["peak_rate_km"] = peak_rate_map[seg_id]["peak_rate_km"]
                            else:
                                seg_metrics.setdefault("peak_rate", 0.0)
                        
                        segment_metrics = segment_metrics_filtered
                        logger.info(
                            f"   ✅ segment_metrics.json: {len(segment_metrics)} segments "
                            f"(filtered from {len(segment_metrics) + len(segment_metrics) - len(segment_metrics_filtered)})"
                        )
                    else:
                        logger.warning("   ⚠️  No bins data available, generating empty segment_metrics")
                        segment_metrics = {}
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not generate segment_metrics: {e}")
                    segment_metrics = {}
        
        # Calculate summary metrics
        peak_density_overall = max((seg.get("peak_density", 0.0) for seg in segment_metrics.values()), default=0.0)
        peak_rate_overall = max((seg.get("peak_rate", 0.0) for seg in segment_metrics.values()), default=0.0)
        
        # 3. Generate flags.json
        logger.info("3️⃣  Generating flags.json...")
        try:
            if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                flags = generate_flags_json(temp_reports, segment_metrics)
            else:
                flags = []
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate flags: {e}")
            flags = []
        
        segments_with_flags = len(flags)
        flagged_bins = sum(flag.get("flagged_bins", 0) for flag in flags)
        
        # Add summary metrics
        segment_metrics_with_summary = {
            "peak_density": round(peak_density_overall, 4),
            "peak_rate": round(peak_rate_overall, 2),
            "segments_with_flags": segments_with_flags,
            "flagged_bins": flagged_bins,
            "overtaking_segments": overtaking_segments,
            "co_presence_segments": co_presence_segments,
            **segment_metrics
        }
        
        (ui_path / "segment_metrics.json").write_text(json.dumps(segment_metrics_with_summary, indent=2))
        logger.info(f"   ✅ segment_metrics.json: {len(segment_metrics)} segments + summary")
        
        (ui_path / "flags.json").write_text(json.dumps(flags, indent=2))
        logger.info(f"   ✅ flags.json: {len(flags)} flagged segments")
        
        # 4. Generate flow.json
        logger.info("4️⃣  Generating flow.json...")
        try:
            if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                flow = generate_flow_json(temp_reports)
            else:
                flow = {
                    "schema_version": "1.0.0",
                    "units": {"rate": "persons_per_second", "time": "ISO8601"},
                    "rows": [],
                    "summaries": []
                }
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate flow.json: {e}")
            flow = {
                "schema_version": "1.0.0",
                "units": {"rate": "persons_per_second", "time": "ISO8601"},
                "rows": [],
                "summaries": []
            }
        
        (ui_path / "flow.json").write_text(json.dumps(flow, indent=2))
        logger.info(f"   ✅ flow.json: {len(flow.get('summaries', []))} segments, {len(flow.get('rows', []))} rows")
        
                # 5. Generate segments.geojson (day-scoped)
                logger.info("5️⃣  Generating segments.geojson...")
                try:
                    if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                        segments_geojson = generate_segments_geojson(temp_reports)
                        
                        # CRITICAL FIX: Filter features to only include day segments
                        if "features" in segments_geojson:
                            original_count = len(segments_geojson["features"])
                            segments_geojson["features"] = [
                                feature for feature in segments_geojson["features"]
                                if feature.get("properties", {}).get("segment_id") in day_segment_ids
                            ]
                            logger.info(
                                f"   ✅ Filtered segments.geojson: {original_count} -> "
                                f"{len(segments_geojson['features'])} features for day {day.value}"
                            )
                    else:
                        segments_geojson = {"type": "FeatureCollection", "features": []}
                except Exception as e:
                    logger.warning(f"   ⚠️  Could not generate segments.geojson: {e}")
                    segments_geojson = {"type": "FeatureCollection", "features": []}
                
                (ui_path / "segments.geojson").write_text(json.dumps(segments_geojson, indent=2))
                logger.info(f"   ✅ segments.geojson: {len(segments_geojson.get('features', []))} features")
        
        # 6. Generate schema_density.json
        logger.info("6️⃣  Generating schema_density.json...")
        schema_density = generate_density_schema_json(meta.get('dataset_version', 'unknown'))
        (ui_path / "schema_density.json").write_text(json.dumps(schema_density, indent=2))
        logger.info(f"   ✅ schema_density.json: schema_version={schema_density.get('schema_version')}")
        
        # 7. Generate health.json
        logger.info("7️⃣  Generating health.json...")
        health = generate_health_json(ui_path, run_id, environment)
        (ui_path / "health.json").write_text(json.dumps(health, indent=2))
        logger.info(f"   ✅ health.json generated")
        
        # 8. Generate heatmaps and captions
        logger.info("8️⃣  Generating heatmaps and captions...")
        try:
            if temp_reports:
                export_heatmaps_and_captions(run_id, temp_reports, None)
                
                # Move heatmaps and captions to day-scoped UI directory
                # Check multiple possible source locations
                import shutil
                runflow_root = get_runflow_root()
                
                # Heatmaps can be in multiple locations:
                # 1. runflow/{run_id}/heatmaps/ (run level - most common)
                # 2. runflow/{run_id}/ui/heatmaps/ (ui subdirectory)
                # 3. artifacts/{run_id}/ui/heatmaps/ (legacy)
                heatmaps_source = None
                for possible_path in [
                    runflow_root / run_id / "heatmaps",  # Run level (most common)
                    runflow_root / run_id / "ui" / "heatmaps",  # UI subdirectory
                    Path("/app/artifacts") / run_id / "ui" / "heatmaps"  # Legacy
                ]:
                    if possible_path.exists():
                        heatmaps_source = possible_path
                        break
                
                # Captions can be in:
                # 1. runflow/{run_id}/ui/captions.json (most common)
                # 2. artifacts/{run_id}/ui/captions.json (legacy)
                captions_source = None
                for possible_path in [
                    runflow_root / run_id / "ui" / "captions.json",  # UI subdirectory
                    Path("/app/artifacts") / run_id / "ui" / "captions.json"  # Legacy
                ]:
                    if possible_path.exists():
                        captions_source = possible_path
                        break
                
                # Move heatmaps and filter by day segments
                if heatmaps_source and heatmaps_source.exists():
                    heatmaps_dest = ui_path / "heatmaps"
                    heatmaps_dest.mkdir(parents=True, exist_ok=True)
                    
                    # CRITICAL FIX: Filter heatmap PNGs to only include day segments
                    import os
                    heatmaps_moved = 0
                    for png_file in heatmaps_source.glob("*.png"):
                        # Extract segment_id from filename (e.g., "A1.png" -> "A1")
                        seg_id = png_file.stem
                        if str(seg_id) in day_segment_ids:
                            dest_file = heatmaps_dest / png_file.name
                            shutil.copy2(png_file, dest_file)
                            heatmaps_moved += 1
                    
                    logger.info(
                        f"   ✅ Heatmaps filtered and moved: {heatmaps_moved} PNGs "
                        f"for day {day.value} ({len(day_segment_ids)} segments)"
                    )
                else:
                    logger.warning(f"   ⚠️  Heatmaps not found at expected locations")
                
                # Move captions.json
                if captions_source and captions_source.exists():
                    captions_dest = ui_path / "captions.json"
                    if captions_dest.exists():
                        captions_dest.unlink()
                    shutil.move(str(captions_source), str(captions_dest))
                    logger.info(f"   ✅ Captions moved to {captions_dest}")
                else:
                    logger.warning(f"   ⚠️  Captions not found at expected locations")
                
                # Clean up empty /ui folder at run level (Issue #501: Remove empty ui folder)
                run_level_ui = runflow_root / run_id / "ui"
                if run_level_ui.exists() and run_level_ui.is_dir():
                    try:
                        # Check if folder is empty
                        contents = list(run_level_ui.iterdir())
                        if len(contents) == 0:
                            run_level_ui.rmdir()
                            logger.info(f"   ✅ Removed empty run-level /ui folder: {run_level_ui}")
                        else:
                            logger.debug(f"   Run-level /ui folder not empty, keeping: {contents}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not remove empty /ui folder: {e}")
            else:
                logger.warning("   ⚠️  Skipping heatmaps (no temp_reports directory)")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate heatmaps/captions: {e}")
        
        # Clean up temporary directory
        if temp_reports and temp_reports.exists():
            import shutil
            shutil.rmtree(temp_reports)
        
        logger.info(f"✅ All UI artifacts generated for day {day.value}")
        return ui_path
        
    except Exception as e:
        logger.error(f"Error generating UI artifacts: {e}", exc_info=True)
        return None


def _aggregate_bins_from_all_days(run_id: str) -> Optional[pd.DataFrame]:
    """
    Aggregate bins.parquet from all days into a single DataFrame.
    
    Args:
        run_id: Unique run identifier
        
    Returns:
        Aggregated DataFrame with bins from all days, or None if no bins found
    """
    runflow_root = get_runflow_root()
    run_path = runflow_root / run_id
    
    if not run_path.exists():
        logger.warning(f"Run directory not found: {run_path}")
        return None
    
    all_bins = []
    
    # Collect bins from all day directories
    for day_dir in run_path.iterdir():
        if day_dir.is_dir() and day_dir.name in ['fri', 'sat', 'sun', 'mon']:
            bins_parquet = day_dir / "reports" / "bins.parquet"
            if bins_parquet.exists():
                try:
                    day_bins = pd.read_parquet(bins_parquet)
                    all_bins.append(day_bins)
                    logger.debug(f"Loaded {len(day_bins)} bins from {day_dir.name}")
                except Exception as e:
                    logger.warning(f"Could not load bins from {day_dir.name}: {e}")
    
    if not all_bins:
        logger.warning("No bins found in any day directory")
        return None
    
    # Concatenate all bins
    aggregated = pd.concat(all_bins, ignore_index=True)
    logger.info(f"Aggregated {len(aggregated)} bins from {len(all_bins)} day(s)")
    
    return aggregated

