"""
Analytics-Driven Frontend Artifacts Exporter (RF-FE-002)

Transforms real analytics outputs from /reports/<run_id>/ into UI artifacts
in artifacts/<run_id>/ui/ for the FastAPI dashboard.

NO placeholder data. NO markdown parsing. NO folium/geopandas/matplotlib.
Uses real parquet/CSV/GeoJSON from analytics pipeline.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 7
Architecture: Option 3 - Hybrid Approach | Local=Cloud Parity
"""

import json
import pandas as pd
import gzip
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import hashlib
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.common.config import load_rulebook, load_reporting

# Issue #283: Import SSOT for flagging logic parity
from app import flagging as ssot_flagging


def _load_bins_df(reports_root: Path, run_id: str) -> pd.DataFrame:
    """Load and normalize bins.parquet DataFrame."""
    bins_path = reports_root / run_id / "bins.parquet"
    df = pd.read_parquet(bins_path)
    
    # Normalize expected columns
    rename_map = {}
    if "seg_id" in df.columns and "segment_id" not in df.columns:
        rename_map["seg_id"] = "segment_id"
    if "rate" in df.columns and "rate_p_s" not in df.columns:
        rename_map["rate"] = "rate_p_s"
    
    df = df.rename(columns=rename_map)
    
    # Basic guards
    assert "segment_id" in df.columns, f"segment_id column not found. Available: {list(df.columns)}"
    assert "rate_p_s" in df.columns, f"rate_p_s column not found. Available: {list(df.columns)}"
    
    return df


def _compute_peak_rate_per_segment(bins_df: pd.DataFrame) -> dict:
    """Compute peak rate per segment from bins.parquet."""
    # idxmax per segment_id to grab the whole bin row
    idx = bins_df.groupby("segment_id")["rate_p_s"].idxmax()
    peaks = bins_df.loc[idx, ["segment_id", "rate_p_s", "start_km", "end_km", "t_end"]].copy()
    
    # Build dict { seg_id: {peak_rate, peak_rate_time, peak_rate_km} }
    out = {}
    for _, row in peaks.iterrows():
        seg = str(row["segment_id"])
        out[seg] = {
            "peak_rate": float(round(row["rate_p_s"], 3)),
            "peak_rate_time": str(row.get("t_end", "")),   # use t_end for time
            "peak_rate_km": f'{row.get("start_km", "")}-{row.get("end_km", "")}'
        }
    return out


