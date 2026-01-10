"""
Density Heatmaps & Captions Generator (Issue #280)

Generates per-segment 2D heatmap PNGs and automated captions directly from bin.parquet,
using the same SSOT LOS rules as other analytics modules.

Architecture:
- Input: bin.parquet (canonical SSOT from density.py)
- Output: heatmaps/*.png + captions.json
- Colors: density_rulebook.yml LOS palette
- Storage: app/storage_service.py abstraction

Author: Cursor AI Assistant (per Senior Architect guidance)
Epic: RF-FE-002 | Issue: #280
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
import sys

# Add parent directory to path for imports

from app.common.config import load_rulebook, load_reporting
# Issue #466 Step 2: Storage consolidated to app.storage=None

HEATMAP_POWER_NORM_GAMMA = 0.5
HEATMAP_NAN_COLOR = "white"
HEATMAP_DENSITY_VMIN = 0
HEATMAP_DENSITY_VMAX = 2.0


def _assert_heatmap_invariants(norm: mcolors.Normalize, cmap: mcolors.Colormap) -> None:
    """Regression guard for heatmap normalization + NaN rendering invariants."""
    if not isinstance(norm, mcolors.PowerNorm) or norm.gamma != HEATMAP_POWER_NORM_GAMMA:
        raise ValueError(
            "Heatmap normalization must remain PowerNorm(gamma=0.5) for density rendering."
        )
    if not np.allclose(cmap.get_bad(), mcolors.to_rgba(HEATMAP_NAN_COLOR)):
        raise ValueError("Heatmap NaN values must render as white (no data).")


def create_los_colormap(los_colors: Dict[str, str]) -> mcolors.LinearSegmentedColormap:
    """
    Create a LOS-compliant colormap from rulebook colors.
    
    Args:
        los_colors: Dictionary mapping LOS grades (A-F) to hex colors
        
    Returns:
        Matplotlib LinearSegmentedColormap for LOS visualization
    """
    # Create color sequence from A to F (green to red)
    color_sequence = [
        los_colors.get("A", "#4CAF50"),  # Green - excellent
        los_colors.get("B", "#8BC34A"),  # Light green - good  
        los_colors.get("C", "#FFC107"),  # Amber - acceptable
        los_colors.get("D", "#FF9800"),  # Orange - concerning
        los_colors.get("E", "#FF5722"),  # Red-orange - poor
        los_colors.get("F", "#F44336")   # Red - unacceptable
    ]
    
    # Create colormap
    cmap = mcolors.LinearSegmentedColormap.from_list("los_density", color_sequence)
    return cmap


def load_bin_data(reports_dir: Path) -> pd.DataFrame:
    """
    Load bin data from bin.parquet (canonical SSOT) and apply filtering.
    
    Args:
        reports_dir: Path to run directory (reports/<run_id>/ or runflow/<uuid>/)
        
    Returns:
        DataFrame with filtered bin-level data (flagged bins only)
    """
    # Issue #455: bins.parquet is in bins/ subdirectory
    bins_path = reports_dir / "bins" / "bins.parquet"
    
    if not bins_path.exists():
        raise FileNotFoundError(f"bins.parquet not found at {bins_path}")
    
    print(f"   📊 Loading bin data from {bins_path}")
    df = pd.read_parquet(bins_path)
    print(f"   📊 Loaded {len(df)} bins from parquet")
    
    # Filter to flagged bins only (Issue #280 alignment)
    # This creates more whitespace by only showing operationally significant bins
    if 'flag_severity' in df.columns:
        filtered_bins = df[df['flag_severity'] != 'none'].copy()
        print(f"   📊 Filtered to {len(filtered_bins)} flagged bins (removed {len(df) - len(filtered_bins)} unflagged)")
        return filtered_bins
    else:
        print(f"   ⚠️  flag_severity column not found, using all bins (no filtering)")
        return df



def _prepare_segment_data(segment_bins):
    """Prepare time and distance arrays from segment bins."""
    times = []
    for _, row in segment_bins.iterrows():
        if "t_start" in row:
            times.append(row.get("t_start", ""))
        elif "start_time" in row:
            times.append(row.get("start_time", ""))
    
    distances = sorted(set(segment_bins.get("start_km", 0)))
    times = sorted(set(times))
    return times, distances


def _create_density_matrix(segment_bins, times, distances):
    """Create density matrix from segment bins."""
    import numpy as np
    matrix = np.full((len(times), len(distances)), np.nan)
    
    for _, row in segment_bins.iterrows():
        try:
            if "t_start" in row:
                time_val = row.get("t_start", "")
            elif "start_time" in row:
                time_val = row.get("start_time", "")
            else:
                continue
            
            t_idx = times.index(time_val)
            d_idx = distances.index(row.get("start_km", 0))
            density = float(row.get("density", 0))
            matrix[t_idx, d_idx] = density
        except (ValueError, TypeError):
            continue
    
    return matrix


def _setup_heatmap_plot(matrix, times, distances, seg_id, los_cmap):
    """Set up matplotlib heatmap plot."""
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(12, 6))
    matrix_transposed = matrix.T
    los_cmap.set_bad(color=HEATMAP_NAN_COLOR)
    norm = mcolors.PowerNorm(
        gamma=HEATMAP_POWER_NORM_GAMMA,
        vmin=HEATMAP_DENSITY_VMIN,
        vmax=HEATMAP_DENSITY_VMAX,
    )
    _assert_heatmap_invariants(norm, los_cmap)
    im = ax.imshow(matrix_transposed, cmap=los_cmap, norm=norm, aspect='auto', origin='lower')
    
    segment_labels = {
        'A1': 'Start Corral', 'B1': '10K Turn', 'B2': '10K Turn to Friel',
        'D1': 'Full Turn Blake (Out)', 'F1': 'Friel to Station Rd.',
        'H1': 'Trail/Aberdeen to/from Station Rd', 'I1': 'Station Rd to Bridge/Mill',
        'J1': 'Bridge/Mill to Half Turn (Outbound)', 'J4': 'Half Turn to Bridge/Mill',
        'J5': 'Half Turn to Bridge/Mill (Slow Half)', 'K1': 'Bridge/Mill to Station Rd',
        'L1': 'Trail/Aberdeen to/from Station Rd', 'M1': 'Trail/Aberdeen to Finish (Full to Loop)'
    }
    
    segment_label = segment_labels.get(seg_id, f'Segment {seg_id}')
    ax.set_title(f'Segment {seg_id} — {segment_label}: Density Through Space & Time')
    ax.set_xlabel('Time of day (HH:MM)')
    ax.set_ylabel('Distance along segment (km)')
    
    return fig, ax, im


def _format_heatmap_axes(ax, times, distances):
    """Format heatmap axes with time and distance labels."""
    from datetime import datetime
    
    # Format time labels
    clean_times = []
    for time_str in times:
        try:
            if 'T' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                clean_time = dt.strftime('%H:%M')
            elif ':' in time_str and len(time_str) > 5:
                time_part = time_str.split(' ')[-1] if ' ' in time_str else time_str
                clean_time = time_part[:5] if len(time_part) >= 5 else time_str
            else:
                clean_time = time_str
            clean_times.append(clean_time)
        except Exception:
            clean_times.append(time_str)
    
    # Set ticks with smart spacing
    n_ticks = min(8, len(times))
    if len(times) > 1:
        step = max(1, len(times) // n_ticks)
        tick_indices = range(0, len(times), step)
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([clean_times[i] for i in tick_indices], rotation=30, ha='right')
    else:
        ax.set_xticks([0])
        ax.set_xticklabels(clean_times, rotation=30, ha='right')
    
    ax.set_yticks(range(len(distances)))
    ax.set_yticklabels([f'{d:.1f}' for d in distances])
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)


def generate_segment_heatmap(
    seg_id: str, 
    bins_df: pd.DataFrame, 
    los_colors: Dict[str, str],
    output_path: Path
) -> bool:
    """
    Generate heatmap PNG for a single segment.

    Invariants: heatmaps are density-only (no LOS recompute), use the rulebook palette,
    PowerNorm(gamma=0.5), and NaN=white for missing data.
    
    Args:
        seg_id: Segment identifier (e.g., "A1")
        bins_df: DataFrame with all bin data
        los_colors: LOS color mapping from rulebook
        output_path: Path to save PNG file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Filter bins for this segment
        segment_bins = bins_df[bins_df['segment_id'] == seg_id].copy()
        
        if len(segment_bins) == 0:
            print(f"   ⚠️  No bins found for segment {seg_id}")
            return False
        
        # Create 2D matrix (time × distance)
        # Handle both t_start/t_end and start_time/end_time field names
        times, distances = _prepare_segment_data(segment_bins)
        
        if not times or not distances:
            print(f"   ⚠️  No valid time/distance data for segment {seg_id}")
            return False
        
        print(f"   📊 {seg_id}: Creating {len(times)}×{len(distances)} matrix")
        
        # Create density matrix with NaN for missing data (white in mock-ups)
        matrix = np.full((len(times), len(distances)), np.nan)
        for _, row in segment_bins.iterrows():
            try:
                # Get time field (handle both field names)
                if "t_start" in row:
                    time_val = row.get("t_start", "")
                elif "start_time" in row:
                    time_val = row.get("start_time", "")
                else:
                    continue
                
                t_idx = times.index(time_val)
                d_idx = distances.index(row.get("start_km", 0))
                density = float(row.get("density", 0))
                matrix[t_idx, d_idx] = density
            except (ValueError, TypeError):
                continue
        
        # Create heatmap
        los_cmap = create_los_colormap(los_colors)
        fig, ax, im = _setup_heatmap_plot(matrix, times, distances, seg_id, los_cmap)
        
        # Format axes
        _format_heatmap_axes(ax, times, distances)
        
        # Add colorbar with proper label
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Density (persons / m²)')
        
        # Save PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"   ⚠️  Could not generate heatmap for segment {seg_id}: {e}")
        return False



