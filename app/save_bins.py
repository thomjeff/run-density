# app/save_bins.py
from __future__ import annotations
import os, gzip, json, math, typing as t
from dataclasses import is_dataclass, asdict
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

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
    """
    if not isinstance(feature, dict):
        raise TypeError(f"Feature must be a dict, got {type(feature)}")
    props = feature.get("properties") or {}
    if not isinstance(props, dict):
        # Bad structure; treat as empty props
        props = {}
    return props

def _determine_event_from_time_window(t_start: t.Any, t_end: t.Any, start_times: t.Dict[str, float]) -> t.Optional[str]:
    """
    Determine which event is active for a bin based on its time window.
    
    Args:
        t_start: Bin start time (ISO string or datetime)
        t_end: Bin end time (ISO string or datetime)
        start_times: Dictionary mapping event names to start times in minutes
                    (keys may be "Full", "10K", "Half", "Elite", "Open" or lowercase variants)
        
    Returns:
        Event name (lowercase) or None if no event matches
    """
    if not t_start or not t_end or not start_times:
        return None
    
    try:
        from datetime import datetime, timezone
        
        # Parse t_start and t_end if they're strings
        if isinstance(t_start, str):
            t_start_dt = datetime.fromisoformat(t_start.replace('Z', '+00:00'))
        elif isinstance(t_start, datetime):
            t_start_dt = t_start
        else:
            return None
            
        if isinstance(t_end, str):
            t_end_dt = datetime.fromisoformat(t_end.replace('Z', '+00:00'))
        elif isinstance(t_end, datetime):
            t_end_dt = t_end
        else:
            return None
        
        # Convert to UTC if timezone-naive
        if t_start_dt.tzinfo is None:
            t_start_dt = t_start_dt.replace(tzinfo=timezone.utc)
        if t_end_dt.tzinfo is None:
            t_end_dt = t_end_dt.replace(tzinfo=timezone.utc)
        
        # Calculate bin center time in minutes since midnight
        bin_center_dt = t_start_dt + (t_end_dt - t_start_dt) / 2
        base_date = bin_center_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        minutes_since_midnight = (bin_center_dt - base_date).total_seconds() / 60.0
        
        # Normalize event name mapping (v1 uses "Full", "10K", "Half" etc., v2 uses lowercase)
        event_name_mapping = {
            "full": "full",
            "half": "half",
            "10k": "10k",
            "10K": "10k",
            "elite": "elite",
            "open": "open"
        }
        
        # Find the event whose start time is closest to the bin center
        # Prefer events that are active (started before or at bin center)
        best_event = None
        min_time_diff = float('inf')
        
        for event_name, event_start_min in start_times.items():
            # Event is active if it started before or at the bin center
            if event_start_min <= minutes_since_midnight:
                time_diff = abs(minutes_since_midnight - event_start_min)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_event = event_name
        
        # Normalize event name to lowercase (v2 uses lowercase event names)
        if best_event:
            normalized = event_name_mapping.get(best_event.lower(), best_event.lower())
            return normalized
        
        return None
    except Exception:
        # If parsing fails, return None
        return None


def _build_parquet_rows_from_features(features: t.List[Feature], metadata: JsonDict) -> t.List[JsonDict]:
    """Build parquet rows from features and metadata."""
    rows = []
    
    # Extract start_times from metadata for event determination (Issue #535)
    start_times = metadata.get("start_times", {})
    
    for f in features:
        p = _coerce_props(f)
        
        # Determine event from time window (Issue #535)
        event = None
        if start_times:
            event = _determine_event_from_time_window(
                p.get("t_start"),
                p.get("t_end"),
                start_times
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
        
        # Add event column if determined (Issue #535)
        if event is not None:
            row["event"] = event
        
        rows.append(row)
    return rows


def _apply_flagging_to_rows(rows: t.List[JsonDict], logger=None) -> t.List[JsonDict]:
    """Apply rulebook-based flagging to parquet rows (Issue #254)."""
    try:
        from app.new_flagging import apply_new_flagging
        from app.io.loader import load_segments
        
        # Convert rows to DataFrame for flagging
        bins_df = pd.DataFrame(rows)
        
        if logger:
            logger.info(f"Flagging input: {len(bins_df)} rows, columns: {list(bins_df.columns)}")
        
        # Load segments metadata for width_m, seg_label, segment_type
        segments_df = None
        try:
            segments_df = load_segments("data/segments.csv")
        except Exception as e:
            if logger:
                logger.warning(f"Could not load segments.csv for flagging: {e}")
        
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
        # Create a lookup for severity data
        severity_lookup = {row['bin_id']: {
            'flag_severity': row.get('flag_severity', 'none'),
            'flag_reason': row.get('flag_reason', 'none'),
            'los': row.get('los', row.get('los_class', 'A')),
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


def _write_geojson_file(features: t.List[Feature], metadata: JsonDict, output_dir: str, base_name: str) -> str:
    """Write geojson.gz file from features and metadata."""
    fc = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            **metadata,
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
    logger=None,
) -> t.Tuple[str, str]:
    """
    Writes two artifacts:
      - {base_name}.geojson.gz (pure FeatureCollection + optional metadata)
      - {base_name}.parquet    (flat table of properties; geometry not required)
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
    rows = _build_parquet_rows_from_features(features, metadata)
    
    # Apply rulebook-based flagging (Issue #254)
    rows = _apply_flagging_to_rows(rows, logger=logger)
    
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