def get_git_sha() -> str:
    """Get current git commit SHA (short)."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def compute_rulebook_hash() -> str:
    """Compute SHA256 hash of normalized density_rulebook.yml."""
    try:
        rulebook_path = Path("config/density_rulebook.yml")
        content = rulebook_path.read_bytes()
        return f"sha256:{hashlib.sha256(content).hexdigest()[:16]}"
    except Exception as e:
        print(f"Warning: Could not compute rulebook hash: {e}")
        return "sha256:unknown"


def classify_los(density: float, los_thresholds: Dict[str, Any]) -> str:
    """
    Classify density into LOS grade using rulebook thresholds.
    
    Args:
        density: Peak density in persons/m²
        los_thresholds: Dictionary with keys A-F mapping to threshold dicts (min/max) or floats
    
    Returns:
        LOS grade (A-F)
    """
    # Handle both old format (flat thresholds) and new format (min/max dicts)
    grades_with_ranges = []
    
    for grade, threshold_info in los_thresholds.items():
        if isinstance(threshold_info, dict):
            # New format: {"min": 0.0, "max": 0.36, "label": "..."}
            min_val = threshold_info.get("min", 0.0)
            max_val = threshold_info.get("max", float('inf'))
            grades_with_ranges.append((grade, min_val, max_val))
        else:
            # Old format: just a number (upper bound)
            grades_with_ranges.append((grade, 0.0, threshold_info))
    
    # Sort by min value
    grades_with_ranges.sort(key=lambda x: x[1])
    
    # Find the appropriate grade
    for grade, min_val, max_val in grades_with_ranges:
        if min_val <= density < max_val:
            return grade
    
    # If above all ranges, return the last grade (F)
    return grades_with_ranges[-1][0] if grades_with_ranges else "F"


def generate_meta_json(run_id: str, environment: str = "local") -> Dict[str, Any]:
    """
    Generate meta.json with run metadata.
    
    Args:
        run_id: Run identifier (e.g., "2025-10-19-1655" or "2025-10-19")
        environment: Environment name ("local" or "cloud")
    
    Returns:
        Dictionary with meta fields
    """
    # Generate valid ISO-8601 UTC timestamp
    # If run_id contains HHMM, parse it; otherwise use current UTC time
    try:
        # Try to parse YYYY-MM-DD-HHMM format
        parts = run_id.split("-")
        if len(parts) >= 4:
            # Format: YYYY-MM-DD-HHMM
            year, month, day, hhmm = parts[0], parts[1], parts[2], parts[3]
            hour = hhmm[0:2]
            minute = hhmm[2:4]
            run_timestamp = f"{year}-{month}-{day}T{hour}:{minute}:00Z"
        else:
            # Format: YYYY-MM-DD (no time) - use current UTC time
            year, month, day = parts[0], parts[1], parts[2]
            now = datetime.now(timezone.utc)
            run_timestamp = f"{year}-{month}-{day}T{now.hour:02d}:{now.minute:02d}:00Z"
    except Exception:
        # Fallback to current time in ISO-8601 format
        run_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    
    return {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "environment": environment,
        "dataset_version": get_git_sha(),
        "rulebook_hash": compute_rulebook_hash()
    }


def generate_segment_metrics_json(reports_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Generate segment_metrics.json from segment_windows_from_bins.parquet.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
    
    Returns:
        Dictionary mapping seg_id to metrics
    """
    parquet_path = reports_dir / "segment_windows_from_bins.parquet"
    
    if not parquet_path.exists():
        print(f"Warning: {parquet_path} not found, returning empty metrics")
        return {}
    
    # Load rulebook for LOS classification
    try:
        rulebook = load_rulebook()
        los_thresholds = rulebook.get("globals", {}).get("los_thresholds", {})
    except Exception as e:
        print(f"Warning: Could not load rulebook for LOS classification: {e}")
        # Fallback thresholds
        los_thresholds = {"A": 0.2, "B": 0.4, "C": 0.6, "D": 0.8, "E": 1.0, "F": float('inf')}
    
    # Read parquet
    df = pd.read_parquet(parquet_path)
    
    # Group by segment_id and aggregate metrics
    metrics = {}
    
    # Use either 'segment_id' or 'seg_id' column
    group_col = 'segment_id' if 'segment_id' in df.columns else 'seg_id'
    
    for seg_id, group in df.groupby(group_col):
        # Compute peak density (use density_peak if available, else density_mean or density)
        if 'density_peak' in group.columns:
            peak_density = group['density_peak'].max()
        elif 'density_mean' in group.columns:
            peak_density = group['density_mean'].max()
        elif 'density' in group.columns:
            peak_density = group['density'].max()
        else:
            peak_density = 0.0
        
        # Peak rate will be computed from bins.parquet separately
        # Set to 0.0 for now, will be updated later
        peak_rate = 0.0
        
        # Active window: min start time to max end time
        # Use t_start/t_end or start_time/end_time
        if 't_start' in group.columns and 't_end' in group.columns:
            start_dt = pd.to_datetime(group['t_start']).min()
            end_dt = pd.to_datetime(group['t_end']).max()
            active_window = f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
        elif 'start_time' in group.columns and 'end_time' in group.columns:
            start_dt = pd.to_datetime(group['start_time']).min()
            end_dt = pd.to_datetime(group['end_time']).max()
            active_window = f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
        else:
            active_window = "N/A"
        
        # Classify LOS
        worst_los = classify_los(peak_density, los_thresholds)
        
        metrics[seg_id] = {
            "worst_los": worst_los,
            "peak_density": round(peak_density, 4),
            "peak_rate": round(peak_rate, 2),
            "active_window": active_window
        }
    
    return metrics