def _prepare_caption_bins(segment_bins):
    """Prepare and normalize bins for caption generation."""
    import pandas as pd
    
    # Normalize column names
    required_cols = ["t_start", "t_end", "density", "start_km", "end_km"]
    for col in required_cols:
        if col not in segment_bins.columns:
            alias_map = {
                "t_start": "start_time",
                "t_end": "end_time",
                "start_km": "from_km",
                "end_km": "to_km"
            }
            if alias_map.get(col) in segment_bins.columns:
                segment_bins[col] = segment_bins[alias_map[col]]
    
    # Drop rows with missing data and parse timestamps
    segment_bins = segment_bins.dropna(subset=["t_start", "t_end", "density", "start_km", "end_km"]).copy()
    segment_bins["t_start"] = pd.to_datetime(segment_bins["t_start"], errors="coerce")
    segment_bins["t_end"] = pd.to_datetime(segment_bins["t_end"], errors="coerce")
    segment_bins = segment_bins.dropna(subset=["t_start", "t_end"]).sort_values("t_start")
    
    return segment_bins


def _compute_caption_peak(segment_bins):
    """Compute peak density and related metrics for caption."""
    import pandas as pd
    
    peak_idx = segment_bins["density"].idxmax()
    peak_row = segment_bins.loc[peak_idx]
    peak_density = float(peak_row["density"]) if pd.notna(peak_row["density"]) else 0.0
    peak_time = peak_row["t_end"].strftime("%H:%M") if pd.notna(peak_row["t_end"]) else ""
    km_range = f"{float(peak_row['start_km']):.1f}–{float(peak_row['end_km']):.1f} km"
    
    return peak_density, peak_time, km_range, peak_row


