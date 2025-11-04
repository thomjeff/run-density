"""
Run Metadata Management for UUID-based Run Tracking

Handles creation and management of metadata.json files for each analysis run.
Implements two-phase commit pattern to ensure atomic pointer updates.

Epic: #444 - Refactor Report Run ID System
Phase: 1 - UUID Infrastructure
Phase: 2 - Aligned with Issue #447 environment detection (Issue #452)
"""

import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Issue #452: Delegate to canonical environment detection functions
# These follow the Issue #447 priority order documented in docs/architecture/env-detection.md
from app.utils.env import detect_runtime_environment, detect_storage_target


def get_app_version() -> str:
    """
    Get the application version from app.main module.
    
    Returns:
        Version string (e.g., "v1.7.2")
    """
    try:
        from app.main import app
        return app.version
    except (ImportError, AttributeError):
        return "unknown"


def get_git_sha() -> str:
    """
    Get the current Git commit SHA (short form).
    
    Returns:
        Short Git SHA (e.g., "86d4599") or "unknown" if not in Git repo
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def count_files_in_directory(directory: Path) -> int:
    """
    Count files in a directory (non-recursive).
    
    Args:
        directory: Path to directory
    
    Returns:
        Number of files (0 if directory doesn't exist)
    """
    if not directory.exists() or not directory.is_dir():
        return 0
    
    return len([f for f in directory.iterdir() if f.is_file()])


def generate_file_lists(run_path: Path) -> Dict[str, List[str]]:
    """
    Generate file lists for each subdirectory in a run folder.
    
    Args:
        run_path: Path to run directory (e.g., runflow/p0ZoB1FwH6/)
    
    Returns:
        Dictionary mapping subdirectory names to file lists
    """
    file_lists = {}
    
    subdirs = ["reports", "bins", "maps", "heatmaps", "ui"]
    
    for subdir in subdirs:
        subdir_path = run_path / subdir
        if subdir_path.exists():
            files = [f.name for f in subdir_path.iterdir() if f.is_file()]
            file_lists[subdir] = sorted(files)  # Sort for consistency
        else:
            file_lists[subdir] = []
    
    return file_lists


def generate_file_counts(run_path: Path) -> Dict[str, int]:
    """
    Generate file counts for each subdirectory in a run folder.
    
    Args:
        run_path: Path to run directory (e.g., runflow/p0ZoB1FwH6/)
    
    Returns:
        Dictionary mapping subdirectory names to file counts
    """
    file_counts = {}
    
    subdirs = ["reports", "bins", "maps", "heatmaps", "ui"]
    
    for subdir in subdirs:
        subdir_path = run_path / subdir
        file_counts[subdir] = count_files_in_directory(subdir_path)
    
    return file_counts


def create_run_metadata(
    run_id: str,
    run_path: Path,
    status: Literal["in_progress", "complete", "failed"] = "in_progress"
) -> Dict[str, Any]:
    """
    Create metadata dictionary for a run.
    
    Args:
        run_id: Short UUID for this run
        run_path: Path to run directory
        status: Run status (default: "in_progress")
    
    Returns:
        Metadata dictionary ready for JSON serialization
    
    Example:
        >>> metadata = create_run_metadata("p0ZoB1FwH6", Path("runflow/p0ZoB1FwH6"))
        >>> metadata["run_id"]
        'p0ZoB1FwH6'
        >>> metadata["status"]
        'in_progress'
    """
    # Generate ISO timestamp in UTC
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Detect environment
    runtime_env = detect_runtime_environment()
    storage_target = detect_storage_target()
    
    # Get version info
    app_version = get_app_version()
    git_sha = get_git_sha()
    
    # Generate file lists and counts
    files_created = generate_file_lists(run_path)
    file_counts = generate_file_counts(run_path)
    
    metadata = {
        "run_id": run_id,
        "created_at": created_at,
        "status": status,
        "runtime_env": runtime_env,
        "storage_target": storage_target,
        "app_version": app_version,
        "git_sha": git_sha,
        "files_created": files_created,
        "file_counts": file_counts
    }
    
    return metadata


def write_metadata_json(run_path: Path, metadata: Dict[str, Any]) -> Path:
    """
    Write metadata.json to run directory.
    
    Args:
        run_path: Path to run directory (e.g., runflow/p0ZoB1FwH6/)
        metadata: Metadata dictionary
    
    Returns:
        Path to written metadata.json file
    
    Raises:
        OSError: If directory doesn't exist or write fails
    """
    if not run_path.exists():
        raise OSError(f"Run directory does not exist: {run_path}")
    
    metadata_path = run_path / "metadata.json"
    
    # Write with pretty formatting
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata_path


def mark_run_complete(run_path: Path) -> Path:
    """
    Mark a run as complete by updating metadata.json status.
    
    This should be called ONLY after all files are successfully generated.
    The presence of status="complete" gates the update of latest.json and
    run_index.json per Epic #444 atomicity requirements.
    
    Args:
        run_path: Path to run directory
    
    Returns:
        Path to updated metadata.json
    
    Raises:
        FileNotFoundError: If metadata.json doesn't exist
        OSError: If write fails
    """
    metadata_path = run_path / "metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")
    
    # Read existing metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Update status and regenerate file lists/counts
    metadata["status"] = "complete"
    metadata["files_created"] = generate_file_lists(run_path)
    metadata["file_counts"] = generate_file_counts(run_path)
    
    # Write updated metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata_path


def mark_run_failed(run_path: Path, error: Optional[str] = None) -> Path:
    """
    Mark a run as failed by updating metadata.json status.
    
    Args:
        run_path: Path to run directory
        error: Optional error message to include
    
    Returns:
        Path to updated metadata.json
    """
    metadata_path = run_path / "metadata.json"
    
    if not metadata_path.exists():
        # Create minimal metadata for failed run
        metadata = {
            "run_id": run_path.name,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "failed",
            "runtime_env": detect_runtime_environment(),
            "storage_target": detect_storage_target(),
            "app_version": get_app_version(),
            "git_sha": get_git_sha()
        }
        if error:
            metadata["error"] = error
    else:
        # Update existing metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        metadata["status"] = "failed"
        if error:
            metadata["error"] = error
    
    # Write metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    return metadata_path


def read_run_metadata(run_path: Path) -> Optional[Dict[str, Any]]:
    """
    Read metadata.json from a run directory.
    
    Args:
        run_path: Path to run directory
    
    Returns:
        Metadata dictionary or None if file doesn't exist
    """
    metadata_path = run_path / "metadata.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        import logging
        logging.warning(f"Could not read metadata.json from {run_path}: {e}")
        return None

