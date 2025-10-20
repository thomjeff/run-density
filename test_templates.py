"""
Template Rendering Test for RF-FE-002 Step 4

Tests that all 7 page templates render without errors.

Run: python3 test_templates.py
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.routes.ui import router

# Create test app
app = FastAPI()
app.include_router(router)

# Create test client
client = TestClient(app)

def test_all_pages():
    """Test that all 7 pages render successfully."""
    
    pages = [
        ("/", "Password"),
        ("/dashboard", "Dashboard"),
        ("/segments", "Segments"),
        ("/density", "Density"),
        ("/flow", "Flow"),
        ("/reports", "Reports"),
        ("/health-check", "Health"),
    ]
    
    print("=" * 60)
    print("Testing Template Rendering (Step 4)")
    print("=" * 60)
    
    all_passed = True
    
    for path, name in pages:
        try:
            response = client.get(path)
            
            if response.status_code == 200:
                # Check for key indicators
                has_title = "Runflow" in response.text
                has_provenance = "Validated" in response.text or "pending" in response.text
                has_nav = "Dashboard" in response.text
                
                print(f"\n✅ {name:15} ({path})")
                print(f"   Status: {response.status_code}")
                print(f"   Title: {'✓' if has_title else '✗'} Runflow")
                print(f"   Provenance: {'✓' if has_provenance else '✗'}")
                print(f"   Navigation: {'✓' if has_nav else '✗'}")
                
                if not (has_title and has_provenance and has_nav):
                    print(f"   ⚠️  Missing expected content")
                    all_passed = False
            else:
                print(f"\n❌ {name:15} ({path})")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text[:200]}")
                all_passed = False
                
        except Exception as e:
            print(f"\n❌ {name:15} ({path})")
            print(f"   Exception: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All templates rendered successfully!")
    else:
        print("⚠️  Some templates had issues - see above")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = test_all_pages()
    exit(0 if success else 1)

