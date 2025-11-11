"""
Local Filesystem Storage Adapter for Run-Density

Provides unified interface for reading files from local filesystem.
Ensures consistent behavior across all environments.

Author: Cursor AI Assistant (per ChatGPT specification)
Architecture: Local-only filesystem approach
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import os
import logging

# Single source of truth for dataset paths
# These paths are relative to the ARTIFACTS_ROOT resolved from latest.json
DATASET = {
    "meta": "meta.json",
    "segments": "segments.geojson", 
    "metrics": "segment_metrics.json",
    "flags": "flags.json",
    "flow": "flow.json",
    "runners": "data/runners.csv"  # Absolute path from project root
}


class Storage:
    """
    Unified storage interface for local filesystem operations.
    
    Environment Variables:
        DATA_ROOT: Root directory for local mode (e.g., "./data")
    
    Example:
        storage = Storage(root="./data")
        meta = storage.read_json("meta.json")
    """
    
    def __init__(self, root: Optional[str] = None):
        """
        Initialize storage adapter.
        
        Args:
            root: Root directory for local mode
        """
        self.mode = "local"
        self.root = Path(root) if root else None
    
    def _full_local(self, path: str) -> Path:
        """Get full local path from relative path."""
        assert self.root is not None, "root must be set for local mode"
        # Issue #460 Phase 5: Remove hardcoded bypass for 'reports/' to support runflow structure
        # For runflow operations, all paths are relative to self.root (e.g., /app/runflow/<uuid>/)
        # Only bypass for data/ and config/ which are truly absolute workspace paths
        if path.startswith(('data/', 'config/')):
            return Path(path).resolve()
        # All other paths are relative to self.root
        return (self.root / path).resolve()
    
    def read_json(self, path: str) -> Dict[str, Any]:
        """
        Read and parse JSON file.
        
        Args:
            path: Relative path to JSON file
            
        Returns:
            dict: Parsed JSON content
        """
        return json.loads(self.read_text(path))
    
    def read_text(self, path: str) -> str:
        """
        Read file as text.
        
        Args:
            path: Relative path to file
            
        Returns:
            str: File contents as UTF-8 text
        """
        return self._full_local(path).read_text(encoding="utf-8")
    
    def read_bytes(self, path: str) -> bytes:
        """
        Read file as bytes (for binary files like PNGs).
        
        Args:
            path: Relative path to file
            
        Returns:
            bytes: File contents as raw bytes
        """
        return self._full_local(path).read_bytes()
    
    def exists(self, path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            path: Relative path to file
            
        Returns:
            bool: True if file exists
        """
        return self._full_local(path).exists()
    
    def mtime(self, path: str) -> float:
        """
        Get file modification time.
        
        Args:
            path: Relative path to file
            
        Returns:
            float: Modification time as epoch seconds (0.0 if not exists)
        """
        p = self._full_local(path)
        return p.stat().st_mtime if p.exists() else 0.0
    
    def size(self, path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            path: Relative path to file
            
        Returns:
            int: File size in bytes (0 if not exists)
        """
        p = self._full_local(path)
        return p.stat().st_size if p.exists() else 0
    
    def list_paths(self, prefix: str) -> List[str]:
        """
        List all files under a path prefix.
        
        Args:
            prefix: Directory prefix to list
            
        Returns:
            list: Relative paths of all files found
        """
        base = self._full_local(prefix)
        if not base.exists():
            return []
        out = []
        for root, _, files in os.walk(base):
            for f in files:
                rel = Path(root, f).relative_to(self.root)
                out.append(str(rel).replace("\\", "/"))
        return out

    def get_heatmap_signed_url(self, segment_id: str, expiry_seconds=3600):
        """Generate local URL for heatmap."""
        run_id = os.getenv("RUN_ID")
        if not run_id:
            try:
                # Issue #470: Read from runflow/latest.json (single source of truth)
                latest_path = Path("runflow/latest.json")
                if latest_path.exists():
                    latest_data = json.loads(latest_path.read_text())
                    run_id = latest_data.get("run_id")
                else:
                    logging.warning("runflow/latest.json not found for run_id")
                    run_id = None
            except Exception as e:
                    logging.warning(f"Could not load runflow/latest.json for run_id: {e}")
                    run_id = None
        
        # Issue #361: Do not fall back to hardcoded date - return None if run_id unavailable
        if not run_id:
            logging.warning("No run_id available - cannot generate heatmap URL. Artifacts missing for current run.")
            return None
        # Issue #470: Heatmaps stored in runflow structure
        return f"/runflow/{run_id}/ui/heatmaps/{segment_id}.png"
    
    # ===== Write Methods (Issue #455 - Phase 3) =====
    
    def write_file(self, path: str, content: str) -> str:
        """
        Write text content to local filesystem.
        
        Args:
            path: Relative path for the file
            content: Text content to write
            
        Returns:
            Full path where file was written
        """
        full_path = self._full_local(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        return str(full_path)
    
    def write_json(self, path: str, data: Dict[str, Any]) -> str:
        """
        Write JSON data to local filesystem.
        
        Args:
            path: Relative path for the JSON file
            data: Dictionary to serialize as JSON
            
        Returns:
            Full path where file was written
        """
        json_content = json.dumps(data, indent=2)
        full_path = self._full_local(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(json_content, encoding='utf-8')
        return str(full_path)
    
    def write_bytes(self, path: str, content: bytes) -> str:
        """
        Write binary content to local filesystem.
        
        Args:
            path: Relative path for the file
            content: Binary content to write
            
        Returns:
            Full path where file was written
        """
        full_path = self._full_local(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(full_path)
    
    def copy_file(self, source_path: Path, dest_path: str) -> str:
        """
        Copy a local file to local filesystem storage.
        
        Args:
            source_path: Path to source file (local filesystem)
            dest_path: Destination path (relative to storage root)
            
        Returns:
            Full path where file was written
        """
        full_dest = self._full_local(dest_path)
        full_dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(source_path, full_dest)
        return str(full_dest)
    
    def read_parquet(self, path: str) -> Optional['pd.DataFrame']:
        """
        Read parquet file from local filesystem.
        
        Issue #466 Step 2: Migrated from storage_service.py for consolidation.
        
        Args:
            path: Relative path to parquet file
            
        Returns:
            DataFrame or None if not found
        """
        try:
            import pandas as pd
            full_path = self._full_local(path)
            if not full_path.exists():
                logger.warning(f"Parquet file not found: {full_path}")
                return None
            return pd.read_parquet(full_path)
        except Exception as e:
            logger.error(f"Failed to read parquet {path}: {e}")
            return None
    
    def read_csv(self, path: str) -> Optional['pd.DataFrame']:
        """
        Read CSV file from local filesystem.
        
        Issue #466 Step 2: Migrated from storage_service.py for consolidation.
        
        Args:
            path: Relative path to CSV file
            
        Returns:
            DataFrame or None if not found
        """
        try:
            import pandas as pd
            full_path = self._full_local(path)
            if not full_path.exists():
                logger.warning(f"CSV file not found: {full_path}")
                return None
            return pd.read_csv(full_path)
        except Exception as e:
            logger.error(f"Failed to read CSV {path}: {e}")
            return None
    
    def read_geojson(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Read GeoJSON file from local filesystem.
        
        Issue #466 Step 2: Migrated from storage_service.py for consolidation.
        
        Args:
            path: Relative path to GeoJSON file
            
        Returns:
            dict or None if not found
        """
        try:
            full_path = self._full_local(path)
            if not full_path.exists():
                logger.warning(f"GeoJSON file not found: {full_path}")
                return None
            return json.loads(full_path.read_text())
        except Exception as e:
            logger.error(f"Failed to read GeoJSON {path}: {e}")
            return None


# ===== Helper Functions =====

def create_runflow_storage(run_id: str) -> Storage:
    """
    Create Storage instance for runflow operations (Issue #455).
    
    Issue #466 Step 1: Uses centralized path resolution from app.utils.run_id.
    
    Args:
        run_id: UUID for the run
        
    Returns:
        Storage instance configured for runflow structure
        
    Example:
        storage = create_runflow_storage("abc123xyz")
        storage.write_json("reports/Density.md", content)
        # Writes to: /users/.../runflow/abc123xyz/reports/Density.md
    """
    # Issue #466 Step 1: Use centralized path resolution
    from app.utils.run_id import get_run_directory
    
    run_dir = get_run_directory(run_id)
    return Storage(root=str(run_dir))


def create_storage_from_env() -> Storage:
    """
    Create Storage instance from environment variables.
    
    Issue #466 Step 1: Uses centralized run_id module for path resolution.
    Resolves runflow/<run_id>/ui/ from runflow/latest.json pointer.
    
    Environment Variables:
        DATA_ROOT: Root directory (default: resolved from runflow/latest.json)
    
    Returns:
        Storage: Configured storage instance
    """
    root = os.getenv("DATA_ROOT")
    
    # Issue #466 Step 1: Use centralized run_id module
    if not root:
        try:
            from app.utils.run_id import get_latest_run_id, get_run_directory
            
            run_id = get_latest_run_id()
            run_dir = get_run_directory(run_id)
            root = str(run_dir / "ui")
        except (FileNotFoundError, ValueError) as e:
            import logging
            logging.warning(f"Could not load latest run_id: {e}")
    
    # Fallback to "./data" if pointer not found
    if not root:
        root = "./data"
    
    return Storage(root=root)


# ===== UI Artifact Helpers (Step 8) =====

def load_latest_run_id(storage: Storage) -> Optional[str]:
    """
    Load the latest run_id from runflow/latest.json.
    
    Issue #466 Step 1: Uses centralized implementation from app.utils.run_id.
    
    Returns:
        Run ID string (e.g., "abc123xyz") or None if not found
    """
    try:
        # Issue #466 Step 1: Use centralized implementation
        from app.utils.run_id import get_latest_run_id
        return get_latest_run_id()
    except (FileNotFoundError, ValueError):
        return None


def list_reports(storage: Storage, run_id: str) -> List[Dict[str, Any]]:
    """
    List all report files for a given run_id.
    
    Args:
        storage: Storage instance
        run_id: Run identifier
    
    Returns:
        List of dicts with name, path, mtime, size
    """
    try:
        # Read from local reports directory
        reports_dir = Path("reports") / run_id
        if not reports_dir.exists():
            return []
        
        files = []
        for file_path in reports_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(Path("reports"))),
                    "mtime": file_path.stat().st_mtime,
                    "size": file_path.stat().st_size
                })
        
        return sorted(files, key=lambda x: x["name"])
            
    except Exception as e:
        import logging
        logging.warning(f"Could not list reports for {run_id}: {e}")
        return []


