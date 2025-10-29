"""
Heatmap Generation Module (Issue #365)

Moves heatmap generation from CI pipeline to application layer, enabling on-demand generation.

Architecture:
- Uses StorageService for environment-aware file access (local vs cloud)
- Generates PNG heatmaps for each segment
- Uploads to GCS via StorageService
- Compatible with existing signed URL serving logic

Author: Cursor AI Assistant (per Senior Architect guidance)
Issue: #365
"""

import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless backend for cloud environments
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import logging

from app.common.config import load_rulebook, load_reporting
from app.storage_service import get_storage_service

logger = logging.getLogger(__name__)


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


def load_bin_data(run_id: str) -> pd.DataFrame:
    """
    Load bin data from bins.parquet using StorageService (environment-aware).
    
    Args:
        run_id: Run identifier (e.g., "2025-10-27")
        
    Returns:
        DataFrame with filtered bin-level data (flagged bins only)
    """
    try:
        storage = get_storage_service()
        
        # Use StorageService.read_parquet() for environment-aware access
        # This automatically handles local (./reports/) vs cloud (GCS) paths
        logger.info(f"Loading bins.parquet for run_id: {run_id}")
        bins_df = storage.read_parquet(f"reports/{run_id}/bins.parquet")
        
        if bins_df is None or bins_df.empty:
            raise FileNotFoundError(f"bins.parquet not found or empty for run_id: {run_id}")
        
        logger.info(f"Loaded {len(bins_df)} bins from parquet")
        
        # Filter to flagged bins only (Issue #280 alignment)
        # This creates more whitespace by only showing operationally significant bins
        if 'flag_severity' in bins_df.columns:
            filtered_bins = bins_df[bins_df['flag_severity'] != 'none'].copy()
            logger.info(f"Filtered to {len(filtered_bins)} flagged bins (removed {len(bins_df) - len(filtered_bins)} unflagged)")
            return filtered_bins
        else:
            logger.warning("flag_severity column not found, using all bins (no filtering)")
            return bins_df
            
    except Exception as e:
        logger.error(f"Failed to load bins.parquet: {e}")
        raise


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
            logger.warning(f"No bins found for segment {seg_id}")
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
            logger.warning(f"No valid time/distance data for segment {seg_id}")
            return False
        
        logger.info(f"{seg_id}: Creating {len(times)}×{len(distances)} matrix")
        
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
        
        # Enhanced contrast for better visual separation
        from matplotlib.colors import PowerNorm
        norm = PowerNorm(gamma=0.5, vmin=0, vmax=2.0)
        
        # Use LOS colormap with enhanced contrast for density visualization
        im = ax.imshow(matrix_transposed, cmap=los_cmap, norm=norm, aspect='auto', origin='lower')
        
        # Set labels
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
        
        # Clean up x-axis labels to show HH:MM format
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
            except (ValueError, TypeError) as e:
                logging.warning(f"Failed to parse time string '{time_str}': {e}. Using raw value.")
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
        
        # Add grid
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
        logger.error(f"Could not generate heatmap for segment {seg_id}: {e}")
        return False


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
            logger.warning(f"Could not load segments metadata: {e}")
    
    return segments_meta


def generate_heatmaps_for_run(run_id: str) -> Tuple[int, List[str]]:
    """
    Generate heatmaps for all segments in a run.
    
    Args:
        run_id: Run identifier (e.g., "2025-10-27")
        
    Returns:
        Tuple of (heatmaps_generated, segment_ids) or (0, []) on error
    """
    logger.info(f"Generating heatmaps for run_id: {run_id}")
    
    # Load LOS colors from rulebook (SSOT)
    try:
        reporting_config = load_reporting()
        los_colors = reporting_config.get("reporting", {}).get("los_colors", {})
        logger.info(f"Loaded LOS colors from rulebook: {len(los_colors)} colors")
    except Exception as e:
        logger.warning(f"Could not load LOS colors from rulebook: {e}")
        # Fallback colors (same as rulebook)
        los_colors = {
            "A": "#4CAF50", "B": "#8BC34A", "C": "#FFC107",
            "D": "#FF9800", "E": "#FF5722", "F": "#F44336"
        }
    
    # Load bin data using StorageService (environment-aware)
    try:
        bins_df = load_bin_data(run_id)
    except FileNotFoundError as e:
        logger.error(f"Failed to load bins: {e}")
        return (0, [])
    
    # Load segment metadata
    segments_meta = load_segments_metadata()
    
    # Get unique segments
    segments = sorted(bins_df['segment_id'].unique())
    logger.info(f"Found {len(segments)} segments with bin data")
    
    # Generate heatmaps
    heatmaps_generated = 0
    generated_segments = []
    
    # Create heatmaps directory in artifacts
    heatmaps_dir = Path("artifacts") / run_id / "ui" / "heatmaps"
    heatmaps_dir.mkdir(parents=True, exist_ok=True)
    
    for seg_id in segments:
        try:
            # Create output path in artifacts directory
            heatmap_path = heatmaps_dir / f"{seg_id}.png"
            
            # Generate heatmap
            if generate_segment_heatmap(seg_id, bins_df, los_colors, heatmap_path):
                heatmaps_generated += 1
                generated_segments.append(seg_id)
                logger.info(f"{seg_id}: Heatmap generated")
            else:
                logger.warning(f"{seg_id}: Heatmap generation failed")
                
        except Exception as e:
            logger.error(f"{seg_id}: Error generating heatmap: {e}")
            continue
    
    logger.info(f"Generated {heatmaps_generated} heatmaps for {run_id}")
    return (heatmaps_generated, generated_segments)


def get_heatmap_files(run_id: str) -> List[Path]:
    """
    Get list of generated heatmap PNG files.
    
    Args:
        run_id: Run identifier
        
    Returns:
        List of Path objects for generated PNG files
    """
    local_heatmaps_dir = Path("artifacts") / run_id / "ui" / "heatmaps"
    
    if not local_heatmaps_dir.exists():
        return []
    
    return list(local_heatmaps_dir.glob("*.png"))

