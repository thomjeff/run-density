"""
Preflight Validator for Density Inputs

Validates segments.csv structure and content before E2E tests run.
Fails fast with friendly error messages for quick fixes.

Usage:
    from app.validation.preflight import validate_segments_csv
    validate_segments_csv()  # Raises ValidationError if invalid
"""

import pandas as pd
import os
from typing import Dict, Any


class ValidationError(Exception):
    """Raised when preflight validation fails."""
    pass


def _check_required_columns(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that all required columns are present."""
    required_columns = [
        "seg_id", "seg_label", "width_m", "direction",
        "full", "half", "10K",
        "full_from_km", "full_to_km",
        "half_from_km", "half_to_km",
        "10K_from_km", "10K_to_km"
        # Issue #549: flow_type removed from segments.csv (flow-specific, only in flow.csv)
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        validation_results["errors"].append(f"❌ Missing required columns: {missing_columns}")
        validation_results["checks_failed"] += 1
    else:
        validation_results["warnings"].append("✅ All required columns present")
        validation_results["checks_passed"] += 1


def _check_empty_dataframe(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that DataFrame is not empty."""
    if len(df) == 0:
        validation_results["errors"].append("❌ CSV file is empty")
        validation_results["checks_failed"] += 1
    else:
        validation_results["warnings"].append(f"✅ CSV contains {len(df)} rows")
        validation_results["checks_passed"] += 1


def _check_seg_id_uniqueness(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that seg_id values are unique."""
    if "seg_id" in df.columns:
        duplicate_seg_ids = df[df.duplicated(subset=["seg_id"], keep=False)]["seg_id"].tolist()
        if duplicate_seg_ids:
            validation_results["errors"].append(f"❌ Duplicate seg_id values: {duplicate_seg_ids}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append("✅ All seg_id values are unique")
            validation_results["checks_passed"] += 1


def _check_width_m_values(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that width_m values are valid (not NaN and > 0)."""
    if "width_m" in df.columns:
        invalid_widths = df[df["width_m"].isna() | (df["width_m"] <= 0)]
        if not invalid_widths.empty:
            invalid_seg_ids = invalid_widths["seg_id"].tolist()
            validation_results["errors"].append(f"❌ Invalid width_m values (NaN or <= 0): {invalid_seg_ids}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append("✅ All width_m values are valid")
            validation_results["checks_passed"] += 1


def _check_direction_values(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that direction values are valid ('uni' or 'bi')."""
    if "direction" in df.columns:
        valid_directions = {"uni", "bi"}
        invalid_directions = df[~df["direction"].isin(valid_directions)]
        if not invalid_directions.empty:
            invalid_seg_ids = invalid_directions["seg_id"].tolist()
            validation_results["errors"].append(f"❌ Invalid direction values (must be 'uni' or 'bi'): {invalid_seg_ids}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append("✅ All direction values are valid")
            validation_results["checks_passed"] += 1


def _check_event_flag_values(df: pd.DataFrame, event: str, validation_results: Dict[str, Any]) -> None:
    """Check that event flag values are valid ('y' or 'n')."""
    if event in df.columns:
        invalid_flags = df[~df[event].isin(["y", "n"])]
        if not invalid_flags.empty:
            invalid_seg_ids = invalid_flags["seg_id"].tolist()
            validation_results["errors"].append(f"❌ Invalid {event} flag values (must be 'y' or 'n'): {invalid_seg_ids}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append(f"✅ All {event} flag values are valid")
            validation_results["checks_passed"] += 1


def _check_event_window_values(df: pd.DataFrame, event: str, validation_results: Dict[str, Any]) -> None:
    """Check that event window values are valid for flagged segments."""
    if event not in df.columns:
        return

    flagged_segments = df[df[event] == "y"]
    for _, row in flagged_segments.iterrows():
        from_col = f"{event}_from_km"
        to_col = f"{event}_to_km"

        if from_col not in df.columns or to_col not in df.columns:
            validation_results["errors"].append(f"❌ Missing window columns for {event}: {from_col}, {to_col}")
            validation_results["checks_failed"] += 1
            continue

        from_km = row[from_col]
        to_km = row[to_col]

        if pd.isna(from_km) or pd.isna(to_km):
            validation_results["errors"].append(f"❌ Missing window values for {row['seg_id']} {event}: {from_col}={from_km}, {to_col}={to_km}")
            validation_results["checks_failed"] += 1
        elif from_km > to_km:
            validation_results["errors"].append(f"❌ Invalid window for {row['seg_id']} {event}: {from_col}={from_km} > {to_col}={to_km}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append(f"✅ Valid window for {row['seg_id']} {event}: {from_km}-{to_km}km")
            validation_results["checks_passed"] += 1


def _check_flow_type_values(df: pd.DataFrame, validation_results: Dict[str, Any]) -> None:
    """Check that flow_type values are valid."""
    if "flow_type" in df.columns:
        valid_flow_types = {"overtake", "merge", "none", "parallel", "counterflow"}
        invalid_flow_types = df[~df["flow_type"].isin(valid_flow_types)]
        if not invalid_flow_types.empty:
            invalid_seg_ids = invalid_flow_types["seg_id"].tolist()
            validation_results["errors"].append(f"❌ Invalid flow_type values (must be one of {valid_flow_types}): {invalid_seg_ids}")
            validation_results["checks_failed"] += 1
        else:
            validation_results["warnings"].append("✅ All flow_type values are valid")
            validation_results["checks_passed"] += 1


def _raise_if_validation_failed(validation_results: Dict[str, Any]) -> None:
    """Raise ValidationError if validation failed."""
    if validation_results["checks_failed"] > 0:
        error_summary = "\n".join(validation_results["errors"])
        raise ValidationError(f"❌ Preflight validation failed ({validation_results['checks_failed']} errors):\n{error_summary}")


def validate_segments_csv(file_path: str) -> Dict[str, Any]:
    """
    Validate segments.csv structure and content.

    Args:
        file_path: Path to segments.csv file (required)

    Returns:
        Dictionary with validation results

    Raises:
        ValidationError: If validation fails with detailed error message
    """
    if not os.path.exists(file_path):
        raise ValidationError(f"❌ File not found: {file_path}")

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise ValidationError(f"❌ Cannot read CSV file: {str(e)}")

    validation_results = {
        "file_path": file_path,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "checks_passed": 0,
        "checks_failed": 0,
        "errors": [],
        "warnings": []
    }

    # Run all validation checks
    _check_required_columns(df, validation_results)
    _check_empty_dataframe(df, validation_results)
    _check_seg_id_uniqueness(df, validation_results)
    _check_width_m_values(df, validation_results)
    _check_direction_values(df, validation_results)

    # Check event flags and windows
    event_columns = ["full", "half", "10K"]
    for event in event_columns:
        _check_event_flag_values(df, event, validation_results)
        _check_event_window_values(df, event, validation_results)

    # Issue #549: flow_type validation removed (flow_type no longer in segments.csv)
    # Flow_type is validated in flow.csv processing (see app/core/v2/flow.py::_get_required_flow_type)

    # Raise error if validation failed
    _raise_if_validation_failed(validation_results)

    return validation_results


def validate_preflight(file_path: str) -> bool:
    """
    Run preflight validation and return success status.

    Args:
        file_path: Path to segments.csv file (required)

    Returns:
        True if validation passes, False otherwise
    """
    try:
        results = validate_segments_csv(file_path=file_path)
        print(f"✅ Preflight validation passed: {results['checks_passed']} checks passed")
        return True
    except ValidationError as e:
        print(f"❌ Preflight validation failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Preflight validation error: {str(e)}")
        return False


if __name__ == "__main__":
    # Run preflight validation when called directly
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.validation.preflight <segments_csv_path>")
        exit(1)
    success = validate_preflight(file_path=sys.argv[1])
    exit(0 if success else 1)
