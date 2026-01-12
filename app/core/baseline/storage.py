"""
Baseline Storage Manager

Handles saving baseline metrics and generated runner files to disk.

Issue: #676 - Utility to create new runner files
"""

from pathlib import Path
from typing import Dict, Any, List
import json
import logging

from app.utils.run_id import generate_run_id

logger = logging.getLogger(__name__)


def create_baseline_directory(reports_path: Path) -> Path:
    """
    Create new baseline directory with unique run_id.
    
    Args:
        reports_path: Path to reports directory
    
    Returns:
        Path to created baseline directory (reports_path/baseline/{run_id}/)
    
    Issue: #676 - Baseline directory management
    """
    # Generate new run_id for baseline
    run_id = generate_run_id()  # Default ~22 chars
    
    baseline_dir = reports_path / "baseline" / run_id
    baseline_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Created baseline directory: {baseline_dir}")
    return baseline_dir


def save_baseline_metrics(
    baseline_dir: Path,
    run_id: str,
    data_dir: str,
    reports_path: str,
    selected_files: List[str],
    baseline_metrics: Dict[str, Any]
) -> Path:
    """
    Save baseline metrics to JSON and CSV files.
    
    Args:
        baseline_dir: Directory to save files
        run_id: Baseline run ID
        data_dir: Data directory path
        reports_path: Reports directory path
        selected_files: List of selected runner file names
        baseline_metrics: Dictionary of baseline metrics per event
    
    Returns:
        Path to saved baseline.json file
    
    Issue: #676 - Baseline metrics storage
    """
    # Build baseline.json structure
    baseline_json = {
        "run_id": run_id,
        "data_dir": data_dir,
        "reports_path": reports_path,
        "selected_files": selected_files,
        "baseline_metrics": baseline_metrics,
        "control_variables": {},  # Will be populated when scenario is generated
        "new_baseline_metrics": {},  # Will be populated when scenario is generated
        "generated_files": []  # Will be populated when files are generated
    }
    
    # Save baseline.json
    baseline_json_path = baseline_dir / "baseline.json"
    with open(baseline_json_path, "w") as f:
        json.dump(baseline_json, f, indent=2)
    
    logger.info(f"Saved baseline.json to {baseline_json_path}")
    return baseline_json_path


def save_generated_files(
    baseline_dir: Path,
    generated_files: List[Dict[str, str]]
) -> None:
    """
    Save generated runner CSV files and update baseline.json.
    
    Args:
        baseline_dir: Baseline directory
        generated_files: List of dicts with 'event' and 'path' keys
    
    Issue: #676 - Generated file storage
    """
    # Load existing baseline.json
    baseline_json_path = baseline_dir / "baseline.json"
    if not baseline_json_path.exists():
        raise FileNotFoundError(f"baseline.json not found at {baseline_json_path}")
    
    with open(baseline_json_path, "r") as f:
        baseline_json = json.load(f)
    
    # Update generated_files list
    baseline_json["generated_files"] = generated_files
    
    # Save updated baseline.json
    with open(baseline_json_path, "w") as f:
        json.dump(baseline_json, f, indent=2)
    
    logger.info(f"Updated baseline.json with {len(generated_files)} generated files")
