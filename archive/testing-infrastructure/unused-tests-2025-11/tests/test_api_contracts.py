"""
API Contracts Tests (Step 8)

Tests that all APIs return correct schemas and handle missing data gracefully.

Run: pytest tests/test_api_contracts.py
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_summary_api():
    """Test dashboard summary API contract."""
    response = client.get("/api/dashboard/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    # Required keys
    required = ["timestamp", "environment", "segments_total", "peak_density", 
                "peak_density_los", "status", "warnings"]
    for key in required:
        assert key in data, f"Missing required key: {key}"
    
    # If data present, should have non-zero segments
    if not data["warnings"]:
        assert data["segments_total"] > 0
    
    print("✅ Dashboard summary API contract valid")


def test_segments_geojson_api():
    """Test segments GeoJSON API contract."""
    response = client.get("/api/segments/geojson")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    
    if data["features"]:
        first = data["features"][0]
        assert "type" in first
        assert "geometry" in first
        assert "properties" in first
        assert "seg_id" in first["properties"]
        assert "worst_los" in first["properties"]
        assert "is_flagged" in first["properties"]
    
    print("✅ Segments GeoJSON API contract valid")


def test_density_segments_api():
    """Test density segments API contract."""
    response = client.get("/api/density/segments")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    
    if data:
        first = data[0]
        required = ["seg_id", "name", "peak_density", "worst_los", "flagged"]
        for key in required:
            assert key in first, f"Missing required key: {key}"
    
    print("✅ Density segments API contract valid")


def test_flow_segments_api():
    """Test flow segments API contract."""
    response = client.get("/api/flow/segments")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, dict)
    
    if data:
        first_key = list(data.keys())[0]
        first = data[first_key]
        required = ["overtaking_a", "overtaking_b", "copresence_a", "copresence_b"]
        for key in required:
            assert key in first, f"Missing required key: {key}"
    
    print("✅ Flow segments API contract valid")


def test_reports_list_api():
    """Test reports list API contract."""
    response = client.get("/api/reports/list")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    
    if data:
        first = data[0]
        required = ["name", "path"]
        for key in required:
            assert key in first, f"Missing required key: {key}"
    
    print("✅ Reports list API contract valid")


def test_health_data_api():
    """Test health data API contract."""
    response = client.get("/api/health/data")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, dict)
    assert "_storage" in data
    
    print("✅ Health data API contract valid")


if __name__ == "__main__":
    print("🧪 API Contracts Tests")
    print("=" * 60)
    
    test_dashboard_summary_api()
    test_segments_geojson_api()
    test_density_segments_api()
    test_flow_segments_api()
    test_reports_list_api()
    test_health_data_api()
    
    print("=" * 60)
    print("🎉 All API contract tests passed!")
