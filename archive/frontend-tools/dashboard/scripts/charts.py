"""
Runflow Dashboard Chart Generation

Generates lightweight SVG charts for dashboard using Matplotlib.
No explicit styles/colors - uses default Matplotlib styling.

Author: AI Assistant (Cursor)
Issue: #264 - Phase 3: Dashboard Summary View
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save_bar_svg(labels, values, out_path):
    """
    Generate a simple bar chart as SVG.
    
    Args:
        labels: List of x-axis labels (LOS letters: A-F)
        values: List of corresponding values (segment counts)
        out_path: Output path for SVG file
    """
    fig, ax = plt.subplots(figsize=(4.0, 2.2), dpi=96)
    ax.bar(labels, values)
    ax.set_xlabel("")
    ax.set_ylabel("Segments")
    ax.grid(axis='y', linestyle=':', linewidth=0.5, alpha=0.7)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg")
    plt.close(fig)


def save_timeline_svg(labels, times_min, out_path):
    """
    Generate a simple timeline scatter plot as SVG.
    
    Args:
        labels: Event names ["Full", "10K", "Half"]
        times_min: Times in minutes from midnight [450, 465, 480]
        out_path: Output path for SVG file
    """
    fig, ax = plt.subplots(figsize=(4.0, 2.2), dpi=96)
    ax.scatter(times_min, [1]*len(times_min), s=80, alpha=0.7)
    for t, lbl in zip(times_min, labels):
        ax.text(t, 1.05, lbl, rotation=0, ha="center", va="bottom", fontsize=10, fontweight='bold')
    ax.set_yticks([])
    ax.set_xlabel("Minutes after 00:00")
    ax.set_ylim(0.9, 1.15)
    ax.grid(axis='x', linestyle=':', linewidth=0.5, alpha=0.7)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg")
    plt.close(fig)

