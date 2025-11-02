"""
Run ID Generator for UUID-based Run Tracking

Generates short, unique identifiers for each analysis run to replace date-based
folder naming. Uses shortuuid library for collision-resistant IDs.

Epic: #444 - Refactor Report Run ID System
Phase: 1 - UUID Infrastructure
"""

import shortuuid
from typing import Optional


def generate_run_id(length: Optional[int] = None) -> str:
    """
    Generate a short, unique run identifier.
    
    Uses shortuuid library with default configuration for truly random,
    collision-resistant IDs. Default length is ~22 characters.
    
    Args:
        length: Optional length for UUID (default: shortuuid default ~22 chars).
                Minimum 10 chars required per Epic #444.
    
    Returns:
        Short UUID string (e.g., "p0ZoB1FwH6yT2dKx")
    
    Examples:
        >>> run_id = generate_run_id()
        >>> len(run_id) >= 10
        True
        >>> run_id_short = generate_run_id(length=10)
        >>> len(run_id_short)
        10
    
    Notes:
        - Non-deterministic: Each call generates a new random UUID
        - No prefix: Just the UUID (not "run-p0ZoB1FwH6")
        - Collision-safe: Default length provides >10^30 combinations
        - Test mocking: Use dependency injection or monkeypatch in tests
    """
    if length is not None:
        # Ensure minimum length requirement (Epic #444)
        if length < 10:
            raise ValueError("Run ID length must be at least 10 characters")
        return shortuuid.ShortUUID().random(length=length)
    else:
        # Use default shortuuid length (~22 characters)
        return shortuuid.uuid()


def validate_run_id(run_id: str) -> bool:
    """
    Validate that a string is a valid run ID format.
    
    Args:
        run_id: String to validate
    
    Returns:
        True if valid run ID format, False otherwise
    
    Examples:
        >>> validate_run_id("p0ZoB1FwH6")
        True
        >>> validate_run_id("2025-11-02")  # Old date-based format
        False
        >>> validate_run_id("abc")  # Too short
        False
    """
    if not run_id or not isinstance(run_id, str):
        return False
    
    # Must be at least 10 characters (Epic #444 minimum)
    if len(run_id) < 10:
        return False
    
    # Must not contain date-like patterns (YYYY-MM-DD)
    if "-" in run_id and len(run_id.split("-")) >= 3:
        return False
    
    # shortuuid uses alphanumeric characters (Base57 alphabet)
    # Allow alphanumeric only (no special chars except potentially underscore)
    if not run_id.replace("_", "").replace("-", "").isalnum():
        return False
    
    return True


def is_legacy_date_format(run_id: str) -> bool:
    """
    Check if a run_id uses the legacy date-based format (YYYY-MM-DD).
    
    Args:
        run_id: String to check
    
    Returns:
        True if legacy date format, False otherwise
    
    Examples:
        >>> is_legacy_date_format("2025-11-02")
        True
        >>> is_legacy_date_format("p0ZoB1FwH6")
        False
    """
    if not run_id or not isinstance(run_id, str):
        return False
    
    # Date format: YYYY-MM-DD (10 characters, two hyphens)
    if len(run_id) == 10 and run_id.count("-") == 2:
        parts = run_id.split("-")
        if len(parts) == 3:
            try:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                # Basic range validation
                if 2020 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31:
                    return True
            except ValueError:
                pass
    
    return False

