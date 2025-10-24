"""
Bin Summary Module - Canonical Operational Intelligence Artifact

This module generates bin_summary.json, a filtered and flagged JSON artifact that serves
as the single source of operational intelligence across:
- /density.md report
- /bins UI table  
- Segment heatmaps (Issue #280)
- Future exports or APIs

The module summarizes raw bin data (~19,440 records) into a curated set of 
operationally significant bins, with per-segment metadata.

CRITICAL ARCHITECTURAL NOTE:
This module uses the 'density' column (NOT 'density_peak') to maintain perfect parity
with the density report. The bins.parquet file contains pre-computed flagging data
that was generated using the 'density' column. Changing to 'density_peak' would
break this parity and cause discrepancies.

Issue #329: Create Reusable Bin Summary Module
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import pandas as pd
import numpy as np

from app.common.config import load_reporting
from app.bin_intelligence import (
    FlaggingConfig,
    compute_utilization_threshold,
    classify_flag_reason,
    classify_severity,
    get_severity_rank,
    filter_by_min_bin_length,
    apply_bin_flagging
)

logger = logging.getLogger(__name__)


@dataclass
class BinSummaryConfig:
    """Configuration for bin summary generation."""
    input_path: str = "bins.parquet"
    output_path: str = "bin_summary.json"
    strict_mode: bool = True  # Environment-dependent error handling
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.input_path:
            raise ValueError("input_path cannot be empty")
        if not self.output_path:
            raise ValueError("output_path cannot be empty")


def load_flagging_config() -> FlaggingConfig:
    """
    Load flagging configuration from reporting.yml with fallback to defaults.
    
    Returns:
        FlaggingConfig: Configuration for bin flagging logic
        
    Raises:
        FileNotFoundError: If reporting.yml not found
        ValueError: If configuration is invalid
    """
    try:
        reporting_config = load_reporting()
        flagging_config = reporting_config.get("flagging", {})
        
        return FlaggingConfig(
            min_los_flag=flagging_config.get("min_los_flag", "C"),
            utilization_pctile=flagging_config.get("utilization_pctile", 95),
            require_min_bin_len_m=flagging_config.get("require_min_bin_len_m", 10.0),
            density_field="density"  # Use density field from bins.parquet (NOT density_peak)
        )
    except FileNotFoundError as e:
        logger.warning(f"reporting.yml not found, using defaults: {e}")
        return FlaggingConfig()
    except Exception as e:
        logger.error(f"Error loading flagging config: {e}")
        if os.getenv("ENV") == "production":
            raise
        else:
            logger.warning("Using default configuration in development mode")
            return FlaggingConfig()


def format_time_for_display(iso_string: str) -> str:
    """
    Format an ISO timestamp string to HH:MM for display.
    
    Args:
        iso_string: ISO timestamp string (e.g., "2025-10-23T07:00:00Z")
        
    Returns:
        str: Formatted time string (e.g., "07:00")
    """
    try:
        # Parse the ISO string, assuming UTC if 'Z' is present
        dt_object = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt_object.strftime("%H:%M")
    except ValueError:
        logger.warning(f"Failed to format time '{iso_string}': Invalid ISO format")
        return iso_string
    except Exception as e:
        logger.warning(f"Failed to format time '{iso_string}': {e}")
        return iso_string


def load_bins_data(input_path: str) -> pd.DataFrame:
    """
    Load bin data from parquet file.
    
    Args:
        input_path: Path to bins.parquet file
        
    Returns:
        pd.DataFrame: Bin data with required columns
        
    Raises:
        FileNotFoundError: If input file not found
        ValueError: If data is invalid or missing required columns
    """
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Bin data file not found: {input_path}")
    
    try:
        df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(df)} bins from {input_path}")
        
        # Validate required columns
        required_columns = [
            "segment_id", "start_km", "end_km", "t_start", "t_end", 
            "density", "rate", "los_class"
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Add bin_len_m column if missing (required for filtering)
        if "bin_len_m" not in df.columns:
            df["bin_len_m"] = (df["end_km"] - df["start_km"]) * 1000  # Convert km to meters
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading bin data: {e}")
        raise




def generate_bin_summary(
    bins_df: pd.DataFrame,
    flagging_config: FlaggingConfig
) -> Dict[str, Any]:
    """
    Generate bin summary from raw bin dataset using existing flagging data.
    
    This creates the canonical operational intelligence artifact by using
    the EXACT SAME flagged bins as the density report.
    
    CRITICAL: This function uses the 'density' column (NOT 'density_peak') because:
    1. The bins.parquet file contains pre-computed flagging data
    2. The density report uses the same 'density' column for consistency
    3. Using 'density_peak' would break parity with the density report
    4. The flagging logic was already applied during bin generation phase
    
    Args:
        bins_df: DataFrame with bin data (already contains flagging info)
        flagging_config: Configuration for flagging logic (unused, kept for compatibility)
        
    Returns:
        dict: Bin summary with operationally significant bins
    """
    logger.info(f"Generating bin summary for {len(bins_df)} bins")
    
    # Use existing flagging data from bins.parquet
    # This matches the density report exactly since it uses the same data source
    # IMPORTANT: We use 'density' column, NOT 'density_peak' to maintain parity
    if 'flag_severity' in bins_df.columns:
        # Filter to only flagged bins (severity != 'none')
        filtered_bins = bins_df[bins_df['flag_severity'] != 'none'].copy()
        logger.info(f"Found {len(filtered_bins)} flagged bins (using existing flagging data)")
    else:
        # Fallback: apply flagging logic if not already present
        logger.warning("No existing flagging data found, applying flagging logic...")
        flagged_df = apply_bin_flagging(bins_df, flagging_config)
        from app.bin_intelligence import get_flagged_bins
        filtered_bins = get_flagged_bins(flagged_df)
        logger.info(f"Found {len(filtered_bins)} flagged bins (applied flagging logic)")
    
    # Group by segment
    segments = {}
    total_filtered_bins = 0
    
    for segment_id in bins_df["segment_id"].unique():
        segment_bins = bins_df[bins_df["segment_id"] == segment_id]
        segment_filtered_bins = filtered_bins[filtered_bins["segment_id"] == segment_id]
        
        # Format bins for this segment
        bins_list = []
        for _, bin_row in segment_filtered_bins.iterrows():
            bin_data = {
                "start_km": round(float(bin_row["start_km"]), 3),
                "end_km": round(float(bin_row["end_km"]), 3),
                "start_time": format_time_for_display(str(bin_row["t_start"])),
                "end_time": format_time_for_display(str(bin_row["t_end"])),
                "density": round(float(bin_row["density"]), 3),  # Use density column (NOT density_peak)
                "rate": round(float(bin_row["rate"]), 3),
                "los": str(bin_row["los_class"]),  # Use los_class column
                "flag": bin_row["flag_reason"] if pd.notna(bin_row["flag_reason"]) else "flagged"
            }
            bins_list.append(bin_data)
        
        segments[segment_id] = {
            "meta": {
                "total_bins": len(segment_bins),
                "flagged_bins": len(segment_filtered_bins)
            },
            "bins": bins_list
        }
        
        total_filtered_bins += len(segment_filtered_bins)
    
    # Generate summary
    segments_with_bins = sum(1 for seg in segments.values() if seg["meta"]["flagged_bins"] > 0)
    
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_bins": len(bins_df),
            "flagged_bins": total_filtered_bins,
            "segments_with_flags": segments_with_bins
        },
        "segments": segments
    }
    
    logger.info(f"Generated summary: {total_filtered_bins} operationally significant bins across {segments_with_bins} segments")
    return summary


def save_bin_summary(summary: Dict[str, Any], output_path: str) -> None:
    """
    Save bin summary to JSON file.
    
    Args:
        summary: Bin summary data
        output_path: Output file path
    """
    try:
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved bin summary to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving bin summary: {e}")
        raise


def generate_bin_summary_from_file(
    input_path: str,
    output_path: str,
    strict_mode: bool = True
) -> Dict[str, Any]:
    """
    Generate bin summary from input file with error handling.
    
    Args:
        input_path: Path to bins.parquet file
        output_path: Path for output JSON file
        strict_mode: If True, fail on errors; if False, continue with warnings
        
    Returns:
        dict: Generated bin summary
        
    Raises:
        FileNotFoundError: If input file not found (strict mode)
        ValueError: If data is invalid (strict mode)
    """
    try:
        # Load configuration
        flagging_config = load_flagging_config()
        
        # Load bin data
        bins_df = load_bins_data(input_path)
        
        # Generate summary from raw bin dataset
        summary = generate_bin_summary(bins_df, flagging_config)
        
        # Save to file
        save_bin_summary(summary, output_path)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating bin summary: {e}")
        if strict_mode:
            raise
        else:
            logger.warning(f"Continuing in lenient mode: {e}")
            # Return empty summary in lenient mode
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {"total_bins": 0, "flagged_bins": 0, "segments_with_flags": 0},
                "segments": {},
                "error": str(e)
            }


def main():
    """
    CLI entry point for standalone bin summary generation.
    
    Usage:
        python -m app.bin_summary --input bins.parquet --output bin_summary.json
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate bin summary JSON")
    parser.add_argument("--input", required=True, help="Input bins.parquet file")
    parser.add_argument("--output", required=True, help="Output bin_summary.json file")
    parser.add_argument("--strict", action="store_true", help="Enable strict error handling")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Set environment mode
    strict_mode = args.strict or os.getenv("ENV") == "production"
    
    try:
        summary = generate_bin_summary_from_file(
            input_path=args.input,
            output_path=args.output,
            strict_mode=strict_mode
        )
        
        print(f"✅ Bin summary generated successfully")
        print(f"📊 Total bins: {summary['summary']['total_bins']}")
        print(f"🚩 Flagged bins: {summary['summary']['flagged_bins']}")
        print(f"📍 Segments with flags: {summary['summary']['segments_with_flags']}")
        print(f"💾 Saved to: {args.output}")
        
    except Exception as e:
        print(f"❌ Error generating bin summary: {e}")
        if strict_mode:
            exit(1)
        else:
            print("⚠️  Continuing in lenient mode")


