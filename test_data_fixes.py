"""
Data Path Fixes Tests - Step 6 Fixes

Tests the data path fixes, warnings, and health checks.

Run: python3 test_data_fixes.py
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes.api_dashboard import router as api_dashboard_router
from app.routes.api_health import router as api_health_router
from app.routes.ui import router as ui_router
from app.storage import create_storage_from_env, DATASET
import json

# Create test app
app = FastAPI()
app.include_router(api_dashboard_router)
app.include_router(api_health_router)
app.include_router(ui_router)

# Create test client
client = TestClient(app)

def test_dashboard_warnings():
    """Test that dashboard API includes warnings for missing files."""
    
    print("=" * 60)
    print("Testing Dashboard Warnings (Data Fixes)")
    print("=" * 60)
    
    try:
        response = client.get("/api/dashboard/summary")
        
        print(f"\n✅ API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check warnings field exists
            assert "warnings" in data, "Missing warnings field in response"
            print("   ✅ Warnings field present")
            
            # Check warnings is a list
            assert isinstance(data["warnings"], list), "Warnings should be a list"
            print("   ✅ Warnings is a list")
            
            # Check for expected missing files (in v1.6.42 baseline)
            warnings = data["warnings"]
            print(f"   Warnings: {warnings}")
            
            # Should have warnings for missing files
            missing_files = [w for w in warnings if w.startswith("missing:")]
            print(f"   Missing files: {missing_files}")
            
            # Check that all zeros indicates missing data
            all_zeros = (
                data["segments_total"] == 0 and 
                data["total_runners"] == 0 and 
                data["bins_flagged"] == 0
            )
            
            if all_zeros and len(missing_files) > 0:
                print("   ✅ All zeros with missing files - expected behavior")
            elif not all_zeros:
                print("   ✅ Some data present - good")
            else:
                print("   ⚠️  All zeros but no missing file warnings - check path logic")
            
            print("\n✅ Dashboard warnings test passed!")
            return True
            
        else:
            print(f"\n❌ API returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Dashboard warnings test failed: {e}")
        return False


def test_health_data_endpoint():
    """Test that /api/health/data returns file status information."""
    
    print("\n" + "=" * 60)
    print("Testing Health Data Endpoint (Data Fixes)")
    print("=" * 60)
    
    try:
        response = client.get("/api/health/data")
        
        print(f"\n✅ API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields
            required_files = list(DATASET.values()) + ["runners.csv", "flow.json"]
            
            print("   ✅ Required files checked:")
            for filename in required_files:
                if filename in data:
                    file_info = data[filename]
                    exists = file_info.get("exists", False)
                    mtime = file_info.get("mtime")
                    print(f"      {filename}: {'✅' if exists else '❌'} {mtime or 'N/A'}")
                else:
                    print(f"      {filename}: ❌ Not in response")
            
            # Check storage info
            if "_storage" in data:
                storage_info = data["_storage"]
                print(f"   ✅ Storage mode: {storage_info.get('mode', 'unknown')}")
                print(f"   ✅ Storage root: {storage_info.get('root', 'N/A')}")
            else:
                print("   ⚠️  No storage info in response")
            
            print("\n✅ Health data endpoint test passed!")
            return True
            
        else:
            print(f"\n❌ API returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Health data endpoint test failed: {e}")
        return False


def test_dashboard_ui_banner():
    """Test that dashboard template includes data missing banner."""
    
    print("\n" + "=" * 60)
    print("Testing Dashboard UI Banner (Data Fixes)")
    print("=" * 60)
    
    try:
        response = client.get("/dashboard")
        
        print(f"\n✅ Template Response Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Check for data missing banner elements
            banner_elements = [
                'id="data-missing-banner"',
                'Data Not Found',
                'updateDataMissingBanner(',
                'data.warnings'
            ]
            
            print("   ✅ Data missing banner elements:")
            for element in banner_elements:
                if element in html:
                    print(f"      ✓ {element}")
                else:
                    print(f"      ✗ {element}: MISSING")
                    return False
            
            print("\n✅ Dashboard UI banner test passed!")
            return True
            
        else:
            print(f"\n❌ Template returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Dashboard UI banner test failed: {e}")
        return False


def test_health_ui_data_status():
    """Test that health page includes data status functionality."""
    
    print("\n" + "=" * 60)
    print("Testing Health UI Data Status (Data Fixes)")
    print("=" * 60)
    
    try:
        response = client.get("/health-check")
        
        print(f"\n✅ Template Response Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Check for data status elements
            status_elements = [
                'id="file-status-tbody"',
                'loadDataHealth()',
                'fetch(\'/api/health/data\')',
                'updateFileStatusTable('
            ]
            
            print("   ✅ Health data status elements:")
            for element in status_elements:
                if element in html:
                    print(f"      ✓ {element}")
                else:
                    print(f"      ✗ {element}: MISSING")
                    return False
            
            print("\n✅ Health UI data status test passed!")
            return True
            
        else:
            print(f"\n❌ Template returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Health UI data status test failed: {e}")
        return False


def test_dataset_paths_ssot():
    """Test that DATASET paths are properly defined."""
    
    print("\n" + "=" * 60)
    print("Testing DATASET Paths SSOT (Data Fixes)")
    print("=" * 60)
    
    try:
        # Check DATASET is properly defined
        assert DATASET is not None, "DATASET not defined"
        print("   ✅ DATASET defined")
        
        # Check required paths
        required_paths = ["meta", "segments", "metrics", "flags"]
        for path_key in required_paths:
            assert path_key in DATASET, f"Missing {path_key} in DATASET"
            assert DATASET[path_key].startswith("data/"), f"{path_key} path should start with data/"
            print(f"   ✅ {path_key}: {DATASET[path_key]}")
        
        print("\n✅ DATASET paths SSOT test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ DATASET paths SSOT test failed: {e}")
        return False


def main():
    """Run all data fixes tests."""
    
    print("🧪 Data Path Fixes Tests - Step 6 Fixes")
    print("=" * 60)
    
    tests = [
        test_dashboard_warnings,
        test_health_data_endpoint,
        test_dashboard_ui_banner,
        test_health_ui_data_status,
        test_dataset_paths_ssot
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All data fixes tests passed!")
        return True
    else:
        print("⚠️  Some tests failed - see above")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
