# app/save_bins.py
from __future__ import annotations
import os, gzip, json, math, typing as t
from dataclasses import is_dataclass, asdict
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import numpy as np

JsonDict = t.Dict[str, t.Any]
Feature = JsonDict

def _is_geojson_collection(obj: t.Any) -> bool:
    return isinstance(obj, dict) and obj.get("type") == "FeatureCollection" and isinstance(obj.get("features"), list)

def _extract_features_and_metadata(obj: t.Any, logger=None) -> t.Tuple[t.List[Feature], JsonDict]:
    """
    Accepts:
      - BinBuildResult (dataclass with .features, .metadata) from bins_accumulator
      - GeoJSON dict {type: 'FeatureCollection', features: [...], metadata: {...}}
    Returns: (features_list, metadata_dict)
    """
    if obj is None:
        raise ValueError("save_bin_artifacts: input obj is None (no bin dataset was returned).")

    # Case 1: BinBuildResult dataclass
    if is_dataclass(obj):
        d = asdict(obj)  # {'features': [...], 'metadata': {...}} for our dataclasses
        feats = d.get("features")
        meta = d.get("metadata") or {}
        if not isinstance(feats, list):
            raise TypeError(f"save_bin_artifacts: expected list of features in dataclass, got {type(feats)}.")
        return feats, meta

    # Case 2: GeoJSON dict
    if _is_geojson_collection(obj):
        feats = obj.get("features") or []
        meta = obj.get("metadata") or {}
        if not isinstance(feats, list):
            raise TypeError("save_bin_artifacts: 'features' must be a list in GeoJSON.")
        return feats, meta

    # Unknown type
    raise TypeError(f"save_bin_artifacts: unsupported input type {type(obj)}")

def _coerce_props(feature: Feature) -> JsonDict:
    """
    Returns a non-None 'properties' dict for a feature.
    We do NOT assume geometry exists; Parquet path doesn't need it.
    
    Converts numpy int64/float64 to native Python types for JSON serialization.
    """
    import numpy as np
    if not isinstance(feature, dict):
        raise TypeError(f"Feature must be a dict, got {type(feature)}")
    props = feature.get("properties") or {}
    if not isinstance(props, dict):
        # Bad structure; treat as empty props
        props = {}
    
    # Convert numpy types to native Python types for JSON serialization
    coerced_props = {}
    for k, v in props.items():
        if isinstance(v, (int, np.integer)):
            coerced_props[k] = int(v)
        elif isinstance(v, (float, np.floating)):
            coerced_props[k] = float(v)
        elif pd.isna(v):
            coerced_props[k] = None
        else:
            coerced_props[k] = v
    
    return coerced_props

