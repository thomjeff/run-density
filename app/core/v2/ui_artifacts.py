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
            # Issue #548 Bug 3: Transform flow_results structure
            # flow_results from v2 flow analysis has structure: {Day: {"ok": True, "segments": [...], ...}}
            # Need to convert segments list to dict keyed by seg_id
            day_flow_result = flow_results.get(day, {})  # Get by Day enum, not day.value
            if isinstance(day_flow_result, dict) and day_flow_result.get("ok") and "segments" in day_flow_result:
                # Transform segments list to dict keyed by seg_id
                segments_list = day_flow_result.get("segments", [])
                day_flow_dict = {}
                for segment in segments_list:
                    if isinstance(segment, dict):
                        seg_id = segment.get("seg_id")
                        if seg_id:
                            day_flow_dict[seg_id] = segment
                
                # Now count segments with overtaking/co-presence activity
                overtaking_segments_set = set()
                copresence_segments_set = set()
                
                for seg_id, flow_data in day_flow_dict.items():
                    if isinstance(flow_data, dict):
                        # Check for overtaking activity
                        overtaking_a = flow_data.get("overtaking_a", 0)
                        overtaking_b = flow_data.get("overtaking_b", 0)
                        if (isinstance(overtaking_a, (int, float)) and overtaking_a > 0) or \
                           (isinstance(overtaking_b, (int, float)) and overtaking_b > 0):
                            overtaking_segments_set.add(seg_id)
                        
                        # Check for co-presence activity
                        copresence_a = flow_data.get("copresence_a", 0)
                        copresence_b = flow_data.get("copresence_b", 0)
                        if (isinstance(copresence_a, (int, float)) and copresence_a > 0) or \
                           (isinstance(copresence_b, (int, float)) and copresence_b > 0):
                            copresence_segments_set.add(seg_id)
                
                overtaking_segments = len(overtaking_segments_set)
                co_presence_segments = len(copresence_segments_set)
                
                logger.info(
                    f"Day {day.value} flow segment counts: {overtaking_segments} overtaking, "
                    f"{co_presence_segments} co-presence (from {len(segments_list)} segments)"
                )
            else:
                logger.warning(
                    f"Day {day.value} flow_results structure unexpected: "
                    f"ok={day_flow_result.get('ok') if isinstance(day_flow_result, dict) else 'N/A'}, "
                    f"has_segments={'segments' in day_flow_result if isinstance(day_flow_result, dict) else False}"
                )
        except Exception as e:
            logger.warning(f"Could not calculate flow segment counts: {e}", exc_info=True)
        
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
    
    # Issue #574: Create subdirectories for organized artifact structure
    metadata_dir = ui_path / "metadata"
    metrics_dir = ui_path / "metrics"
    geospatial_dir = ui_path / "geospatial"
    visualizations_dir = ui_path / "visualizations"
    
    metadata_dir.mkdir(exist_ok=True)
    metrics_dir.mkdir(exist_ok=True)
    geospatial_dir.mkdir(exist_ok=True)
    visualizations_dir.mkdir(exist_ok=True)
    
    logger.info(f"Generating UI artifacts in {ui_path} (day-scoped to {len(day_segment_ids)} segments)")
    logger.info(f"Issue #574: Using organized structure: metadata/, metrics/, geospatial/, visualizations/")
    
    # Aggregate bins.parquet from all days, then filter by day segments
    aggregated_bins = None
    aggregated_bins_for_flags = None  # Issue #528: Keep original bins with 'rate' column for flagging
    temp_reports = None
    heatmap_reports = None
    
    try:
        # Aggregate bins from all days first
        aggregated_bins = _aggregate_bins_from_all_days(run_id)
        if aggregated_bins is not None and not aggregated_bins.empty:
            # Issue #528: Keep a copy with 'rate' column for flagging before renaming
            aggregated_bins_for_flags = aggregated_bins.copy()
            
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
                # Also filter the flags copy
                flags_segment_col = 'segment_id' if 'segment_id' in aggregated_bins_for_flags.columns else ('seg_id' if 'seg_id' in aggregated_bins_for_flags.columns else segment_col)
                aggregated_bins_for_flags = aggregated_bins_for_flags[
                    aggregated_bins_for_flags[flags_segment_col].astype(str).isin(day_segment_ids)
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

            # Prepare a dedicated reports directory for heatmaps so we can
            # bypass flag-only filtering in v1 load_bin_data when necessary.
            heatmap_reports = ui_path.parent / "reports_heatmaps"
            heatmap_bins_dir = heatmap_reports / "bins"
            heatmap_bins_dir.mkdir(parents=True, exist_ok=True)

            heatmap_bins = aggregated_bins.copy()
            if "flag_severity" in heatmap_bins.columns and heatmap_bins["flag_severity"].eq("none").all():
                heatmap_bins = heatmap_bins.drop(columns=["flag_severity"])
                logger.info(
                    "   ℹ️ Heatmap bins contain only 'none' flag_severity; dropping column to keep all bins"
                )

            heatmap_bins.to_parquet(heatmap_bins_dir / "bins.parquet", index=False)
            logger.info(f"   ✅ Saved {len(heatmap_bins)} bins for heatmap generation")
        else:
            logger.warning("   ⚠️  No bins data available from any day")
    except Exception as e:
        logger.warning(f"   ⚠️  Could not aggregate/filter bins: {e}")
    
    try:
        # 1. Generate meta.json (Issue #574: in metadata/ subdirectory)
        logger.info("1️⃣  Generating meta.json...")
        meta = generate_meta_json(run_id, environment)
        # Add day information for v2
        meta["day"] = day.value
        (metadata_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        logger.info(f"   ✅ meta.json: run_id={meta['run_id']}, day={day.value} (in metadata/)")
        
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
                    seg_id: metrics
                    for seg_id, metrics in segment_metrics.items()
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
                    f"(day-scoped to {day.value})"
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
            # Issue #528: Use bins with 'rate' column (not 'rate_p_s') for flagging
            if aggregated_bins_for_flags is not None and not aggregated_bins_for_flags.empty and temp_reports:
                # Ensure bins have required columns for flagging
                required_cols = {'segment_id', 't_start', 't_end', 'density', 'rate', 'los', 'flag_severity', 'flag_reason'}
                missing_cols = required_cols - set(aggregated_bins_for_flags.columns)
                if missing_cols:
                    logger.warning(f"   ⚠️  Bins DataFrame missing required columns for flagging: {missing_cols}")
                    flags = []
                else:
                    # Save bins with 'rate' column to temp_reports for generate_flags_json
                    # This overwrites the bins.parquet saved earlier (which had 'rate_p_s')
                    # Note: temp_reports structure is reports_temp/bins/bins.parquet
                    temp_bins_path = Path(temp_reports) / "bins" / "bins.parquet"
                    temp_bins_path.parent.mkdir(parents=True, exist_ok=True)
                    aggregated_bins_for_flags.to_parquet(temp_bins_path, index=False)
                    logger.info(f"   📊 Saved {len(aggregated_bins_for_flags)} bins with 'rate' column for flagging")
                    flags = generate_flags_json(temp_reports, segment_metrics)
            elif aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                # Fallback: try with aggregated_bins if aggregated_bins_for_flags not available
                logger.warning("   ⚠️  Using aggregated_bins (may have 'rate_p_s' instead of 'rate')")
                flags = generate_flags_json(temp_reports, segment_metrics)
            else:
                flags = []
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate flags: {e}")
            import traceback
            logger.debug(f"   Traceback: {traceback.format_exc()}")
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
        
        # Issue #574: Write to metrics/ subdirectory
        (metrics_dir / "segment_metrics.json").write_text(json.dumps(segment_metrics_with_summary, indent=2))
        logger.info(f"   ✅ segment_metrics.json: {len(segment_metrics)} segments + summary (in metrics/)")
        
        (metrics_dir / "flags.json").write_text(json.dumps(flags, indent=2))
        logger.info(f"   ✅ flags.json: {len(flags)} flagged segments (in metrics/)")
        
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
        
        # Issue #574: Write to geospatial/ subdirectory
        (geospatial_dir / "flow.json").write_text(json.dumps(flow, indent=2))
        logger.info(f"   ✅ flow.json: {len(flow.get('summaries', []))} segments, {len(flow.get('rows', []))} rows (in geospatial/)")
        
        # 5. Generate segments.geojson (day-scoped)
        logger.info("5️⃣  Generating segments.geojson...")
        try:
            if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
                segments_geojson = generate_segments_geojson(temp_reports)

                # CRITICAL FIX: Filter features to only include day segments
                if "features" in segments_geojson:
                    original_count = len(segments_geojson["features"])

                    def _feature_segment_id(feature: Dict[str, Any]) -> str:
                        props = feature.get("properties", {})
                        return str(
                            props.get("segment_id")
                            or props.get("seg_id")
                            or props.get("id")
                            or ""
                        )

                    segments_geojson["features"] = [
                        feature
                        for feature in segments_geojson["features"]
                        if _feature_segment_id(feature) in day_segment_ids
                    ]
                    logger.info(
                        f"   ✅ Filtered segments.geojson: {original_count} -> "
                        f"{len(segments_geojson['features'])} features for day {day.value}"
                    )
                    
                    # Issue #548 Bug 1 & 2: Add events property from segments_df to each feature
                    # Extract events from segments.csv (lowercase: full, half, 10k, elite, open)
                    if segments_df is not None and not segments_df.empty:
                        for feature in segments_geojson["features"]:
                            seg_id = _feature_segment_id(feature)
                            if seg_id:
                                seg_row = segments_df[segments_df['seg_id'] == seg_id]
                                if not seg_row.empty:
                                    events = []
                                    # Issue #548 Bug 1: Use lowercase column names to match CSV format
                                    if seg_row.iloc[0].get('full') == 'y':
                                        events.append('full')
                                    if seg_row.iloc[0].get('half') == 'y':
                                        events.append('half')
                                    if seg_row.iloc[0].get('10k') == 'y' or seg_row.iloc[0].get('10K') == 'y':
                                        events.append('10k')
                                    if seg_row.iloc[0].get('elite') == 'y':
                                        events.append('elite')
                                    if seg_row.iloc[0].get('open') == 'y':
                                        events.append('open')
                                    
                                    # Add events to feature properties
                                    props = feature.get("properties", {})
                                    props["events"] = events
                                    feature["properties"] = props
                        logger.info(f"   ✅ Added events property to segments.geojson features from segments_df")
            else:
                segments_geojson = {"type": "FeatureCollection", "features": []}
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate segments.geojson: {e}")
            segments_geojson = {"type": "FeatureCollection", "features": []}
        
        # Issue #574: Write to geospatial/ subdirectory
        (geospatial_dir / "segments.geojson").write_text(json.dumps(segments_geojson, indent=2))
        logger.info(f"   ✅ segments.geojson: {len(segments_geojson.get('features', []))} features (in geospatial/)")
        
        # 5.5. Generate flow_segments.json (Issue #628)
        logger.info("5️⃣.5️⃣  Generating flow_segments.json...")
        try:
            day_flow_result = flow_results.get(day, {})
            if isinstance(day_flow_result, dict) and day_flow_result.get("ok") and "segments" in day_flow_result:
                flow_segments = _generate_flow_segments_json(flow_results, day_segment_ids, day)
            else:
                flow_segments = {}
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate flow_segments.json: {e}")
            flow_segments = {}
        
        # Issue #628: Write to metrics/ subdirectory
        (metrics_dir / "flow_segments.json").write_text(json.dumps(flow_segments, indent=2))
        logger.info(f"   ✅ flow_segments.json: {len(flow_segments)} segment+event-pair entries (in metrics/)")
        
        # 5.6. Generate zone_captions.json (Issue #628)
        logger.info("5️⃣.6️⃣  Generating zone_captions.json...")
        try:
            day_flow_result = flow_results.get(day, {})
            if isinstance(day_flow_result, dict) and day_flow_result.get("ok") and "segments" in day_flow_result:
                zone_captions = _generate_zone_captions_json(flow_results, day_segment_ids, day, segments_df)
            else:
                zone_captions = []
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate zone_captions.json: {e}")
            zone_captions = []
        
        # Issue #628: Write to visualizations/ subdirectory
        (visualizations_dir / "zone_captions.json").write_text(json.dumps(zone_captions, indent=2))
        logger.info(f"   ✅ zone_captions.json: {len(zone_captions)} zone captions (in visualizations/)")
        
        # 6. Generate schema_density.json (Issue #574: in metadata/ subdirectory)
        logger.info("6️⃣  Generating schema_density.json...")
        schema_density = generate_density_schema_json(meta.get('dataset_version', 'unknown'))
        (metadata_dir / "schema_density.json").write_text(json.dumps(schema_density, indent=2))
        logger.info(f"   ✅ schema_density.json: schema_version={schema_density.get('schema_version')} (in metadata/)")
        
        # 7. Generate health.json (Issue #574: in metadata/ subdirectory)
        logger.info("7️⃣  Generating health.json...")
        # Note: generate_health_json expects ui_path, but we'll pass it and then move the file
        health = generate_health_json(ui_path, run_id, environment)
        (metadata_dir / "health.json").write_text(json.dumps(health, indent=2))
        logger.info(f"   ✅ health.json generated (in metadata/)")
        
        # 8. Generate heatmaps and captions
        logger.info("8️⃣  Generating heatmaps and captions...")
        try:
            if heatmap_reports and heatmap_reports.exists():
                export_heatmaps_and_captions(run_id, heatmap_reports, None)
                
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
                
                # Issue #574: Move heatmaps to visualizations/ subdirectory
                if heatmaps_source and heatmaps_source.exists():
                    heatmaps_dest = visualizations_dir  # visualizations/ subdirectory
                    heatmaps_dest.mkdir(parents=True, exist_ok=True)

                    heatmaps_moved = 0
                    for png_file in heatmaps_source.glob("*.png"):
                        # Extract segment_id from filename (e.g., "A1.png" -> "A1")
                        seg_id = png_file.stem
                        if str(seg_id) in day_segment_ids:
                            dest_file = heatmaps_dest / png_file.name
                            shutil.move(str(png_file), str(dest_file))
                            heatmaps_moved += 1

                    # Clean up source directory if empty after move
                    try:
                        if heatmaps_source.exists() and not any(heatmaps_source.iterdir()):
                            heatmaps_source.rmdir()
                    except Exception as cleanup_err:
                        logger.debug(f"   ⚠️  Could not remove source heatmaps dir: {cleanup_err}")

                    logger.info(
                        f"   ✅ Heatmaps filtered and moved: {heatmaps_moved} PNGs "
                        f"for day {day.value} ({len(day_segment_ids)} segments) (in visualizations/)"
                    )
                else:
                    logger.warning(f"   ⚠️  Heatmaps not found at expected locations")
                
                # Issue #574: Move captions.json to visualizations/ subdirectory
                if captions_source and captions_source.exists():
                    captions_dest = visualizations_dir / "captions.json"
                    if captions_dest.exists():
                        captions_dest.unlink()
                    shutil.move(str(captions_source), str(captions_dest))
                    logger.info(f"   ✅ Captions moved to {captions_dest} (in visualizations/)")
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
                logger.warning("   ⚠️  Skipping heatmaps (no heatmap_reports directory)")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not generate heatmaps/captions: {e}")
        
        # Clean up temporary directory
        if temp_reports and temp_reports.exists():
            import shutil
            shutil.rmtree(temp_reports)

        if heatmap_reports and heatmap_reports.exists():
            import shutil
            shutil.rmtree(heatmap_reports)
        
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
    # Issue #574: Bins are stored in {day}/bins/bins.parquet, not {day}/reports/bins.parquet
    for day_dir in run_path.iterdir():
        if day_dir.is_dir() and day_dir.name in ['fri', 'sat', 'sun', 'mon']:
            bins_parquet = day_dir / "bins" / "bins.parquet"
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


def _generate_flow_segments_json(
    flow_results: Dict[str, Any],
    day_segment_ids: set,
    day: Any  # Day enum
) -> Dict[str, Any]:
    """
    Generate flow_segments.json for Flow UI.
    
    Issue #628: Creates segment-level data with worst zone metrics and nested zones.
    Each segment+event-pair combination gets one entry with worst zone metrics.
    
    Args:
        flow_results: Flow results dict keyed by Day enum
        day_segment_ids: Set of segment IDs for the specific day
        day: Day enum for filtering
        
    Returns:
        Dictionary keyed by composite key (seg_id_event_a_event_b)
    """
    from app.core.flow.flow import select_worst_zone, ConflictZone
    
    flow_segments = {}
    
    # Get day-specific flow results
    day_flow_result = flow_results.get(day, {})
    if not isinstance(day_flow_result, dict) or not day_flow_result.get("ok"):
        logger.warning(f"Day {day.value} flow_results not available or invalid")
        return flow_segments
    
    segments_list = day_flow_result.get("segments", [])
    if not segments_list:
        logger.debug(f"Day {day.value}: No segments in flow results")
        return flow_segments
    
    for segment in segments_list:
        if not isinstance(segment, dict):
            continue
            
        seg_id = segment.get("seg_id", "")
        event_a = segment.get("event_a", "")
        event_b = segment.get("event_b", "")
        
        # Only include day-scoped segments
        # Issue #628: Normalize segment ID check - flow_results may have composite IDs (e.g., "A2a")
        # while day_segment_ids contains base IDs (e.g., "A2"). Check both composite and base ID.
        seg_id_str = str(seg_id)
        base_seg_id = seg_id_str.rstrip('abcdefghijklmnopqrstuvwxyz')
        if seg_id_str not in day_segment_ids and base_seg_id not in day_segment_ids:
            continue
        
        # Skip segments without zones
        zones = segment.get("zones", [])
        if not zones:
            continue
        
        # Create composite key
        composite_key = f"{seg_id}_{event_a}_{event_b}"
        
        # Get segment-level metadata
        segment_label = segment.get("segment_label", "")
        flow_type = segment.get("flow_type", "overtake")
        total_a = segment.get("total_a", 0)
        total_b = segment.get("total_b", 0)
        width_m = segment.get("width_m", 0.0)
        has_convergence = segment.get("has_convergence", False)
        
        # Convert zones to ConflictZone objects if needed (for select_worst_zone)
        conflict_zones = []
        zone_dicts = []
        
        for zone in zones:
            if isinstance(zone, ConflictZone):
                conflict_zones.append(zone)
                zone_dicts.append(_zone_to_dict(zone))
            elif isinstance(zone, dict):
                # Normalize zone dict
                zone_dict = _normalize_zone_dict(zone)
                zone_dicts.append(zone_dict)
                # For worst zone selection, we need ConflictZone objects
                try:
                    conflict_zone = _dict_to_conflict_zone(zone)
                    if conflict_zone:
                        conflict_zones.append(conflict_zone)
                except Exception as e:
                    logger.debug(f"Could not convert zone dict to ConflictZone: {e}")
        
        # Select worst zone
        worst_zone = select_worst_zone(conflict_zones) if conflict_zones else None
        
        # Calculate worst zone metrics
        worst_zone_data = None
        if worst_zone:
            worst_metrics = worst_zone.metrics if isinstance(worst_zone, ConflictZone) else worst_zone.get("metrics", {})
            worst_zone_index = worst_zone.zone_index if isinstance(worst_zone, ConflictZone) else worst_zone.get("zone_index", 0)
            worst_cp_km = worst_zone.cp.km if isinstance(worst_zone, ConflictZone) and worst_zone.cp else worst_zone.get("cp", {}).get("km", 0)
            worst_cp_type = worst_zone.cp.type if isinstance(worst_zone, ConflictZone) and worst_zone.cp else worst_zone.get("cp", {}).get("type", "")
            worst_zone_source = worst_zone.source if isinstance(worst_zone, ConflictZone) else worst_zone.get("source", "")
            
            overtaking_a = worst_metrics.get("overtaking_a", 0) if isinstance(worst_metrics, dict) else 0
            overtaking_b = worst_metrics.get("overtaking_b", 0) if isinstance(worst_metrics, dict) else 0
            copresence_a = worst_metrics.get("copresence_a", 0) if isinstance(worst_metrics, dict) else 0
            copresence_b = worst_metrics.get("copresence_b", 0) if isinstance(worst_metrics, dict) else 0
            
            # Calculate percentages
            pct_a = round((overtaking_a / total_a * 100), 1) if total_a > 0 else 0.0
            pct_b = round((overtaking_b / total_b * 100), 1) if total_b > 0 else 0.0
            
            worst_zone_data = {
                "zone_index": worst_zone_index,
                "zone_count": len(zones),
                "display": f"{worst_zone_index}/{len(zones)}",
                "cp_km": round(float(worst_cp_km), 2),
                "cp_type": str(worst_cp_type),
                "zone_source": str(worst_zone_source),
                "overtaking_a": int(overtaking_a),
                "overtaking_b": int(overtaking_b),
                "overtaken_a": int(worst_metrics.get("overtaken_a", 0) if isinstance(worst_metrics, dict) else 0),
                "overtaken_b": int(worst_metrics.get("overtaken_b", 0) if isinstance(worst_metrics, dict) else 0),
                "copresence_a": int(copresence_a),
                "copresence_b": int(copresence_b),
                "pct_a": pct_a,
                "pct_b": pct_b,
                "unique_encounters": int(worst_metrics.get("unique_encounters", 0) if isinstance(worst_metrics, dict) else 0),
                "participants_involved": int(worst_metrics.get("participants_involved", 0) if isinstance(worst_metrics, dict) else 0),
                "multi_category_runners": int(worst_metrics.get("multi_category_runners", 0) if isinstance(worst_metrics, dict) else 0)
            }
        
        # Build segment entry
        flow_segments[composite_key] = {
            "seg_id": seg_id,
            "event_a": event_a,
            "event_b": event_b,
            "segment_label": segment_label,
            "flow_type": flow_type,
            "total_a": int(total_a),
            "total_b": int(total_b),
            "width_m": float(width_m) if width_m else 0.0,
            "has_convergence": bool(has_convergence),
            "worst_zone": worst_zone_data,
            "zones": zone_dicts
        }
    
    logger.info(f"Generated flow_segments.json: {len(flow_segments)} segment+event-pair entries")
    return flow_segments


def _normalize_zone_dict(zone: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize zone dict to standard format."""
    metrics = zone.get("metrics", {})
    cp = zone.get("cp", {})
    
    return {
        "zone_index": zone.get("zone_index", 0),
        "cp_km": round(float(cp.get("km", 0)), 2) if isinstance(cp, dict) else 0.0,
        "cp_type": str(cp.get("type", "")) if isinstance(cp, dict) else "",
        "zone_source": str(zone.get("source", "")),
        "zone_start_km_a": round(float(zone.get("zone_start_km_a", 0)), 2),
        "zone_end_km_a": round(float(zone.get("zone_end_km_a", 0)), 2),
        "zone_start_km_b": round(float(zone.get("zone_start_km_b", 0)), 2),
        "zone_end_km_b": round(float(zone.get("zone_end_km_b", 0)), 2),
        "overtaking_a": int(metrics.get("overtaking_a", 0) if isinstance(metrics, dict) else 0),
        "overtaking_b": int(metrics.get("overtaking_b", 0) if isinstance(metrics, dict) else 0),
        "overtaken_a": int(metrics.get("overtaken_a", 0) if isinstance(metrics, dict) else 0),
        "overtaken_b": int(metrics.get("overtaken_b", 0) if isinstance(metrics, dict) else 0),
        "copresence_a": int(metrics.get("copresence_a", 0) if isinstance(metrics, dict) else 0),
        "copresence_b": int(metrics.get("copresence_b", 0) if isinstance(metrics, dict) else 0),
        "unique_encounters": int(metrics.get("unique_encounters", 0) if isinstance(metrics, dict) else 0),
        "participants_involved": int(metrics.get("participants_involved", 0) if isinstance(metrics, dict) else 0),
        "multi_category_runners": int(metrics.get("multi_category_runners", 0) if isinstance(metrics, dict) else 0)
    }


def _zone_to_dict(zone: Any) -> Dict[str, Any]:
    """Convert ConflictZone object to dict."""
    from app.core.flow.flow import ConflictZone
    
    if isinstance(zone, ConflictZone):
        metrics = zone.metrics
        return {
            "zone_index": zone.zone_index,
            "cp_km": round(zone.cp.km, 2) if zone.cp else 0.0,
            "cp_type": zone.cp.type if zone.cp else "",
            "zone_source": zone.source,
            "zone_start_km_a": round(zone.zone_start_km_a, 2),
            "zone_end_km_a": round(zone.zone_end_km_a, 2),
            "zone_start_km_b": round(zone.zone_start_km_b, 2),
            "zone_end_km_b": round(zone.zone_end_km_b, 2),
            "overtaking_a": int(metrics.get("overtaking_a", 0)),
            "overtaking_b": int(metrics.get("overtaking_b", 0)),
            "overtaken_a": int(metrics.get("overtaken_a", 0)),
            "overtaken_b": int(metrics.get("overtaken_b", 0)),
            "copresence_a": int(metrics.get("copresence_a", 0)),
            "copresence_b": int(metrics.get("copresence_b", 0)),
            "unique_encounters": int(metrics.get("unique_encounters", 0)),
            "participants_involved": int(metrics.get("participants_involved", 0)),
            "multi_category_runners": int(metrics.get("multi_category_runners", 0))
        }
    return _normalize_zone_dict(zone)


def _dict_to_conflict_zone(zone_dict: Dict[str, Any]) -> Optional[Any]:
    """
    Convert zone dict to ConflictZone for select_worst_zone.
    
    Note: This creates a minimal ConflictZone-like object for selection purposes only.
    """
    from app.core.flow.flow import ConvergencePoint
    
    try:
        cp_dict = zone_dict.get("cp", {})
        cp = ConvergencePoint(
            km=float(cp_dict.get("km", 0)),
            type=str(cp_dict.get("type", "unknown"))
        ) if cp_dict else None
        
        if cp is None:
            return None
        
        # Create minimal ConflictZone-like object
        # Note: select_worst_zone only needs metrics and cp.km, so we can create a minimal object
        class MinimalConflictZone:
            def __init__(self, zone_index, cp, source, metrics):
                self.zone_index = zone_index
                self.cp = cp
                self.source = source
                self.metrics = metrics
                # Add other required attributes with defaults
                self.zone_start_km_a = zone_dict.get("zone_start_km_a", 0)
                self.zone_end_km_a = zone_dict.get("zone_end_km_a", 0)
                self.zone_start_km_b = zone_dict.get("zone_start_km_b", 0)
                self.zone_end_km_b = zone_dict.get("zone_end_km_b", 0)
        
        metrics = zone_dict.get("metrics", {})
        return MinimalConflictZone(
            zone_index=zone_dict.get("zone_index", 0),
            cp=cp,
            source=zone_dict.get("source", ""),
            metrics=metrics
        )
    except Exception as e:
        logger.debug(f"Could not create ConflictZone from dict: {e}")
        return None


def _generate_zone_captions_json(
    flow_results: Dict[str, Any],
    day_segment_ids: set,
    day: Any,  # Day enum
    segments_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Generate zone_captions.json for Flow UI.
    
    Issue #628: Creates narrative captions for each zone following density caption pattern.
    
    Returns array of caption objects with explicit keys:
    [
      {
        "seg_id": "F1a",
        "event_a": "10k",
        "event_b": "half",
        "zone_index": 8,
        "summary": "In Zone 8 of segment F1a (230m)...",
        "copresence_pct_a": 89.6,
        "copresence_pct_b": 100.0,
        "overtaking_ratio": "2:1",
        "participants_involved": 830,
        ...
      },
      ...
    ]
    
    Args:
        flow_results: Flow results dict keyed by Day enum
        day_segment_ids: Set of segment IDs for the specific day
        day: Day enum for filtering
        segments_df: Segments DataFrame for metadata lookup
        
    Returns:
        List of caption dictionaries
    """
    zone_captions = []
    
    # Get day-specific flow results
    day_flow_result = flow_results.get(day, {})
    if not isinstance(day_flow_result, dict) or not day_flow_result.get("ok"):
        logger.warning(f"Day {day.value} flow_results not available or invalid")
        return zone_captions
    
    segments_list = day_flow_result.get("segments", [])
    if not segments_list:
        logger.debug(f"Day {day.value}: No segments in flow results")
        return zone_captions
    
    for segment in segments_list:
        if not isinstance(segment, dict):
            continue
            
        seg_id = segment.get("seg_id", "")
        event_a = segment.get("event_a", "")
        event_b = segment.get("event_b", "")
        
        # Only include day-scoped segments
        # Issue #628: Normalize segment ID check - flow_results may have composite IDs (e.g., "A2a")
        # while day_segment_ids contains base IDs (e.g., "A2"). Check both composite and base ID.
        seg_id_str = str(seg_id)
        base_seg_id = seg_id_str.rstrip('abcdefghijklmnopqrstuvwxyz')
        if seg_id_str not in day_segment_ids and base_seg_id not in day_segment_ids:
            continue
        
        # Skip segments without zones
        zones = segment.get("zones", [])
        if not zones:
            continue
        
        # Get segment metadata for label
        segment_label = segment.get("segment_label", "")
        total_a = segment.get("total_a", 0)
        total_b = segment.get("total_b", 0)
        
        # Generate caption for each zone
        for zone in zones:
            # Normalize zone to dict format
            if isinstance(zone, dict):
                zone_dict = zone
            else:
                # Convert ConflictZone to dict
                zone_dict = _zone_to_dict(zone)
            
            zone_index = zone_dict.get("zone_index", 0)
            metrics = zone_dict  # Metrics are at top level in normalized dict
            
            # Extract zone metrics
            overtaking_a = metrics.get("overtaking_a", 0)
            overtaking_b = metrics.get("overtaking_b", 0)
            overtaken_a = metrics.get("overtaken_a", 0)
            overtaken_b = metrics.get("overtaken_b", 0)
            copresence_a = metrics.get("copresence_a", 0)
            copresence_b = metrics.get("copresence_b", 0)
            participants_involved = metrics.get("participants_involved", 0)
            unique_encounters = metrics.get("unique_encounters", 0)
            multi_category_runners = metrics.get("multi_category_runners", 0)
            
            # Calculate zone length in meters
            zone_start_km_a = metrics.get("zone_start_km_a", 0)
            zone_end_km_a = metrics.get("zone_end_km_a", 0)
            zone_length_m = int((zone_end_km_a - zone_start_km_a) * 1000)
            
            # Calculate co-presence percentages
            copresence_pct_a = round((copresence_a / total_a * 100), 1) if total_a > 0 else 0.0
            copresence_pct_b = round((copresence_b / total_b * 100), 1) if total_b > 0 else 0.0
            
            # Calculate overtaking ratio
            overtaking_ratio = _calculate_overtaking_ratio(overtaking_a, overtaking_b)
            
            # Generate summary text
            summary = _build_zone_caption_summary(
                seg_id=seg_id,
                segment_label=segment_label,
                zone_index=zone_index,
                zone_length_m=zone_length_m,
                event_a=event_a,
                event_b=event_b,
                copresence_pct_a=copresence_pct_a,
                copresence_pct_b=copresence_pct_b,
                overtaking_a=overtaking_a,
                overtaking_b=overtaking_b,
                overtaken_a=overtaken_a,
                overtaken_b=overtaken_b,
                overtaking_ratio=overtaking_ratio,
                participants_involved=participants_involved
            )
            
            # Build caption object
            caption = {
                "seg_id": seg_id,
                "event_a": event_a,
                "event_b": event_b,
                "zone_index": zone_index,
                "summary": summary,
                "zone_length_m": zone_length_m,
                "cp_km": metrics.get("cp_km", 0),
                "cp_type": metrics.get("cp_type", ""),
                "zone_source": metrics.get("zone_source", ""),
                "overtaking_a": int(overtaking_a),
                "overtaking_b": int(overtaking_b),
                "overtaken_a": int(overtaken_a),
                "overtaken_b": int(overtaken_b),
                "copresence_a": int(copresence_a),
                "copresence_b": int(copresence_b),
                "copresence_pct_a": copresence_pct_a,
                "copresence_pct_b": copresence_pct_b,
                "overtaking_ratio": overtaking_ratio,
                "unique_encounters": int(unique_encounters),
                "participants_involved": int(participants_involved),
                "multi_category_runners": int(multi_category_runners)
            }
            
            zone_captions.append(caption)
    
    logger.info(f"Generated zone_captions.json: {len(zone_captions)} zone captions")
    return zone_captions


def _calculate_overtaking_ratio(overtaking_a: int, overtaking_b: int) -> str:
    """
    Calculate overtaking ratio as simplified fraction.
    
    Examples:
        (555, 275) -> "2:1" (Half:10K)
        (127, 0) -> "127:0"
        (0, 50) -> "0:50"
        (10, 10) -> "1:1"
    """
    if overtaking_a == 0 and overtaking_b == 0:
        return "0:0"
    
    if overtaking_a == 0:
        return f"0:{overtaking_b}"
    
    if overtaking_b == 0:
        return f"{overtaking_a}:0"
    
    # Find GCD for simplified ratio
    def gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a
    
    common = gcd(overtaking_b, overtaking_a)
    simplified_a = overtaking_a // common
    simplified_b = overtaking_b // common
    
    return f"{simplified_b}:{simplified_a}"  # event_b:event_a


def _build_zone_caption_summary(
    seg_id: str,
    segment_label: str,
    zone_index: int,
    zone_length_m: int,
    event_a: str,
    event_b: str,
    copresence_pct_a: float,
    copresence_pct_b: float,
    overtaking_a: int,
    overtaking_b: int,
    overtaken_a: int,
    overtaken_b: int,
    overtaking_ratio: str,
    participants_involved: int
) -> str:
    """
    Build narrative summary caption for a zone.
    
    Example:
    "In Zone 8 of segment F1a (230m), 89.6% of 10K runners and 100% of Half runners were co-present. 
    555 Half runners overtook 275 10K runners, forming a 2:1 overtaking ratio. 
    Meanwhile, 127 fast 10K runners overtook slower Half runners. 
    This zone demonstrates peak congestion and bidirectional overtaking pressure."
    """
    # Segment reference
    seg_ref = f"{seg_id} ({segment_label})" if segment_label else seg_id
    summary_parts = [f"In Zone {zone_index} of segment {seg_ref} ({zone_length_m}m)"]
    
    # Co-presence statement
    copresence_parts = []
    if copresence_pct_a > 0:
        copresence_parts.append(f"{copresence_pct_a}% of {event_a.upper()} runners")
    if copresence_pct_b > 0:
        copresence_parts.append(f"{copresence_pct_b}% of {event_b.upper()} runners")
    
    if copresence_parts:
        if len(copresence_parts) == 1:
            summary_parts.append(f"{copresence_parts[0]} were co-present.")
        else:
            summary_parts.append(f"{', '.join(copresence_parts[:-1])} and {copresence_parts[-1]} were co-present.")
    
    # Overtaking statement (primary direction)
    if overtaking_b > 0 and overtaking_a > 0:
        summary_parts.append(
            f"{overtaking_b} {event_b.upper()} runners overtook {overtaking_a} {event_a.upper()} runners, "
            f"forming a {overtaking_ratio} overtaking ratio."
        )
    elif overtaking_b > 0:
        summary_parts.append(f"{overtaking_b} {event_b.upper()} runners overtook {overtaking_a} {event_a.upper()} runners.")
    elif overtaking_a > 0:
        summary_parts.append(f"{overtaking_a} {event_a.upper()} runners overtook {overtaking_b} {event_b.upper()} runners.")
    
    # Bidirectional overtaking (if applicable)
    if overtaken_a > 0 or overtaken_b > 0:
        if overtaken_a > 0 and overtaking_a > 0:
            summary_parts.append(
                f"Meanwhile, {overtaking_a} fast {event_a.upper()} runners overtook slower {event_b.upper()} runners."
            )
        elif overtaken_b > 0 and overtaking_b > 0:
            summary_parts.append(
                f"Meanwhile, {overtaking_b} fast {event_b.upper()} runners overtook slower {event_a.upper()} runners."
            )
    
    # Overall characterization
    if participants_involved > 500:
        summary_parts.append("This zone demonstrates peak congestion and bidirectional overtaking pressure.")
    elif participants_involved > 200:
        summary_parts.append("This zone shows significant interaction with bidirectional overtaking.")
    elif participants_involved > 100:
        summary_parts.append("This zone has moderate interaction between events.")
    else:
        summary_parts.append("This zone shows limited interaction between events.")
    
    return " ".join(summary_parts)

