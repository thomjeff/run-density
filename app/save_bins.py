# app/save_bins.py
from __future__ import annotations
import os, gzip, json, math, typing as t
from dataclasses import is_dataclass, asdict
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq

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

    # -------- Parquet (properties only) --------
    rows = []
    for f in features:
        p = _coerce_props(f)
        # Pull required fields safely; missing fields become None
        rows.append({
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
        })
    table = pa.Table.from_pylist(rows)
    parquet_path = os.path.join(output_dir, f"{base_name}.parquet")
    pq.write_table(table, parquet_path, compression="zstd", compression_level=3)

    # -------- GeoJSON (gzip) --------
    # Keep exactly what caller gave us (don't mutate geometries). Ensure minimal structure.
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