def _determine_events_from_time_window(
    t_start: t.Any, 
    t_end: t.Any, 
    start_times: t.Dict[str, float], 
    event_durations: t.Optional[t.Dict[str, int]] = None,
    logger=None
) -> t.List[str]:
    """
    Determine which events are active for a bin based on its time window.
    
    A bin can belong to multiple events when:
    - Multiple events share the same segment (e.g., A1-A3 for Full, Half, 10K)
    - Events start close together (within minutes)
    - The bin's time window overlaps with multiple events' active periods
    
    Issue #535: Uses event durations to compute full active windows, not just start times.
    Issue #553 Phase 4.3: Uses event_durations from analysis.json (no fallback to constant).
    An event is active from its start time until (start_time + duration).
    
    Args:
        t_start: Bin start time (ISO string or datetime)
        t_end: Bin end time (ISO string or datetime)
        start_times: Dictionary mapping event names to start times in minutes
                    (keys may be "Full", "10K", "Half", "Elite", "Open" or lowercase variants)
        event_durations: Optional dictionary mapping event names to durations in minutes.
                        If not provided, will attempt to load from analysis.json via metadata.
                        Required for Issue #553 (no fallback to EVENT_DURATION_MINUTES constant).
        logger: Optional logger for warning messages
        
    Returns:
        List of event names (lowercase) that are active during this bin's time window.
        Returns empty list if no events match.
    """
    if not t_start or not t_end or not start_times:
        return []
    
    try:
        from datetime import datetime, timezone
        
        # Parse t_start and t_end if they're strings
        if isinstance(t_start, str):
            t_start_dt = datetime.fromisoformat(t_start.replace('Z', '+00:00'))
        elif isinstance(t_start, datetime):
            t_start_dt = t_start
        else:
            return []
            
        if isinstance(t_end, str):
            t_end_dt = datetime.fromisoformat(t_end.replace('Z', '+00:00'))
        elif isinstance(t_end, datetime):
            t_end_dt = t_end
        else:
            return []
        
        # Convert to UTC if timezone-naive
        if t_start_dt.tzinfo is None:
            t_start_dt = t_start_dt.replace(tzinfo=timezone.utc)
        if t_end_dt.tzinfo is None:
            t_end_dt = t_end_dt.replace(tzinfo=timezone.utc)
        
        # Calculate bin time window boundaries in minutes since midnight
        base_date = t_start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        bin_start_min = (t_start_dt - base_date).total_seconds() / 60.0
        bin_end_min = (t_end_dt - base_date).total_seconds() / 60.0
        
        # Normalize event name mapping (v1 uses "Full", "10K", "Half" etc., v2 uses lowercase)
        event_name_mapping = {
            "full": "full",
            "half": "half",
            "10k": "10k",
            "10K": "10k",
            "elite": "elite",
            "open": "open"
        }
        
        # Build event active windows using durations (Issue #535, Issue #553)
        # Event is active from start_time to (start_time + duration)
        active_events = []
        
        # Issue #553 Phase 4.3: Require event_durations (no fallback)
        if event_durations is None:
            if logger:
                logger.error(
                    "event_durations parameter required for _determine_events_from_time_window. "
                    "Event durations must come from analysis.json per Issue #553."
                )
            return []
        
        for event_name, event_start_min in start_times.items():
            # Get event duration from provided dict (Issue #553: from analysis.json)
            # Normalize event name for lookup (support both case variants)
            event_name_lower = event_name.lower()
            event_duration = event_durations.get(event_name, event_durations.get(event_name_lower))
            
            if event_duration is None or event_duration == 0:
                if logger:
                    logger.warning(
                        f"Event duration not found for '{event_name}' in event_durations dict. "
                        f"Available keys: {list(event_durations.keys())}. Skipping event assignment."
                    )
                continue
            
            if not isinstance(event_duration, int) or event_duration < 1:
                if logger:
                    logger.warning(
                        f"Invalid event duration for '{event_name}': {event_duration} "
                        f"(must be integer >= 1). Skipping event assignment."
                    )
                continue
            
            event_end_min = event_start_min + event_duration
            
            # Check if bin overlaps with event's active window
            # Bin overlaps if: bin_start < event_end AND bin_end > event_start
            if bin_start_min < event_end_min and bin_end_min > event_start_min:
                # Normalize event name to lowercase (v2 uses lowercase event names)
                normalized = event_name_mapping.get(event_name_lower, event_name_lower)
                if normalized not in active_events:
                    active_events.append(normalized)
        
        # Sort events by start time for consistency
        active_events.sort(key=lambda e: start_times.get(e.capitalize(), start_times.get(e, float('inf'))))
        
        return active_events
    except Exception as e:
        # Log the error instead of silently failing (Issue #535)
        if logger:
            logger.warning(f"Event assignment failed for bin at {t_start}: {e}")
        else:
            import logging
            logging.warning(f"Event assignment failed for bin at {t_start}: {e}")
        return []


def _build_parquet_rows_from_features(features: t.List[Feature], metadata: JsonDict, logger=None) -> t.List[JsonDict]:
    """Build parquet rows from features and metadata."""
    rows = []
    
    # Extract start_times and event_durations from metadata for event determination
    # Issue #535: Uses event durations to compute full active windows
    # Issue #553 Phase 4.3: Event durations come from analysis.json (no fallback)
    start_times = metadata.get("start_times", {})
    event_durations = metadata.get("event_durations", {})
    
    for f in features:
        p = _coerce_props(f)
        
        # Determine events from time window (Issue #535, Issue #553)
        # A bin can belong to multiple events in shared segments
        events = []
        if start_times and event_durations:
            events = _determine_events_from_time_window(
                p.get("t_start"),
                p.get("t_end"),
                start_times,
                event_durations=event_durations,
                logger=logger
            )
        
        # Pull required fields safely; missing fields become None
        row = {
            "bin_id":               p.get("bin_id"),
            "segment_id":           p.get("segment_id"),
            "start_km":             _safe_float(p.get("start_km")),
            "end_km":               _safe_float(p.get("end_km")),
            "t_start":              p.get("t_start"),
            "t_end":                p.get("t_end"),
            "density":              _safe_float(p.get("density")),
            "rate":                 _safe_float(p.get("rate")),
            "los_class":            p.get("los_class"),
            "bin_size_km":          _safe_float(p.get("bin_size_km")),
            "schema_version":       (metadata.get("schema_version") or "1.0.0"),
            "analysis_hash":        metadata.get("analysis_hash"),
        }
        
        # Add event column (Issue #535)
        # Store as list for multi-event support (parquet supports list types)
        if events:
            row["event"] = events
        else:
            # If no events determined, set to empty list (rather than None)
            # This ensures consistent schema
            row["event"] = []
        
        rows.append(row)
    return rows


