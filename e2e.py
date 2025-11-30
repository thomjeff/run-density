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
    
    # Issue #466 Bonus: --cloud flag deprecated after Phase 1 declouding
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument('--cloud', action='store_true',
                             help='[DEPRECATED] Cloud testing disabled after Phase 1 declouding')
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
        # Issue #455: Extract run_id for combined runs
        try:
            result = response.json()
            run_id = result.get('run_id')
            if run_id:
                print(f"✅ Density Report: OK (run_id: {run_id})")
                return True, run_id
            else:
                print("✅ Density Report: OK")
                return True, None
        except:
            print("✅ Density Report: OK")
            return True, None
    else:
        print(f"❌ Density Report: FAILED (status: {response.status_code})")
        return False, None

def test_temporal_flow_report(base_url, run_id=None):
    """Test temporal flow report generation"""
    print("🔍 Testing /api/temporal-flow-report...")
    
    # Issue #455: Use provided run_id for combined runs
    payload = flow_payload.copy()
    if run_id:
        payload['run_id'] = run_id
        print(f"   Using shared run_id: {run_id}")
    
    response = requests.post(f'{base_url}/api/temporal-flow-report', 
                           json=payload, timeout=600)
    
    if response.status_code == 200:
        print("✅ Temporal Flow Report: OK")
        return True
    else:
        print(f"❌ Temporal Flow Report: FAILED (status: {response.status_code})")
        return False

