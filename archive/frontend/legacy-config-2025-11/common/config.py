"""
Runflow Configuration Loader - YAML SSOT

NOTE FOR MAINTAINERS:
===================
This module enforces the "Write Once, Use Many" (SSOT) principle for Runflow configuration.

LOS (Level of Service) Configuration:
--------------------------------------
- LOS THRESHOLDS (min/max/label) → config/density_rulebook.yml :: globals.los_thresholds
  * Authoritative source for how LOS is DETERMINED from density metrics
  * Used by: analytics pipeline, map generation, reports
  * Owner: Analytics / Systems team

- LOS COLORS (palette) → config/reporting.yml :: reporting.los_colors
  * Authoritative source for how LOS is DISPLAYED
  * Used by: map visualization, reports, dashboards
  * Owner: Presentation / UI team

Legacy Note:
-----------
The "los" section in reporting.yml contains legacy threshold values.
These are NOT authoritative and should be IGNORED by all code.
Only use reporting.yml for presentation (colors, labels, formatting).

This separation ensures:
1. Analytics and front-end use identical LOS classification logic
2. Presentation can be themed independently without affecting calculations
3. No hardcoded LOS values anywhere in the codebase
4. Changes to policy (thresholds) are made in one place only
"""

import os
import yaml
from pathlib import Path


def _load_yaml(path: str) -> dict:
    """Load and parse a YAML configuration file."""
    return yaml.safe_load(Path(path).read_text())


def load_rulebook() -> dict:
    """
    Load the density rulebook YAML (SSOT for LOS thresholds and operational policy).
    
    Returns:
        dict: Parsed rulebook containing globals.los_thresholds and operational rules
    
    Environment Variables:
        RUNFLOW_RULEBOOK_YML: Override default path (for testing/sandboxing)
    """
    path = os.getenv("RUNFLOW_RULEBOOK_YML", "config/density_rulebook.yml")
    return _load_yaml(path)


def load_reporting() -> dict:
    """
    Load the reporting configuration YAML (SSOT for LOS colors and presentation).
    
    Returns:
        dict: Parsed reporting config containing reporting.los_colors and display settings
    
    Environment Variables:
        RUNFLOW_REPORTING_YML: Override default path (for testing/sandboxing)
    """
    path = os.getenv("RUNFLOW_REPORTING_YML", "config/reporting.yml")
    return _load_yaml(path)