def _get_los_grade(peak_density):
    """Determine LOS grade for a density value."""
    try:
        from app import rulebook
    except Exception:
        return "F"

    bands = rulebook.get_thresholds("on_course_open").los
    return rulebook.classify_los(peak_density, bands)



def _load_caption_config():
    """Load captioning configuration from rulebook."""
    try:
        from app.common.config import load_rulebook
        rulebook = load_rulebook()
        caption_cfg = rulebook.get("globals", {}).get("captioning", {})
    except Exception:
        caption_cfg = {}
    
    return {
        "wave_gap_minutes": float(caption_cfg.get("wave_gap_minutes", 5)),
        "clearance_threshold": float(caption_cfg.get("clearance_threshold_p_m2", 0.10)),
        "clearance_sustain": int(caption_cfg.get("clearance_sustain_minutes", 6)),
        "similarity_pct": float(caption_cfg.get("similarity_pct", 0.10)),
        "spread_pct": float(caption_cfg.get("spread_pct", 0.20))
    }


def _split_into_waves(segment_bins, wave_gap_minutes):
    """Split bins into waves based on time gaps."""
    import pandas as pd
    
    waves_bins = []
    current = []
    prev_end = None
    
    for idx, row in segment_bins.iterrows():
        if prev_end is None:
            current = [idx]
            prev_end = row["t_end"]
            continue
        
        gap_min = (pd.Timestamp(row["t_start"]) - pd.Timestamp(prev_end)).total_seconds() / 60.0
        if gap_min > wave_gap_minutes:
            waves_bins.append(segment_bins.loc[current])
            current = [idx]
        else:
            current.append(idx)
        prev_end = row["t_end"]
    
    if current:
        waves_bins.append(segment_bins.loc[current])
    
    return waves_bins


