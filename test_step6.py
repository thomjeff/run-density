"""
Step 6 Tests - Dashboard Data Bindings + KPI Tiles

Tests the dashboard summary API and template data binding.

Run: python3 test_step6.py
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes.api_dashboard import router as api_dashboard_router
from app.routes.ui import router as ui_router
from app.storage import create_storage_from_env
import json

# Create test app
app = FastAPI()
app.include_router(api_dashboard_router)
app.include_router(ui_router)

# Create test client
client = TestClient(app)

def test_api_dashboard_summary():
    """Test that /api/dashboard/summary returns valid JSON with required keys."""
    
    print("=" * 60)
    print("Testing API Dashboard Summary (Step 6)")
    print("=" * 60)
    
    try:
        response = client.get("/api/dashboard/summary")
        
        print(f"\n✅ API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required keys
            required_keys = [
                "timestamp", "environment", "total_runners", "cohorts",
                "segments_total", "segments_flagged", "bins_flagged",
                "peak_density", "peak_density_los", "peak_rate",
                "segments_overtaking", "segments_copresence", "status"
            ]
            
            print("   ✅ Required keys present:")
            for key in required_keys:
                if key in data:
                    print(f"      ✓ {key}: {type(data[key]).__name__}")
                else:
                    print(f"      ✗ {key}: MISSING")
                    return False
            
            # Check data types
            type_checks = {
                "timestamp": str,
                "environment": str,
                "total_runners": int,
                "cohorts": dict,
                "segments_total": int,
                "segments_flagged": int,
                "bins_flagged": int,
                "peak_density": (int, float),
                "peak_density_los": str,
                "peak_rate": (int, float),
                "segments_overtaking": int,
                "segments_copresence": int,
                "status": str
            }
            
            print("   ✅ Data types correct:")
            for key, expected_type in type_checks.items():
                actual_type = type(data[key])
                if isinstance(data[key], expected_type) or (isinstance(expected_type, tuple) and actual_type in expected_type):
                    print(f"      ✓ {key}: {actual_type.__name__}")
                else:
                    print(f"      ✗ {key}: expected {expected_type}, got {actual_type.__name__}")
                    return False
            
            # Check LOS grade is valid
            valid_los = ["A", "B", "C", "D", "E", "F"]
            if data["peak_density_los"] in valid_los:
                print(f"   ✅ LOS grade valid: {data['peak_density_los']}")
            else:
                print(f"   ✗ Invalid LOS grade: {data['peak_density_los']}")
                return False
            
            # Check status is valid
            valid_status = ["normal", "action_required"]
            if data["status"] in valid_status:
                print(f"   ✅ Status valid: {data['status']}")
            else:
                print(f"   ✗ Invalid status: {data['status']}")
                return False
            
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


def test_dashboard_template():
    """Test that dashboard template includes data binding elements."""
    
    print("\n" + "=" * 60)
    print("Testing Dashboard Template (Step 6)")
    print("=" * 60)
    
    try:
        response = client.get("/dashboard")
        
        print(f"\n✅ Template Response Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Check for KPI elements
            kpi_elements = [
                'id="kpi-peak-density"',
                'id="kpi-peak-rate"',
                'id="kpi-flagged-segments"',
                'id="kpi-flagged-bins"',
                'id="kpi-overtaking"',
                'id="kpi-copresence"'
            ]
            
            print("   ✅ KPI elements present:")
            for element in kpi_elements:
                if element in html:
                    print(f"      ✓ {element}")
                else:
                    print(f"      ✗ {element}: MISSING")
                    return False
            
            # Check for data binding JavaScript
            js_elements = [
                'loadDashboardData()',
                'fetch(\'/api/dashboard/summary\')',
                'updateDashboard(',
                'updateModelInputs(',
                'updateModelOutputs(',
                'updateStatusBanner('
            ]
            
            print("   ✅ JavaScript functions present:")
            for element in js_elements:
                if element in html:
                    print(f"      ✓ {element}")
                else:
                    print(f"      ✗ {element}: MISSING")
                    return False
            
            # Check for LOS colors injection
            if 'const LOS_COLORS =' in html:
                print("   ✅ LOS_COLORS JavaScript present")
            else:
                print("   ✗ LOS_COLORS JavaScript missing")
                return False
            
            # Check for refresh button
            if 'id="refresh-btn"' in html:
                print("   ✅ Refresh button present")
            else:
                print("   ✗ Refresh button missing")
                return False
            
            # Check for status banner
            if 'id="status-banner"' in html:
                print("   ✅ Status banner present")
            else:
                print("   ✗ Status banner missing")
                return False
            
            # Check for last updated timestamp
            if 'id="last-updated"' in html:
                print("   ✅ Last updated timestamp present")
            else:
                print("   ✗ Last updated timestamp missing")
                return False
            
            print("\n✅ Template test passed!")
            return True
            
        else:
            print(f"\n❌ Template returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Template test failed: {e}")
        return False


def test_los_calculation():
    """Test LOS calculation with boundary values."""
    
    print("\n" + "=" * 60)
    print("Testing LOS Calculation (Step 6)")
    print("=" * 60)
    
    try:
        from app.routes.api_dashboard import calculate_peak_density_los
        
        # Test boundary values
        test_cases = [
            (0.0, "A"),
            (0.1, "A"),
            (0.2, "B"),
            (0.4, "C"),
            (0.6, "D"),
            (0.8, "E"),
            (1.0, "F"),
            (1.5, "F")
        ]
        
        print("   ✅ LOS calculation test cases:")
        all_passed = True
        
        for density, expected_los in test_cases:
            actual_los = calculate_peak_density_los(density)
            if actual_los == expected_los:
                print(f"      ✓ {density} → {actual_los}")
            else:
                print(f"      ✗ {density} → {actual_los} (expected {expected_los})")
                all_passed = False
        
        if all_passed:
            print("\n✅ LOS calculation test passed!")
            return True
        else:
            print("\n❌ LOS calculation test failed!")
            return False
            
    except Exception as e:
        print(f"\n❌ LOS calculation test failed: {e}")
        return False


def test_storage_integration():
    """Test that storage adapter works with dashboard data."""
    
    print("\n" + "=" * 60)
    print("Testing Storage Integration (Step 6)")
    print("=" * 60)
    
    try:
        # Test storage creation
        storage = create_storage_from_env()
        print(f"   Storage mode: {storage.mode}")
        
        # Test file existence checks
        test_files = ["meta.json", "segment_metrics.json", "flags.json", "runners.csv", "flow.json"]
        
        for file_path in test_files:
            exists = storage.exists(file_path)
            print(f"   {file_path}: {'✅ exists' if exists else '❌ missing'}")
        
        print("\n✅ Storage integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Storage integration test failed: {e}")
        return False


def main():
    """Run all Step 6 tests."""
    
    print("🧪 Step 6 Tests - Dashboard Data Bindings + KPI Tiles")
    print("=" * 60)
    
    tests = [
        test_api_dashboard_summary,
        test_dashboard_template,
        test_los_calculation,
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
        print("🎉 All Step 6 tests passed!")
        return True
    else:
        print("⚠️  Some tests failed - see above")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
