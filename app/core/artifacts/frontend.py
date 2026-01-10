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
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import hashlib
import subprocess

# Add parent directory to path for imports

from app.common.config import load_reporting

# Issue #283: Import SSOT for flagging logic parity
from app import flagging as ssot_flagging


def _load_bins_df(reports_root: Path, run_id: str) -> pd.DataFrame:
    """Load and normalize bins.parquet DataFrame."""
    # Issue #455: Use runflow structure for UUID run_ids
    from app.utils.run_id import is_legacy_date_format
    if is_legacy_date_format(run_id):
        bins_path = reports_root / run_id / "bins.parquet"
    else:
        # UUID: Use runflow structure
        from app.report_utils import get_runflow_file_path
        bins_path = Path(get_runflow_file_path(run_id, "bins", "bins.parquet"))
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
    assert "los_class" in df.columns, f"los_class column not found. Available: {list(df.columns)}"
    
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
    Generate segment_metrics.json from bins.parquet.
    
    Issue #603: Active Window, Peak Rate, and LOS now come from the worst bin (max density bin)
    to ensure consistency with heatmap generation and Bin-Level Details table.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
    
    Returns:
        Dictionary mapping seg_id to metrics
    """
    parquet_path = reports_dir / "bins" / "bins.parquet"
    
    if not parquet_path.exists():
        print(f"Warning: {parquet_path} not found, returning empty metrics")
        return {}
    
    # Read parquet
    df = pd.read_parquet(parquet_path)
    
    # Group by segment_id and aggregate metrics
    metrics = {}
    
    # Use either 'segment_id' or 'seg_id' column
    group_col = 'segment_id' if 'segment_id' in df.columns else 'seg_id'
    
    for seg_id, group in df.groupby(group_col):
        # Issue #603: Find worst bin by max density (same approach as load_density_metrics_from_bins)
        # This ensures all metrics (active_window, peak_rate, worst_los) come from the same bin
        if 'density' in group.columns:
            worst_bin_idx = group['density'].idxmax() if len(group) > 0 else None
        elif 'density_peak' in group.columns:
            worst_bin_idx = group['density_peak'].idxmax() if len(group) > 0 else None
        elif 'density_mean' in group.columns:
            worst_bin_idx = group['density_mean'].idxmax() if len(group) > 0 else None
        else:
            worst_bin_idx = None
        
        if worst_bin_idx is None:
            # Fallback: use first bin if no density column found
            worst_bin_row = group.iloc[0] if len(group) > 0 else None
            peak_density = 0.0
            peak_rate = 0.0
            active_window = "N/A"
        else:
            worst_bin_row = group.loc[worst_bin_idx]
            
            # Extract peak_density from worst bin
            if 'density' in worst_bin_row:
                peak_density = float(worst_bin_row['density'])
            elif 'density_peak' in worst_bin_row:
                peak_density = float(worst_bin_row['density_peak'])
            elif 'density_mean' in worst_bin_row:
                peak_density = float(worst_bin_row['density_mean'])
            else:
                peak_density = 0.0
            
            # Issue #603: Extract peak_rate from worst bin (not separate calculation)
            if 'rate' in worst_bin_row:
                peak_rate = float(worst_bin_row['rate'])
            elif 'rate_p_s' in worst_bin_row:
                peak_rate = float(worst_bin_row['rate_p_s'])
            else:
                peak_rate = 0.0
            
            # Issue #603: Extract LOS from worst bin (not recalculated)
            # Issue #640: LOS must be present (computed via rulebook SSOT upstream)
            if 'los_class' not in worst_bin_row or not worst_bin_row['los_class']:
                raise ValueError(f"Missing los_class for segment {seg_id} worst bin; LOS must be computed upstream via rulebook SSOT.")
            worst_los = str(worst_bin_row['los_class'])
            
            # Issue #603: Extract active_window from worst bin's t_start/t_end
            active_window = "N/A"
            t_start = worst_bin_row.get("t_start", "")
            t_end = worst_bin_row.get("t_end", "")
            if t_start and t_end:
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(str(t_start).replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(str(t_end).replace('Z', '+00:00'))
                    start_str = start_dt.strftime("%H:%M")
                    end_str = end_dt.strftime("%H:%M")
                    active_window = f"{start_str}–{end_str}"
                except (ValueError, TypeError) as e:
                    pass  # Fallback to "N/A" if parsing fails
        
        if worst_bin_row is None:
            raise ValueError("Missing bins for segment; cannot determine los_class.")

        if 'los_class' not in worst_bin_row:
            raise ValueError("Missing los_class in bins.parquet; LOS must be computed upstream.")

        if worst_bin_idx is None:
            worst_los = str(worst_bin_row['los_class'])

        # Get schema_key from the first bin in the group (all bins in a segment should have the same schema_key)
        schema_key = group['schema_key'].iloc[0] if 'schema_key' in group.columns else 'on_course_open'
        
        metrics[seg_id] = {
            "schema": schema_key,  # Issue #285: Add operational schema tag
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
        bins_path = reports_dir / "bins" / "bins.parquet"
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


def generate_flow_metrics_legacy(reports_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Generate flow metrics (overtaking/copresence) from Flow.csv.
    
    LEGACY: This generates event-overlap metrics, not time-series rate data.
    Kept for backwards compatibility but should be phased out.
    
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


def generate_flow_json(reports_dir: Path) -> Dict[str, Any]:
    """
    Generate authoritative flow.json with time-series rate data from bins.parquet.
    
    Issue #287: Emit complete per-segment time series of rate (p/s) for entire active window.
    Source of truth: bins.parquet (same bins that drive the density report).
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
    
    Returns:
        Dictionary with schema_version, units, rows (bin-level time series), and summaries (segment aggregates)
    """
    bins_path = reports_dir / "bins" / "bins.parquet"
    
    if not bins_path.exists():
        print(f"   ⚠️  bins.parquet not found at {bins_path}")
        return {
            "schema_version": "1.0.0",
            "units": {"rate": "persons_per_second", "time": "ISO8601"},
            "rows": [],
            "summaries": []
        }
    
    # Load bins data
    bins_df = pd.read_parquet(bins_path)
    
    # Filter to bins with valid rate data
    bins_with_rate = bins_df[bins_df['rate'].notna()].copy()
    
    if len(bins_with_rate) == 0:
        print(f"   ⚠️  No bins with rate data found in {bins_path}")
        return {
            "schema_version": "1.0.0",
            "units": {"rate": "persons_per_second", "time": "ISO8601"},
            "rows": [],
            "summaries": []
        }
    
    # Generate rows: one per bin with segment_id, t_start, t_end, rate
    rows = []
    for _, row in bins_with_rate.iterrows():
        rows.append({
            "segment_id": str(row['segment_id']),
            "t_start": str(row['t_start']),
            "t_end": str(row['t_end']),
            "rate": float(row['rate'])
        })
    
    # Generate summaries: aggregate stats per segment
    summaries = []
    for seg_id, group in bins_with_rate.groupby('segment_id'):
        summaries.append({
            "segment_id": str(seg_id),
            "bins": int(len(group)),
            "peak_rate": float(group['rate'].max()),
            "avg_rate": float(group['rate'].mean()),
            "active_start": str(group['t_start'].min()),
            "active_end": str(group['t_end'].max())
        })
    
    payload = {
        "schema_version": "1.0.0",
        "units": {"rate": "persons_per_second", "time": "ISO8601"},
        "rows": rows,
        "summaries": summaries
    }
    
    print(f"   ✅ Generated {len(rows)} bin-level rate records across {len(summaries)} segments")
    
    return payload



def _load_segment_dimensions(segments_csv_path: str):
    """Load segment dimensions from segments.csv.
    
    Issue #616: Accept segments_csv_path parameter instead of hardcoded "data/segments.csv"
    
    Args:
        segments_csv_path: Path to segments CSV file from analysis.json
    """
    import pandas as pd
    from pathlib import Path
    
    dimensions_path = Path(segments_csv_path)
    if not dimensions_path.exists():
        print(f"ERROR: {dimensions_path} not found (from analysis.json: {segments_csv_path})")
        return {}
    
    df_dims = pd.read_csv(dimensions_path)
    return df_dims.set_index('seg_id').to_dict('index')


def _load_schema_keys(reports_dir):
    """Load schema keys from bins.parquet."""
    import pandas as pd
    from pathlib import Path
    
    schema_keys = {}
    bins_parquet_path = reports_dir / "bins.parquet"
    
    if bins_parquet_path.exists():
        try:
            bins_df = pd.read_parquet(bins_parquet_path)
            if 'schema_key' in bins_df.columns:
                for seg_id, group in bins_df.groupby('segment_id'):
                    schema_keys[seg_id] = group['schema_key'].iloc[0]
                print(f"   ✅ Loaded schema keys for {len(schema_keys)} segments from bins.parquet")
            else:
                print(f"   ⚠️  schema_key column not found in bins.parquet")
        except Exception as e:
            print(f"   ⚠️  Could not load schema keys from bins.parquet: {e}")
    else:
        print(f"   ⚠️  bins.parquet not found at {bins_parquet_path}")
    
    return schema_keys


def _create_segment_feature(seg_id, segment_dims, schema_keys):
    """Create a GeoJSON feature for a segment."""
    dims = segment_dims.get(seg_id, {})
    
    return {
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
            "events": [event for event in ["Full", "Half", "10K"] if dims.get(event.lower() if event != "10K" else "10K", "") == "y"],
            "schema": schema_keys.get(seg_id, "on_course_open"),
            "description": dims.get("description", "No description available")
        }
    }



def _load_segment_schema_keys(reports_dir):
    """Load schema keys from bins.parquet."""
    import pandas as pd
    schema_keys = {}
    bins_parquet_path = reports_dir / "bins.parquet"
    
    if bins_parquet_path.exists():
        try:
            bins_df = pd.read_parquet(bins_parquet_path)
            if 'schema_key' in bins_df.columns:
                for seg_id, group in bins_df.groupby('segment_id'):
                    schema_keys[seg_id] = group['schema_key'].iloc[0]
                print(f"   ✅ Loaded schema keys for {len(schema_keys)} segments")
        except Exception as e:
            print(f"   ⚠️  Could not load schema keys: {e}")
    
    return schema_keys


def _build_segment_feature_properties(seg_id, segment_dims, schema_keys):
    """Build GeoJSON feature properties for a segment."""
    dims = segment_dims.get(seg_id, {})
    
    return {
        "seg_id": seg_id,
        "label": dims.get("seg_label", dims.get("name", seg_id)),
        "length_km": float(dims.get("full_length", dims.get("half_length", dims.get("10K_length", 0.0)))),
        "width_m": float(dims.get("width_m", 0.0)),
        "direction": dims.get("direction", "uni"),
        "events": [event for event in ["Full", "Half", "10K"] 
                   if dims.get(event.lower() if event != "10K" else "10K", "") == "y"],
        "schema": schema_keys.get(seg_id, "on_course_open"),
        "description": dims.get("description", "No description available")
    }


def generate_segments_geojson(reports_dir: Path) -> Dict[str, Any]:
    """
    Generate segments.geojson from GPX course coordinates.
    
    Issue #477: Previously used bin centroids which resulted in:
    - Only 5 unique coordinates per segment (repeated 80 times)
    - Segments not starting at official start line
    - Gaps between segments (e.g., 153m gap between A1 and A2)
    
    Now uses real GPX coordinates from generate_segment_coordinates().
    
    Issue #616: Get segments_csv_path from analysis.json instead of hardcoded "data/segments.csv"
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory (used to locate analysis.json)
    
    Returns:
        GeoJSON FeatureCollection with real course coordinates in Web Mercator (EPSG:3857)
    """
    from app.core.gpx.processor import load_all_courses, generate_segment_coordinates, create_geojson_from_segments
    from app.io.loader import load_segments
    from pyproj import Transformer
    import json
    from app.utils.run_id import get_runflow_root
    
    # Issue #616: Get segments_csv_path from analysis.json
    # reports_dir is typically {runflow_root}/{run_id}/{day}/reports_temp
    # analysis.json is at {runflow_root}/{run_id}/analysis.json
    segments_csv_path = None
    try:
        runflow_root = get_runflow_root()
        # Navigate from reports_dir back to run_id directory
        # reports_dir: {runflow_root}/{run_id}/{day}/reports_temp
        # Need: {runflow_root}/{run_id}/analysis.json
        run_id_dir = reports_dir.parent.parent  # Go from reports_temp -> {day} -> {run_id}
        if run_id_dir.name == "reports_temp":
            # If reports_dir is actually reports_temp, go up one more level
            run_id_dir = reports_dir.parent
        analysis_json_path = run_id_dir / "analysis.json"
        if not analysis_json_path.exists():
            # Try alternative: reports_dir might be {runflow_root}/{run_id}/reports_temp
            alt_run_id_dir = reports_dir.parent
            if (alt_run_id_dir / "analysis.json").exists():
                analysis_json_path = alt_run_id_dir / "analysis.json"
        if analysis_json_path.exists():
            with open(analysis_json_path, 'r') as af:
                analysis_config = json.load(af)
                data_files = analysis_config.get("data_files", {})
                segments_csv_path = data_files.get("segments")
                if not segments_csv_path:
                    # Fallback to segments_file + data_dir
                    segments_file = analysis_config.get("segments_file")
                    data_dir = analysis_config.get("data_dir", "data")
                    if segments_file:
                        segments_csv_path = f"{data_dir}/{segments_file}"
    except Exception as e:
        print(f"Warning: Could not load segments_csv_path from analysis.json: {e}")
    
    if not segments_csv_path:
        error_msg = (
            "segments_csv_path not found in analysis.json for generate_segments_geojson. "
            "This should not happen in v2 pipeline - analysis.json should include segments_file."
        )
        print(f"ERROR: {error_msg}")
        return {"type": "FeatureCollection", "features": []}
    
    # Load GPX courses
    courses = load_all_courses("data")
    if not courses:
        print("Warning: No GPX courses found, returning empty GeoJSON")
        return {"type": "FeatureCollection", "features": []}
    
    # Load segments data to get segment definitions
    try:
        segments_df = load_segments(segments_csv_path)
        segments_list = segments_df.to_dict('records')
    except Exception as e:
        print(f"ERROR: Could not load segments.csv from {segments_csv_path}: {e}")
        return {"type": "FeatureCollection", "features": []}
    
    # Generate real coordinates for all segments from GPX (returns WGS84)
    segments_with_coords = generate_segment_coordinates(courses, segments_list)
    
    # Convert to GeoJSON (coordinates are in WGS84 [lon, lat])
    geojson = create_geojson_from_segments(segments_with_coords)
    
    # Issue #477: Convert coordinates from WGS84 to Web Mercator (EPSG:3857)
    # segments.geojson is stored in Web Mercator, API converts to WGS84 when serving
    wgs84_to_webmerc = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    
    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        if geom.get("type") == "LineString":
            coords = geom.get("coordinates", [])
            # Convert each coordinate from WGS84 [lon, lat] to Web Mercator [x, y]
            geom["coordinates"] = [
                list(wgs84_to_webmerc.transform(lon, lat)) for lon, lat in coords
            ]
        elif geom.get("type") == "MultiLineString":
            coords = geom.get("coordinates", [])
            geom["coordinates"] = [
                [list(wgs84_to_webmerc.transform(lon, lat)) for lon, lat in line]
                for line in coords
            ]
    
    # Load dimensions for segment metadata enrichment
    segment_dims = _load_segment_dimensions(segments_csv_path)
    schema_keys = _load_schema_keys(reports_dir)
    
    # Enrich features with metadata from segments.csv
    for feature in geojson.get("features", []):
        seg_id = feature.get("properties", {}).get("seg_id")
        if seg_id and seg_id in segment_dims:
            dims = segment_dims[seg_id]
            props = feature["properties"]
            
            # Update properties with dimensions
            props["label"] = dims.get("seg_label", dims.get("name", seg_id))
            props["length_km"] = float(dims.get("full_length", dims.get("half_length", dims.get("10K_length", 0.0))))
            props["width_m"] = float(dims.get("width_m", 0.0))
            props["direction"] = dims.get("direction", "uni")
            props["events"] = [event for event in ["Full", "Half", "10K"] 
                              if dims.get(event.lower() if event != "10K" else "10K", "") == "y"]
            props["schema"] = schema_keys.get(seg_id, "on_course_open")
            props["description"] = dims.get("description", "No description available")
    
    return geojson


def export_ui_artifacts(reports_dir: Path, run_id: str, overtaking_segments: int = 0, co_presence_segments: int = 0, environment: str = "local") -> Path:
    """
    Export all UI artifacts from analytics outputs.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
        run_id: Run identifier (e.g., "2025-10-19-1655")
        overtaking_segments: Count of segments with overtaking activity (Issue #304)
        co_presence_segments: Count of segments with co-presence activity (Issue #304)
        environment: Environment name ("local" or "cloud")
    
    Returns:
        Path to artifacts/<run_id>/ui/ directory
    """
    print(f"\n{'='*60}")
    print(f"Exporting UI Artifacts for {run_id}")
    print(f"{'='*60}\n")
    
    # Create output directory
    # Issue #455: Use runflow structure for UUID run_ids, legacy artifacts/ for dates
    from app.utils.run_id import is_legacy_date_format
    if is_legacy_date_format(run_id):
        artifacts_dir = Path("artifacts") / run_id / "ui"
    else:
        # UUID-based run: use runflow structure
        from app.report_utils import get_runflow_category_path
        artifacts_dir = Path(get_runflow_category_path(run_id, "ui"))
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
    
    # Issue #304: Add summary-level metrics to segment_metrics.json
    # Calculate overall peak metrics from per-segment data
    peak_density_overall = max((seg.get("peak_density", 0.0) for seg in segment_metrics.values()), default=0.0)
    peak_rate_overall = max((seg.get("peak_rate", 0.0) for seg in segment_metrics.values()), default=0.0)
    
    # 3. Generate flags.json (needed for flagged_bins count)
    print("\n3️⃣  Generating flags.json...")
    flags = generate_flags_json(reports_dir, segment_metrics)
    
    # Count segments with flags and total flagged bins
    segments_with_flags = len(flags)
    flagged_bins = sum(flag.get("flagged_bins", 0) for flag in flags)
    
    # Add summary metrics at top level (Issue #304)
    segment_metrics_with_summary = {
        "peak_density": round(peak_density_overall, 4),
        "peak_rate": round(peak_rate_overall, 2),
        "segments_with_flags": segments_with_flags,
        "flagged_bins": flagged_bins,
        "overtaking_segments": overtaking_segments,
        "co_presence_segments": co_presence_segments,
        **segment_metrics  # Merge per-segment metrics
    }
    
    (artifacts_dir / "segment_metrics.json").write_text(json.dumps(segment_metrics_with_summary, indent=2))
    print(f"   ✅ segment_metrics.json: {len(segment_metrics)} segments + summary metrics")
    
    (artifacts_dir / "flags.json").write_text(json.dumps(flags, indent=2))
    print(f"   ✅ flags.json: {len(flags)} flagged segments")
    
    # 4. Generate flow.json
    print("\n4️⃣  Generating flow.json...")
    flow = generate_flow_json(reports_dir)
    (artifacts_dir / "flow.json").write_text(json.dumps(flow, indent=2))
    num_segments = len(flow.get('summaries', []))
    num_rows = len(flow.get('rows', []))
    print(f"   ✅ flow.json: {num_segments} segments, {num_rows} bin-level records")
    
    # 5. Generate segments.geojson
    print("\n5️⃣  Generating segments.geojson...")
    segments_geojson = generate_segments_geojson(reports_dir)
    (artifacts_dir / "segments.geojson").write_text(json.dumps(segments_geojson, indent=2))
    print(f"   ✅ segments.geojson: {len(segments_geojson['features'])} features")
    
    # 6. Generate schema_density.json (Issue #285)
    print("\n6️⃣  Generating schema_density.json...")
    schema_density = generate_density_schema_json(meta.get('dataset_version', 'unknown'))
    (artifacts_dir / "schema_density.json").write_text(json.dumps(schema_density, indent=2))
    print(f"   ✅ schema_density.json: schema_version={schema_density.get('schema_version')}")
    
    # 7. Generate health.json (Issue #288)
    print("\n7️⃣  Generating health.json...")
    health = generate_health_json(artifacts_dir, run_id, environment)
    (artifacts_dir / "health.json").write_text(json.dumps(health, indent=2))
    print(f"   ✅ health.json: platform={health['environment']['platform']}, version={health['environment']['version']}")
    
    print(f"\n{'='*60}")
    print(f"✅ All artifacts exported to: {artifacts_dir}")
    print(f"{'='*60}\n")
    
    # Issue #415 Phase 3: Upload UI artifacts to GCS when enabled
    if os.getenv("GCS_UPLOAD", "true").lower() in {"1", "true", "yes", "on"}:
        try:
            # Issue #466 Step 2: Storage consolidated to app.storage
            # Issue #466 Step 2: storage_service removed
            
            # Upload all JSON artifacts to GCS
            ui_artifacts = [
                ("meta.json", meta),
                ("segment_metrics.json", segment_metrics_with_summary),
                ("flags.json", flags),
                ("flow.json", flow),
                ("segments.geojson", segments_geojson),
                ("schema_density.json", schema_density),
                ("health.json", health)
            ]
            
            uploaded_count = 0
            for filename, data in ui_artifacts:
                try:
                    gcs_path = storage_service.save_artifact_json(f"artifacts/{run_id}/ui/{filename}", data)
                    uploaded_count += 1
                except Exception as e:
                    print(f"   ⚠️ Failed to upload {filename} to GCS: {e}")
            
            print(f"☁️ Uploaded {uploaded_count}/{len(ui_artifacts)} UI artifacts to GCS")
        except Exception as e:
            print(f"⚠️ Failed to upload UI artifacts to GCS: {e}")
    
    # Issue #334: Also generate heatmaps and captions to ensure UI completeness
    try:
        from app.core.artifacts.heatmaps import export_heatmaps_and_captions
        # Issue #466 Step 2: Storage consolidated to app.storage
        # Issue #466 Step 2: storage_service removed
        print("\n============================================================")
        print("Generating Heatmaps")
        print("============================================================")
        print("   Generating heatmaps...")
        export_heatmaps_and_captions(run_id, reports_dir, None)
    except Exception as e:
        print(f"   ⚠️  Skipping heatmaps/captions generation: {e}")

    return artifacts_dir


def calculate_flow_segment_counts(reports_root: Path, run_id: str) -> Tuple[int, int]:
    """
    Calculate overtaking and co-presence segment counts from Flow.csv.
    
    Issue #304: Counts unique segments with overtaking or co-presence activity.
    Issue #486: Fixed to find Flow.csv in reports/ subdirectory and handle both Flow.csv and *-Flow.csv patterns.
    
    Args:
        reports_root: Root directory containing reports
        run_id: Run identifier
        
    Returns:
        Tuple of (overtaking_segments_count, co_presence_segments_count)
    """
    try:
        # Issue #486: Find Flow.csv in reports/ subdirectory
        # Flow.csv is located at: runflow/<run_id>/reports/Flow.csv
        run_dir = reports_root / run_id
        reports_dir = run_dir / "reports"
        
        # Try both patterns: Flow.csv (no prefix) and *-Flow.csv (with prefix, for backward compat)
        flow_files = []
        if reports_dir.exists():
            # Look for Flow.csv (exact match) and *-Flow.csv (pattern match)
            flow_files.extend(reports_dir.glob("Flow.csv"))
            flow_files.extend(reports_dir.glob("*-Flow.csv"))
        
        # Also check run_dir directly for backward compatibility
        if not flow_files:
            flow_files.extend(run_dir.glob("Flow.csv"))
            flow_files.extend(run_dir.glob("*-Flow.csv"))
        
        flow_files = sorted(set(flow_files), reverse=True)  # Remove duplicates and sort
        
        if not flow_files:
            print(f"⚠️  No Flow.csv found in {run_dir} or {reports_dir}, returning zero counts")
            return (0, 0)
        
        flow_path = flow_files[0]  # Get most recent
        print(f"📊 Reading flow data from {flow_path.name}")
        
        # Load Flow.csv
        df = pd.read_csv(flow_path)
        
        # Count unique segments with overtaking (overtaking_a > 0 OR overtaking_b > 0)
        overtaking_mask = (df['overtaking_a'] > 0) | (df['overtaking_b'] > 0)
        overtaking_segments = df[overtaking_mask]['seg_id'].nunique()
        
        # Count unique segments with co-presence (copresence_a > 0 OR copresence_b > 0)
        copresence_mask = (df['copresence_a'] > 0) | (df['copresence_b'] > 0)
        co_presence_segments = df[copresence_mask]['seg_id'].nunique()
        
        print(f"   Overtaking segments: {overtaking_segments}")
        print(f"   Co-presence segments: {co_presence_segments}")
        
        return (overtaking_segments, co_presence_segments)
        
    except Exception as e:
        print(f"⚠️  Error calculating flow segment counts: {e}")
        return (0, 0)


def update_latest_pointer(run_id: str) -> None:
    """
    Update artifacts/latest.json to point to the most recent run.
    
    This file is metadata-only (run_id, timestamp). Analytics metrics
    are exported to segment_metrics.json per Issue #304.
    
    Uploads to both local filesystem and GCS (when GCS_UPLOAD is enabled).
    
    Args:
        run_id: Run identifier (e.g., "2025-10-19-1655" or "2025-10-19")
    """
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    # Parse timestamp from run_id or use current time
    # Note: Not all run_ids include HHMM (e.g., directory names are date-only)
    # Python string slicing never raises exceptions, so we need explicit length check
    try:
        dt_str = run_id.replace("-", "")
        
        # Validate minimum length for date (YYYYMMDD = 8 chars)
        if len(dt_str) < 8:
            raise ValueError(f"run_id too short to contain valid date: {run_id}")
        
        year = dt_str[0:4]
        month = dt_str[4:6]
        day = dt_str[6:8]
        
        # Check if run_id includes time component (at least 12 chars: YYYYMMDDHHMM)
        if len(dt_str) >= 12:
            hour = dt_str[8:10]
            minute = dt_str[10:12]
            ts = f"{year}-{month}-{day}T{hour}:{minute}:00Z"
        else:
            # Date-only format: use current UTC time for hour/minute
            now = datetime.now(timezone.utc)
            ts = f"{year}-{month}-{day}T{now.hour:02d}:{now.minute:02d}:00Z"
    except Exception:
        # Fallback to current UTC time in ISO-8601 format
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Metadata-only pointer (Issue #304: analytics metrics go to segment_metrics.json)
    pointer = {
        "run_id": run_id,
        "ts": ts
    }
    
    # Write to local filesystem
    pointer_path = artifacts_dir / "latest.json"
    pointer_path.write_text(json.dumps(pointer, indent=2))
    
    print(f"✅ Updated artifacts/latest.json → {run_id}")
    
    # Upload to GCS if enabled (Issue #415 Phase 3)
    if os.getenv("GCS_UPLOAD", "true").lower() in {"1", "true", "yes", "on"}:
        try:
            # Issue #466 Step 2: Storage consolidated to app.storage
            # Issue #466 Step 2: storage_service removed
            
            # Use save_artifact_json to upload to GCS at artifacts/latest.json path
            gcs_path = storage_service.save_artifact_json("artifacts/latest.json", pointer)
            print(f"☁️ latest.json uploaded to GCS: {gcs_path}")
        except Exception as e:
            print(f"⚠️ Failed to upload latest.json to GCS: {e}")


def main():
    """Main entry point for standalone execution."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m app.core.artifacts.frontend <run_id>")
        print("Example: python -m app.core.artifacts.frontend 2025-10-19-1655")
        sys.exit(1)
    
    run_id = sys.argv[1]
    reports_root = Path("reports")
    reports_dir = reports_root / run_id
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    # Issue #304: Calculate flow segment counts for dashboard tiles
    overtaking_segments, co_presence_segments = calculate_flow_segment_counts(reports_root, run_id)
    
    # Export artifacts (including flow metrics in segment_metrics.json)
    artifacts_dir = export_ui_artifacts(reports_dir, run_id, overtaking_segments, co_presence_segments)
    
    # Update pointer (metadata-only)
    update_latest_pointer(run_id)
    
    print("\n🎉 Export complete!")


def generate_density_schema_json(dataset_version: str = "unknown") -> Dict[str, Any]:
    """
    Generate the canonical density schema definition for UI display.
    
    Issue #285: This provides the authoritative schema for the Density page
    instead of using geometry metadata from segments.geojson.
    
    Args:
        dataset_version: Version identifier for traceability
        
    Returns:
        Dict containing the density schema definition
    """
    import hashlib
    
    # Generate a simple hash for rulebook identification
    rulebook_hash = hashlib.sha256(dataset_version.encode()).hexdigest()[:16]
    
    return {
        "schema_version": "1.0.0",
        "rulebook_hash": f"sha256:{rulebook_hash}",
        "dataset_version": dataset_version,
        "units": {
            "density": "persons_per_m2",
            "rate": "persons_per_second", 
            "los_class": "A-F",
            "severity": "NONE|WATCH|ALERT|CRITICAL",
            "time": "ISO8601"
        },
        "fields": [
            {
                "name": "segment_id",
                "type": "string",
                "required": True,
                "description": "Canonical segment identifier (A1, B2, ...)."
            },
            {
                "name": "t_start", 
                "type": "timestamp",
                "required": True,
                "description": "Bin start time (ISO 8601)."
            },
            {
                "name": "t_end",
                "type": "timestamp", 
                "required": True,
                "description": "Bin end time (ISO 8601)."
            },
            {
                "name": "density",
                "type": "number",
                "required": True,
                "description": "Persons per square meter (p/m²)."
            },
            {
                "name": "rate",
                "type": "number",
                "required": True,
                "description": "Persons per second (p/s)."
            },
            {
                "name": "los_class",
                "type": "string",
                "required": True,
                "description": "Level of Service classification (A–F)."
            },
            {
                "name": "severity",
                "type": "string",
                "required": False,
                "description": "Flag severity for the bin (NONE/WATCH/ALERT/CRITICAL)."
            },
            {
                "name": "flag_reason",
                "type": "string",
                "required": False,
                "description": "Reason code when flagged (e.g., DENSITY_WATCH, RATE_ALERT)."
            }
        ],
        "aliases": {
            "seg_id": ["segmentId", "segId"],
            "flow": ["pax_per_sec", "rate_per_sec"],
            "pax_per_m2": ["dens"]
        }
    }


def generate_health_json(artifacts_dir: Path, run_id: str, environment: str = "local") -> Dict[str, Any]:
    """
    Generate system health data for the Health Check page.
    
    Issue #288: This provides system/runtime health information instead of
    operational metrics. The Health page should render from this data exclusively.
    
    Args:
        artifacts_dir: Path to artifacts/<run_id>/ui/ directory
        run_id: Run identifier (e.g., "2025-10-19-1655")
        environment: Environment name ("local", "cloud", etc.)
        
    Returns:
        Dict containing system health information
    """
    import hashlib
    import os
    
    # Get current timestamp
    now = datetime.now(timezone.utc)
    
    # Determine platform
    platform = "Cloud Run" if environment == "cloud" else "Local"
    
    # Get version from app version or fallback
    try:
        from app.version import __version__
        version = __version__
    except ImportError:
        version = "unknown"
    
    # Generate data root path
    data_root = f"/app/data/race-{run_id}" if environment == "cloud" else f"./data"
    
    # Check file presence and modification times
    files = []
    file_names = ["segments.geojson", "segment_metrics.json", "flags.json", "meta.json", "flow.json", "schema_density.json"]
    
    for file_name in file_names:
        file_path = artifacts_dir / file_name
        present = file_path.exists()
        modified = None
        
        if present:
            try:
                # Get modification time
                mtime = file_path.stat().st_mtime
                modified = datetime.fromtimestamp(mtime, timezone.utc).isoformat()
            except OSError:
                modified = None
        
        files.append({
            "name": file_name,
            "present": present,
            "modified": modified
        })
    
    # Generate config hashes
    hashes = {}
    
    # Rulebook hash
    try:
        rulebook_path = Path("config/density_rulebook.yml")
        if rulebook_path.exists():
            rulebook_content = rulebook_path.read_text(encoding="utf-8")
            hashes["rulebook"] = hashlib.sha256(rulebook_content.encode()).hexdigest()[:16]
    except Exception:
        hashes["rulebook"] = "unknown"
    
    # Reporting hash  
    try:
        reporting_path = Path("config/reporting.yml")
        if reporting_path.exists():
            reporting_content = reporting_path.read_text(encoding="utf-8")
            hashes["reporting"] = hashlib.sha256(reporting_content.encode()).hexdigest()[:16]
    except Exception:
        hashes["reporting"] = "unknown"
    
    # Endpoint status (optional - can be null in service context)
    endpoints = [
        {"path": "/api/segments", "status": "up", "latency_ms": None},
        {"path": "/api/density", "status": "up", "latency_ms": None},
        {"path": "/api/flow", "status": "up", "latency_ms": None},
        {"path": "/api/reports", "status": "up", "latency_ms": None},
        {"path": "/api/health", "status": "up", "latency_ms": None}
    ]
    
    return {
        "schema_version": "1.0.0",
        "environment": {
            "platform": platform,
            "version": version,
            "data_root": data_root,
            "last_updated": now.isoformat()
        },
        "files": files,
        "hashes": hashes,
        "endpoints": endpoints
    }


if __name__ == "__main__":
    main()
