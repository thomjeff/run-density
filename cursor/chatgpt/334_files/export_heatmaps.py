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
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.common.config import load_rulebook, load_reporting
from app.storage_service import get_storage_service


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
        reports_dir: Path to reports/<run_id>/ directory
        
    Returns:
        DataFrame with filtered bin-level data (flagged bins only)
    """
    bins_path = reports_dir / "bins.parquet"
    
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


def generate_segment_heatmap(
    seg_id: str, 
    bins_df: pd.DataFrame, 
    los_colors: Dict[str, str],
    output_path: Path
) -> bool:
    """
    Generate heatmap PNG for a single segment.
    
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
        times = []
        for _, row in segment_bins.iterrows():
            if "t_start" in row:
                times.append(row.get("t_start", ""))
            elif "start_time" in row:
                times.append(row.get("start_time", ""))
        
        distances = sorted(set(segment_bins.get("start_km", 0)))
        times = sorted(set(times))
        
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
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Transpose matrix so X=time, Y=distance (proper spatiotemporal visualization)
        matrix_transposed = matrix.T
        
        # Create LOS-compliant colormap from rulebook
        los_cmap = create_los_colormap(los_colors)
        
        # Set NaN values to white (no data) to match Epic #279 mock-ups
        los_cmap.set_bad(color="white")
        
        # Enhanced contrast for better visual separation (Epic #279 mock-ups)
        from matplotlib.colors import PowerNorm
        norm = PowerNorm(gamma=0.5, vmin=0, vmax=2.0)
        
        # Use LOS colormap with enhanced contrast for density visualization
        im = ax.imshow(matrix_transposed, cmap=los_cmap, norm=norm, aspect='auto', origin='lower')
        
        # Set labels to match Epic #279 mock-ups
        ax.set_xlabel('Time of day (HH:MM)')
        ax.set_ylabel('Distance along segment (km)')
        
        # Create descriptive title based on segment
        segment_labels = {
            'A1': 'Start Corral',
            'B1': '10K Turn',
            'B2': '10K Turn to Friel', 
            'D1': 'Full Turn Blake (Out)',
            'F1': 'Friel to Station Rd.',
            'H1': 'Trail/Aberdeen to/from Station Rd',
            'I1': 'Station Rd to Bridge/Mill',
            'J1': 'Bridge/Mill to Half Turn (Outbound)',
            'J4': 'Half Turn to Bridge/Mill',
            'J5': 'Half Turn to Bridge/Mill (Slow Half)',
            'K1': 'Bridge/Mill to Station Rd',
            'L1': 'Trail/Aberdeen to/from Station Rd',
            'M1': 'Trail/Aberdeen to Finish (Full to Loop)'
        }
        
        segment_label = segment_labels.get(seg_id, f'Segment {seg_id}')
        ax.set_title(f'Segment {seg_id} — {segment_label}: Density Through Space & Time')
        
        # Set ticks with proper formatting (transposed)
        ax.set_xticks(range(len(times)))
        ax.set_xticklabels(times, rotation=45, ha='right')
        ax.set_yticks(range(len(distances)))
        ax.set_yticklabels([f'{d:.1f}' for d in distances])
        
        # Clean up x-axis labels to show HH:MM format (Epic #279 mock-ups)
        # Convert timestamps to clean HH:MM format
        clean_times = []
        for time_str in times:
            try:
                # Handle different timestamp formats
                if 'T' in time_str:
                    # ISO format: 2025-10-24T07:42:00Z
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    clean_time = dt.strftime('%H:%M')
                elif ':' in time_str and len(time_str) > 5:
                    # Extract time part: 07:42:00
                    time_part = time_str.split(' ')[-1] if ' ' in time_str else time_str
                    if len(time_part) >= 5:
                        clean_time = time_part[:5]  # HH:MM
                    else:
                        clean_time = time_str
                else:
                    clean_time = time_str
                clean_times.append(clean_time)
            except:
                clean_times.append(time_str)
        
        # Set clean time labels with smart spacing
        n_ticks = min(8, len(times))  # Max 8 ticks to avoid clutter
        if len(times) > 1:
            step = max(1, len(times) // n_ticks)
            tick_indices = range(0, len(times), step)
            ax.set_xticks(tick_indices)
            ax.set_xticklabels([clean_times[i] for i in tick_indices], rotation=30, ha='right')
        else:
            ax.set_xticks([0])
            ax.set_xticklabels(clean_times, rotation=30, ha='right')
        
        # Add grid like in mock-ups
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        
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
        # Load captioning thresholds from density_rulebook.yml (globals.captioning)
        try:
            rulebook = load_rulebook()
            caption_cfg = rulebook.get("globals", {}).get("captioning", {})
        except Exception:
            caption_cfg = {}
        wave_gap_minutes = float(caption_cfg.get("wave_gap_minutes", 5))
        clearance_threshold = float(caption_cfg.get("clearance_threshold_p_m2", 0.10))
        clearance_sustain = int(caption_cfg.get("clearance_sustain_minutes", 6))
        similarity_pct = float(caption_cfg.get("similarity_pct", 0.10))
        spread_pct = float(caption_cfg.get("spread_pct", 0.20))

        # Filter bins for this segment
        segment_bins = bins_df[bins_df['segment_id'] == seg_id].copy()
        
        if len(segment_bins) == 0:
            return None
        
        # Get segment metadata
        meta = segments_meta.get(seg_id, {})
        label = meta.get('label', seg_id)

        # Normalize/parse times
        # Ensure expected columns exist
        required_cols = ["t_start", "t_end", "density", "start_km", "end_km"]
        for col in required_cols:
            if col not in segment_bins.columns:
                # Attempt aliases
                alias_map = {
                    "t_start": "start_time",
                    "t_end": "end_time",
                    "density": "density",
                    "start_km": "from_km",
                    "end_km": "to_km"
                }
                if alias_map.get(col) in segment_bins.columns:
                    segment_bins[col] = segment_bins[alias_map[col]]

        segment_bins = segment_bins.dropna(subset=["t_start", "t_end", "density", "start_km", "end_km"]).copy()
        if len(segment_bins) == 0:
            return None

        # Parse to pandas timestamps and sort
        segment_bins["t_start"] = pd.to_datetime(segment_bins["t_start"], errors="coerce")
        segment_bins["t_end"] = pd.to_datetime(segment_bins["t_end"], errors="coerce")
        segment_bins = segment_bins.dropna(subset=["t_start", "t_end"]).sort_values("t_start")

        # Compute global peak
        peak_idx = segment_bins["density"].idxmax()
        peak_row = segment_bins.loc[peak_idx]
        peak_density = float(peak_row["density"]) if pd.notna(peak_row["density"]) else 0.0
        peak_time = peak_row["t_end"].strftime("%H:%M") if pd.notna(peak_row["t_end"]) else ""
        km_range = f"{float(peak_row['start_km']):.1f}–{float(peak_row['end_km']):.1f} km"

        # Determine LOS using rulebook
        try:
            los_thresholds = load_rulebook().get("globals", {}).get("los_thresholds", {})
        except Exception:
            los_thresholds = {}
        # Simple classifier using local helper from export_frontend_artifacts if available is not imported here;
        # replicate minimal logic: find first grade whose max exceeds density
        los_grade = "F"
        if isinstance(los_thresholds, dict) and los_thresholds:
            # Expect dict of grades with min/max
            for grade, rng in los_thresholds.items():
                try:
                    min_v = float(rng.get("min", 0.0))
                    max_v = float(rng.get("max", float("inf")))
                    if min_v <= peak_density < max_v:
                        los_grade = grade
                        break
                except Exception:
                    continue

        # Wave detection per Issue #280: split when gap (next.t_start - prev.t_end) > wave_gap_minutes
        waves_bins: List[pd.DataFrame] = []
        current: List[int] = []
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

        waves_out: List[Dict[str, Any]] = []
        spread_scores: List[float] = []
        for wdf in waves_bins:
            w_peak_idx = wdf["density"].idxmax()
            w_peak = wdf.loc[w_peak_idx]
            w_peak_density = float(w_peak["density"]) if pd.notna(w_peak["density"]) else 0.0
            w_start = pd.to_datetime(wdf["t_start"].min()).strftime("%H:%M")
            w_end = pd.to_datetime(wdf["t_end"].max()).strftime("%H:%M")
            w_km_range = f"{float(w_peak['start_km']):.1f}–{float(w_peak['end_km']):.1f} km"
            # spread score = unique minutes × unique distance bins
            unique_minutes = wdf["t_start"].dt.floor("min").nunique()
            unique_dist = pd.Index(wdf["start_km"]).nunique()
            spread = float(unique_minutes * unique_dist)
            spread_scores.append(spread)
            waves_out.append({
                "start_time": w_start,
                "end_time": w_end,
                "peak_density_p_m2": w_peak_density,
                "peak_time": pd.to_datetime(w_peak["t_end"]).strftime("%H:%M") if pd.notna(w_peak["t_end"]) else "",
                "peak_km_range": w_km_range,
                "bins_count": int(len(wdf)),
            })

        # Qualitative comparison between first two waves, if available
        qualitative_note = None
        if len(waves_out) >= 2:
            p0 = waves_out[0]["peak_density_p_m2"]
            p1 = waves_out[1]["peak_density_p_m2"]
            rel = (p1 - p0) / p0 if p0 > 0 else 0.0
            if abs(rel) <= similarity_pct:
                rel_txt = "similar"
            elif rel < 0:
                rel_txt = "lighter"
            else:
                rel_txt = "heavier"
            s0 = spread_scores[0]
            s1 = spread_scores[1]
            spread_rel = (s1 - s0) / s0 if s0 > 0 else 0.0
            if spread_rel >= spread_pct:
                spread_txt = "more dispersed"
            elif spread_rel <= -spread_pct:
                spread_txt = "more concentrated"
            else:
                spread_txt = "similar spread"
            qualitative_note = {"relative_peak": rel_txt, "spread": spread_txt}
            waves_out[1]["qualitative"] = qualitative_note

        # Clearance detection: 1-minute series, find earliest T with sustained <= threshold
        # Build per-minute max density across km
        minute_index = pd.date_range(
            start=segment_bins["t_start"].min().floor("min"),
            end=segment_bins["t_end"].max().ceil("min"),
            freq="1min"
        )
        per_min = pd.Series(index=minute_index, dtype=float)
        for _, row in segment_bins.iterrows():
            ts = pd.date_range(start=row["t_start"].floor("min"), end=row["t_end"].ceil("min"), freq="1min")
            # take max across overlaps
            per_min.loc[ts] = np.fmax(per_min.loc[ts].to_numpy(dtype=float, copy=True), float(row["density"])) if per_min.loc[ts].notna().any() else float(row["density"])
        clearance_time = None
        if len(per_min) > 0:
            # find window after peak time
            start_idx = per_min.index.get_indexer([pd.to_datetime(peak_row["t_end"]).floor("min")], method="nearest")[0]
            series_after = per_min.iloc[start_idx:]
            window = clearance_sustain
            for i in range(0, max(0, len(series_after) - window)):
                window_slice = series_after.iloc[i:i+window]
                if window_slice.isna().any():
                    continue  # unknown minutes cannot prove clearance
                if (window_slice <= clearance_threshold).all():
                    clearance_time = window_slice.index[0].strftime("%H:%M")
                    break

        # Compose summary text
        if len(waves_out) <= 1:
            summary = (
                f"Segment {seg_id} — {label}. A single density wave passes, peaking near {peak_time} "
                f"around {km_range} at {peak_density:.2f} p/m² ({los_grade}). "
                f"{"Clears by " + clearance_time if clearance_time else "Does not fully clear in the observed window"}."
            )
        else:
            wave1 = waves_out[0]
            wave2 = waves_out[1]
            adj = qualitative_note["relative_peak"] if qualitative_note else "similar"
            spread_txt = qualitative_note["spread"] if qualitative_note else "similar spread"
            summary = (
                f"Segment {seg_id} — {label}. Two distinct waves are visible. "
                f"The first ({wave1['start_time']}–{wave1['end_time']}) peaks at ~{wave1['peak_density_p_m2']:.2f} p/m². "
                f"A subsequent wave ({wave2['start_time']}–{wave2['end_time']}) is {adj} and {spread_txt}. "
                f"Overall peak near {peak_time} around {km_range} at {peak_density:.2f} p/m² ({los_grade}). "
                f"{"Clears by " + clearance_time if clearance_time else "Remains active in window"}."
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


def load_segments_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Load segment metadata from segments.csv.
    
    Returns:
        Dictionary mapping seg_id to metadata
    """
    segments_path = Path("data/segments.csv")
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
            print(f"   ⚠️  Could not load segments metadata: {e}")
    
    return segments_meta


def export_heatmaps_and_captions(
    run_id: str, 
    reports_dir: Path, 
    storage
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
    
    # Load segment metadata
    segments_meta = load_segments_metadata()
    
    # Get unique segments
    segments = sorted(bins_df['segment_id'].unique())
    print(f"   📊 Found {len(segments)} segments with bin data")
    
    # Generate heatmaps
    print("\n7️⃣  Generating heatmaps...")
    heatmaps_generated = 0
    
    # Create heatmaps directory in artifacts
    heatmaps_dir = Path("artifacts") / run_id / "ui" / "heatmaps"
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
    
    # Save captions.json using StorageService to support Cloud (GCS) and Local
    if captions:
        try:
            artifacts_path = f"artifacts/{run_id}/ui/captions.json"
            storage.save_artifact_json(artifacts_path, captions)
            print(f"   ✅ captions.json: {len(captions)} segments captioned")
        except Exception as e:
            print(f"   ⚠️  Could not save captions.json via StorageService: {e}")
    
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
        print("Usage: python export_heatmaps.py <run_id>")
        print("Example: python export_heatmaps.py 2025-10-24")
        sys.exit(1)
    
    run_id = sys.argv[1]
    reports_dir = Path("reports") / run_id
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    # Create storage abstraction using modern StorageService
    storage = get_storage_service()
    
    # Generate heatmaps and captions
    heatmaps_generated, captions_generated = export_heatmaps_and_captions(
        run_id, reports_dir, storage
    )
    
    print(f"🎉 Export complete! Generated {heatmaps_generated} heatmaps and {captions_generated} captions.")


if __name__ == "__main__":
    main()

// ... existing code ...

