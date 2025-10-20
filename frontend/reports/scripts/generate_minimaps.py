"""
Runflow Mini-Map Generator

Generates small PNG mini-maps for each segment, colored by LOS using SSOT colors.

Author: AI Assistant (Cursor)
Issue: #265 - Phase 4: Report Integration & Storytelling
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
from frontend.common.config import load_reporting

MINI_DIR = Path("frontend/reports/output/mini_maps")


def mini_for_segment(geo_row, color, out_path):
    """
    Generate a mini-map PNG for a single segment.
    
    Args:
        geo_row: GeoDataFrame row with geometry
        color: Hex color string for the segment line
        out_path: Path to save PNG file
    """
    fig, ax = plt.subplots(figsize=(2.2, 1.3), dpi=96)  # ~200x120
    gpd.GeoSeries([geo_row.geometry]).plot(ax=ax, linewidth=2, color=color)
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    MINI_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def build_minimaps():
    """
    Generate mini-maps for all segments using SSOT LOS colors.
    
    Returns:
        list: Paths to generated PNG files
    """
    print("[Mini-Maps] Loading segments and metrics...")
    segs = gpd.read_file("data/segments.geojson")
    metrics = {m["segment_id"]: m for m in json.load(open("data/segment_metrics.json"))["items"]}
    colors = load_reporting()["reporting"]["los_colors"]
    
    print(f"[Mini-Maps] Generating mini-maps for {len(segs)} segments...")
    generated = []
    for _, row in segs.iterrows():
        seg_id = row["segment_id"]
        worst = metrics.get(seg_id, {}).get("worst_los")
        color = colors.get(worst, "#999999")
        out = MINI_DIR / f"{seg_id}.png"
        mini_for_segment(row, color, out)
        generated.append(str(out))
    
    print(f"[Mini-Maps] ✅ Generated {len(generated)} mini-maps")
    return generated


if __name__ == "__main__":
    build_minimaps()

