"""
Runflow Density Report Builder - Phase 4

Orchestrates the complete report build pipeline:
1. Generate mini-maps for all segments
2. Generate sparklines (if time-series data available)
3. Convert density.md to HTML
4. Replace tokens with visual/link elements
5. Wrap in template with provenance

Author: AI Assistant (Cursor)
Issue: #265 - Phase 4: Report Integration & Storytelling
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from markdown import markdown
from jinja2 import Environment, FileSystemLoader
from frontend.reports.scripts.generate_minimaps import build_minimaps
from frontend.reports.scripts.generate_sparklines import build_sparklines
from frontend.reports.scripts.html_postprocess import replace_tokens

MD_SRC = Path("reports/density.md")
OUT_DIR = Path("frontend/reports/output")
OUT_HTML = OUT_DIR / "density.html"
PROV = Path("frontend/validation/output/provenance_snippet.html")


def main():
    """
    Build the complete density report with embedded visuals and links.
    
    Pipeline:
    1. Generate mini-maps (SSOT colors)
    2. Generate sparklines (optional time-series)
    3. Convert markdown to HTML
    4. Replace tokens ({{mini_map:S001}}, etc.)
    5. Wrap in template with provenance
    
    Outputs:
        - frontend/reports/output/density.html
        - frontend/reports/output/mini_maps/*.png
        - frontend/reports/output/sparklines/*.svg (if data available)
    """
    print("[Runflow Reports] Starting report build pipeline...")
    
    # Ensure output directory exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Generate mini-maps
    print("[Runflow Reports] Step 1: Generating mini-maps...")
    build_minimaps()
    
    # Step 2: Generate sparklines (optional)
    print("[Runflow Reports] Step 2: Generating sparklines...")
    build_sparklines()
    
    # Step 3: Convert markdown to HTML
    print("[Runflow Reports] Step 3: Converting markdown to HTML...")
    if MD_SRC.exists():
        md_content = MD_SRC.read_text()
    else:
        print(f"[Runflow Reports] Warning: {MD_SRC} not found, using placeholder")
        md_content = """# Density Report

## Overview
This is a placeholder density report for testing.

## Flagged Segments

### Segment S001
**LOS:** C (Moderate)
**Flag:** Co-presence warning

{{mini_map:S001}}
{{sparkline:S001}}
{{open_map:S001}}
"""
    
    html_raw = markdown(md_content, extensions=["tables", "fenced_code"])
    
    # Step 4: Token replacement
    print("[Runflow Reports] Step 4: Replacing tokens...")
    html_aug = replace_tokens(html_raw)
    
    # Step 5: Wrap with template and provenance
    print("[Runflow Reports] Step 5: Wrapping with template and provenance...")
    env = Environment(loader=FileSystemLoader("frontend/reports/templates"))
    tpl = env.get_template("density_base.j2")
    
    # Load provenance snippet
    if PROV.exists():
        prov_html = PROV.read_text()
    else:
        print(f"[Runflow Reports] Warning: Provenance snippet not found at {PROV}")
        prov_html = ""
    
    # Render final HTML
    final = tpl.render(content=html_aug, provenance_html=prov_html)
    
    # Write output
    OUT_HTML.write_text(final)
    print(f"[Runflow Reports] ✅ Saved → {OUT_HTML}")
    print("[Runflow Reports] Complete! Report with embedded visuals and provenance.")


if __name__ == "__main__":
    main()

