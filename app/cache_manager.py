"""
Persistent Cache Manager for Analysis Results

This module provides cross-environment caching for flow and density analysis results
with timestamps to improve map UX and eliminate infinite analysis loops.

Supports both local development (file system) and Cloud Run (Google Cloud Storage).
"""

from __future__ import annotations
import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

class CacheEntry:
    """Data structure for cached analysis results."""
    
    def __init__(self, analysis_type: str, dataset_hash: str, data: Dict[str, Any], 
                 timestamp: datetime, metadata: Optional[Dict[str, Any]] = None):
        self.analysis_type = analysis_type
        self.dataset_hash = dataset_hash
        self.data = data
        self.timestamp = timestamp
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "analysis_type": self.analysis_type,
            "dataset_hash": self.dataset_hash,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary."""
        return cls(
            analysis_type=data["analysis_type"],
            dataset_hash=data["dataset_hash"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )

class CacheManager(ABC):
    """Abstract base class for cache managers."""
    
    @abstractmethod
    def get_analysis(self, analysis_type: str, dataset_hash: str) -> Optional[CacheEntry]:
        """Get cached analysis results."""
        pass
    
    @abstractmethod
    def store_analysis(self, analysis_type: str, dataset_hash: str, 
                      data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store analysis results in cache."""
        pass
    
    @abstractmethod
    def get_cache_status(self, analysis_type: str, dataset_hash: str) -> Dict[str, Any]:
        """Get cache status information."""
        pass
    
    @abstractmethod
    def invalidate_cache(self, analysis_type: str, dataset_hash: str) -> bool:
        """Invalidate cached analysis results."""
        pass
    
    @abstractmethod
    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """Clean up old cache entries."""
        pass

