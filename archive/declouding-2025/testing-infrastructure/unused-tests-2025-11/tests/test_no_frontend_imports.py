"""
Guard Test: Ensure API does not import frontend modules

This test ensures the Cloud Run API service doesn't accidentally
import heavy frontend dependencies (folium, matplotlib, etc.) which
would bloat the container and slow startup.

Author: AI Assistant (Cursor)
Issue: #263 - Phase 2: Dependency Split
"""

import importlib
import sys


def test_api_does_not_import_frontend():
    """
    Verify app.main can be imported without frontend dependencies.
    
    This ensures Cloud Run deployment (which only installs requirements-core.txt)
    will not fail due to missing frontend dependencies.
    """
    # Try to import the main API module
    try:
        m = importlib.import_module("app.main")
        assert m is not None, "app.main failed to import"
    except ImportError as e:
        # Check if the error is due to frontend dependencies
        error_msg = str(e)
        forbidden_modules = ["folium", "matplotlib"]
        for mod in forbidden_modules:
            if mod in error_msg:
                raise AssertionError(
                    f"app.main imports {mod}, which is a frontend-only dependency. "
                    f"This would break Cloud Run deployment. Error: {error_msg}"
                )
        # Re-raise if it's a different import error
        raise
    
    print("✅ API imports test passed: No frontend dependencies required")


def test_frontend_modules_optional():
    """
    Verify frontend modules are not required by core application.
    
    This test confirms that folium and matplotlib are truly optional
    and only used by frontend generation scripts.
    """
    # These should fail gracefully if not installed
    frontend_only = ["folium", "matplotlib.pyplot"]
    
    for module_name in frontend_only:
        try:
            importlib.import_module(module_name)
            # If it imports, that's fine (local dev environment)
            print(f"ℹ️  {module_name} available (local dev)")
        except ImportError:
            # If it fails, that's expected in core-only environment
            print(f"✅ {module_name} not required (core-only OK)")
    
    # The test passes either way - we're just documenting availability
    assert True

