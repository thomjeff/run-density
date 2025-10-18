"""
Runflow Static Map Generator - Phase 2

Generates an interactive HTML map showing course segments colored by LOS,
with flagged segments highlighted and provenance badge embedded.

Uses YAML SSOT for all configuration:
- LOS thresholds from config/density_rulebook.yml
- LOS colors from config/reporting.yml

Author: AI Assistant (Cursor)
Issue: #263 - Phase 2: Static Map Generation
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import geopandas as gpd
import json
import folium
from frontend.common.config import load_rulebook, load_reporting

DATA = {
    "segments": "data/segments.geojson",
    "metrics": "data/segment_metrics.json",
    "flags":   "data/flags.json",
    "meta":    "data/meta.json",
}
OUTPUT_HTML = "frontend/map/output/map.html"
WARNINGS_JSON = "frontend/map/output/map_warnings.json"
PROV_SNIPPET = "frontend/validation/output/provenance_snippet.html"


def infer_los(value: float, los_bands: dict) -> str:
    """
    Infer LOS classification from a density value using rulebook thresholds.
    
    Args:
        value: Density value (p/m²)
        los_bands: LOS threshold bands from density_rulebook.yml
        
    Returns:
        str: LOS letter (A-F)
    """
    for k, band in los_bands.items():
        if band["min"] <= value <= band["max"]:
            return k
    return "F"


def build_map():
    """
    Generate interactive HTML map with LOS coloring and operational intelligence.
    
    Outputs:
        - frontend/map/output/map.html (interactive map)
        - frontend/map/output/map_warnings.json (optional, if drift detected)
    """
    # Ensure output directory exists
    Path("frontend/map/output").mkdir(parents=True, exist_ok=True)
    
    # Load inputs
    print("[Runflow Map] Loading data...")
    segs = gpd.read_file(DATA["segments"])
    metrics = {m["segment_id"]: m for m in json.load(open(DATA["metrics"]))["items"]}
    flags_data = json.load(open(DATA["flags"]))["items"]
    flags = {f["segment_id"]: f for f in flags_data}
    
    # Load configs (SSOT)
    print("[Runflow Map] Loading YAML configuration (SSOT)...")
    rulebook = load_rulebook()
    reporting = load_reporting()
    los_bands = rulebook["globals"]["los_thresholds"]  # A..F: {label,min,max}
    los_colors = reporting["reporting"]["los_colors"]  # A..F → color hex
    
    # Join & style fields
    segs["worst_los"] = segs["segment_id"].map(lambda x: metrics.get(x, {}).get("worst_los"))
    segs["flagged"]   = segs["segment_id"].apply(lambda x: x in flags)
    
    # Basic map
    print("[Runflow Map] Creating base map...")
    m = folium.Map(location=[45.96, -66.65], zoom_start=12, tiles="CartoDB Positron")
    
    # Anti-drift warnings (optional, non-fatal)
    warnings = []
    
    # Add segments to map
    print("[Runflow Map] Adding segments with LOS coloring...")
    for idx, r in segs.iterrows():
        seg_id = r["segment_id"]
        met = metrics.get(seg_id, {})
        worst = met.get("worst_los")
        
        # Optional anti-drift check
        if "peak_density" in met:
            computed = infer_los(met["peak_density"], los_bands)
            if worst and computed and worst != computed:
                warnings.append({
                    "segment_id": seg_id,
                    "reported_los": worst,
                    "computed_los": computed,
                    "peak_density": met["peak_density"]
                })
        
        # Get color for this segment
        color = los_colors.get(worst, "#9e9e9e")
        
        # Build tooltip with all relevant metrics
        flag_info = flags.get(seg_id, {})
        popup_html = f"""
        <div style='font-family: system-ui, sans-serif; min-width: 200px;'>
            <div style='font-weight: 600; font-size: 16px; margin-bottom: 8px;'>{r.get('label','')}</div>
            <table style='font-size: 13px; width: 100%;'>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Segment ID:</b></td><td>{seg_id}</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Length:</b></td><td>{r.get('length_m', 0):.1f} m</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Events:</b></td><td>{', '.join(r.get('events', []))}</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>LOS:</b></td><td><span style='color:{color};font-weight:600;'>{worst if worst else 'N/A'}</span></td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Peak Window:</b></td><td>{met.get('peak_density_window', 'N/A')}</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Co-presence:</b></td><td>{met.get('co_presence_pct', 0):.1f}%</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Overtaking:</b></td><td>{met.get('overtaking_pct', 0):.1f}%</td></tr>
                <tr><td style='padding: 2px 8px 2px 0;'><b>Utilization:</b></td><td>{met.get('utilization_pct', 0):.1f}%</td></tr>
                {f"<tr><td colspan='2' style='padding-top:8px;border-top:1px solid #ddd;'><b>🚩 Flag:</b> {flag_info.get('severity', '')} - {flag_info.get('note', '')}</td></tr>" if seg_id in flags else ""}
            </table>
        </div>
        """
        
        # Add segment to map
        folium.GeoJson(
            r["geometry"].__geo_interface__,
            style_function=lambda x, worst_los=worst, flagged=r["flagged"]: {
                "color": "#000000" if flagged else los_colors.get(worst_los, "#9e9e9e"),
                "weight": 4 if flagged else 2,
                "opacity": 1.0 if flagged else 0.7
            },
            tooltip=popup_html,
        ).add_to(m)
    
    # Dynamic legend from YAML order (A..F)
    print("[Runflow Map] Building dynamic legend from YAML...")
    rows = []
    for k, band in los_bands.items():
        rows.append(
            f"<tr>"
            f"<td><span style='display:inline-block;width:16px;height:16px;background:{los_colors.get(k,'#9e9e9e')};border:1px solid #ccc;border-radius:2px;'></span></td>"
            f"<td style='padding-left:8px;'><b>{k}</b></td>"
            f"<td style='padding-left:8px;color:#666;'>{band.get('label','')}</td>"
            f"</tr>"
        )
    legend_html = (
        "<div style='position:absolute;top:10px;right:10px;background:#fff;padding:12px;border-radius:8px;"
        "box-shadow:0 2px 8px rgba(0,0,0,0.15);font:14px system-ui;z-index:9999;'>"
        "<div style='font-weight:600;margin-bottom:8px;font-size:15px;'>Level of Service</div>"
        "<table style='border-spacing:0;'>" + "".join(rows) + "</table>"
        "<div style='margin-top:10px;padding-top:8px;border-top:1px solid #e0e0e0;font-size:12px;color:#666;'>"
        "🚩 Black outline = Flagged segment"
        "</div>"
        "</div>"
    )
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Provenance badge
    print("[Runflow Map] Embedding provenance badge...")
    if Path(PROV_SNIPPET).exists():
        prov_html = Path(PROV_SNIPPET).read_text()
        prov_div = folium.Element(
            f'<div style="position:absolute;bottom:10px;left:10px;z-index:9999;background:#fff;'
            f'padding:8px 12px;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.15);">{prov_html}</div>'
        )
        m.get_root().html.add_child(prov_div)
    else:
        print(f"[Runflow Map] Warning: Provenance snippet not found at {PROV_SNIPPET}")
    
    # Write outputs
    print("[Runflow Map] Writing outputs...")
    Path(OUTPUT_HTML).write_text(m.get_root().render())
    print(f"[Runflow Map] ✅ Saved → {OUTPUT_HTML}")
    
    if warnings:
        Path(WARNINGS_JSON).write_text(json.dumps(warnings, indent=2))
        print(f"[Runflow Map] ⚠️  LOS drift warnings → {WARNINGS_JSON} ({len(warnings)} segments)")
    
    print(f"[Runflow Map] Complete! Generated map with {len(segs)} segments.")


if __name__ == "__main__":
    build_map()

