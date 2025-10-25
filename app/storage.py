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
from datetime import timedelta
import datetime
import logging
from google.cloud import storage
import google.auth
from google.auth import impersonated_credentials

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
            self.client = self._gcs  # For heatmap URL generation
    
    def _full_local(self, path: str) -> Path:
        """Get full local path from relative path."""
        assert self.root is not None, "root must be set for local mode"
        # Handle absolute paths (starting with data/, config/, etc.)
        if path.startswith(('data/', 'config/', 'reports/')):
            return Path(path).resolve()
        # Handle relative paths from artifacts root
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
    
    def size(self, path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            path: Relative path to file
            
        Returns:
            int: File size in bytes (0 if not exists)
        """
        if self.mode == "local":
            p = self._full_local(path)
            return p.stat().st_size if p.exists() else 0
        blob = self._bkt.blob(f"{self.prefix}/{path}" if self.prefix else path)
        if not blob.exists():
            return 0
        # GCS size
        blob.reload()  # ensure metadata
        return blob.size or 0
    
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

    def get_heatmap_signed_url(self, segment_id: str, expiry_seconds=3600):
        """Generate signed URL for heatmap using service account key."""
        if self.mode == "local":
            # For local mode, return the local path
            run_id = os.getenv("RUN_ID")
            if not run_id:
                try:
                    latest_data = self.read_json("latest.json")
                    run_id = latest_data.get("run_id", "2025-10-25")
                except Exception as e:
                        logging.warning(f"Could not load latest.json for run_id: {e}")
                        run_id = "2025-10-25"
            return f"/artifacts/{run_id}/ui/heatmaps/{segment_id}.png"
        
        # For GCS mode, use service account key for signing
        try:
            # Try to use the service account key file
            key_file = "/tmp/run-density-web-key.json"
            if os.path.exists(key_file):
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(key_file)
                logging.info("Using service account key file for signed URL generation")
            else:
                # Fallback to default credentials
                creds, project = google.auth.default()
                logging.info("Using default credentials for signed URL generation")
        except Exception as e:
            logging.warning(f"Could not load service account key: {e}")
            creds, project = google.auth.default()
        
        client = storage.Client(credentials=creds, project=project)
        bucket = client.bucket(self.bucket)
        
        # Get run_id for blob path
        run_id = os.getenv("RUN_ID")
        if not run_id:
            try:
                latest_data = self.read_json("latest.json")
                run_id = latest_data.get("run_id", "current")
            except Exception as e:
                logging.warning(f"Could not load latest.json for run_id: {e}")
                run_id = "current"
        
        blob_path = f"artifacts/{run_id}/ui/heatmaps/{segment_id}.png"
        blob = bucket.blob(blob_path)
        
        return blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=expiry_seconds),
            method="GET",
        )


# ===== Helper Functions =====

def create_storage_from_env() -> Storage:
    """
    Create Storage instance from environment variables.
    
    Resolves artifacts/<run_id>/ui/ from artifacts/latest.json pointer.
    
    Environment Variables:
        K_SERVICE or GOOGLE_CLOUD_PROJECT: Auto-detected for Cloud Run
        DATA_ROOT: Root directory for local mode (default: resolved from artifacts/latest.json)
        GCS_BUCKET: Bucket name for cloud mode (default: run-density-reports)
        GCS_PREFIX: Optional prefix for GCS paths (default: artifacts)
    
    Returns:
        Storage: Configured storage instance
    """
    # Auto-detect Cloud Run environment (same as storage_service.py)
    is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    env = "cloud" if is_cloud else "local"
    
    if env == "local":
        root = os.getenv("DATA_ROOT")
        
        # Try to resolve from artifacts/latest.json pointer
        if not root:
            latest_pointer = Path("artifacts/latest.json")
            if latest_pointer.exists():
                try:
                    pointer_data = json.loads(latest_pointer.read_text())
                    run_id = pointer_data.get("run_id")
                    if run_id:
                        root = f"artifacts/{run_id}/ui"
                except Exception as e:
                    import logging
                    logging.warning(f"Could not read artifacts/latest.json: {e}")
        
        # Fallback to "./data" if pointer not found
        if not root:
            root = "./data"
        
        return Storage(mode="local", root=root)
    else:
        # Cloud Run mode - use GCS with defaults
        bucket = os.getenv("GCS_BUCKET", "run-density-reports")
        prefix = os.getenv("GCS_PREFIX", "artifacts")
        return Storage(mode="gcs", bucket=bucket, prefix=prefix)


# ===== UI Artifact Helpers (Step 8) =====

def load_latest_run_id(storage: Storage) -> Optional[str]:
    """
    Load the latest run_id from artifacts/latest.json.
    
    Returns:
        Run ID string (e.g., "2025-10-19") or None if not found
    """
    try:
        pointer = storage.read_json("artifacts/latest.json")
        return pointer.get("run_id")
    except Exception:
        # Fallback: try direct read for local mode
        if storage.mode == "local":
            try:
                latest_path = Path("artifacts/latest.json")
                if latest_path.exists():
                    import json
                    return json.loads(latest_path.read_text()).get("run_id")
            except Exception:
                pass
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
    reports_prefix = f"../reports/{run_id}"
    
    try:
        if storage.mode == "local":
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
        else:
            # GCS mode - list blobs
            paths = storage.list_paths(reports_prefix)
            files = []
            for path in paths:
                files.append({
                    "name": Path(path).name,
                    "path": path,
                    "mtime": 0,
                    "size": 0
                })
            return files
            
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


# Removed duplicate global heatmap helper functions - now handled by Storage class methods

