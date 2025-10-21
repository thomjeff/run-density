"""
Google Cloud Storage Service for Persistent File Storage

This module provides a unified interface for file storage operations that works
in both local development and Cloud Run production environments.

Features:
- Automatic environment detection (local vs Cloud Run)
- File upload/download with retry logic
- Organized file structure by date
- Error handling and logging
- Support for all file types (JSON, PDF, CSV, MD)
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
from dataclasses import dataclass

# Google Cloud Storage imports
try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound, GoogleCloudError
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None
    NotFound = Exception
    GoogleCloudError = Exception

logger = logging.getLogger(__name__)

@dataclass
class StorageConfig:
    """Configuration for storage service."""
    bucket_name: str = "run-density-reports"
    local_reports_dir: str = "reports"
    use_cloud_storage: bool = False
    project_id: Optional[str] = None

class StorageService:
    """
    Unified storage service for local and Cloud Storage operations.
    
    Automatically detects environment and uses appropriate storage method:
    - Local development: File system storage
    - Cloud Run production: Google Cloud Storage
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._detect_environment()
        self._client = None
        
        if self.config.use_cloud_storage:
            self._initialize_gcs_client()
    
    def _detect_environment(self):
        """Detect if running in Cloud Run or local environment."""
        # Check for Cloud Run environment variables
        if os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
            self.config.use_cloud_storage = True
            self.config.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            logger.info("Detected Cloud Run environment - using Cloud Storage")
        else:
            self.config.use_cloud_storage = False
            logger.info("Detected local environment - using file system storage")
    
    def _initialize_gcs_client(self):
        """Initialize Google Cloud Storage client."""
        if not GCS_AVAILABLE:
            raise ImportError("google-cloud-storage not available. Install with: pip install google-cloud-storage")
        
        try:
            self._client = storage.Client(project=self.config.project_id)
            # Test bucket access
            bucket = self._client.bucket(self.config.bucket_name)
            if not bucket.exists():
                logger.warning(f"Bucket {self.config.bucket_name} does not exist. Creating...")
                bucket.create()
            logger.info(f"Initialized Cloud Storage client for bucket: {self.config.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Storage client: {e}")
            raise
    
    def _get_date_path(self, date: Optional[str] = None) -> str:
        """Get the date-based path for file organization."""
        if date:
            return date
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_file_path(self, filename: str, date: Optional[str] = None) -> str:
        """Get the full file path including date directory."""
        date_path = self._get_date_path(date)
        return f"{date_path}/{filename}"
    
    def save_file(self, filename: str, content: str, date: Optional[str] = None) -> str:
        """
        Save file content to storage.
        
        Args:
            filename: Name of the file to save
            content: File content as string
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Full path where file was saved
        """
        file_path = self._get_file_path(filename, date)
        
        if self.config.use_cloud_storage:
            return self._save_to_gcs(file_path, content)
        else:
            return self._save_to_local(file_path, content)
    
    def save_json(self, filename: str, data: Dict[str, Any], date: Optional[str] = None) -> str:
        """
        Save JSON data to storage.
        
        Args:
            filename: Name of the file to save
            data: Dictionary to save as JSON
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Full path where file was saved
        """
        content = json.dumps(data, indent=2, default=str)
        return self.save_file(filename, content, date)
    
    def load_file(self, filename: str, date: Optional[str] = None) -> Optional[str]:
        """
        Load file content from storage.
        
        Args:
            filename: Name of the file to load
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            File content as string, or None if not found
        """
        file_path = self._get_file_path(filename, date)
        
        if self.config.use_cloud_storage:
            return self._load_from_gcs(file_path)
        else:
            return self._load_from_local(file_path)
    
    def load_json(self, filename: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load JSON data from storage.
        
        Args:
            filename: Name of the file to load
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dictionary with loaded data, or None if not found
        """
        content = self.load_file(filename, date)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from {filename}: {e}")
                return None
        return None
    
    def load_ui_artifact(self, filename: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load UI artifact JSON from storage.
        
        UI artifacts are stored in artifacts/{run_id}/ui/ directory structure.
        If date is None, uses the latest run_id from artifacts/latest.json.
        
        Args:
            filename: Name of the UI artifact file (e.g., "health.json", "flags.json")
            date: Optional date/run_id string, defaults to latest run_id from latest.json
            
        Returns:
            Parsed JSON data, or None if not found
        """
        if date is None:
            # Try to get the latest run_id from artifacts/latest.json
            try:
                # Read latest.json from appropriate storage (local or GCS)
                if self.config.use_cloud_storage:
                    content = self._load_from_gcs("artifacts/latest.json")
                else:
                    latest_path = Path("artifacts/latest.json")
                    content = latest_path.read_text() if latest_path.exists() else None
                
                if content:
                    latest_data = json.loads(content)
                    date = latest_data.get("run_id")
                    logger.info(f"Using latest run_id from latest.json: {date}")
                else:
                    logger.warning("artifacts/latest.json not found, using today's date")
                    date = datetime.now().strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Could not read artifacts/latest.json: {e}, using today's date")
                date = datetime.now().strftime("%Y-%m-%d")
        
        # UI artifacts are stored in artifacts/{run_id}/ui/ path
        ui_artifact_path = f"artifacts/{date}/ui/{filename}"
        
        try:
            if self.config.use_cloud_storage:
                content = self._load_from_gcs(ui_artifact_path)
            else:
                content = self._load_from_local(ui_artifact_path)
            
            if content is None:
                logger.warning(f"UI artifact not found: {ui_artifact_path}")
                return None
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse UI artifact JSON {ui_artifact_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading UI artifact {ui_artifact_path}: {e}")
            return None
    
    def list_files(self, date: Optional[str] = None, pattern: Optional[str] = None) -> List[str]:
        """
        List files in storage for a given date.
        
        Args:
            date: Optional date string (YYYY-MM-DD), defaults to today
            pattern: Optional filename pattern to filter by
            
        Returns:
            List of filenames
        """
        date_path = self._get_date_path(date)
        
        if self.config.use_cloud_storage:
            return self._list_gcs_files(date_path, pattern)
        else:
            return self._list_local_files(date_path, pattern)
    
    def file_exists(self, filename: str, date: Optional[str] = None) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            filename: Name of the file to check
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            True if file exists, False otherwise
        """
        file_path = self._get_file_path(filename, date)
        
        if self.config.use_cloud_storage:
            return self._gcs_file_exists(file_path)
        else:
            return self._local_file_exists(file_path)
    
    def _save_to_gcs(self, file_path: str, content: str) -> str:
        """Save file to Google Cloud Storage."""
        try:
            bucket = self._client.bucket(self.config.bucket_name)
            blob = bucket.blob(file_path)
            blob.upload_from_string(content)
            logger.info(f"Saved file to GCS: {file_path}")
            return f"gs://{self.config.bucket_name}/{file_path}"
        except GoogleCloudError as e:
            logger.error(f"Failed to save file to GCS {file_path}: {e}")
            raise
    
    def _save_to_local(self, file_path: str, content: str) -> str:
        """Save file to local file system."""
        try:
            full_path = Path(self.config.local_reports_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            logger.info(f"Saved file locally: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Failed to save file locally {file_path}: {e}")
            raise
    
    def _load_from_gcs(self, path: str) -> Optional[str]:
        """Load file from Google Cloud Storage."""
        try:
            # Normalize path
            if path.startswith("reports/"):
                gcs_path = path[len("reports/"):]
            else:
                gcs_path = path

            bucket = self._client.bucket(self.config.bucket_name)
            blob = bucket.blob(gcs_path)

            if not blob.exists():
                logger.warning(f"[GCS] Blob not found: {gcs_path}")
                return None

            logger.info(f"[GCS] Downloading blob: {gcs_path}")
            return blob.download_as_text()

        except Exception as e:
            logger.error(f"[GCS] Failed to load {path}: {e}")
            return None
    
    def _load_from_local(self, file_path: str) -> Optional[str]:
        """Load file from local file system."""
        try:
            # UI artifacts are in the root artifacts/ directory, not under reports/
            if file_path.startswith("artifacts/"):
                full_path = Path(file_path)
            else:
                full_path = Path(self.config.local_reports_dir) / file_path
            
            if not full_path.exists():
                logger.debug(f"File not found locally: {full_path}")
                return None
            content = full_path.read_text()
            logger.debug(f"Loaded file locally: {full_path}")
            return content
        except Exception as e:
            logger.error(f"Failed to load file locally {file_path}: {e}")
            return None
    
    def _list_gcs_files(self, date_path: str, pattern: Optional[str] = None) -> List[str]:
        """List files in Google Cloud Storage."""
        try:
            bucket = self._client.bucket(self.config.bucket_name)
            blobs = bucket.list_blobs(prefix=date_path + "/")
            
            files = []
            for blob in blobs:
                filename = blob.name.split("/")[-1]
                if not pattern or pattern in filename:
                    files.append(filename)
            
            logger.debug(f"Listed {len(files)} files from GCS: {date_path}")
            return files
        except GoogleCloudError as e:
            logger.error(f"Failed to list files from GCS {date_path}: {e}")
            return []
    
    def _list_local_files(self, date_path: str, pattern: Optional[str] = None) -> List[str]:
        """List files in local file system."""
        try:
            full_path = Path(self.config.local_reports_dir) / date_path
            if not full_path.exists():
                logger.debug(f"Directory not found locally: {full_path}")
                return []
            
            files = []
            for file_path in full_path.iterdir():
                if file_path.is_file():
                    filename = file_path.name
                    if not pattern or pattern in filename:
                        files.append(filename)
            
            logger.debug(f"Listed {len(files)} files locally: {date_path}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files locally {date_path}: {e}")
            return []
    
    def _gcs_file_exists(self, file_path: str) -> bool:
        """Check if file exists in Google Cloud Storage."""
        try:
            bucket = self._client.bucket(self.config.bucket_name)
            blob = bucket.blob(file_path)
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"Failed to check file existence in GCS {file_path}: {e}")
            return False
    
    def _local_file_exists(self, file_path: str) -> bool:
        """Check if file exists in local file system."""
        try:
            full_path = Path(self.config.local_reports_dir) / file_path
            return full_path.exists()
        except Exception as e:
            logger.error(f"Failed to check file existence locally {file_path}: {e}")
            return False
    
    def get_latest_run_id(self) -> Optional[str]:
        """
        Get latest run_id from artifacts/latest.json (environment-aware).
        
        Reads from GCS in Cloud Run, local filesystem in development.
        Falls back to today's date if latest.json not found.
        
        Returns:
            Run ID string (e.g., "2025-10-21") or today's date as fallback
        """
        try:
            if self.config.use_cloud_storage:
                content = self._load_from_gcs("artifacts/latest.json")
            else:
                latest_path = Path("artifacts/latest.json")
                content = latest_path.read_text() if latest_path.exists() else None
            
            if content:
                latest_data = json.loads(content)
                run_id = latest_data.get("run_id")
                if run_id:
                    logger.info(f"Loaded latest run_id: {run_id}")
                    return run_id
        except Exception as e:
            logger.warning(f"Could not load latest run_id: {e}")
        
        # Fallback to today's date
        from datetime import datetime
        fallback = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Using fallback run_id: {fallback}")
        return fallback
    
    def read_parquet(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read parquet file from GCS or local filesystem.
        
        Args:
            file_path: Path like "reports/2025-10-21/bins.parquet"
        
        Returns:
            DataFrame or None if file not found/error
        """
        try:
            if self.config.use_cloud_storage:
                # Normalize GCS path (strip "reports/" prefix if present)
                if file_path.startswith("reports/"):
                    gcs_path = file_path[len("reports/"):]
                else:
                    gcs_path = file_path
                
                bucket = self._client.bucket(self.config.bucket_name)
                blob = bucket.blob(gcs_path)
                data = blob.download_as_bytes()
                from io import BytesIO
                return pd.read_parquet(BytesIO(data))
            else:
                return pd.read_parquet(file_path)
        except Exception as e:
            logger.warning(f"Could not read parquet {file_path}: {e}")
            return None
    
    def read_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read CSV file from GCS or local filesystem.
        
        Args:
            file_path: Path like "reports/2025-10-21/Flow.csv"
        
        Returns:
            DataFrame or None if file not found/error
        """
        try:
            if self.config.use_cloud_storage:
                # Normalize GCS path (strip "reports/" prefix if present)
                if file_path.startswith("reports/"):
                    gcs_path = file_path[len("reports/"):]
                else:
                    gcs_path = file_path
                
                bucket = self._client.bucket(self.config.bucket_name)
                blob = bucket.blob(gcs_path)
                content = blob.download_as_text()
                from io import StringIO
                return pd.read_csv(StringIO(content))
            else:
                return pd.read_csv(file_path)
        except Exception as e:
            logger.warning(f"Could not read CSV {file_path}: {e}")
            return None
    
    def read_json(self, file_path: str) -> Optional[dict]:
        """
        Read JSON file from GCS or local filesystem.
        
        Args:
            file_path: Path like "artifacts/2025-10-21/ui/flow.json"
        
        Returns:
            Dict or None if file not found/error
        """
        try:
            if self.config.use_cloud_storage:
                # Normalize GCS path (strip "reports/" or "artifacts/" prefix if present)
                if file_path.startswith("reports/"):
                    gcs_path = file_path[len("reports/"):]
                elif file_path.startswith("artifacts/"):
                    # artifacts/ is already in GCS path structure, keep as-is
                    gcs_path = file_path
                else:
                    gcs_path = file_path
                
                bucket = self._client.bucket(self.config.bucket_name)
                blob = bucket.blob(gcs_path)
                content = blob.download_as_text()
                return json.loads(content)
            else:
                with open(file_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read JSON {file_path}: {e}")
            return None
    
    def read_geojson(self, file_path: str) -> Optional[dict]:
        """
        Read GeoJSON file from GCS or local filesystem.
        
        Args:
            file_path: Path like "artifacts/2025-10-21/ui/segments.geojson"
        
        Returns:
            Dict or None if file not found/error
        """
        # GeoJSON is just JSON with geo features
        return self.read_json(file_path)
    
    def list_files(self, directory: str, suffix: str = "") -> List[str]:
        """
        List files in a directory from GCS or local filesystem.
        
        Args:
            directory: Directory path like "reports/2025-10-21" or "2025-10-21"
            suffix: Optional suffix filter like "-Flow.csv"
        
        Returns:
            List of file paths (relative to directory)
        """
        try:
            if self.config.use_cloud_storage:
                # Normalize GCS path (strip "reports/" prefix if present)
                if directory.startswith("reports/"):
                    gcs_dir = directory[len("reports/"):]
                else:
                    gcs_dir = directory
                
                # Ensure directory ends with /
                if not gcs_dir.endswith("/"):
                    gcs_dir += "/"
                
                bucket = self._client.bucket(self.config.bucket_name)
                blobs = bucket.list_blobs(prefix=gcs_dir)
                
                files = []
                for blob in blobs:
                    # Get filename relative to directory
                    filename = blob.name[len(gcs_dir):]
                    if filename and suffix and filename.endswith(suffix):
                        files.append(filename)
                    elif filename and not suffix:
                        files.append(filename)
                
                return sorted(files)
            else:
                dir_path = Path(directory)
                if not dir_path.exists():
                    return []
                
                if suffix:
                    files = [f.name for f in dir_path.glob(f"*{suffix}")]
                else:
                    files = [f.name for f in dir_path.iterdir() if f.is_file()]
                
                return sorted(files)
        except Exception as e:
            logger.warning(f"Could not list files in {directory}: {e}")
            return []

# Global storage service instance
_storage_service = None

def get_storage_service() -> StorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

def initialize_storage_service(config: Optional[StorageConfig] = None) -> StorageService:
    """Initialize the global storage service with custom config."""
    global _storage_service
    _storage_service = StorageService(config)
    return _storage_service