class FileSystemCacheManager(CacheManager):
    """File system cache manager for local development."""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        logger.info(f"File system cache initialized at {self.cache_dir.absolute()}")
    
    def _get_cache_file_path(self, analysis_type: str, dataset_hash: str) -> Path:
        """Get cache file path for analysis type and dataset hash."""
        filename = f"{analysis_type}_{dataset_hash}.json"
        return self.cache_dir / filename
    
    def get_analysis(self, analysis_type: str, dataset_hash: str) -> Optional[CacheEntry]:
        """Get cached analysis results from file system."""
        cache_file = self._get_cache_file_path(analysis_type, dataset_hash)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load cache file {cache_file}: {e}")
            return None
    
    def store_analysis(self, analysis_type: str, dataset_hash: str, 
                      data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store analysis results in file system."""
        cache_file = self._get_cache_file_path(analysis_type, dataset_hash)
        
        entry = CacheEntry(
            analysis_type=analysis_type,
            dataset_hash=dataset_hash,
            data=data,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(entry.to_dict(), f, indent=2)
            logger.info(f"Cached {analysis_type} analysis for dataset {dataset_hash}")
        except Exception as e:
            logger.error(f"Failed to store cache file {cache_file}: {e}")
    
    def get_cache_status(self, analysis_type: str, dataset_hash: str) -> Dict[str, Any]:
        """Get cache status information."""
        entry = self.get_analysis(analysis_type, dataset_hash)
        
        if entry is None:
            return {
                "cached": False,
                "analysis_type": analysis_type,
                "dataset_hash": dataset_hash
            }
        
        return {
            "cached": True,
            "analysis_type": analysis_type,
            "dataset_hash": dataset_hash,
            "timestamp": entry.timestamp.isoformat(),
            "age_hours": (datetime.now(timezone.utc) - entry.timestamp).total_seconds() / 3600,
            "metadata": entry.metadata
        }
    
    def invalidate_cache(self, analysis_type: str, dataset_hash: str) -> bool:
        """Invalidate cached analysis results."""
        cache_file = self._get_cache_file_path(analysis_type, dataset_hash)
        
        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.info(f"Invalidated cache for {analysis_type} analysis")
                return True
            except Exception as e:
                logger.error(f"Failed to invalidate cache file {cache_file}: {e}")
                return False
        
        return False
    
    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """Clean up old cache entries."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        cleaned_count = 0
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old cache file: {cache_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up cache file {cache_file}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old cache entries")
        return cleaned_count

class CloudStorageCacheManager(CacheManager):
    """Google Cloud Storage cache manager for Cloud Run."""
    
    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or os.getenv('CACHE_BUCKET_NAME', 'run-density-cache')
        try:
            from google.cloud import storage
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Cloud Storage cache initialized with bucket {self.bucket_name}")
        except ImportError:
            logger.error("Google Cloud Storage client not available")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Storage cache: {e}")
            raise
    
    def _get_blob_name(self, analysis_type: str, dataset_hash: str) -> str:
        """Get blob name for analysis type and dataset hash."""
        return f"cache/{analysis_type}_{dataset_hash}.json"
    
    def get_analysis(self, analysis_type: str, dataset_hash: str) -> Optional[CacheEntry]:
        """Get cached analysis results from Cloud Storage."""
        blob_name = self._get_blob_name(analysis_type, dataset_hash)
        blob = self.bucket.blob(blob_name)
        
        if not blob.exists():
            return None
        
        try:
            data = json.loads(blob.download_as_text())
            return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load cache blob {blob_name}: {e}")
            return None
    
    def store_analysis(self, analysis_type: str, dataset_hash: str, 
                      data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store analysis results in Cloud Storage."""
        blob_name = self._get_blob_name(analysis_type, dataset_hash)
        blob = self.bucket.blob(blob_name)
        
        entry = CacheEntry(
            analysis_type=analysis_type,
            dataset_hash=dataset_hash,
            data=data,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        try:
            blob.upload_from_string(
                json.dumps(entry.to_dict(), indent=2),
                content_type='application/json'
            )
            logger.info(f"Cached {analysis_type} analysis for dataset {dataset_hash}")
        except Exception as e:
            logger.error(f"Failed to store cache blob {blob_name}: {e}")
    
    def get_cache_status(self, analysis_type: str, dataset_hash: str) -> Dict[str, Any]:
        """Get cache status information."""
        entry = self.get_analysis(analysis_type, dataset_hash)
        
        if entry is None:
            return {
                "cached": False,
                "analysis_type": analysis_type,
                "dataset_hash": dataset_hash
            }
        
        return {
            "cached": True,
            "analysis_type": analysis_type,
            "dataset_hash": dataset_hash,
            "timestamp": entry.timestamp.isoformat(),
            "age_hours": (datetime.now(timezone.utc) - entry.timestamp).total_seconds() / 3600,
            "metadata": entry.metadata
        }
    
    def invalidate_cache(self, analysis_type: str, dataset_hash: str) -> bool:
        """Invalidate cached analysis results."""
        blob_name = self._get_blob_name(analysis_type, dataset_hash)
        blob = self.bucket.blob(blob_name)
        
        try:
            if blob.exists():
                blob.delete()
                logger.info(f"Invalidated cache for {analysis_type} analysis")
                return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache blob {blob_name}: {e}")
            return False
        
        return False
    
    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """Clean up old cache entries."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        cleaned_count = 0
        
        try:
            blobs = self.bucket.list_blobs(prefix="cache/")
            for blob in blobs:
                if blob.time_created.timestamp() < cutoff_time:
                    blob.delete()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old cache blob: {blob.name}")
        except Exception as e:
            logger.error(f"Failed to clean up old cache entries: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old cache entries")
        return cleaned_count

def get_cache_manager() -> CacheManager:
    """Get appropriate cache manager based on environment."""
    if os.getenv('GOOGLE_CLOUD_PROJECT'):
        # Cloud Run environment
        return CloudStorageCacheManager()
    else:
        # Local development environment
        return FileSystemCacheManager()

# Global cache manager instance
_cache_manager = None

def get_global_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = get_cache_manager()
    return _cache_manager
