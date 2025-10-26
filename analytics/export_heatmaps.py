"""
Density Heatmaps & Captions Generator (Issue #280)

Generates per-segment 2D heatmap PNGs and automated captions directly from bin.parquet,
using the same SSOT LOS rules as other analytics modules.

Architecture:
- Input: bin.parquet (canonical SSOT from density.py)
- Output: heatmaps/*.png + captions.json
- Colors: density_rulebook.yml LOS palette
- Storage: app/storage.py abstraction

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
from app.storage import Storage


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
    Load bin data from bin.parquet (canonical SSOT) without filtering.
    
    Args:
        reports_dir: Path to reports/<run_id>/ directory
        
    Returns:
        DataFrame with all bin-level data (no filtering applied)
    """
    bins_path = reports_dir / "bins.parquet"
    
    if not bins_path.exists():
        raise FileNotFoundError(f"bins.parquet not found at {bins_path}")
    
    print(f"   📊 Loading bin data from {bins_path}")
    df = pd.read_parquet(bins_path)
    print(f"   📊 Loaded {len(df)} bins from parquet")
    
    # Issue #355: Show ALL bins in heatmaps (not just flagged bins)
    # This restores the original behavior where all 19,440 bins are displayed
    # This reduces whitespace and shows the full data distribution
    print(f"   📊 Using all {len(df)} bins for heatmap generation (no filtering)")
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
        # Filter bins for this segment
        segment_bins = bins_df[bins_df['segment_id'] == seg_id].copy()
        
        if len(segment_bins) == 0:
            return None
        
        # Get segment metadata
        meta = segments_meta.get(seg_id, {})
        label = meta.get('label', seg_id)
        
        # Calculate peak density
        densities = [float(row.get("density", 0)) for _, row in segment_bins.iterrows()]
        peak_density = max(densities) if densities else 0.0
        
        # Find peak time and location
        peak_bin = segment_bins.loc[segment_bins['density'].idxmax()]
        peak_time = peak_bin.get("t_start", "")
        peak_km = peak_bin.get("start_km", 0)
        
        # Determine LOS
        if peak_density <= 0.36:
            los = "A"
        elif peak_density <= 0.54:
            los = "B"
        elif peak_density <= 0.72:
            los = "C"
        elif peak_density <= 1.08:
            los = "D"
        elif peak_density <= 1.63:
            los = "E"
        else:
            los = "F"
        
        # Generate summary
        summary = f"Segment {seg_id} — {label}. Peak density of {peak_density:.2f} p/m² ({los}) occurs at {peak_time} around {peak_km:.1f} km."
        
        return {
            "seg_id": seg_id,
            "label": label,
            "summary": summary,
            "peak": {
                "density_p_m2": peak_density,
                "time": peak_time,
                "km_range": f"{peak_km:.1f} km",
                "los": los
            },
            "waves": [],  # Simplified for now
            "clearance_time": None,  # Simplified for now
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
    storage: Storage
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
    
    # Save captions.json in artifacts directory
    if captions:
        captions_path = Path("artifacts") / run_id / "ui" / "captions.json"
        try:
            with open(captions_path, 'w') as f:
                json.dump(captions, f, indent=2)
            print(f"   ✅ captions.json: {len(captions)} segments captioned")
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
        print("Usage: python export_heatmaps.py <run_id>")
        print("Example: python export_heatmaps.py 2025-10-24")
        sys.exit(1)
    
    run_id = sys.argv[1]
    reports_dir = Path("reports") / run_id
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    # Create storage abstraction
    storage = Storage(mode="local")
    
    # Generate heatmaps and captions
    heatmaps_generated, captions_generated = export_heatmaps_and_captions(
        run_id, reports_dir, storage
    )
    
    print(f"🎉 Export complete! Generated {heatmaps_generated} heatmaps and {captions_generated} captions.")


if __name__ == "__main__":
    main()