def _analyze_wave(wdf):
    """Analyze a single density wave."""
    import pandas as pd
    
    w_peak_idx = wdf["density"].idxmax()
    w_peak = wdf.loc[w_peak_idx]
    w_peak_density = float(w_peak["density"]) if pd.notna(w_peak["density"]) else 0.0
    w_start = pd.to_datetime(wdf["t_start"].min()).strftime("%H:%M")
    w_end = pd.to_datetime(wdf["t_end"].max()).strftime("%H:%M")
    w_km_range = f"{float(w_peak['start_km']):.1f}–{float(w_peak['end_km']):.1f} km"
    
    unique_minutes = wdf["t_start"].dt.floor("min").nunique()
    unique_dist = pd.Index(wdf["start_km"]).nunique()
    spread = float(unique_minutes * unique_dist)
    
    return {
        "start_time": w_start,
        "end_time": w_end,
        "peak_density_p_m2": w_peak_density,
        "peak_time": pd.to_datetime(w_peak["t_end"]).strftime("%H:%M") if pd.notna(w_peak["t_end"]) else "",
        "peak_km_range": w_km_range,
        "bins_count": int(len(wdf)),
    }, spread


def _compare_waves(waves_out, spread_scores, config):
    """Compare first two waves if available."""
    if len(waves_out) < 2:
        return None
    
    p0 = waves_out[0]["peak_density_p_m2"]
    p1 = waves_out[1]["peak_density_p_m2"]
    rel = (p1 - p0) / p0 if p0 > 0 else 0.0
    
    if abs(rel) <= config["similarity_pct"]:
        rel_txt = "similar"
    elif rel < 0:
        rel_txt = "lighter"
    else:
        rel_txt = "heavier"
    
    s0 = spread_scores[0]
    s1 = spread_scores[1]
    spread_rel = (s1 - s0) / s0 if s0 > 0 else 0.0
    
    if spread_rel >= config["spread_pct"]:
        spread_txt = "more dispersed"
    elif spread_rel <= -config["spread_pct"]:
        spread_txt = "more concentrated"
    else:
        spread_txt = "similar spread"
    
    return {"relative_peak": rel_txt, "spread": spread_txt}


def _find_clearance_time(segment_bins, peak_row, config):
    """Find when segment clears after peak."""
    import pandas as pd
    import numpy as np
    
    minute_index = pd.date_range(
        start=segment_bins["t_start"].min().floor("min"),
        end=segment_bins["t_end"].max().ceil("min"),
        freq="1min"
    )
    per_min = pd.Series(index=minute_index, dtype=float)
    
    for _, row in segment_bins.iterrows():
        ts = pd.date_range(start=row["t_start"].floor("min"), end=row["t_end"].ceil("min"), freq="1min")
        per_min.loc[ts] = np.fmax(
            per_min.loc[ts].to_numpy(dtype=float, copy=True), 
            float(row["density"])
        ) if per_min.loc[ts].notna().any() else float(row["density"])
    
    clearance_time = None
    if len(per_min) > 0:
        start_idx = per_min.index.get_indexer([pd.to_datetime(peak_row["t_end"]).floor("min")], method="nearest")[0]
        series_after = per_min.iloc[start_idx:]
        window = config["clearance_sustain"]
        
        for i in range(0, max(0, len(series_after) - window)):
            window_slice = series_after.iloc[i:i+window]
            if window_slice.isna().any():
                continue
            if (window_slice <= config["clearance_threshold"]).all():
                clearance_time = window_slice.index[0].strftime("%H:%M")
                break
    
    return clearance_time


