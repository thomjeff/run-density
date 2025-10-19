"""
Environment-Aware Storage Adapter for Run-Density (RF-FE-002)

Provides unified interface for reading files from local filesystem or GCS.
Ensures identical behavior across Local and Cloud Run environments.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 3
Architecture: Option 3 - Hybrid Approach
"""

from typing import Literal, List, Optional, Dict, Any
from pathlib import Path
import json
import os
import time

# Single source of truth for dataset paths
DATASET = {
    "meta": "data/meta.json",
    "segments": "data/segments.geojson", 
    "metrics": "data/segment_metrics.json",
    "flags": "data/flags.json",
}


class Storage:
    """
    Unified storage interface supporting local filesystem and Google Cloud Storage.
    
    Environment Variables:
        RUNFLOW_ENV: "local" or "cloud" (determines mode)
        DATA_ROOT: Root directory for local mode (e.g., "./data")
        GCS_BUCKET: Bucket name for cloud mode
        GCS_PREFIX: Optional prefix for GCS paths
    
    Example:
        # Local mode
        storage = Storage(mode="local", root="./data")
        meta = storage.read_json("meta.json")
        
        # Cloud mode
        storage = Storage(mode="gcs", bucket="run-density-data", prefix="current")
        meta = storage.read_json("meta.json")
    """
    
    def __init__(
        self,
        mode: Literal["local", "gcs"],
        root: Optional[str] = None,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None
    ):
        """
        Initialize storage adapter.
        
        Args:
            mode: "local" for filesystem, "gcs" for Google Cloud Storage
            root: Root directory for local mode
            bucket: GCS bucket name for cloud mode
            prefix: Optional GCS path prefix
        """
        self.mode = mode
        self.root = Path(root) if root else None
        self.bucket = bucket
        self.prefix = prefix
        
        # Lazy import GCS client (only for cloud mode)
        if self.mode == "gcs":
            from google.cloud import storage as gcs
            self._gcs = gcs.Client()
            self._bkt = self._gcs.bucket(self.bucket)
    
    def _full_local(self, path: str) -> Path:
        """Get full local path from relative path."""
        assert self.root is not None, "root must be set for local mode"
        return (self.root / path).resolve()
    
    def read_json(self, path: str) -> Dict[str, Any]:
        """
        Read and parse JSON file.
        
        Args:
            path: Relative path to JSON file
            
        Returns:
            dict: Parsed JSON content
        """
        if self.mode == "local":
            return json.loads(self.read_text(path))
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        return json.loads(blob.download_as_text())
    
    def read_text(self, path: str) -> str:
        """
        Read file as text.
        
        Args:
            path: Relative path to file
            
        Returns:
            str: File contents as UTF-8 text
        """
        if self.mode == "local":
            return self._full_local(path).read_text(encoding="utf-8")
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        return blob.download_as_text()
    
    def read_bytes(self, path: str) -> bytes:
        """
        Read file as bytes (for binary files like PNGs).
        
        Args:
            path: Relative path to file
            
        Returns:
            bytes: File contents as raw bytes
        """
        if self.mode == "local":
            return self._full_local(path).read_bytes()
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        return blob.download_as_bytes()  # noqa
    
    def exists(self, path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            path: Relative path to file
            
        Returns:
            bool: True if file exists
        """
        if self.mode == "local":
            return self._full_local(path).exists()
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        return blob.exists()
    
    def mtime(self, path: str) -> float:
        """
        Get file modification time.
        
        Args:
            path: Relative path to file
            
        Returns:
            float: Modification time as epoch seconds (0.0 if not exists)
        """
        if self.mode == "local":
            p = self._full_local(path)
            return p.stat().st_mtime if p.exists() else 0.0
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        if not blob.exists():
            return 0.0
        # GCS updated time → epoch seconds
        updated = blob.reload() or blob.updated  # ensure metadata
        return blob.updated.timestamp() if blob.updated else 0.0
    
    def list_paths(self, prefix: str) -> List[str]:
        """
        List all files under a path prefix.
        
        Args:
            prefix: Directory prefix to list
            
        Returns:
            list: Relative paths of all files found
        """
        if self.mode == "local":
            base = self._full_local(prefix)
            if not base.exists():
                return []
            out = []
            for root, _, files in os.walk(base):
                for f in files:
                    rel = Path(root, f).relative_to(self.root)
                    out.append(str(rel).replace("\\", "/"))
            return out
        # GCS
        base = f"{self.prefix}/{prefix}" if self.prefix else prefix
        return [b.name for b in self._gcs.list_blobs(self.bucket, prefix=base)]


# ===== Helper Functions =====

def create_storage_from_env() -> Storage:
    """
    Create Storage instance from environment variables.
    
    Environment Variables:
        RUNFLOW_ENV: "local" or "cloud"
        DATA_ROOT: Root directory for local mode (default: "./data")
        GCS_BUCKET: Bucket name for cloud mode
        GCS_PREFIX: Optional prefix for GCS paths
    
    Returns:
        Storage: Configured storage instance
    """
    env = os.getenv("RUNFLOW_ENV", "local")
    
    if env == "local":
        root = os.getenv("DATA_ROOT", "./data")
        return Storage(mode="local", root=root)
    else:
        bucket = os.getenv("GCS_BUCKET")
        prefix = os.getenv("GCS_PREFIX", "")
        if not bucket:
            raise ValueError("GCS_BUCKET environment variable required for cloud mode")
        return Storage(mode="gcs", bucket=bucket, prefix=prefix)


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


def get_heatmap_path(segment_id: str) -> str:
    """Get expected heatmap PNG path for a segment."""
    return f"heatmaps/{segment_id}.png"


def heatmap_exists(storage: Storage, segment_id: str) -> bool:
    """Check if heatmap PNG exists for a segment."""
    try:
        return storage.exists(get_heatmap_path(segment_id))
    except Exception:
        return False

