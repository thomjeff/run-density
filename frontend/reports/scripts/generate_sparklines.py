"""
Runflow Sparkline Generator

Generates density-over-time sparklines as SVG for segments with time-series data.

Author: AI Assistant (Cursor)
Issue: #265 - Phase 4: Report Integration & Storytelling
"""

from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SPARK_DIR = Path("frontend/reports/output/sparklines")


def save_sparkline(values, out_path):
    """
    Generate a sparkline SVG from density time-series values.
    
    Args:
        values: List of density values over time
        out_path: Path to save SVG file
    """
    fig, ax = plt.subplots(figsize=(3.0, 0.9), dpi=96)  # ~300x90
    ax.plot(range(len(values)), values, linewidth=1.5)
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    SPARK_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def build_sparklines():
    """
    Generate sparklines for segments with time-series data.
    
    Expects optional per-segment density time series:
    data/segment_series.json: {"S001": {"density": [0.5, 0.7, 0.9, ...]}, ...}
    
    Returns:
        list: Paths to generated SVG files
    """
    series_path = Path("data/segment_series.json")
    generated = []
    
    if not series_path.exists():
        print("[Sparklines] No segment_series.json found - skipping sparkline generation")
        return generated
    
    print("[Sparklines] Loading time-series data...")
    data = json.loads(series_path.read_text())
    
    print(f"[Sparklines] Generating sparklines for {len(data)} segments...")
    for seg_id, payload in data.items():
        vals = payload.get("density", [])
        if not vals:
            continue
        out = SPARK_DIR / f"{seg_id}.svg"
        save_sparkline(vals, out)
        generated.append(str(out))
    
    print(f"[Sparklines] ✅ Generated {len(generated)} sparklines")
    return generated


if __name__ == "__main__":
    build_sparklines()

