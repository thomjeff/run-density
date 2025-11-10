"""
GCS Uploader for Cloud Run bin artifacts

Uploads bin dataset artifacts from Cloud Run container to Google Cloud Storage.
"""
import os
import logging
import time
from typing import Optional
from google.cloud import storage

logger = logging.getLogger(__name__)

# Module-level variable to track when the current run started
# This is used to filter out files from previous runs (Issue #441)
_RUN_START_TIME = time.time()

def upload_dir_to_gcs(local_dir: str, bucket_name: str, prefix: str = "", min_mtime: Optional[float] = None) -> bool:
    """
    Upload directory contents to Google Cloud Storage.
    
    Only uploads files modified after min_mtime to avoid re-uploading files
    from previous runs (Issue #441: Docker volume persistence).
    
    Args:
        local_dir: Local directory path (e.g., /tmp/reports/2025-09-18)
        bucket_name: GCS bucket name (e.g., run-density-reports)
        prefix: GCS prefix path (e.g., 2025-09-18)
        min_mtime: Minimum modification time (unix timestamp). Only upload files modified after this time.
                   If None, uses module-level _RUN_START_TIME to avoid re-uploading old files.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Use module-level run start time if min_mtime not provided
        # This prevents re-uploading files from previous runs (Issue #441)
        filter_time = min_mtime if min_mtime is not None else _RUN_START_TIME
        
        uploaded_files = []
        skipped_files = []
        
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                
                # Check file modification time (Issue #441 fix)
                try:
                    file_mtime = os.path.getmtime(local_path)
                    if file_mtime < filter_time:
                        skipped_files.append(local_path)
                        logger.debug(f"Skipping old file: {local_path} (mtime: {file_mtime} < {filter_time})")
                        continue
                except OSError as e:
                    logger.warning(f"Could not get mtime for {local_path}: {e}, uploading anyway")
                
                relative_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                
                # Construct GCS path
                if prefix:
                    gcs_path = f"{prefix.rstrip('/')}/{relative_path}"
                else:
                    gcs_path = relative_path
                
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_path)
                uploaded_files.append(gcs_path)
                logger.info(f"Uploaded: {local_path} → gs://{bucket_name}/{gcs_path}")
        
        if skipped_files:
            logger.info(f"Skipped {len(skipped_files)} old files from previous runs")
        logger.info(f"GCS upload complete: {len(uploaded_files)} files uploaded")
        return True
        
    except Exception as e:
        logger.error(f"GCS upload failed: {e}")
        return False

def upload_bin_artifacts(local_dir: str, bucket_name: str = "run-density-reports") -> bool:
    """
    Upload bin artifacts specifically to GCS with date-based prefix.
    
    Args:
        local_dir: Local directory containing bin files (e.g., /tmp/reports/2025-09-18)
        bucket_name: GCS bucket name
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract date from directory path for prefix
        date_folder = os.path.basename(local_dir)
        
        # Upload with date-based prefix
        return upload_dir_to_gcs(local_dir, bucket_name, date_folder)
        
    except Exception as e:
        logger.error(f"Bin artifacts upload failed: {e}")
        return False