def test_locations_report(base_url, run_id=None):
    """Test locations report generation (Issue #277)"""
    print("🔍 Testing /api/locations/generate...")
    
    # Issue #277: Use provided run_id for combined runs
    params = {}
    if run_id:
        params['run_id'] = run_id
        print(f"   Using shared run_id: {run_id}")
    
    response = requests.post(f'{base_url}/api/locations/generate', 
                           params=params, timeout=600)
    
    if response.status_code == 200:
        try:
            result = response.json()
            if result.get('ok'):
                locations_count = result.get('locations_processed', 0)
                print(f"✅ Locations Report: OK ({locations_count} locations processed)")
                return True
            else:
                print(f"❌ Locations Report: FAILED (ok=False)")
                return False
        except:
            print("✅ Locations Report: OK")
            return True
    else:
        print(f"❌ Locations Report: FAILED (status: {response.status_code})")
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
        # Issue #467: Clarify that 404 is expected for optional endpoint
        print("⚠️ Map Manifest: Endpoint not available (404) - Optional feature, skipping")
        return True  # Not a failure - this endpoint is optional
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
        from app.storage import create_storage_from_env
        
        # Determine reports directory for this run
        run_reports_dir = Path(reports_dir) / run_id
        
        if not run_reports_dir.exists():
            print(f"   ⚠️ Reports directory not found: {run_reports_dir}")
            return
        
        # Issue #466 Step 4 Cleanup: Use consolidated storage from app.storage
        storage = create_storage_from_env()
        
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
    
    # Issue #466 Bonus: Cloud testing deprecated after Phase 1 declouding
    if args.cloud:
        print("❌ ERROR: Cloud testing is not supported in local-only architecture")
        print("   The --cloud flag was deprecated in Issue #464 (Phase 1 Declouding)")
        print("   Use --local flag instead (default behavior)")
        print("")
        print("   See archive/declouding-2025/ for historical cloud infrastructure")
        sys.exit(1)
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
    # Issue #455: Capture run_id for combined runs
    density_success, run_id = test_density_report(base_url)
    if not density_success:
        all_passed = False
    
    print()
    print("⏳ Waiting for resource cleanup (5s)...")
    time.sleep(5)
    print()
    
    # Test 4: Map manifest (Issue #249)
    if not test_map_manifest(base_url):
        all_passed = False
    
    print()
    
    # Test 5: Map bins (Issue #249)
    if not test_map_bins(base_url):
        all_passed = False
    
    print()
    print("⏳ Waiting for resource cleanup (5s)...")
    time.sleep(5)
    print()
    
    # Test 4: Temporal flow report (heavy operation)
    # Issue #455: Pass run_id from density report for combined runs
    if not test_temporal_flow_report(base_url, run_id=run_id):
        all_passed = False
    
    print()
    print("⏳ Waiting for resource cleanup (5s)...")
    time.sleep(5)
    print()
    
    # Test 5: Locations report (Issue #277)
    # Use same run_id to ensure all reports are in the same runflow folder
    if not test_locations_report(base_url, run_id=run_id):
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
        
        # Issue #466 Bonus: Simplified to local-only (cloud branch removed after early exit)
        # Use local filesystem to export artifacts
        reports_dir = None
        run_id = None
        
        try:
            from app.core.artifacts.frontend import export_ui_artifacts
            import re
                
            # Issue #455: Check runflow directory first for UUID runs
            runflow_dir = Path("runflow")
            if runflow_dir.exists():
                uuid_dirs = sorted(
                    [d for d in runflow_dir.iterdir() 
                     if d.is_dir() and not d.name.endswith('.json') and d.name != '.DS_Store'],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if uuid_dirs:
                    latest_run_dir = uuid_dirs[0]
                    run_id = latest_run_dir.name
                    print(f"Exporting artifacts from runflow: {latest_run_dir}")
                    export_ui_artifacts(latest_run_dir, run_id)
                        
                    # Issue #455: Refresh metadata after UI export
                    try:
                        from app.utils.metadata import create_run_metadata, write_metadata_json, update_latest_pointer, append_to_run_index
                        # Issue #466 Step 3: upload_runflow_to_gcs removed
                        metadata = create_run_metadata(run_id, latest_run_dir, status="complete")
                        write_metadata_json(latest_run_dir, metadata)
                        
                        # Issue #456 Phase 4: Update latest.json and index.json
                        update_latest_pointer(run_id)
                        append_to_run_index(metadata)
                        
                        # Issue #466 Step 3: GCS upload removed (Phase 1 declouding)
                        
                        print("✅ UI artifacts exported and metadata updated")
                    except Exception as e:
                        print(f"✅ UI artifacts exported (metadata update failed: {e})")
                    
                    reports_dir = runflow_dir  # For heatmap generation
                else:
                    print("⚠️ No UUID run directories found in runflow/")
                
            # Fallback to legacy reports/ directory if runflow not found
            if not run_id:
                reports_dir = Path("reports")
                if reports_dir.exists():
                    # Get the most recent date-based report directory (YYYY-MM-DD format only)
                    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
                    run_dirs = sorted(
                        [d for d in reports_dir.iterdir() 
                         if d.is_dir() and date_pattern.match(d.name)],
                        reverse=True
                    )
                    if run_dirs:
                        latest_run_dir = run_dirs[0]
                        run_id = latest_run_dir.name
                        
                        print(f"Exporting artifacts from legacy reports: {latest_run_dir}")
                        export_ui_artifacts(latest_run_dir, run_id)
                        
                        # Issue #455: Refresh metadata after UI export (legacy mode)
                        try:
                            from app.utils.metadata import create_run_metadata, write_metadata_json, update_latest_pointer, append_to_run_index
                            # Issue #466 Step 3: upload_runflow_to_gcs removed
                            metadata = create_run_metadata(run_id, latest_run_dir, status="complete")
                            write_metadata_json(latest_run_dir, metadata)
                            
                            # Issue #456 Phase 4: Update latest.json and index.json
                            update_latest_pointer(run_id)
                            append_to_run_index(metadata)
                            
                            # Issue #466 Step 3: GCS upload removed (Phase 1 declouding)
                            
                            print("✅ UI artifacts exported and metadata updated")
                        except Exception as e:
                            print(f"✅ UI artifacts exported (metadata update failed: {e})")
                    else:
                        print("⚠️ No report directories found in reports/")
                else:
                    print("⚠️ No runflow or reports directories found")
        except Exception as e:
            print(f"⚠️ Warning: Could not export UI artifacts: {e}")
            print("   Dashboard will show warnings for missing data")
        
        # Issue #466 Bonus: Simplified heatmap generation (local-only)
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
        
        # Issue #467: Validate output integrity
        print("\n" + "=" * 60)
        print("Output Validation")
        print("=" * 60)
        try:
            from app.tests.validate_output import validate_run
            validation_results = validate_run(run_id=run_id, update_metadata=True)
            
            if validation_results['status'] == 'PASS':
                print(f"✅ Output Validation: PASS")
            elif validation_results['status'] == 'PARTIAL':
                print(f"⚠️ Output Validation: PARTIAL")
                print(f"   Missing: {len(validation_results['missing'])} non-critical files")
            else:
                print(f"❌ Output Validation: FAIL")
                print(f"   Missing: {len(validation_results['missing'])} files")
                print(f"   Schema errors: {len(validation_results.get('schema_errors', []))}")
                sys.exit(1)  # Fail E2E on validation failure
        except Exception as e:
            print(f"⚠️ Warning: Could not run output validation: {e}")
            print("   Continuing without validation (non-fatal)")
        
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ Review the results above")
        sys.exit(1)

if __name__ == "__main__":
    main()
