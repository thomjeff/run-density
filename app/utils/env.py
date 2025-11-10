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


# Canonical Environment Detection Functions
# Simplified for local-only operations after Phase 1 declouding

def detect_runtime_environment() -> Literal["local_docker"]:
    """
    Detect the runtime environment where the container is running.
    
    This is the canonical runtime detection function used across the application.
    After Phase 1 declouding, this always returns "local_docker".
    
    Returns:
        "local_docker" - local Docker container or development
    
    Examples:
        >>> detect_runtime_environment()
        'local_docker'
    
    References:
        - Issue #464: Phase 1 - Declouding (cloud detection removed)
        - Issue #465: Phase 0 - Disable Cloud CI
    """
    return "local_docker"


def detect_storage_target() -> Literal["filesystem"]:
    """
    Detect storage target for the application.
    
    This is the canonical storage detection function used across the application.
    After Phase 1 declouding, this always returns "filesystem".
    
    Returns:
        "filesystem" - local filesystem storage
    
    Examples:
        >>> detect_storage_target()
        'filesystem'
    
    References:
        - Issue #464: Phase 1 - Declouding (GCS support removed)
        - Issue #465: Phase 0 - Disable Cloud CI
    """
    return "filesystem"
