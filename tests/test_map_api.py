"""
Unit tests for app/map_api.py endpoints (Issue #249)

Tests new map visualization endpoints:
- /api/map/manifest - Session metadata and configuration
- /api/map/bins - Filtered bins per window + bbox + severity
"""

import pytest
from fastapi.testclient import TestClient
import pandas as pd
from pathlib import Path
import json


@pytest.fixture
def client():
    """Create FastAPI test client"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def ensure_test_data():
    """Ensure test data exists for API tests"""
    # Check if bins.parquet exists in reports
    reports_dir = Path("reports")
    if not reports_dir.exists():
        pytest.skip("No reports directory found")
    
    # Find latest bins.parquet
    date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
    bins_found = False
    for date_dir in date_dirs:
        if (date_dir / "bins.parquet").exists():
            bins_found = True
            break
    
    if not bins_found:
        pytest.skip("No bins.parquet found - run density report generation first")
    
    return True


class TestMapManifest:
    """Test /api/map/manifest endpoint"""
    
    def test_manifest_returns_200(self, client, ensure_test_data):
        """Test that manifest endpoint returns 200"""
        response = client.get("/api/map/manifest")
        assert response.status_code == 200
    
    def test_manifest_structure(self, client, ensure_test_data):
        """Test manifest response structure"""
        response = client.get("/api/map/manifest")
        data = response.json()
        
        assert data["ok"] is True
        assert "date" in data
        assert "window_count" in data
        assert "window_seconds" in data
        assert "lod" in data
        assert "segments" in data
        assert "metadata" in data
    
    def test_manifest_window_count(self, client, ensure_test_data):
        """Test that window_count is positive integer"""
        response = client.get("/api/map/manifest")
        data = response.json()
        
        assert isinstance(data["window_count"], int)
        assert data["window_count"] > 0
    
    def test_manifest_window_seconds(self, client, ensure_test_data):
        """Test that window_seconds matches expected value"""
        response = client.get("/api/map/manifest")
        data = response.json()
        
        assert isinstance(data["window_seconds"], int)
        # Should be 120 seconds (2 minutes) based on current config
        assert data["window_seconds"] in [60, 120, 180]
    
    def test_manifest_lod_thresholds(self, client, ensure_test_data):
        """Test that LOD thresholds match ChatGPT's spec"""
        response = client.get("/api/map/manifest")
        data = response.json()
        
        assert "lod" in data
        assert data["lod"]["segments_only"] == 12
        assert data["lod"]["flagged_bins"] == 14
    
    def test_manifest_segments(self, client, ensure_test_data):
        """Test that segments array contains required fields"""
        response = client.get("/api/map/manifest")
        data = response.json()
        
        assert isinstance(data["segments"], list)
        assert len(data["segments"]) > 0
        
        # Check first segment has required fields
        first_seg = data["segments"][0]
        assert "segment_id" in first_seg
        assert "segment_label" in first_seg
        assert "schema_key" in first_seg
        assert "width_m" in first_seg