# Lightweight artifact loading helpers with graceful fallbacks

def load_segments_geojson(storage: Storage) -> Optional[Dict[str, Any]]:
    """Load segments.geojson with graceful fallback."""
    try:
        return storage.read_json("segments.geojson")
    except Exception as e:
        print(f"⚠️  Could not load segments.geojson: {e}")
        return None


def load_segment_metrics(storage: Storage) -> Optional[Dict[str, Any]]:
    """Load segment_metrics.json with graceful fallback."""
    try:
        return storage.read_json("segment_metrics.json")
    except Exception as e:
        print(f"⚠️  Could not load segment_metrics.json: {e}")
        return None


def load_flags(storage: Storage) -> Optional[Dict[str, Any]]:
    """Load flags.json with graceful fallback."""
    try:
        return storage.read_json("flags.json")
    except Exception as e:
        print(f"⚠️  Could not load flags.json: {e}")
        return None


def load_meta(storage: Storage) -> Optional[Dict[str, Any]]:
    """Load meta.json with graceful fallback."""
    try:
        return storage.read_json("meta.json")
    except Exception as e:
        print(f"⚠️  Could not load meta.json: {e}")
        return None


def load_bin_details_csv(storage: Storage, segment_id: str) -> Optional[str]:
    """Load bin_details/<segment_id>.csv with graceful fallback."""
    try:
        return storage.read_text(f"bin_details/{segment_id}.csv")
    except Exception as e:
        print(f"⚠️  Could not load bin_details/{segment_id}.csv: {e}")
        return None
