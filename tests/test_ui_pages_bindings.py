"""
UI Pages Data Bindings Tests (Step 8)

Tests that all pages render correctly and bind to real artifacts.

Run: pytest tests/test_ui_pages_bindings.py
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_page_renders():
    """Test dashboard page renders with real data."""
    response = client.get("/dashboard")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for KPI elements
    assert 'id="kpi-peak-density"' in html
    assert 'id="kpi-peak-rate"' in html
    assert 'loadDashboardData()' in html
    print("✅ Dashboard page renders")


def test_segments_page_renders():
    """Test segments page renders with Leaflet map."""
    response = client.get("/segments")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for map elements
    assert 'id="segments-map"' in html
    assert 'leaflet' in html.lower()
    assert "fetch('/api/segments/geojson')" in html
    print("✅ Segments page renders")


def test_density_page_renders():
    """Test density page renders with table."""
    response = client.get("/density")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for table and detail panel
    assert 'id="density-table"' in html
    assert 'id="segment-detail"' in html
    assert "fetch('/api/density/segments')" in html
    print("✅ Density page renders")


def test_flow_page_renders():
    """Test flow page renders with table."""
    response = client.get("/flow")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for flow table
    assert 'id="flow-table"' in html
    assert "fetch('/api/flow/segments')" in html
    print("✅ Flow page renders")


def test_reports_page_renders():
    """Test reports page renders with list."""
    response = client.get("/reports")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for reports list
    assert 'id="reports-list"' in html
    assert "fetch('/api/reports/list')" in html
    print("✅ Reports page renders")


def test_health_page_renders():
    """Test health page renders with data status."""
    response = client.get("/health-check")
    
    assert response.status_code == 200
    html = response.text
    
    # Check for health elements
    assert 'id="file-status-tbody"' in html
    assert "fetch('/api/health/data')" in html
    print("✅ Health page renders")


if __name__ == "__main__":
    print("🧪 UI Pages Bindings Tests")
    print("=" * 60)
    
    test_dashboard_page_renders()
    test_segments_page_renders()
    test_density_page_renders()
    test_flow_page_renders()
    test_reports_page_renders()
    test_health_page_renders()
    
    print("=" * 60)
    print("🎉 All page render tests passed!")

