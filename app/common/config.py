"""
SSOT Configuration Loader for Run-Density (RF-FE-002)

Loads YAML configuration files without hardcoded defaults.
Provides single source of truth for LOS thresholds, colors, and operational rules.

Author: Cursor AI Assistant
Epic: RF-FE-002 | Issue: #279 | Step: 2
Architecture: Option 3 - Hybrid Approach
"""

from typing import Dict, Any
from pathlib import Path
import yaml
import os
import logging

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("config")


def load_rulebook() -> Dict[str, Any]:
    """
    Load density_rulebook.yml with no hardcoded defaults.
    
    Returns:
        dict: Parsed rulebook containing:
            - globals.los_thresholds (A-F): LOS classification thresholds
            - schemas: Segment-specific rules
            - operational rules and policies
    
    Raises:
        FileNotFoundError: If density_rulebook.yml not found
        yaml.YAMLError: If YAML parsing fails
    
    Example:
        >>> rulebook = load_rulebook()
        >>> los_thresholds = rulebook["globals"]["los_thresholds"]
        >>> assert "A" in los_thresholds
    """
    path = CONFIG_DIR / "density_rulebook.yml"
    
    # Debug logging for Issue #354
    logger.info(f"Loading rulebook from: {path.absolute()}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Config directory exists: {CONFIG_DIR.exists()}")
    logger.info(f"Rulebook file exists: {path.exists()}")
    
    if not path.exists():
        logger.error(f"density_rulebook.yml not found at {path.absolute()}")
        raise FileNotFoundError(
            f"density_rulebook.yml not found at {path}. "
            f"Ensure config/ directory exists with required YAML files."
        )
    
    with path.open("r", encoding="utf-8") as f:
        rulebook = yaml.safe_load(f)
        logger.info(f"Successfully loaded rulebook with version: {rulebook.get('version', 'unknown')}")
        return rulebook


def load_reporting() -> Dict[str, Any]:
    """
    Load reporting.yml (presentation configuration).
    
    Returns:
        dict: Parsed reporting config containing:
            - reporting.los_colors (A-F): Hex color codes for LOS levels
            - reporting configuration for visualization
    
    Raises:
        FileNotFoundError: If reporting.yml not found
        yaml.YAMLError: If YAML parsing fails
    
    Example:
        >>> reporting = load_reporting()
        >>> los_colors = reporting["reporting"]["los_colors"]
        >>> assert los_colors["A"].startswith("#")
    """
    path = CONFIG_DIR / "reporting.yml"
    
    if not path.exists():
        raise FileNotFoundError(
            f"reporting.yml not found at {path}. "
            f"Ensure config/ directory exists with required YAML files."
        )
    
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

