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
    
# Phase 3 cleanup: Removed unused methods (never called):
# - mtime() - Only 33.3% coverage (definition only), code uses stat.st_mtime directly
# - size() - Only 33.3% coverage (definition only), code uses stat.st_size directly
# - list_paths() - Only 10.0% coverage (definition only), never called

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
        # Issue #580: Updated path to visualizations/heatmaps/ subdirectory
        return f"/runflow/{run_id}/ui/visualizations/heatmaps/{segment_id}.png"
    
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
    
    # Phase 3 cleanup: Removed unused method copy_file() - Only 16.7% coverage (definition only), never called
    
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
    
    # Phase 3 cleanup: Removed unused methods (never called, code uses pd.read_csv() and json.loads() directly):
    # - read_csv() - Only 9.1% coverage (definition only), code uses pd.read_csv() directly
    # - read_geojson() - Only 10.0% coverage (definition only), code uses json.loads() directly


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


# Phase 3 cleanup: Removed unused helper functions (never imported or called):
# - create_storage_from_env() - Only 7.1% coverage (definition only), never imported
# - load_latest_run_id() - Only 16.7% coverage (definition only), never imported (use get_latest_run_id() directly)
# - list_reports() - Only 7.1% coverage (definition only), never imported
# - load_segments_geojson() - Only 16.7% coverage (definition only), never imported
# - load_segment_metrics() - Only 16.7% coverage (definition only), never imported
# - load_flags() - Only 16.7% coverage (definition only), never imported
# - load_meta() - Only 16.7% coverage (definition only), never imported
# - load_bin_details_csv() - Only 16.7% coverage (definition only), never imported