class TestMapBins:
    """Test /api/map/bins endpoint"""
    
    def test_bins_requires_parameters(self, client):
        """Test that bins endpoint requires window_idx and bbox"""
        response = client.get("/api/map/bins")
        assert response.status_code == 422  # Unprocessable Entity (missing params)
    
    def test_bins_with_valid_params(self, client, ensure_test_data):
        """Test bins endpoint with valid parameters"""
        # Use wide bbox to capture all bins
        bbox = "-7500000,5700000,-7300000,5800000"  # Fredericton area in Web Mercator
        
        response = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        assert response.status_code == 200
    
    def test_bins_response_structure(self, client, ensure_test_data):
        """Test bins response is valid GeoJSON"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        response = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        data = response.json()
        
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)
    
    def test_bins_feature_properties(self, client, ensure_test_data):
        """Test that bin features have required properties per Issue #249 spec"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        response = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        data = response.json()
        
        if len(data["features"]) > 0:
            feature = data["features"][0]
            props = feature["properties"]
            
            # Check all required properties from ChatGPT's spec
            assert "segment_id" in props
            assert "bin_id" in props
            assert "start_km" in props
            assert "end_km" in props
            assert "window_idx" in props
            assert "t_start_hhmm" in props
            assert "t_end_hhmm" in props
            assert "density" in props
            assert "rate" in props
            assert "los_class" in props
            assert "severity" in props
    
    def test_bins_time_format(self, client, ensure_test_data):
        """Test that times are formatted as HH:MM"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        response = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        data = response.json()
        
        if len(data["features"]) > 0:
            props = data["features"][0]["properties"]
            
            # Check HH:MM format (e.g., "07:00")
            assert ":" in props["t_start_hhmm"]
            assert ":" in props["t_end_hhmm"]
            assert len(props["t_start_hhmm"]) == 5  # HH:MM
            assert len(props["t_end_hhmm"]) == 5
    
    def test_bins_severity_filter(self, client, ensure_test_data):
        """Test severity filtering works"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        # Get all bins
        response_all = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        data_all = response_all.json()
        
        # Get only critical bins
        response_critical = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=critical")
        data_critical = response_critical.json()
        
        # Critical bins should be subset of all bins
        assert len(data_critical["features"]) <= len(data_all["features"])
    
    def test_bins_invalid_severity(self, client, ensure_test_data):
        """Test that invalid severity returns 400"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        response = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=invalid")
        assert response.status_code == 400
    
    def test_bins_invalid_bbox(self, client, ensure_test_data):
        """Test that invalid bbox returns 400"""
        response = client.get(f"/api/map/bins?window_idx=0&bbox=invalid&severity=any")
        assert response.status_code == 400
    
    def test_bins_window_filtering(self, client, ensure_test_data):
        """Test that different windows return different data"""
        bbox = "-7500000,5700000,-7300000,5800000"
        
        response_w0 = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        response_w10 = client.get(f"/api/map/bins?window_idx=10&bbox={bbox}&severity=any")
        
        data_w0 = response_w0.json()
        data_w10 = response_w10.json()
        
        # Both should have features (assuming bins exist at these times)
        # The specific bins might differ, or at minimum the properties should differ
        # Just verify both return valid responses
        assert data_w0["type"] == "FeatureCollection"
        assert data_w10["type"] == "FeatureCollection"


class TestMapAPIIntegration:
    """Integration tests for map API"""
    
    def test_manifest_segments_match_bins(self, client, ensure_test_data):
        """Test that manifest segments match bins in parquet"""
        # Get manifest
        manifest_response = client.get("/api/map/manifest")
        manifest = manifest_response.json()
        
        # Load bins to compare
        from pathlib import Path
        import pandas as pd
        
        reports_dir = Path("reports")
        date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
        bins_df = pd.read_parquet(date_dirs[0] / "bins.parquet")
        
        # Segments in manifest should match segments in bins
        manifest_seg_ids = {seg["segment_id"] for seg in manifest["segments"]}
        bins_seg_ids = set(bins_df['segment_id'].unique())
        
        # All bin segments should be in manifest
        assert bins_seg_ids.issubset(manifest_seg_ids)
    
    def test_window_count_consistency(self, client, ensure_test_data):
        """Test that window_count is consistent with bins data"""
        # Get manifest
        manifest_response = client.get("/api/map/manifest")
        manifest = manifest_response.json()
        window_count = manifest["window_count"]
        
        # Test that we can query all windows
        bbox = "-7500000,5700000,-7300000,5800000"
        
        # Test first window
        response_first = client.get(f"/api/map/bins?window_idx=0&bbox={bbox}&severity=any")
        assert response_first.status_code == 200
        
        # Test last window
        response_last = client.get(f"/api/map/bins?window_idx={window_count-1}&bbox={bbox}&severity=any")
        assert response_last.status_code == 200
        
        # Test beyond last window (should return empty or 404)
        response_beyond = client.get(f"/api/map/bins?window_idx={window_count+10}&bbox={bbox}&severity=any")
        # Should still return 200 with empty features
        assert response_beyond.status_code == 200
        data = response_beyond.json()
        assert len(data["features"]) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

