"""
Baseline Runner File Generation Module

Utility for generating new runner CSV files with scenario-based modifications.
Supports percentile-based pace adjustments and participant count changes.

Issue: #676 - Utility to create new runner files
"""

from app.core.baseline.calculator import calculate_baseline_metrics
from app.core.baseline.generator import generate_runner_file
from app.core.baseline.storage import (
    create_baseline_directory,
    save_baseline_metrics,
    save_generated_files,
)
from app.core.baseline.validation import validate_runner_file, validate_control_variables

__all__ = [
    "calculate_baseline_metrics",
    "generate_runner_file",
    "create_baseline_directory",
    "save_baseline_metrics",
    "save_generated_files",
    "validate_runner_file",
    "validate_control_variables",
]
