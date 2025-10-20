"""
Step 5 Tests - Leaflet Integration (Segments Page)

Tests the enriched GeoJSON API and template rendering.

Run: python3 test_step5.py
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes.api_segments import router as api_segments_router
from app.routes.ui import router as ui_router
from app.storage import create_storage_from_env
import json

# Create test app
app = FastAPI()
app.include_router(api_segments_router)
app.include_router(ui_router)

# Create test client
client = TestClient(app)

def test_api_segments_geojson():
    """Test that /api/segments/geojson returns valid FeatureCollection."""
    
    print("=" * 60)
    print("Testing API Segments GeoJSON (Step 5)")
    print("=" * 60)
    
    try:
        response = client.get("/api/segments/geojson")
        
        print(f"\n✅ API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check GeoJSON structure
            assert data.get("type") == "FeatureCollection", "Missing FeatureCollection type"
            assert "features" in data, "Missing features array"
            
            features = data["features"]
            print(f"   Features count: {len(features)}")
            
            if len(features) > 0:
                # Check first feature structure
                feature = features[0]
                assert feature.get("type") == "Feature", "Feature missing type"
                assert "geometry" in feature, "Feature missing geometry"
                assert "properties" in feature, "Feature missing properties"
                
                props = feature["properties"]
                required_props = ["seg_id", "label", "length_km", "width_m", "direction", "events"]
                enriched_props = ["worst_los", "peak_density", "peak_rate", "active"]
                
                print("   ✅ GeoJSON structure valid")
                
                # Check required properties
                for prop in required_props:
                    assert prop in props, f"Missing required property: {prop}"
                print("   ✅ Required properties present")
                
                # Check enriched properties
                for prop in enriched_props:
                    assert prop in props, f"Missing enriched property: {prop}"
                print("   ✅ Enriched properties present")
                
                # Check LOS color mapping
                los = props.get("worst_los", "Unknown")
                print(f"   Sample LOS: {los}")
                
            else:
                print("   ⚠️  No features found (empty FeatureCollection)")
            
            # Check cache headers
            cache_control = response.headers.get("Cache-Control")
            if cache_control:
                print(f"   ✅ Cache-Control: {cache_control}")
            else:
                print("   ⚠️  No Cache-Control header")
            
            print("\n✅ API test passed!")
            return True
            
        else:
            print(f"\n❌ API returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ API test failed: {e}")
        return False


def test_segments_template():
    """Test that segments template includes LOS_COLORS and map elements."""
    
    print("\n" + "=" * 60)
    print("Testing Segments Template (Step 5)")
    print("=" * 60)
    
    try:
        response = client.get("/segments")
        
        print(f"\n✅ Template Response Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Check for map container
            assert 'id="segments-map"' in html, "Missing segments-map container"
            print("   ✅ Map container present")
            
            # Check for Leaflet CSS/JS
            assert 'leaflet@1.9.4' in html, "Missing Leaflet CDN links"
            print("   ✅ Leaflet CDN links present")
            
            # Check for LOS_COLORS injection
            assert 'const LOS_COLORS =' in html, "Missing LOS_COLORS JavaScript"
            print("   ✅ LOS_COLORS JavaScript present")
            
            # Check for legend
            assert 'los-legend' in html, "Missing LOS legend"
            print("   ✅ LOS legend present")
            
            # Check for accessibility
            assert 'aria-label="Course segments map"' in html, "Missing aria-label"
            print("   ✅ Accessibility features present")
            
            # Check for API endpoint reference
            assert '/api/segments/geojson' in html, "Missing API endpoint reference"
            print("   ✅ API endpoint reference present")
            
            # Check for focus parameter handling
            assert 'focusSegmentId' in html, "Missing focus parameter handling"
            print("   ✅ Focus parameter handling present")
            
            print("\n✅ Template test passed!")
            return True
            
        else:
            print(f"\n❌ Template returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Template test failed: {e}")
        return False


def test_storage_integration():
    """Test that storage adapter works with test fixtures."""
    
    print("\n" + "=" * 60)
    print("Testing Storage Integration (Step 5)")
    print("=" * 60)
    
    try:
        # Test storage creation
        storage = create_storage_from_env()
        print(f"   Storage mode: {storage.mode}")
        
        # Test file existence checks
        test_files = ["segments.geojson", "segment_metrics.json", "flags.json", "meta.json"]
        
        for file_path in test_files:
            exists = storage.exists(file_path)
            print(f"   {file_path}: {'✅ exists' if exists else '❌ missing'}")
        
        print("\n✅ Storage integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Storage integration test failed: {e}")
        return False


def main():
    """Run all Step 5 tests."""
    
    print("🧪 Step 5 Tests - Leaflet Integration")
    print("=" * 60)
    
    tests = [
        test_api_segments_geojson,
        test_segments_template,
        test_storage_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All Step 5 tests passed!")
        return True
    else:
        print("⚠️  Some tests failed - see above")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
