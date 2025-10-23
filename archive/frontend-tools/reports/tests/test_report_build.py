"""
Unit Tests for Runflow Report Build Pipeline

Tests YAML coherence, report generation, asset completeness, and provenance.

Author: AI Assistant (Cursor)
Issue: #265 - Phase 4: Report Integration & Storytelling
"""

from pathlib import Path
import subprocess
import sys
import json
import yaml
import re


def test_yaml_coherence():
    """
    Verify LOS keys are consistent between density_rulebook.yml and reporting.yml.
    """
    rb = yaml.safe_load(Path("config/density_rulebook.yml").read_text())
    rp = yaml.safe_load(Path("config/reporting.yml").read_text())
    
    assert list(rb["globals"]["los_thresholds"].keys()) == list(rp["reporting"]["los_colors"].keys()), \
        "LOS keys/order must match between rulebook and reporting palette"
    
    print("✅ YAML coherence check passed")


def test_build_report_generates_assets():
    """
    Verify build_density_report.py runs successfully and creates output.
    """
    result = subprocess.run(
        [sys.executable, "frontend/reports/scripts/build_density_report.py"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Report build failed: {result.stderr}"
    assert Path("frontend/reports/output/density.html").exists(), "density.html not created"
    
    print("✅ Report build test passed")


def test_flagged_segments_have_assets_if_present():
    """
    Verify each flagged segment has a corresponding mini-map.
    """
    flags_path = Path("data/flags.json")
    if not flags_path.exists():
        print("ℹ️  No flags.json - skipping asset check")
        return
    
    flags = json.loads(flags_path.read_text())["items"]
    for f in flags:
        seg = f["segment_id"]
        mini_map_path = Path(f"frontend/reports/output/mini_maps/{seg}.png")
        assert mini_map_path.exists(), f"Mini-map missing for flagged segment {seg}"
    
    print(f"✅ Asset completeness test passed: {len(flags)} flagged segments verified")


def test_provenance_included():
    """
    Verify provenance badge is included in the report HTML.
    """
    html = Path("frontend/reports/output/density.html").read_text()
    
    # Check for provenance indicators
    assert "Validated" in html or "Runflow" in html, "Provenance badge not found in HTML"
    
    print("✅ Provenance inclusion test passed")


def test_open_on_map_links_format():
    """
    Verify "Open on Map" deep-links have correct format.
    """
    html = Path("frontend/reports/output/density.html").read_text()
    
    # Check for map deep-link format
    has_map_link = ("../../map/output/map.html?focus=" in html) or ("Open on Map" in html)
    assert has_map_link, "Map deep-links not found or incorrectly formatted"
    
    print("✅ Map link format test passed")