def _build_caption_summary(seg_id, label, waves_out, peak_time, km_range, peak_density, los_grade, clearance_time, qualitative_note):
    """Build summary text for caption."""
    clearance_phrase = f"Clears by {clearance_time}" if clearance_time else "Does not fully clear in the observed window"
    
    if len(waves_out) <= 1:
        return (
            f"Segment {seg_id} — {label}. A single density wave passes, peaking near {peak_time} "
            f"around {km_range} at {peak_density:.2f} p/m² ({los_grade}). "
            f"{clearance_phrase}."
        )
    
    wave1 = waves_out[0]
    wave2 = waves_out[1]
    adj = qualitative_note["relative_peak"] if qualitative_note else "similar"
    spread_txt = qualitative_note["spread"] if qualitative_note else "similar spread"
    clearance_phrase = f"Clears by {clearance_time}" if clearance_time else "Remains active in window"
    
    w1_start = wave1.get("start_time")
    w1_end = wave1.get("end_time")
    w1_peak = wave1.get("peak_density_p_m2", 0.0)
    w2_start = wave2.get("start_time")
    w2_end = wave2.get("end_time")
    
    return (
        f"Segment {seg_id} — {label}. Two distinct waves are visible. "
        f"The first ({w1_start}–{w1_end}) peaks at ~{w1_peak:.2f} p/m². "
        f"A subsequent wave ({w2_start}–{w2_end}) is {adj} and {spread_txt}. "
        f"Overall peak near {peak_time} around {km_range} at {peak_density:.2f} p/m² ({los_grade}). "
        f"{clearance_phrase}."
    )


