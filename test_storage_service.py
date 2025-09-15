#!/usr/bin/env python3
"""
Test script for Storage Service Module

This script tests the storage service in both local and Cloud Storage modes.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.storage_service import StorageService, StorageConfig, get_storage_service
import json

def test_local_storage():
    """Test local file system storage."""
    print("🧪 Testing Local Storage...")
    
    # Force local mode
    config = StorageConfig(use_cloud_storage=False)
    storage = StorageService(config)
    
    # Test data
    test_data = {
        "test": "data",
        "timestamp": "2025-09-15",
        "values": [1, 2, 3]
    }
    
    # Test JSON save/load
    filename = "test_map_data.json"
    print(f"  Saving {filename}...")
    path = storage.save_json(filename, test_data)
    print(f"  Saved to: {path}")
    
    print(f"  Loading {filename}...")
    loaded_data = storage.load_json(filename)
    print(f"  Loaded: {loaded_data}")
    
    # Test file existence
    exists = storage.file_exists(filename)
    print(f"  File exists: {exists}")
    
    # Test file listing
    files = storage.list_files()
    print(f"  Files in directory: {files}")
    
    print("✅ Local storage test completed")

def test_cloud_storage():
    """Test Cloud Storage (if available)."""
    print("🧪 Testing Cloud Storage...")
    
    try:
        # Try to use Cloud Storage
        config = StorageConfig(use_cloud_storage=True)
        storage = StorageService(config)
        
        # Test data
        test_data = {
            "test": "cloud_data",
            "timestamp": "2025-09-15",
            "environment": "cloud_run"
        }
        
        # Test JSON save/load
        filename = "test_cloud_map_data.json"
        print(f"  Saving {filename} to Cloud Storage...")
        path = storage.save_json(filename, test_data)
        print(f"  Saved to: {path}")
        
        print(f"  Loading {filename} from Cloud Storage...")
        loaded_data = storage.load_json(filename)
        print(f"  Loaded: {loaded_data}")
        
        # Test file existence
        exists = storage.file_exists(filename)
        print(f"  File exists: {exists}")
        
        print("✅ Cloud storage test completed")
        
    except Exception as e:
        print(f"❌ Cloud storage test failed: {e}")
        print("  This is expected if not running in Cloud Run environment")

def test_environment_detection():
    """Test automatic environment detection."""
    print("🧪 Testing Environment Detection...")
    
    storage = get_storage_service()
    print(f"  Using Cloud Storage: {storage.config.use_cloud_storage}")
    print(f"  Bucket name: {storage.config.bucket_name}")
    print(f"  Local reports dir: {storage.config.local_reports_dir}")
    
    print("✅ Environment detection test completed")

if __name__ == "__main__":
    print("🚀 Starting Storage Service Tests")
    print("=" * 50)
    
    test_environment_detection()
    print()
    
    test_local_storage()
    print()
    
    test_cloud_storage()
    print()
    
    print("🎉 All tests completed!")
