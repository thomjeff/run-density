"""
Unit Tests for Runflow Map Generation

Tests YAML coherence, map generation, and segment presence validation.

Author: AI Assistant (Cursor)
Issue: #263 - Phase 2: Static Map Generation
"""

from pathlib import Path
import subprocess
import sys
import json
import yaml


def test_yaml_coherence():
    """
    Verify LOS keys are consistent between density_rulebook.yml and reporting.yml.
    
    This ensures:
    1. All LOS bands (A-F) in rulebook have corresponding colors in reporting
    2. No extra or missing LOS keys between the two files
    3. Optional: Warn if reporting.yml has legacy "los" thresholds
    """
    rb = yaml.safe_load(Path("config/density_rulebook.yml").read_text())
    rp = yaml.safe_load(Path("config/reporting.yml").read_text())
    
    # Primary check: LOS bands in rulebook must match colors in reporting
    bands = set(rb["globals"]["los_thresholds"].keys())
    colors = set(rp["reporting"]["los_colors"].keys())
    
    assert bands == colors, (
        f"LOS keys differ between rulebook and reporting palette. "
        f"Rulebook: {sorted(bands)}, Reporting: {sorted(colors)}"
    )
    
    # Optional: Check for legacy LOS thresholds in reporting.yml
    if "los" in rp.get("reporting", {}):
        # Legacy thresholds exist - warn if they differ from rulebook
        legacy_keys = set(rp["reporting"]["los"].keys())
        if legacy_keys != bands:
            print(f"⚠️  Warning: reporting.yml contains legacy 'los' thresholds "
                  f"with different keys. These are IGNORED per SSOT principle.")
    
    print(f"✅ YAML coherence check passed: {len(bands)} LOS bands consistent")


def test_map_generation():
    """
    Verify map.html is generated successfully and contains all segments.
    
    This ensures:
    1. generate_map.py runs without errors
    2. map.html is created
    3. Every segment_id from segment_metrics.json appears in the HTML
    """
    result = subprocess.run(
        [sys.executable, "frontend/map/scripts/generate_map.py"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Map generation failed: {result.stderr}"
    assert Path("frontend/map/output/map.html").exists(), "map.html not created"
    
    # Verify all segments present
    html = Path("frontend/map/output/map.html").read_text()
    data = json.load(open("data/segment_metrics.json"))
    
    for item in data["items"]:
        seg_id = item["segment_id"]
        assert seg_id in html, f"Segment {seg_id} missing from map.html"
    
    print(f"✅ Map generation test passed: {len(data['items'])} segments verified")


def test_png_export():
    """
    Verify PNG export script runs (best-effort, non-fatal).
    
    PNG export is optional in Phase 2. If the script succeeds and creates
    a PNG, verify it's non-empty. If PNG isn't created, that's acceptable.
    """
    r = subprocess.run(
        [sys.executable, "frontend/map/scripts/render_static_png.py"],
        capture_output=True,
        text=True
    )
    
    # PNG may be skipped; if present, assert non-empty
    png = Path("frontend/map/output/map.png")
    if png.exists():
        assert png.stat().st_size > 0, "PNG file is empty"
        print("✅ PNG export test passed: PNG generated")
    else:
        print("ℹ️  PNG export skipped (best-effort feature)")
    
    # Script should exit cleanly even if PNG not generated
    assert r.returncode == 0, f"PNG script failed unexpectedly: {r.stderr}"


def test_yaml_ssot_loading():
    """
    Verify the config loader properly loads YAML SSOT files.
    
    This ensures:
    1. Config loader can import and run
    2. Both YAML files can be loaded
    3. Expected structure is present in both files
    """
    from frontend.common.config import load_rulebook, load_reporting
    
    rb = load_rulebook()
    rp = load_reporting()
    
    # Verify expected structure
    assert "globals" in rb, "density_rulebook.yml missing 'globals' section"
    assert "los_thresholds" in rb["globals"], "density_rulebook.yml missing 'los_thresholds'"
    assert "reporting" in rp, "reporting.yml missing 'reporting' section"
    assert "los_colors" in rp["reporting"], "reporting.yml missing 'los_colors'"
    
    # Verify all LOS bands have required fields
    for los_key, band in rb["globals"]["los_thresholds"].items():
        assert "min" in band, f"LOS {los_key} missing 'min' threshold"
        assert "max" in band, f"LOS {los_key} missing 'max' threshold"
        assert "label" in band, f"LOS {los_key} missing 'label'"
    
    print(f"✅ YAML SSOT loading test passed")

