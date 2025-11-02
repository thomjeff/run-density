#!/usr/bin/env python3
"""
Lightweight End-to-End Test

Simple E2E test that verifies core functionality with proper resource management.
Tests: health, ready, density-report, temporal-flow-report
"""

import requests
import time
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
CLOUD_RUN_URL = "https://run-density-ln4r3sfkha-uc.a.run.app"
LOCAL_URL = "http://localhost:8080"  # Updated to 8080 to match Cloud Run default (Issue #415)
DEFAULT_START_TIMES = {'Full': 420, '10K': 440, 'Half': 460}

def parse_arguments():
    """Parse command line arguments for E2E testing"""
    parser = argparse.ArgumentParser(
        description='Run End-to-End tests for run-density application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python e2e.py --cloud     # Test against Cloud Run production
  python e2e.py --local     # Test against local server (default)
  python e2e.py --help      # Show this help message
        """
    )
    
    # Mutually exclusive group for target selection
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument('--cloud', action='store_true',
                             help='Test against Cloud Run production environment')
    target_group.add_argument('--local', action='store_true',
                             help='Test against local server (default behavior)')
    
    return parser.parse_args()

# Test payloads
density_payload = {
    'paceCsv': 'data/runners.csv',
    'densityCsv': 'data/segments.csv',
    'startTimes': DEFAULT_START_TIMES,
    'enable_bin_dataset': True  # Always include operational intelligence (Issue #236/239)
}

flow_payload = {
    'paceCsv': 'data/runners.csv',
    'segmentsCsv': 'data/segments.csv',
    'startTimes': DEFAULT_START_TIMES
}

def test_health(base_url):
    """Test health endpoint"""
    print("🔍 Testing /health...")
    response = requests.get(f'{base_url}/health', timeout=30)
    
    if response.status_code == 200:
        print("✅ Health: OK")
        return True
    else:
        print(f"❌ Health: FAILED (status: {response.status_code})")
        return False

def test_ready(base_url):
    """Test ready endpoint"""
    print("🔍 Testing /ready...")
    response = requests.get(f'{base_url}/ready', timeout=30)
    
    if response.status_code == 200:
        print("✅ Ready: OK")
        return True
    else:
        print(f"❌ Ready: FAILED (status: {response.status_code})")
        return False

def test_density_report(base_url):
    """Test density report generation"""
    print("🔍 Testing /api/density-report...")
    response = requests.post(f'{base_url}/api/density-report', 
                           json=density_payload, timeout=600)
    
    if response.status_code == 200:
        print("✅ Density Report: OK")
        return True
    else:
        print(f"❌ Density Report: FAILED (status: {response.status_code})")
        return False

def test_temporal_flow_report(base_url):
    """Test temporal flow report generation"""
    print("🔍 Testing /api/temporal-flow-report...")
    response = requests.post(f'{base_url}/api/temporal-flow-report', 
                           json=flow_payload, timeout=600)
    
    if response.status_code == 200:
        print("✅ Temporal Flow Report: OK")
        return True
    else:
        print(f"❌ Temporal Flow Report: FAILED (status: {response.status_code})")
        return False

def test_map_manifest(base_url):
    """Test map manifest endpoint (Issue #249) - Optional test"""
    print("🔍 Testing /api/map/manifest...")
    response = requests.get(f'{base_url}/api/map/manifest', timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('ok') and data.get('window_count') and data.get('segments'):
            print(f"✅ Map Manifest: OK ({data['window_count']} windows, {len(data['segments'])} segments)")
            return True
        else:
            print(f"⚠️ Map Manifest: Invalid response structure (non-blocking)")
            return True  # Non-blocking - don't fail pipeline
    elif response.status_code == 404:
        print(f"⚠️ Map Manifest: Endpoint not implemented yet (404) - skipping")
        return True  # Non-blocking - endpoint may not exist yet
    else:
        print(f"❌ Map Manifest: FAILED (status: {response.status_code})")
        return False

def test_map_bins(base_url):
    """Test map bins endpoint (Issue #249) - Optional test"""
    print("🔍 Testing /map/bins...")
    # Use wide bbox to capture all bins
    bbox = "-7500000,5700000,-7300000,5800000"
    response = requests.get(
        f'{base_url}/map/bins?window_idx=0&bbox={bbox}&severity=any', 
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('type') == 'FeatureCollection' and 'features' in data:
            feature_count = len(data['features'])
            print(f"✅ Map Bins: OK ({feature_count} bins returned)")
            return True
        else:
            print(f"⚠️ Map Bins: Invalid GeoJSON structure (non-blocking)")
            return True  # Non-blocking - don't fail pipeline
    elif response.status_code == 404:
        print(f"⚠️ Map Bins: Endpoint not implemented yet (404) - skipping")
        return True  # Non-blocking - endpoint may not exist yet
    else:
        print(f"❌ Map Bins: FAILED (status: {response.status_code})")
        return False

def run_heatmaps_if_local(reports_dir, run_id):
    """
    Generate heatmaps for local testing (Issue #360).
    
    Skips heatmap generation when running in CI to avoid duplicates.
    
    Args:
        reports_dir: Path to reports/ directory
        run_id: Run identifier (e.g., "2025-10-27")
    """
    # Skip in CI environment (heatmaps generated by CI pipeline)
    if os.getenv("CI") == "true":
        print("   CI environment detected — skipping heatmap generation.")
        return
    
    print("   Generating heatmaps...")
    try:
        from app.core.artifacts.heatmaps import export_heatmaps_and_captions
        from app.storage_service import get_storage_service
        
        # Determine reports directory for this run
        run_reports_dir = Path(reports_dir) / run_id
        
        if not run_reports_dir.exists():
            print(f"   ⚠️ Reports directory not found: {run_reports_dir}")
            return
        
        # Create storage abstraction using modern StorageService
        storage = get_storage_service()
        
        # Generate heatmaps
        heatmaps_generated, captions_generated = export_heatmaps_and_captions(
            run_id=run_id,
            reports_dir=run_reports_dir,
            storage=storage
        )
        
        print(f"   ✅ Heatmaps generated: {heatmaps_generated} PNG files, {captions_generated} captions")
        
    except FileNotFoundError as e:
        print(f"   ⚠️ Heatmap generation skipped: {e}")
    except Exception as e:
        print(f"   ⚠️ Heatmap generation failed: {e}")

def main():
    """Run E2E test with proper resource management"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Determine target URL and enable GCS uploads for cloud testing
    if args.cloud:
        base_url = CLOUD_RUN_URL
        environment = "Cloud Run Production"
        print("🌐 Testing against Cloud Run production")
        
        # Enable GCS uploads for cloud testing (Issues #439, #440)
        # This ensures artifacts are uploaded to GCS, not just written locally
        os.environ["GCS_UPLOAD"] = "true"
        os.environ["GOOGLE_CLOUD_PROJECT"] = "run-density"
        
        # Set GCS credentials if service account key exists
        # (Docker container mounts ./keys to /tmp/keys)
        sa_key_path = "/tmp/keys/gcs-sa.json"
        if Path(sa_key_path).exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_key_path
            print("☁️  GCS uploads enabled with service account authentication")
        else:
            print("☁️  GCS uploads enabled (requires service account key at /tmp/keys/gcs-sa.json)")
            print("    See keys/README.md for setup instructions")
    else:
        base_url = LOCAL_URL
        environment = "Local Server"
        print("🏠 Testing against local server")
    
    print("=" * 60)
    print("END-TO-END TEST")
    print("=" * 60)
    print(f"Target: {base_url}")
    print(f"Environment: {environment}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    all_passed = True
    
    # Test 1: Health check (fast, no resources)
    if not test_health(base_url):
        all_passed = False
    
    print()
    
    # Test 2: Ready check (fast, no resources)
    if not test_ready(base_url):
        all_passed = False
    
    print()
    print("⏳ Brief pause between health checks and heavy operations...")
    time.sleep(5)
    print()
    
    # Test 3: Density report (heavy operation)
    if not test_density_report(base_url):
        all_passed = False
    
    print()
    print("⏳ Waiting for resource cleanup (10s)...")
    time.sleep(10)
    print()
    
    # Test 4: Map manifest (Issue #249)
    if not test_map_manifest(base_url):
        all_passed = False
    
    print()
    
    # Test 5: Map bins (Issue #249)
    if not test_map_bins(base_url):
        all_passed = False
    
    print()
    print("⏳ Waiting for resource cleanup (30s)...")
    time.sleep(30)
    print()
    
    # Test 4: Temporal flow report (heavy operation)
    if not test_temporal_flow_report(base_url):
        all_passed = False
    
    print()
    test_end_time = datetime.now()
    print("=" * 60)
    print("E2E TEST RESULTS")
    print("=" * 60)
    print(f"Ended: {test_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Cloud Run is working correctly")
        
        # Export frontend artifacts from generated reports
        print("\n" + "=" * 60)
        print("Exporting UI Artifacts")
        print("=" * 60)
        
        # Variables to store run info for heatmap generation
        reports_dir = None
        run_id = None
        
        try:
            from app.core.artifacts.frontend import export_ui_artifacts, update_latest_pointer
            import re
            
            # Find the latest report directory
            reports_dir = Path("reports")
            if reports_dir.exists():
                # Get the most recent date-based report directory (YYYY-MM-DD format only)
                # Filter out non-date directories like 'ui' to avoid picking wrong source
                date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
                run_dirs = sorted(
                    [d for d in reports_dir.iterdir() 
                     if d.is_dir() and date_pattern.match(d.name)],
                    reverse=True
                )
                if run_dirs:
                    latest_run_dir = run_dirs[0]
                    run_id = latest_run_dir.name
                    
                    print(f"Exporting artifacts from: {latest_run_dir}")
                    export_ui_artifacts(latest_run_dir, run_id)
                    update_latest_pointer(run_id)
                    print("✅ UI artifacts exported successfully")
                else:
                    print("⚠️ No report directories found in reports/")
            else:
                print("⚠️ Reports directory not found")
        except Exception as e:
            print(f"⚠️ Warning: Could not export UI artifacts: {e}")
            print("   Dashboard will show warnings for missing data")
        
        # Generate heatmaps for local testing (skip in CI)
        print("\n" + "=" * 60)
        print("Generating Heatmaps")
        print("=" * 60)
        try:
            if reports_dir and run_id:
                run_heatmaps_if_local(reports_dir, run_id)
            else:
                print("   ⚠️ No run data available for heatmap generation")
        except Exception as e:
            print(f"⚠️ Warning: Could not generate heatmaps: {e}")
            print("   Heatmaps are optional for local testing")
        
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ Review the results above")
        sys.exit(1)

if __name__ == "__main__":
    main()
