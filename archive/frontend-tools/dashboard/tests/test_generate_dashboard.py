"""
Unit Tests for Runflow Dashboard Generation

Tests YAML coherence, dashboard generation, and numeric parity validation.

Author: AI Assistant (Cursor)
Issue: #264 - Phase 3: Dashboard Summary View
"""

from pathlib import Path
import subprocess
import sys
import json
import yaml
import re
from collections import Counter


def test_yaml_coherence():
    """
    Verify LOS keys and order are consistent between density_rulebook.yml and reporting.yml.
    
    This ensures the dashboard legend will match the data classification logic.
    """
    rb = yaml.safe_load(Path("config/density_rulebook.yml").read_text())
    rp = yaml.safe_load(Path("config/reporting.yml").read_text())
    
    bands = list(rb["globals"]["los_thresholds"].keys())
    colors = list(rp["reporting"]["los_colors"].keys())
    
    assert bands == colors, (
        f"LOS keys/order must match between rulebook and reporting palette. "
        f"Rulebook: {bands}, Reporting: {colors}"
    )
    
    print(f"✅ YAML coherence check passed: {len(bands)} LOS bands in correct order")


def test_dashboard_builds():
    """
    Verify dashboard.html is generated successfully with expected content.
    
    This ensures:
    1. generate_dashboard.py runs without errors
    2. dashboard.html is created
    3. Expected sections are present (LOS Distribution, Start Times, Top 10)
    4. Deep-link format is correct
    """
    result = subprocess.run(
        [sys.executable, "frontend/dashboard/scripts/generate_dashboard.py"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Dashboard generation failed: {result.stderr}"
    assert Path("frontend/dashboard/output/dashboard.html").exists(), "dashboard.html not created"
    
    html = Path("frontend/dashboard/output/dashboard.html").read_text()
    
    # Basic sanity: required sections present
    assert "LOS Distribution" in html, "LOS Distribution section missing"
    assert "Start Times" in html, "Start Times section missing"
    assert "Top 10 Segments by Risk" in html, "Top 10 section missing"
    
    # Deep-link format looks right
    assert re.search(r"map\.html\?focus=\w+", html) is not None, "Deep-link format incorrect"
    
    # Charts exist
    assert Path("frontend/dashboard/output/charts/los_distribution.svg").exists(), "LOS chart not generated"
    assert Path("frontend/dashboard/output/charts/start_timeline.svg").exists(), "Timeline chart not generated"
    
    print("✅ Dashboard generation test passed: All sections present")


def test_numeric_parity():
    """
    Verify numeric values in dashboard match source JSON data.
    
    This ensures the dashboard accurately reflects the underlying metrics.
    """
    metrics = json.loads(Path("data/segment_metrics.json").read_text())["items"]
    html = Path("frontend/dashboard/output/dashboard.html").read_text()
    
    # Count LOS occurrences in source data
    los_counts_source = Counter([m["worst_los"] for m in metrics])
    
    # Verify each LOS count appears in HTML
    for k, v in los_counts_source.items():
        assert f"{k}: {v}" in html, f"LOS count mismatch: {k} should be {v}"
    
    print(f"✅ Numeric parity test passed: {len(los_counts_source)} LOS categories verified")


def test_provenance_embedded():
    """
    Verify provenance badge is embedded in dashboard.
    
    This ensures Phase 1 provenance integration is working.
    """
    html = Path("frontend/dashboard/output/dashboard.html").read_text()
    
    # Check for provenance indicators
    # The exact text will vary, but should contain validation status
    assert "Validated" in html or "provenance" in html.lower(), "Provenance badge not embedded"
    
    print("✅ Provenance embedding test passed")