def generate_flags_json(reports_dir: Path, segment_metrics: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate flags.json from SSOT (Issue #283 fix).
    
    Reads authoritative flags from bins.parquet and uses the SSOT flagging module
    to ensure parity between the Density report and UI artifacts.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
        segment_metrics: Dictionary of segment metrics (for enrichment)
    
    Returns:
        Array of flag objects with canonical names + legacy aliases
    """
    print("   📊 Generating flags.json from SSOT (Issue #283 fix)...")
    
    try:
        # Load bins.parquet (authoritative source)
        bins_path = reports_dir / "bins.parquet"
        if not bins_path.exists():
            print(f"   ⚠️ bins.parquet not found at {bins_path}, returning empty flags")
            return []
        
        bins_df = pd.read_parquet(bins_path)
        print(f"   📊 Loaded {len(bins_df)} bins from bins.parquet")
        
        # Use SSOT to compute and summarize flags
        bin_flags = ssot_flagging.compute_bin_flags(bins_df)
        summary = ssot_flagging.summarize_flags(bin_flags)
        
        print(f"   ✅ SSOT: {summary['flagged_bin_total']} flagged bins across {len(summary['segments_with_flags'])} segments")
        
        # Convert SSOT per_segment to flags.json format
        # Includes both canonical names and legacy aliases for one-release compatibility
        flagged_segments = []
        for seg_data in summary['per_segment']:
            flag_entry = {
                # Canonical names (Issue #283)
                "segment_id": seg_data["segment_id"],
                "flagged_bins": seg_data["flagged_bins"],
                "worst_severity": seg_data["worst_severity"],
                "worst_los": seg_data["worst_los"],
                "peak_density": round(seg_data["peak_density"], 3),
                "peak_rate": round(seg_data["peak_rate"], 3),  # p/s - canonical
                
                # Legacy aliases (DEPRECATED - remove in next release)
                "seg_id": seg_data["segment_id"],
                "flagged_bin_count": seg_data["flagged_bins"],
                
                # Additional fields
                "type": "density",
                "note": f"{seg_data['worst_severity']}: {seg_data['flagged_bins']} bins flagged"
            }
            flagged_segments.append(flag_entry)
        
        print(f"   ✅ Generated {len(flagged_segments)} flag entries with canonical names + legacy aliases")
        return flagged_segments
        
    except Exception as e:
        print(f"   ⚠️ Error generating flags from SSOT: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_flow_json(reports_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Generate flow.json from Flow.csv.
    
    Per ChatGPT QA requirement: flow.json values are SUMS per segment from Flow CSV.
    The CSV has multiple rows per segment (one per event pair), so we sum them.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
    
    Returns:
        Dictionary mapping seg_id to flow metrics (sums across all event pairs)
    """
    # Find Flow.csv file (use the latest one)
    flow_csv = sorted(list(reports_dir.glob("*-Flow.csv")), reverse=True)
    
    if not flow_csv:
        print(f"Warning: No Flow.csv found in {reports_dir}")
        return {}
    
    flow_path = flow_csv[0]
    df = pd.read_csv(flow_path)
    
    # Aggregate by segment_id (sum across all event pairs)
    flow_metrics = {}
    
    # Group by seg_id and sum the flow metrics
    group_col = 'seg_id' if 'seg_id' in df.columns else 'segment_id'
    
    if group_col not in df.columns:
        print(f"Warning: No seg_id or segment_id column in {flow_path}")
        return {}
    
    for seg_id, group in df.groupby(group_col):
        if pd.isna(seg_id):
            continue
        
        # Sum across all event pairs for this segment
        overtaking_a = group['overtaking_a'].sum() if 'overtaking_a' in group.columns else 0.0
        overtaking_b = group['overtaking_b'].sum() if 'overtaking_b' in group.columns else 0.0
        copresence_a = group['copresence_a'].sum() if 'copresence_a' in group.columns else 0.0
        copresence_b = group['copresence_b'].sum() if 'copresence_b' in group.columns else 0.0
        
        flow_metrics[str(seg_id)] = {
            "overtaking_a": float(overtaking_a) if pd.notna(overtaking_a) else 0.0,
            "overtaking_b": float(overtaking_b) if pd.notna(overtaking_b) else 0.0,
            "copresence_a": float(copresence_a) if pd.notna(copresence_a) else 0.0,
            "copresence_b": float(copresence_b) if pd.notna(copresence_b) else 0.0
        }
    
    return flow_metrics


def generate_segments_geojson(reports_dir: Path) -> Dict[str, Any]:
    """
    Generate segments.geojson from bins.geojson.gz by aggregating bins into segment polylines.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
    
    Returns:
        GeoJSON FeatureCollection
    """
    bins_geojson_path = reports_dir / "bins.geojson.gz"
    
    if not bins_geojson_path.exists():
        print(f"Warning: {bins_geojson_path} not found, returning empty GeoJSON")
        return {"type": "FeatureCollection", "features": []}
    
    # Read bins GeoJSON
    with gzip.open(bins_geojson_path, 'rt') as f:
        bins_data = json.load(f)
    
    # Load dimensions for segment metadata
    dimensions_path = Path("data/segments.csv")
    if not dimensions_path.exists():
        print(f"Warning: {dimensions_path} not found")
        segment_dims = {}
    else:
        df_dims = pd.read_csv(dimensions_path)
        segment_dims = df_dims.set_index('seg_id').to_dict('index')
    
    # Group bins by seg_id and create simplified polylines
    segments_features = {}
    
    for feature in bins_data.get("features", []):
        props = feature.get("properties", {})
        seg_id = props.get("seg_id") or props.get("segment_id")
        
        if not seg_id:
            continue
        
        # Get or create segment feature
        if seg_id not in segments_features:
            # Get segment dimensions
            dims = segment_dims.get(seg_id, {})
            
            segments_features[seg_id] = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": []
                },
                "properties": {
                    "seg_id": seg_id,
                    "label": dims.get("seg_label", dims.get("name", seg_id)),
                    "length_km": float(dims.get("full_length", dims.get("half_length", dims.get("10K_length", 0.0)))),
                    "width_m": float(dims.get("width_m", 0.0)),
                    "direction": dims.get("direction", "uni"),
                    "events": [event for event in ["Full", "Half", "10K"] if dims.get(event.lower(), False)]
                }
            }
        
        # Add bin centroid to segment's coordinate list
        geom = feature.get("geometry", {})
        if geom.get("type") == "Polygon":
            # Compute centroid (simple average of coordinates)
            coords = geom.get("coordinates", [[]])[0]
            if coords:
                lon = sum(c[0] for c in coords) / len(coords)
                lat = sum(c[1] for c in coords) / len(coords)
                segments_features[seg_id]["geometry"]["coordinates"].append([lon, lat])
    
    # Simplify polylines (remove duplicates, order by distance)
    features = []
    for seg_id, feature in segments_features.items():
        coords = feature["geometry"]["coordinates"]
        
        # Remove duplicate points
        unique_coords = []
        for coord in coords:
            if not unique_coords or coord != unique_coords[-1]:
                unique_coords.append(coord)
        
        feature["geometry"]["coordinates"] = unique_coords
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def export_ui_artifacts(reports_dir: Path, run_id: str, environment: str = "local") -> Path:
    """
    Export all UI artifacts from analytics outputs.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
        run_id: Run identifier (e.g., "2025-10-19-1655")
        environment: Environment name ("local" or "cloud")
    
    Returns:
        Path to artifacts/<run_id>/ui/ directory
    """
    print(f"\n{'='*60}")
    print(f"Exporting UI Artifacts for {run_id}")
    print(f"{'='*60}\n")
    
    # Create output directory
    artifacts_dir = Path("artifacts") / run_id / "ui"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate meta.json
    print("1️⃣  Generating meta.json...")
    meta = generate_meta_json(run_id, environment)
    (artifacts_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"   ✅ meta.json: run_id={meta['run_id']}, dataset_version={meta['dataset_version']}")
    
    # 2. Generate segment_metrics.json
    print("\n2️⃣  Generating segment_metrics.json...")
    segment_metrics = generate_segment_metrics_json(reports_dir)
    
    # 2a. Compute peak_rate from bins.parquet and merge into segment_metrics
    print("   📊 Computing peak_rate from bins.parquet...")
    try:
        bins_df = _load_bins_df(reports_dir.parent, run_id)
        peak_rate_map = _compute_peak_rate_per_segment(bins_df)
        
        # Merge peak_rate data into segment_metrics
        for seg_id, seg_metrics in segment_metrics.items():
            if seg_id in peak_rate_map:
                seg_metrics["peak_rate"] = peak_rate_map[seg_id]["peak_rate"]
                seg_metrics["peak_rate_time"] = peak_rate_map[seg_id]["peak_rate_time"]
                seg_metrics["peak_rate_km"] = peak_rate_map[seg_id]["peak_rate_km"]
            else:
                # Segment has no bins (rare): set to 0.0 but add a warning
                seg_metrics.setdefault("peak_rate", 0.0)
        
        print(f"   ✅ peak_rate computed for {len(peak_rate_map)} segments")
    except Exception as e:
        print(f"   ⚠️  Warning: Could not compute peak_rate from bins.parquet: {e}")
    
    (artifacts_dir / "segment_metrics.json").write_text(json.dumps(segment_metrics, indent=2))
    print(f"   ✅ segment_metrics.json: {len(segment_metrics)} segments")
    
    # 3. Generate flags.json
    print("\n3️⃣  Generating flags.json...")
    flags = generate_flags_json(reports_dir, segment_metrics)
    (artifacts_dir / "flags.json").write_text(json.dumps(flags, indent=2))
    print(f"   ✅ flags.json: {len(flags)} flagged segments")
    
    # 4. Generate flow.json
    print("\n4️⃣  Generating flow.json...")
    flow = generate_flow_json(reports_dir)
    (artifacts_dir / "flow.json").write_text(json.dumps(flow, indent=2))
    print(f"   ✅ flow.json: {len(flow)} segments with flow metrics")
    
    # 5. Generate segments.geojson
    print("\n5️⃣  Generating segments.geojson...")
    segments_geojson = generate_segments_geojson(reports_dir)
    (artifacts_dir / "segments.geojson").write_text(json.dumps(segments_geojson, indent=2))
    print(f"   ✅ segments.geojson: {len(segments_geojson['features'])} features")
    
    print(f"\n{'='*60}")
    print(f"✅ All artifacts exported to: {artifacts_dir}")
    print(f"{'='*60}\n")
    
    return artifacts_dir


