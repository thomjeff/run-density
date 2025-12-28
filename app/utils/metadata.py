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
from typing import Dict, Any, List, Optional, Literal

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


# ===== Phase 4: Pointer and Index Files (Issue #456) =====

def update_latest_pointer(run_id: str) -> None:
    """
    Update runflow/latest.json to point to the most recent run (Issue #456 Task 1).
    
    This file serves as a lightweight pointer to the latest run, used by future
    GET /api/runs/latest endpoint (Phase 5+).
    
    Atomic write pattern: write to temp file, then rename.
    Works for both local filesystem and GCS (via storage abstraction).
    
    Args:
        run_id: UUID of the completed run
        
    Example:
        update_latest_pointer("G4FAdzseZT3G2gFizftHXX")
        # Writes: { "run_id": "G4FAdzseZT3G2gFizftHXX" }
    """
    # Issue #466 Step 4 Cleanup: Removed GCS imports (local-only)
    from app.utils.constants import RUNFLOW_ROOT_LOCAL, RUNFLOW_ROOT_CONTAINER
    import tempfile
    import shutil
    
    # Issue #466 Step 4 Cleanup: Local-only, dead GCS branch removed
    latest_data = {"run_id": run_id}
    
    # Use container root if in Docker, otherwise use local root
    if Path(RUNFLOW_ROOT_CONTAINER).exists():
        runflow_root = Path(RUNFLOW_ROOT_CONTAINER)
    else:
        runflow_root = Path(RUNFLOW_ROOT_LOCAL)
    runflow_root.mkdir(parents=True, exist_ok=True)
    latest_path = runflow_root / "latest.json"
    
    # Write to temp file first
    with tempfile.NamedTemporaryFile(mode='w', dir=runflow_root, delete=False, suffix='.tmp') as f:
        json.dump(latest_data, f, indent=2)
        temp_path = f.name
    
    # Atomic rename
    shutil.move(temp_path, latest_path)
    print(f"   📌 Updated latest.json → {run_id}")


def append_to_run_index(metadata: Dict[str, Any]) -> None:
    """
    Append run metadata to runflow/index.json (Issue #456 Task 2).
    
    Maintains an append-only log of all runs with their metadata summaries.
    Used by future GET /api/runs endpoint (Phase 5+).
    
    Deduplicates by run_id - if run already exists, skips append.
    
    Issue #566: Loads event_summary from analysis.json and includes it in index entry.
    
    Args:
        metadata: Metadata dictionary from create_run_metadata()
        
    Format:
        [
          { "run_id": "...", "created_at": "...", "file_counts": {...}, "event_summary": {...}, ... },
          { "run_id": "...", "created_at": "...", "file_counts": {...}, "event_summary": {...}, ... }
        ]
    """
    # Issue #466 Step 4 Cleanup: Local-only, dead GCS branch removed
    from app.utils.constants import RUNFLOW_ROOT_LOCAL, RUNFLOW_ROOT_CONTAINER
    
    run_id = metadata.get("run_id")
    
    # Issue #566: Load event_summary from analysis.json
    event_summary = None
    if Path(RUNFLOW_ROOT_CONTAINER).exists():
        runflow_root = Path(RUNFLOW_ROOT_CONTAINER)
    else:
        runflow_root = Path(RUNFLOW_ROOT_LOCAL)
    
    analysis_json_path = runflow_root / run_id / "analysis.json"
    if analysis_json_path.exists():
        try:
            with open(analysis_json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
                event_summary = analysis_data.get("event_summary")
        except (json.JSONDecodeError, Exception) as e:
            # If analysis.json doesn't exist or is invalid, continue without event_summary
            pass
    
    # Extract summary for index (subset of full metadata)
    index_entry = {
        "run_id": run_id,
        "created_at": metadata.get("created_at"),
        "runtime_env": metadata.get("runtime_env"),
        "storage_target": metadata.get("storage_target"),
        "app_version": metadata.get("app_version"),
        "git_sha": metadata.get("git_sha"),
        "file_counts": metadata.get("file_counts", {}),
        "status": metadata.get("status", "complete")
    }
    
    # Issue #566: Add event_summary to index entry if available
    if event_summary is not None:
        index_entry["event_summary"] = event_summary
    
    runflow_root.mkdir(parents=True, exist_ok=True)
    index_path = runflow_root / "index.json"
    
    # Read existing index
    if index_path.exists():
        try:
            index_data = json.loads(index_path.read_text())
            if not isinstance(index_data, list):
                index_data = []
        except (json.JSONDecodeError, Exception):
            index_data = []
    else:
        index_data = []
    
    # Deduplication: Check if run_id already exists
    if any(entry.get("run_id") == run_id for entry in index_data):
        return  # Already indexed, skip
    
    # Append new entry
    index_data.append(index_entry)
    
    # Write back
    index_path.write_text(json.dumps(index_data, indent=2, default=str))
    print(f"   📊 Appended to index.json ({len(index_data)} total runs)")


# ===== Phase 5: API Read Helpers (Issue #460) =====

def get_latest_run_id() -> str:
    """
    Get the most recent run_id from runflow/latest.json.
    
    Issue #466 Step 1: Forwards to centralized implementation in app.utils.run_id.
    This function maintained for backwards compatibility during transition.
    
    Returns:
        run_id string (UUID)
        
    Raises:
        FileNotFoundError: If latest.json doesn't exist
        ValueError: If latest.json is invalid or missing run_id field
        
    Example:
        run_id = get_latest_run_id()
        storage = create_runflow_storage(run_id)
        data = storage.read_json("ui/meta.json")
    """
    # Issue #466 Step 1: Use centralized implementation
    from app.utils.run_id import get_latest_run_id as _get_latest_run_id
    return _get_latest_run_id()


def get_run_index() -> List[Dict[str, Any]]:
    """
    Get the list of all runs from runflow/index.json (Issue #460).
    
    Used by "Multi-run" API endpoints that show recent run summaries.
    
    Returns:
        List of run metadata dictionaries (newest first)
        Returns empty list [] if index.json doesn't exist
        
    Example:
        runs = get_run_index()
        recent_runs = runs[:10]  # Last 10 runs
        return [{"run_id": r["run_id"], "created_at": r["created_at"], ...} for r in recent_runs]
    """
    # Issue #466 Step 4 Cleanup: Local-only, dead GCS branch removed
    from app.utils.constants import RUNFLOW_ROOT_LOCAL, RUNFLOW_ROOT_CONTAINER
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Use container root if in Docker, otherwise use local root
        if Path(RUNFLOW_ROOT_CONTAINER).exists():
            runflow_root = Path(RUNFLOW_ROOT_CONTAINER)
        else:
            runflow_root = Path(RUNFLOW_ROOT_LOCAL)
        
        index_path = runflow_root / "index.json"
        if not index_path.exists():
            logger.warning(f"index.json not found at {index_path}, returning empty list")
            return []
        
        index_data = json.loads(index_path.read_text())
        
        # Validate structure
        if not isinstance(index_data, list):
            logger.warning(f"index.json is not a list, returning empty list")
            return []
        
        # Return in reverse order (newest first)
        return list(reversed(index_data))
    
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error reading index.json: {e}")
        return []

