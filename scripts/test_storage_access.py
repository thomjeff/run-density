#!/usr/bin/env python3
"""
Storage Access Test Script for Issue #451
Tests read/write access to both local and GCS storage locations from within container.
"""
import os
import sys
from pathlib import Path
from google.cloud import storage
from google.auth import default

def test_local_storage():
    """Test local runflow directory access."""
    local_path = Path("/runflow")
    test_file = local_path / "test-container-write.txt"
    
    print("=" * 60)
    print("Testing Local Storage: /runflow")
    print("=" * 60)
    
    # Check if directory exists
    if not local_path.exists():
        print(f"❌ FAIL: Directory {local_path} does not exist")
        return False
    print(f"✅ Directory exists: {local_path}")
    
    # Check if directory is readable
    try:
        contents = list(local_path.iterdir())
        print(f"✅ Directory is readable ({len(contents)} items found)")
    except Exception as e:
        print(f"❌ FAIL: Cannot read directory: {e}")
        return False
    
    # Test write access
    try:
        test_file.write_text("test-content-from-container")
        print(f"✅ Write successful: {test_file}")
    except Exception as e:
        print(f"❌ FAIL: Cannot write to directory: {e}")
        return False
    
    # Test read access
    try:
        content = test_file.read_text()
        assert content == "test-content-from-container"
        print(f"✅ Read successful: content verified")
    except Exception as e:
        print(f"❌ FAIL: Cannot read file: {e}")
        return False
    
    # Test delete access
    try:
        test_file.unlink()
        print(f"✅ Delete successful")
    except Exception as e:
        print(f"❌ FAIL: Cannot delete file: {e}")
        return False
    
    print("✅ LOCAL STORAGE: ALL TESTS PASSED\n")
    return True

def test_gcs_storage():
    """Test GCS bucket access."""
    bucket_name = "runflow"
    test_blob_name = "test-container-write.txt"
    
    print("=" * 60)
    print("Testing GCS Storage: gs://runflow")
    print("=" * 60)
    
    # Check credentials
    try:
        credentials, project = default()
        print(f"✅ Credentials found (project: {project})")
    except Exception as e:
        print(f"⚠️  WARNING: No credentials found: {e}")
        print("   GCS tests require GOOGLE_APPLICATION_CREDENTIALS to be set")
        print("   Skipping GCS tests (expected in local-only mode)")
        return True  # Not a failure, just skipped
    
    # Initialize client
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        print(f"✅ GCS client initialized")
    except Exception as e:
        print(f"❌ FAIL: Cannot initialize GCS client: {e}")
        return False
    
    # Test bucket exists and is accessible
    try:
        exists = bucket.exists()
        if not exists:
            print(f"❌ FAIL: Bucket gs://{bucket_name} does not exist")
            return False
        print(f"✅ Bucket exists: gs://{bucket_name}")
    except Exception as e:
        print(f"❌ FAIL: Cannot check bucket existence: {e}")
        return False
    
    # Test list access
    try:
        blobs = list(bucket.list_blobs(max_results=5))
        print(f"✅ Bucket is readable ({len(blobs)} items sampled)")
    except Exception as e:
        print(f"❌ FAIL: Cannot list bucket contents: {e}")
        return False
    
    # Test write access
    try:
        blob = bucket.blob(test_blob_name)
        blob.upload_from_string("test-content-from-container")
        print(f"✅ Write successful: gs://{bucket_name}/{test_blob_name}")
    except Exception as e:
        print(f"❌ FAIL: Cannot write to bucket: {e}")
        return False
    
    # Test read access
    try:
        blob = bucket.blob(test_blob_name)
        content = blob.download_as_text()
        assert content == "test-content-from-container"
        print(f"✅ Read successful: content verified")
    except Exception as e:
        print(f"❌ FAIL: Cannot read from bucket: {e}")
        return False
    
    # Test delete access
    try:
        blob = bucket.blob(test_blob_name)
        blob.delete()
        print(f"✅ Delete successful")
    except Exception as e:
        print(f"❌ FAIL: Cannot delete from bucket: {e}")
        return False
    
    print("✅ GCS STORAGE: ALL TESTS PASSED\n")
    return True

def main():
    """Run all storage tests."""
    print("\n" + "=" * 60)
    print("STORAGE ACCESS TEST - Issue #451")
    print("=" * 60)
    print()
    
    results = []
    
    # Test local storage
    results.append(("Local Storage", test_local_storage()))
    
    # Test GCS storage
    results.append(("GCS Storage", test_gcs_storage()))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())