def update_latest_pointer(run_id: str) -> None:
    """
    Update artifacts/latest.json to point to the most recent run.
    
    Args:
        run_id: Run identifier (e.g., "2025-10-19-1655")
    """
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    # Parse timestamp from run_id
    try:
        dt_str = run_id.replace("-", "")
        year = dt_str[0:4]
        month = dt_str[4:6]
        day = dt_str[6:8]
        hour = dt_str[8:10]
        minute = dt_str[10:12]
        
        ts = f"{year}-{month}-{day}T{hour}:{minute}:00Z"
    except Exception:
        ts = datetime.now(timezone.utc).isoformat()
    
    pointer = {
        "run_id": run_id,
        "ts": ts
    }
    
    pointer_path = artifacts_dir / "latest.json"
    pointer_path.write_text(json.dumps(pointer, indent=2))
    
    print(f"✅ Updated artifacts/latest.json → {run_id}")


def main():
    """Main entry point for standalone execution."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python export_frontend_artifacts.py <run_id>")
        print("Example: python export_frontend_artifacts.py 2025-10-19-1655")
        sys.exit(1)
    
    run_id = sys.argv[1]
    reports_dir = Path("reports") / run_id
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    # Export artifacts
    artifacts_dir = export_ui_artifacts(reports_dir, run_id)
    
    # Update pointer
    update_latest_pointer(run_id)
    
    print("\n🎉 Export complete!")


if __name__ == "__main__":
    main()