def generate_segment_caption(
    seg_id: str,
    bins_df: pd.DataFrame,
    segments_meta: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate auto-caption for a single segment.
    
    Args:
        seg_id: Segment identifier
        bins_df: DataFrame with all bin data
        segments_meta: Segment metadata from segments.csv
        
    Returns:
        Caption dictionary
    """
    try:
        # Load configuration
        config = _load_caption_config()
        
        # Filter bins for this segment
        segment_bins = bins_df[bins_df['segment_id'] == seg_id].copy()
        if len(segment_bins) == 0:
            return None
        
        # Get segment metadata
        meta = segments_meta.get(seg_id, {})
        label = meta.get('label', seg_id)
        
        # Prepare bins
        segment_bins = _prepare_caption_bins(segment_bins)
        if len(segment_bins) == 0:
            return None
        
        # Compute peak metrics
        peak_density, peak_time, km_range, peak_row = _compute_caption_peak(segment_bins)
        los_grade = _get_los_grade(peak_density)
        
        # Detect waves
        waves_bins = _split_into_waves(segment_bins, config["wave_gap_minutes"])
        
        # Analyze waves
        waves_out = []
        spread_scores = []
        for wdf in waves_bins:
            wave_data, spread = _analyze_wave(wdf)
            waves_out.append(wave_data)
            spread_scores.append(spread)
        
        # Compare waves
        qualitative_note = _compare_waves(waves_out, spread_scores, config)
        if qualitative_note and len(waves_out) >= 2:
            waves_out[1]["qualitative"] = qualitative_note
        
        # Find clearance time
        clearance_time = _find_clearance_time(segment_bins, peak_row, config)
        
        # Build summary
        summary = _build_caption_summary(
            seg_id, label, waves_out, peak_time, km_range, 
            peak_density, los_grade, clearance_time, qualitative_note
        )
        
        return {
            "seg_id": seg_id,
            "label": label,
            "summary": summary,
            "peak": {
                "density_p_m2": peak_density,
                "time": peak_time,
                "km_range": km_range,
                "los": los_grade
            },
            "waves": waves_out,
            "clearance_time": clearance_time,
            "notes": []
        }
        
    except Exception as e:
        print(f"   ⚠️  Could not generate caption for segment {seg_id}: {e}")
        return None



def load_segments_metadata(reports_dir: Optional[Path] = None, run_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load segment metadata from segments.csv.
    
    Issue #616: Get segments_csv_path from analysis.json instead of hardcoded "data/segments.csv"
    
    Args:
        reports_dir: Optional path to reports directory (used to locate analysis.json)
        run_id: Optional run_id (used with get_runflow_root to locate analysis.json)
    
    Returns:
        Dictionary mapping seg_id to metadata
    """
    segments_path = None
    
    # Issue #616: Get segments_csv_path from analysis.json
    if reports_dir is not None:
        try:
            import json
            from app.utils.run_id import get_runflow_root
            runflow_root = get_runflow_root()
            # Navigate from reports_dir back to run_id directory
            # reports_dir: {runflow_root}/{run_id}/{day}/reports_heatmaps or reports_temp
            # Need: {runflow_root}/{run_id}/analysis.json
            run_id_dir = reports_dir.parent.parent  # Go from reports_* -> {day} -> {run_id}
            if run_id_dir.name in ["reports_temp", "reports_heatmaps"]:
                run_id_dir = reports_dir.parent
            analysis_json_path = run_id_dir / "analysis.json"
            if not analysis_json_path.exists() and run_id:
                # Try alternative: use run_id directly
                analysis_json_path = runflow_root / run_id / "analysis.json"
            if analysis_json_path.exists():
                with open(analysis_json_path, 'r') as af:
                    analysis_config = json.load(af)
                    data_files = analysis_config.get("data_files", {})
                    segments_csv_path = data_files.get("segments")
                    if not segments_csv_path:
                        segments_file = analysis_config.get("segments_file")
                        data_dir = analysis_config.get("data_dir", "data")
                        if segments_file:
                            segments_csv_path = f"{data_dir}/{segments_file}"
                    if segments_csv_path:
                        segments_path = Path(segments_csv_path)
        except Exception as e:
            print(f"   ⚠️  Could not load segments_csv_path from analysis.json: {e}")
    elif run_id:
        try:
            import json
            from app.utils.run_id import get_runflow_root
            runflow_root = get_runflow_root()
            analysis_json_path = runflow_root / run_id / "analysis.json"
            if analysis_json_path.exists():
                with open(analysis_json_path, 'r') as af:
                    analysis_config = json.load(af)
                    data_files = analysis_config.get("data_files", {})
                    segments_csv_path = data_files.get("segments")
                    if not segments_csv_path:
                        segments_file = analysis_config.get("segments_file")
                        data_dir = analysis_config.get("data_dir", "data")
                        if segments_file:
                            segments_csv_path = f"{data_dir}/{segments_file}"
                    if segments_csv_path:
                        segments_path = Path(segments_csv_path)
        except Exception as e:
            print(f"   ⚠️  Could not load segments_csv_path from analysis.json: {e}")
    
    # Fallback to hardcoded path only if analysis.json lookup failed (for backward compatibility)
    if not segments_path:
        segments_path = Path("data/segments.csv")
        if not segments_path.exists():
            print(f"   ⚠️  segments.csv not found at {segments_path} and analysis.json lookup failed")
            return {}
    
    segments_meta = {}
    if segments_path.exists():
        try:
            df = pd.read_csv(segments_path)
            for _, row in df.iterrows():
                segments_meta[row.get('seg_id', '')] = {
                    'label': row.get('label', ''),
                    'length_km': row.get('length_km', 0),
                    'width_m': row.get('width_m', 0)
                }
        except Exception as e:
            print(f"   ⚠️  Could not load segments metadata from {segments_path}: {e}")
    
    return segments_meta


def _determine_heatmap_output_dir(run_id: str):
    """Determine output directory for heatmaps based on run ID format."""
    from pathlib import Path
    from app.utils.run_id import is_legacy_date_format
    from app.report_utils import get_runflow_category_path
    
    if is_legacy_date_format(run_id):
        return Path("artifacts") / run_id / "ui" / "heatmaps"
    else:
        return Path(get_runflow_category_path(run_id, "heatmaps"))


def _save_captions_json(run_id: str, captions: dict, storage=None):
    """Save captions.json to appropriate location based on run ID format."""
    from pathlib import Path
    from app.utils.run_id import is_legacy_date_format
    from app.report_utils import get_runflow_file_path
    import json
    
    if is_legacy_date_format(run_id):
        # Legacy mode: Use StorageService
        artifacts_path = f"artifacts/{run_id}/ui/captions.json"
        print(f"   📤 Uploading captions to: gs://run-density-reports/{artifacts_path}")
        storage.save_artifact_json(artifacts_path, captions)
        print(f"   ✅ captions.json: {len(captions)} segments captioned")
    else:
        # Runflow mode: Save locally, GCS upload happens later
        captions_path = Path(get_runflow_file_path(run_id, "ui", "captions.json"))
        captions_path.parent.mkdir(parents=True, exist_ok=True)
        with open(captions_path, 'w') as f:
            json.dump(captions, f, indent=2)
        print(f"   💾 Saved captions locally: {captions_path}")
        print(f"   ✅ captions.json: {len(captions)} segments captioned")



def export_heatmaps_and_captions(
    run_id: str, 
    reports_dir: Path, 
    storage=None
) -> Tuple[int, int]:
    """
    Generate heatmaps and captions for all segments.
    
    Args:
        run_id: Run identifier
        reports_dir: Path to reports/<run_id>/ directory
        storage: Storage abstraction for file operations
        
    Returns:
        Tuple of (heatmaps_generated, captions_generated)
    """
    print(f"\n{'='*60}")
    print(f"Generating Heatmaps & Captions for {run_id}")
    print(f"{'='*60}\n")
    
    # Load LOS colors from rulebook (SSOT)
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
        print(f"   📊 Loaded LOS colors from rulebook: {len(los_colors)} colors")
    except Exception as e:
        print(f"   ⚠️  Could not load LOS colors from rulebook: {e}")
        # Fallback colors (same as rulebook)
        los_colors = {
            "A": "#4CAF50", "B": "#8BC34A", "C": "#FFC107",
            "D": "#FF9800", "E": "#FF5722", "F": "#F44336"
        }
    
    # Load bin data (canonical SSOT)
    bins_df = load_bin_data(reports_dir)
    
    # Load segment metadata (Issue #616: Pass reports_dir and run_id to get segments_csv_path from analysis.json)
    segments_meta = load_segments_metadata(reports_dir=reports_dir, run_id=run_id)
    
    # Get unique segments
    segments = sorted(bins_df['segment_id'].unique())
    print(f"   📊 Found {len(segments)} segments with bin data")
    
    # Generate heatmaps
    print("\n7️⃣  Generating heatmaps...")
    heatmaps_generated = 0
    
    # Create heatmaps directory
    heatmaps_dir = _determine_heatmap_output_dir(run_id)
    heatmaps_dir.mkdir(parents=True, exist_ok=True)
    
    for seg_id in segments:
        try:
            # Create output path in artifacts directory
            heatmap_path = heatmaps_dir / f"{seg_id}.png"
            
            # Generate heatmap
            if generate_segment_heatmap(seg_id, bins_df, los_colors, Path(heatmap_path)):
                heatmaps_generated += 1
                print(f"   ✅ {seg_id}: Heatmap generated")
            else:
                print(f"   ⚠️  {seg_id}: Heatmap generation failed")
                
        except Exception as e:
            print(f"   ⚠️  {seg_id}: Error generating heatmap: {e}")
            continue
    
    # Generate captions
    print("\n8️⃣  Generating captions...")
    captions = {}
    captions_generated = 0
    
    for seg_id in segments:
        try:
            caption = generate_segment_caption(seg_id, bins_df, segments_meta)
            if caption:
                captions[seg_id] = caption
                captions_generated += 1
                print(f"   ✅ {seg_id}: Caption generated")
            else:
                print(f"   ⚠️  {seg_id}: Caption generation failed")
                
        except Exception as e:
            print(f"   ⚠️  {seg_id}: Error generating caption: {e}")
            continue
    
    # Issue #455 Phase 3: Save captions.json locally (GCS upload handled by upload_runflow_to_gcs)
    if captions:
        try:
            _save_captions_json(run_id, captions, storage)
        except Exception as e:
            print(f"   ⚠️  Could not save captions.json: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ Heatmaps & Captions Complete")
    print(f"   📊 Heatmaps: {heatmaps_generated} PNG files generated")
    print(f"   📊 Captions: {captions_generated} segments captioned")
    print(f"{'='*60}\n")
    
    return heatmaps_generated, captions_generated


def main():
    """Main entry point for standalone execution."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m app.core.artifacts.heatmaps <run_id>")
        print("Example: python -m app.core.artifacts.heatmaps 2025-10-24")
        sys.exit(1)
    
    run_id = sys.argv[1]
    reports_dir = Path("reports") / run_id
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    # Create storage abstraction using modern StorageService
    # Issue #466 Step 2: storage_service removed
    
    # Generate heatmaps and captions
    heatmaps_generated, captions_generated = export_heatmaps_and_captions(
        run_id, reports_dir, storage=None
    )
    
    print(f"🎉 Export complete! Generated {heatmaps_generated} heatmaps and {captions_generated} captions.")


if __name__ == "__main__":
    main()
