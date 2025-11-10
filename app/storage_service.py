"""
Local Filesystem Storage Service

This module provides a unified interface for file storage operations using
the local filesystem only.

Features:
- File upload/download operations
- Organized file structure
- Error handling and logging
- Support for all file types (JSON, PDF, CSV, MD, Parquet)
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StorageConfig:
    """Configuration for storage service."""
    local_reports_dir: str = "reports"

class StorageService:
    """
    Filesystem storage service for local development.
    
    Provides file operations for reports, artifacts, and data files.
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        logger.info("Detected local environment - using file system storage")
    
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
        Save file content to local filesystem.
        
        Args:
            filename: Name of the file to save
            content: File content as string
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Full path where file was saved
        """
        file_path = self._get_file_path(filename, date)
        return self._save_to_local(file_path, content)
    
    def save_json(self, filename: str, data: Dict[str, Any], date: Optional[str] = None) -> str:
        """
        Save JSON data to local filesystem.
        
        Args:
            filename: Name of the file to save
            data: Dictionary to save as JSON
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Full path where file was saved
        """
        content = json.dumps(data, indent=2, default=str)
        return self.save_file(filename, content, date)

    def save_artifact_json(self, file_path: str, data: Dict[str, Any]) -> str:
        """
        Save JSON to an explicit artifacts path (e.g., "artifacts/<run_id>/ui/captions.json").
        This avoids automatic date-prefixing used by save_file/save_json.
        """
        content = json.dumps(data, indent=2, default=str)
        try:
            full_path = Path(file_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            logger.info(f"Saved artifact locally: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Failed to save artifact locally {file_path}: {e}")
            raise
    
    def load_file(self, filename: str, date: Optional[str] = None) -> Optional[str]:
        """
        Load file content from local filesystem.
        
        Args:
            filename: Name of the file to load
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            File content as string, or None if not found
        """
        file_path = self._get_file_path(filename, date)
        return self._load_from_local(file_path)
    
    def load_json(self, filename: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load JSON data from local filesystem.
        
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
        Load UI artifact JSON from local filesystem.
        
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
                latest_path = Path("artifacts/latest.json")
                if latest_path.exists():
                    content = latest_path.read_text()
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
        List files in local filesystem for a given date.
        
        Args:
            date: Optional date string (YYYY-MM-DD), defaults to today
            pattern: Optional filename pattern to filter by
            
        Returns:
            List of filenames
        """
        date_path = self._get_date_path(date)
        return self._list_local_files(date_path, pattern)
    
    def file_exists(self, filename: str, date: Optional[str] = None) -> bool:
        """
        Check if a file exists in local filesystem.
        
        Args:
            filename: Name of the file to check
            date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            True if file exists, False otherwise
        """
        file_path = self._get_file_path(filename, date)
        return self._local_file_exists(file_path)
    
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
        Get latest run_id from artifacts/latest.json.
        
        Falls back to today's date if latest.json not found.
        
        Returns:
            Run ID string (e.g., "2025-10-21") or today's date as fallback
        """
        try:
            latest_path = Path("artifacts/latest.json")
            if latest_path.exists():
                content = latest_path.read_text()
                latest_data = json.loads(content)
                run_id = latest_data.get("run_id")
                if run_id:
                    logger.info(f"Loaded latest run_id: {run_id}")
                    return run_id
        except Exception as e:
            logger.warning(f"Could not load latest run_id: {e}")
        
        # Fallback to today's date
        fallback = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Using fallback run_id: {fallback}")
        return fallback
    
    def read_parquet(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read parquet file from local filesystem.
        
        Args:
            file_path: Path like "reports/2025-10-21/bins.parquet"
        
        Returns:
            DataFrame or None if file not found/error
        """
        try:
            return pd.read_parquet(file_path)
        except Exception as e:
            logger.warning(f"Could not read parquet {file_path}: {e}")
            return None
    
    def read_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read CSV file from local filesystem.
        
        Args:
            file_path: Path like "reports/2025-10-21/Flow.csv"
        
        Returns:
            DataFrame or None if file not found/error
        """
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            logger.warning(f"Could not read CSV {file_path}: {e}")
            return None
    
    def read_json(self, file_path: str) -> Optional[dict]:
        """
        Read JSON file from local filesystem.
        
        Args:
            file_path: Path like "artifacts/2025-10-21/ui/flow.json"
        
        Returns:
            Dict or None if file not found/error
        """
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read JSON {file_path}: {e}")
            return None
    
    def read_geojson(self, file_path: str) -> Optional[dict]:
        """
        Read GeoJSON file from local filesystem.
        
        Args:
            file_path: Path like "artifacts/2025-10-21/ui/segments.geojson"
        
        Returns:
            Dict or None if file not found/error
        """
        # GeoJSON is just JSON with geo features
        return self.read_json(file_path)
    
    def list_directory_files(self, directory: str, suffix: str = "") -> List[str]:
        """
        List files in a directory from local filesystem.
        
        Args:
            directory: Directory path like "reports/2025-10-21" or "2025-10-21"
            suffix: Optional suffix filter like "-Flow.csv"
        
        Returns:
            List of file paths (relative to directory)
        """
        try:
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

    def get_heatmap_signed_url(self, segment_id: str, expiry_seconds=3600) -> Optional[str]:
        """Generate local URL for heatmap."""
        run_id = self.get_latest_run_id()
        if not run_id:
            logger.warning("No run_id available - cannot generate heatmap URL. Artifacts missing for current run.")
            return None
        return f"/artifacts/{run_id}/ui/heatmaps/{segment_id}.png"

    @property
    def mode(self) -> str:
        """Return the storage mode for compatibility with legacy code."""
        return "local"
    
    @property
    def bucket(self) -> str:
        """Return empty string for compatibility with legacy code."""
        return ""


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
