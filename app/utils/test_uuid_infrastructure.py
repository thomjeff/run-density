#!/usr/bin/env python3
"""
Test Script for UUID Infrastructure (Epic #444 Phase 1)

Validates:
- UUID generation works
- Metadata creation works
- File structure expectations
- No path changes yet (Phase 1 only adds infrastructure)
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.run_id import generate_run_id, validate_run_id, is_legacy_date_format
from app.utils.metadata import (
    create_run_metadata,
    write_metadata_json,
    mark_run_complete
)
from app.utils.env import detect_runtime_environment, detect_storage_target
from app.utils.constants import RUN_ID_MIN_LENGTH


def test_uuid_generation():
    """Test UUID generation."""
    print("\n" + "=" * 60)
    print("Test 1: UUID Generation")
    print("=" * 60)

    # Generate default UUID
    run_id = generate_run_id()
    print(f"✅ Generated UUID: {run_id}")
    print(f"   Length: {len(run_id)} characters")
    assert len(run_id) >= RUN_ID_MIN_LENGTH, f"UUID too short: {len(run_id)} < {RUN_ID_MIN_LENGTH}"

    # Generate 10-char UUID
    run_id_short = generate_run_id(length=10)
    print(f"✅ Generated 10-char UUID: {run_id_short}")
    assert len(run_id_short) == 10, f"UUID length mismatch: {len(run_id_short)} != 10"

    # Test uniqueness
    uuids = set()
    for i in range(100):
        uuid = generate_run_id()
        uuids.add(uuid)

    print(f"✅ Generated 100 UUIDs, all unique: {len(uuids) == 100}")
    assert len(uuids) == 100, "UUID collision detected!"

    return run_id


def test_uuid_validation():
    """Test UUID validation."""
    print("\n" + "=" * 60)
    print("Test 2: UUID Validation")
    print("=" * 60)

    # Valid UUIDs
    assert validate_run_id("p0ZoB1FwH6yT2d") == True
    print("✅ Valid UUID accepted: p0ZoB1FwH6yT2d")

    assert validate_run_id("fX29Kd81vQ") == True
    print("✅ Valid UUID accepted: fX29Kd81vQ")

    # Invalid UUIDs
    assert validate_run_id("2025-11-02") == False
    print("✅ Legacy date rejected: 2025-11-02")

    assert validate_run_id("abc") == False
    print("✅ Too short rejected: abc")

    assert validate_run_id("") == False
    print("✅ Empty string rejected")

    assert validate_run_id(None) == False
    print("✅ None rejected")


def test_legacy_detection():
    """Test legacy date format detection."""
    print("\n" + "=" * 60)
    print("Test 3: Legacy Date Detection")
    print("=" * 60)

    assert is_legacy_date_format("2025-11-02") == True
    print("✅ Detected legacy format: 2025-11-02")

    assert is_legacy_date_format("p0ZoB1FwH6") == False
    print("✅ UUID not detected as legacy: p0ZoB1FwH6")


def test_environment_detection():
    """Test environment detection."""
    print("\n" + "=" * 60)
    print("Test 4: Environment Detection")
    print("=" * 60)

    runtime_env = detect_runtime_environment()
    storage_target = detect_storage_target()

    print(f"✅ Runtime environment: {runtime_env}")
    print(f"✅ Storage target: {storage_target}")

    assert runtime_env in ["local_docker", "cloud_run"]
    assert storage_target in ["filesystem", "gcs"]


def test_metadata_creation(run_id):
    """Test metadata creation."""
    print("\n" + "=" * 60)
    print("Test 5: Metadata Creation")
    print("=" * 60)

    # Create temporary run directory
    test_run_path = Path("/tmp/test_runflow") / run_id
    test_run_path.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ["reports", "bins", "maps", "heatmaps", "ui"]:
        (test_run_path / subdir).mkdir(exist_ok=True)

    # Create sample files
    (test_run_path / "reports" / "Density.md").write_text("# Test")
    (test_run_path / "reports" / "Flow.csv").write_text("test,data")
    (test_run_path / "ui" / "meta.json").write_text("{}")

    # Create metadata
    metadata = create_run_metadata(run_id, test_run_path, status="in_progress")

    print(f"✅ Created metadata:")
    print(f"   run_id: {metadata['run_id']}")
    print(f"   status: {metadata['status']}")
    print(f"   runtime_env: {metadata['runtime_env']}")
    print(f"   storage_target: {metadata['storage_target']}")
    print(f"   app_version: {metadata['app_version']}")
    print(f"   git_sha: {metadata['git_sha']}")
    print(f"   file_counts: {metadata['file_counts']}")

    # Validate structure
    assert metadata["run_id"] == run_id
    assert metadata["status"] == "in_progress"
    assert "created_at" in metadata
    assert "runtime_env" in metadata
    assert "storage_target" in metadata
    assert "files_created" in metadata
    assert "file_counts" in metadata

    # Validate file counts
    assert metadata["file_counts"]["reports"] == 2  # Density.md, Flow.csv
    assert metadata["file_counts"]["ui"] == 1  # meta.json

    # Write metadata.json
    metadata_path = write_metadata_json(test_run_path, metadata)
    print(f"✅ Written metadata.json: {metadata_path}")
    assert metadata_path.exists()

    # Mark as complete
    completed_path = mark_run_complete(test_run_path)
    print(f"✅ Marked run as complete: {completed_path}")

    # Verify status updated
    import json
    with open(completed_path, 'r') as f:
        updated_metadata = json.load(f)

    assert updated_metadata["status"] == "complete"
    print(f"✅ Status updated to: {updated_metadata['status']}")

    # Cleanup
    import shutil
    shutil.rmtree("/tmp/test_runflow")
    print("✅ Cleanup complete")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UUID Infrastructure Test Suite (Epic #444 Phase 1)")
    print("=" * 60)
    print("\nThis tests UUID generation and metadata.json creation.")
    print("NO path changes in this phase - just infrastructure.")

    try:
        run_id = test_uuid_generation()
        test_uuid_validation()
        test_legacy_detection()
        test_environment_detection()
        test_metadata_creation(run_id)

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nPhase 1 UUID infrastructure is working correctly!")
        print("Ready to proceed to Phase 2: Storage Service Refactor")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