def generate_bin_summary_artifact(output_dir: str) -> str:
    """
    Generate bin_summary.json artifact for a given output directory.
    
    This function is called by the density report generation process
    to create the operational intelligence artifact.
    
    Args:
        output_dir: Directory containing bins.parquet (e.g., reports/2025-10-23/)
        
    Returns:
        str: Path to the generated bin_summary.json file
        
    Raises:
        Exception: If bin_summary generation fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Load bins data from the output directory
        bins_parquet_path = os.path.join(output_dir, "bins.parquet")
        if not os.path.exists(bins_parquet_path):
            raise ValueError(f"bins.parquet not found in {output_dir}")
        
        bins_df = load_bins_data(bins_parquet_path)
        if bins_df is None or bins_df.empty:
            raise ValueError("No bin data available for summary generation")
        
        # Load flagging configuration
        flagging_config = load_flagging_config()
        
        # Generate the summary
        summary = generate_bin_summary(bins_df, flagging_config)
        
        # Save to output directory
        bin_summary_path = os.path.join(output_dir, "bin_summary.json")
        with open(bin_summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Generated bin_summary.json with {summary['summary']['flagged_bins']} flagged bins")
        return bin_summary_path
        
    except Exception as e:
        logger.error(f"Failed to generate bin_summary artifact: {e}")
        raise


if __name__ == "__main__":
    main()
