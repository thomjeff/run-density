"""
Environment variable utilities for reliable configuration handling.

This module provides consistent environment variable parsing across the application.
"""
import os

_TRUE = {"1", "true", "t", "yes", "y", "on"}

def env_bool(name: str, default: bool = False) -> bool:
    """Parse environment variable as boolean with sensible defaults."""
    v = os.getenv(name)
    return default if v is None else str(v).strip().lower() in _TRUE

def env_str(name: str, default: str = "") -> str:
    """Get environment variable as string with default."""
    v = os.getenv(name)
    return v if v is not None else default
