"""
Environment variable utilities for reliable configuration handling.

This module provides consistent environment variable parsing across the application.
"""
import os
from typing import Literal

_TRUE = {"1", "true", "t", "yes", "y", "on"}

def env_bool(name: str, default: bool = False) -> bool:
    """Parse environment variable as boolean with sensible defaults."""
    v = os.getenv(name)
    return default if v is None else str(v).strip().lower() in _TRUE

def env_str(name: str, default: str = "") -> str:
    """Get environment variable as string with default."""
    v = os.getenv(name)
    return v if v is not None else default


# Canonical Environment Detection Functions (Issue #452)
# These functions follow the detection priority established in Issue #447
# and documented in docs/architecture/env-detection.md

def detect_runtime_environment() -> Literal["local_docker", "cloud_run"]:
    """
    Detect the runtime environment where the container is running.
    
    This is the canonical runtime detection function used across the application.
    Follows Issue #447 standards documented in docs/architecture/env-detection.md.
    
    Returns:
        "cloud_run" if running in GCP Cloud Run (K_SERVICE is set)
        "local_docker" if running in local Docker container or development
    
    Examples:
        >>> # In Cloud Run:
        >>> detect_runtime_environment()
        'cloud_run'
        
        >>> # In local Docker:
        >>> detect_runtime_environment()
        'local_docker'
    
    References:
        - Issue #447: E2E Test Refactor (detection priority)
        - Issue #451: Infrastructure & Environment Readiness
        - Issue #452: Phase 2 - Short UUID for Run ID
    """
    # K_SERVICE is set automatically by Cloud Run
    if os.getenv('K_SERVICE'):
        return "cloud_run"
    else:
        return "local_docker"


def detect_storage_target() -> Literal["filesystem", "gcs"]:
    """
    Detect storage target based on environment configuration.
    
    This is the canonical storage detection function used across the application.
    Follows Issue #447 priority order documented in docs/architecture/env-detection.md.
    
    Detection Priority:
    1. Check GCS_UPLOAD flag (explicit override for staging mode)
    2. Check K_SERVICE or GOOGLE_CLOUD_PROJECT (Cloud Run auto-detect)
    3. Default to filesystem (local development mode)
    
    Returns:
        "gcs" if cloud storage should be used
        "filesystem" if local filesystem should be used
    
    Examples:
        >>> # Staging mode (local container with GCS):
        >>> os.environ['GCS_UPLOAD'] = 'true'
        >>> detect_storage_target()
        'gcs'
        
        >>> # Local development (default):
        >>> os.environ.pop('GCS_UPLOAD', None)
        >>> os.environ.pop('K_SERVICE', None)
        >>> detect_storage_target()
        'filesystem'
        
        >>> # Cloud Run (automatic):
        >>> os.environ['K_SERVICE'] = 'run-density'
        >>> detect_storage_target()
        'gcs'
    
    References:
        - Issue #447: E2E Test Refactor (GCS_UPLOAD flag priority)
        - Issue #451: Infrastructure & Environment Readiness
        - Issue #452: Phase 2 - Short UUID for Run ID
    """
    # Issue #447: Check GCS_UPLOAD flag first (staging mode)
    # Default is empty string, which evaluates to local mode
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        return "gcs"
    # Check Cloud Run environment variables (automatic detection)
    elif os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        return "gcs"
    else:
        return "filesystem"
