"""
Runflow Dashboard Generator - Phase 3

Generates a printable HTML dashboard with key metrics, charts, and risk segments.
Uses YAML SSOT for all configuration (LOS thresholds, colors, labels).

Author: AI Assistant (Cursor)
Issue: #264 - Phase 3: Dashboard Summary View
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import json
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from frontend.common.config import load_rulebook, load_reporting
from frontend.dashboard.scripts.charts import save_bar_svg, save_timeline_svg

DATA = {
    "metrics": "data/segment_metrics.json",
    "flags":   "data/flags.json",
    "meta":    "data/meta.json",
    "participants": "data/participants.json"  # optional
}
TEMPLATES = "frontend/dashboard/templates"
OUT_HTML = "frontend/dashboard/output/dashboard.html"
PROV_SNIPPET = "frontend/validation/output/provenance_snippet.html"


def _read_json(path):
    """Load and parse a JSON file."""
    return json.loads(Path(path).read_text())


def minutes_from_hhmm(s):
    """Convert HH:MM string to minutes from midnight."""
    hh, mm = s.split(":")
    return int(hh)*60 + int(mm)


def main():
    """
    Generate the dashboard HTML with tiles, charts, and Top-10 risk segments.
    
    Outputs:
        - frontend/dashboard/output/dashboard.html
        - frontend/dashboard/output/charts/los_distribution.svg
        - frontend/dashboard/output/charts/start_timeline.svg
    """
    # Ensure output directories exist
    Path("frontend/dashboard/output/charts").mkdir(parents=True, exist_ok=True)
    
    print("[Runflow Dashboard] Loading data...")
    
    # Load inputs
    metrics = _read_json(DATA["metrics"])["items"]
    flags   = _read_json(DATA["flags"])["items"]
    meta    = _read_json(DATA["meta"])
    
    # Optional participants data
    if Path(DATA["participants"]).exists():
        participants = _read_json(DATA["participants"])
    else:
        participants = {
            "total": None,
            "full": None,
            "half": None,
            "tenk": None
        }
    
    print("[Runflow Dashboard] Loading YAML configuration (SSOT)...")
    
    # Load SSOT configuration
    rb = load_rulebook()
    rp = load_reporting()
    los_bands = rb["globals"]["los_thresholds"]   # A..F: {min, max, label}
    los_colors = rp["reporting"]["los_colors"]    # A..F → #hex
    los_order = list(los_bands.keys())
    los_labels = {k: v.get("label", k) for k, v in los_bands.items()}
    
    print("[Runflow Dashboard] Computing aggregates...")
    
    # Aggregates
    dfm = pd.DataFrame(metrics)
    los_counts = dfm["worst_los"].value_counts().reindex(los_order, fill_value=0).to_dict()
    
    # Flag counts
    df_flags = pd.DataFrame(flags)
    flags_sum = {"copres": 0, "overtake": 0}
    if not df_flags.empty:
        flags_sum["copres"]   = (df_flags["flag_type"]=="co_presence").sum()
        flags_sum["overtake"] = (df_flags["flag_type"]=="overtaking").sum()
    
    # Top 10 by risk score (utilization * (co_presence + overtaking))
    dfm["risk_score"] = dfm["utilization_pct"] * (dfm["co_presence_pct"] + dfm["overtaking_pct"])
    top10 = dfm.nlargest(10, "risk_score", keep="all")[["segment_id","worst_los"]].to_dict(orient="records")
    
    # Attach labels if available (from segments.geojson)
    if Path("data/segments.geojson").exists():
        segs_data = _read_json("data/segments.geojson")
        seg_labels = {f["properties"]["segment_id"]: f["properties"]["label"] 
                     for f in segs_data["features"]}
    else:
        seg_labels = {}
    
    for r in top10:
        r["label"] = seg_labels.get(r["segment_id"], "")
        # Mark if flagged
        r["flag"] = "⚑" if ((not df_flags.empty) and (r["segment_id"] in set(df_flags["segment_id"]))) else ""
    
    print("[Runflow Dashboard] Generating charts...")
    
    # Generate charts
    save_bar_svg(
        los_order,
        [los_counts[k] for k in los_order],
        "frontend/dashboard/output/charts/los_distribution.svg"
    )
    
    # Start times (from meta or fallback)
    starts = {
        "full": meta.get("start_times", {}).get("full", "07:00"),
        "tenk": meta.get("start_times", {}).get("tenk", "07:20"),
        "half": meta.get("start_times", {}).get("half", "07:40"),
    }
    
    save_timeline_svg(
        ["Full", "10K", "Half"],
        [minutes_from_hhmm(starts["full"]), 
         minutes_from_hhmm(starts["tenk"]), 
         minutes_from_hhmm(starts["half"])],
        "frontend/dashboard/output/charts/start_timeline.svg"
    )
    
    print("[Runflow Dashboard] Rendering HTML...")
    
    # Render HTML
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape()
    )
    tpl = env.get_template("dashboard.j2")
    
    # Load provenance snippet
    provenance_html = ""
    if Path(PROV_SNIPPET).exists():
        provenance_html = Path(PROV_SNIPPET).read_text()
    else:
        print(f"[Runflow Dashboard] Warning: Provenance snippet not found at {PROV_SNIPPET}")
    
    # Render template
    html = tpl.render(
        participants=participants,
        starts={"full": starts["full"], "tenk": starts["tenk"], "half": starts["half"]},
        flags=flags_sum,
        los_order=los_order,
        los_labels=los_labels,
        los_colors=los_colors,
        los_counts=los_counts,
        top10=top10,
        provenance_html=provenance_html
    )
    
    # Write output
    Path(OUT_HTML).write_text(html)
    print(f"[Runflow Dashboard] ✅ Saved → {OUT_HTML}")
    print(f"[Runflow Dashboard] Complete! Dashboard with {len(top10)} risk segments.")


if __name__ == "__main__":
    main()