def _apply_flagging_to_rows(rows: t.List[JsonDict], segments_df: t.Optional[pd.DataFrame] = None, segments_csv_path: t.Optional[str] = None, logger=None) -> t.List[JsonDict]:
    """Apply rulebook-based flagging to parquet rows (Issue #254).
    
    Issue #616: Accept segments_df or segments_csv_path parameter instead of hardcoded "data/segments.csv"
    
    Args:
        rows: List of bin row dictionaries
        segments_df: Optional segments DataFrame (preferred - already loaded)
        segments_csv_path: Optional path to segments CSV file (used if segments_df is None)
        logger: Optional logger instance
    """
    try:
        from app.new_flagging import apply_new_flagging
        from app.io.loader import load_segments
        
        # Convert rows to DataFrame for flagging
        bins_df = pd.DataFrame(rows)
        
        if logger:
            logger.info(f"Flagging input: {len(bins_df)} rows, columns: {list(bins_df.columns)}")
        
        # Issue #616: Load segments metadata - prefer segments_df, then segments_csv_path, fail if neither
        if segments_df is None:
            if segments_csv_path:
                try:
                    segments_df = load_segments(segments_csv_path)
                    if logger:
                        logger.info(f"Loaded segments from {segments_csv_path} for flagging")
                except Exception as e:
                    if logger:
                        logger.error(f"Could not load segments from {segments_csv_path} for flagging: {e}")
                    # Continue without segments_df - flagging will use defaults
            else:
                # Issue #616: No hardcoded fallback - fail if segments not provided
                error_msg = (
                    "segments_df or segments_csv_path is required for _apply_flagging_to_rows. "
                    "This should not happen in v2 pipeline - segments should be provided from analysis.json."
                )
                if logger:
                    logger.error(error_msg)
                # Continue without segments_df - flagging will use defaults, but log error
                if logger:
                    logger.warning("Continuing flagging without segments_df - flagging may be inaccurate")
        
        # Apply rulebook-based flagging (no config needed - thresholds from YAML)
        flagged_df = apply_new_flagging(bins_df, segments_df=segments_df)
        
        # Convert back to rows with new columns
        flagged_rows = flagged_df.to_dict('records')
        
        if logger:
            logger.info(f"Applied rulebook flagging: {len(flagged_df)} bins processed")
        
        return flagged_rows
            
    except Exception as e:
        if logger:
            logger.warning(f"Rulebook flagging failed, using original data: {e}")
            logger.warning(f"Rows count: {len(rows)}, first row keys: {list(rows[0].keys()) if rows else 'No rows'}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
        # Continue with original rows if flagging fails
        return rows


def _update_features_with_severity(features: t.List[Feature], rows: t.List[JsonDict]) -> t.List[Feature]:
    """Update features with severity information if flagging was applied."""
    updated_features = features.copy()
    if len(rows) > 0 and 'flag_severity' in rows[0]:
        missing_los = [row.get('bin_id') for row in rows if not row.get('los_class')]
        if missing_los:
            raise ValueError(f"los_class missing for {len(missing_los)} bins during severity update")
        # Create a lookup for severity data
        severity_lookup = {row['bin_id']: {
            'flag_severity': row.get('flag_severity', 'none'),
            'flag_reason': row.get('flag_reason', 'none'),
            'los_class': row.get('los_class'),
            'rate_per_m_per_min': row.get('rate_per_m_per_min', 0.0)
        } for row in rows}
        
        # Update features with severity data
        for feature in updated_features:
            bin_id = feature.get('properties', {}).get('bin_id')
            if bin_id and bin_id in severity_lookup:
                feature['properties'].update(severity_lookup[bin_id])
    
    return updated_features


def _write_parquet_file(rows: t.List[JsonDict], output_dir: str, base_name: str) -> str:
    """Write parquet file from rows."""
    table = pa.Table.from_pylist(rows)
    parquet_path = os.path.join(output_dir, f"{base_name}.parquet")
    pq.write_table(table, parquet_path, compression="zstd", compression_level=3)
    return parquet_path


def _coerce_metadata(metadata: JsonDict) -> JsonDict:
    """
    Convert numpy types in metadata to native Python types for JSON serialization.
    """
    import numpy as np
    coerced = {}
    for k, v in metadata.items():
        if isinstance(v, dict):
            coerced[k] = _coerce_metadata(v)
        elif isinstance(v, np.ndarray):
            # Convert numpy array to list, then coerce each element
            coerced[k] = [
                int(item) if isinstance(item, (int, np.integer)) else
                float(item) if isinstance(item, (float, np.floating)) else
                item
                for item in v.tolist()
            ]
        elif isinstance(v, (int, np.integer)):
            coerced[k] = int(v)
        elif isinstance(v, (float, np.floating)):
            coerced[k] = float(v)
        elif isinstance(v, list):
            coerced[k] = [
                int(item) if isinstance(item, (int, np.integer)) else
                float(item) if isinstance(item, (float, np.floating)) else
                item
                for item in v
            ]
        elif v is None or (isinstance(v, (str, bool)) and not pd.isna(v)):
            # Handle None, strings, booleans - only check pd.isna for scalar values
            coerced[k] = v
        else:
            # For other types, try pd.isna only if it's a scalar (not array)
            try:
                if pd.isna(v):
                    coerced[k] = None
                else:
                    coerced[k] = v
            except (ValueError, TypeError):
                # If pd.isna fails (e.g., on arrays), just use the value as-is
                coerced[k] = v
    return coerced

def _write_geojson_file(features: t.List[Feature], metadata: JsonDict, output_dir: str, base_name: str) -> str:
    """Write geojson.gz file from features and metadata."""
    # Coerce all feature properties to native Python types
    coerced_features = []
    for feature in features:
        coerced_feature = feature.copy()
        coerced_feature["properties"] = _coerce_props(feature)
        coerced_features.append(coerced_feature)
    
    # Coerce metadata to native Python types
    coerced_metadata = _coerce_metadata(metadata)
    
    fc = {
        "type": "FeatureCollection",
        "features": coerced_features,
        "metadata": {
            **coerced_metadata,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    geojson_path = os.path.join(output_dir, f"{base_name}.geojson.gz")
    with gzip.open(geojson_path, "wb") as gz:
        gz.write(json.dumps(fc, separators=(",", ":")).encode("utf-8"))
    return geojson_path


def save_bin_artifacts(
    bin_obj: t.Any,
    output_dir: str,
    *,
    base_name: str = "bins",
    segments_df: t.Optional[pd.DataFrame] = None,
    segments_csv_path: t.Optional[str] = None,
    logger=None,
) -> t.Tuple[str, str]:
    """
    Writes two artifacts:
      - {base_name}.geojson.gz (pure FeatureCollection + optional metadata)
      - {base_name}.parquet    (flat table of properties; geometry not required)
    
    Issue #616: Accept segments_df or segments_csv_path parameter instead of hardcoded "data/segments.csv"
    
    Args:
        bin_obj: Bin data object with features and metadata
        output_dir: Output directory for artifacts
        base_name: Base name for output files (default: "bins")
        segments_df: Optional segments DataFrame (preferred - already loaded)
        segments_csv_path: Optional path to segments CSV file (used if segments_df is None)
        logger: Optional logger instance
    
    Returns: (geojson_path, parquet_path)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extract features + metadata (defensive)
    features, metadata = _extract_features_and_metadata(bin_obj, logger=logger)

    # Safety counters
    occupied_bins = int(metadata.get("occupied_bins", 0) or 0)
    nonzero_density_bins = int(metadata.get("nonzero_density_bins", 0) or 0)
    total_features = int(metadata.get("total_features", len(features)) or len(features))

    if logger:
        logger.info("Bins: total=%d occupied=%d nonzero=%d", total_features, occupied_bins, nonzero_density_bins)

    if total_features == 0:
        # Still write empty artifacts for diagnosability, but log hard error
        if logger:
            logger.error("save_bin_artifacts: No features to save (total_features=0). Writing empty artifacts.")
    if occupied_bins == 0 or nonzero_density_bins == 0:
        if logger:
            logger.error("save_bin_artifacts: Occupancy counters indicate empty density (occupied=%d, nonzero=%d).",
                         occupied_bins, nonzero_density_bins)

    # Build parquet rows from features
    rows = _build_parquet_rows_from_features(features, metadata, logger=logger)
    
    # Issue #616: Apply rulebook-based flagging with segments_df or segments_csv_path (no hardcoded fallback)
    rows = _apply_flagging_to_rows(rows, segments_df=segments_df, segments_csv_path=segments_csv_path, logger=logger)
    
    # Write parquet file
    parquet_path = _write_parquet_file(rows, output_dir, base_name)

    # Update features with severity information if flagging was applied
    updated_features = _update_features_with_severity(features, rows)
    
    # Write geojson file
    geojson_path = _write_geojson_file(updated_features, metadata, output_dir, base_name)

    if logger:
        logger.info("Saved bin artifacts: %s (GeoJSON gz), %s (Parquet rows=%d)", geojson_path, parquet_path, len(rows))

    return geojson_path, parquet_path

def _safe_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None
