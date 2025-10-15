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

# Configuration
CLOUD_RUN_URL = "https://run-density-ln4r3sfkha-uc.a.run.app"
LOCAL_URL = "http://localhost:8080"
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
    response = requests.get(f'{base_url}/health', timeout=10)
    
    if response.status_code == 200:
        print("✅ Health: OK")
        return True
    else:
        print(f"❌ Health: FAILED (status: {response.status_code})")
        return False

def test_ready(base_url):
    """Test ready endpoint"""
    print("🔍 Testing /ready...")
    response = requests.get(f'{base_url}/ready', timeout=10)
    
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
                           json=density_payload, timeout=300)
    
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
                           json=flow_payload, timeout=300)
    
    if response.status_code == 200:
        print("✅ Temporal Flow Report: OK")
        return True
    else:
        print(f"❌ Temporal Flow Report: FAILED (status: {response.status_code})")
        return False

def main():
    """Run E2E test with proper resource management"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Determine target URL
    if args.cloud:
        base_url = CLOUD_RUN_URL
        environment = "Cloud Run Production"
        print("🌐 Testing against Cloud Run production")
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
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ Review the results above")
        sys.exit(1)

if __name__ == "__main__":
    main()
