"""
GCS Uploader for Cloud Run bin artifacts

Uploads bin dataset artifacts from Cloud Run container to Google Cloud Storage.
"""
import os
import logging
from typing import Optional
from google.cloud import storage

logger = logging.getLogger(__name__)

def upload_dir_to_gcs(local_dir: str, bucket_name: str, prefix: str = "") -> bool:
    """
    Upload directory contents to Google Cloud Storage.
    
    Args:
        local_dir: Local directory path (e.g., /tmp/reports/2025-09-18)
        bucket_name: GCS bucket name (e.g., run-density-reports)
        prefix: GCS prefix path (e.g., 2025-09-18)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        uploaded_files = []
        
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
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
