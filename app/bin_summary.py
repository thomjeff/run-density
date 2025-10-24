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
            density_field="density_peak"
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
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading bin data: {e}")
        raise


def generate_bin_summary(
    bins_df: pd.DataFrame,
    flagging_config: FlaggingConfig
) -> Dict[str, Any]:
    """
    Generate bin summary with operational intelligence filtering.
    
    Args:
        bins_df: DataFrame with bin data
        flagging_config: Configuration for flagging logic
        
    Returns:
        dict: Bin summary with filtered and flagged bins per segment
    """
    logger.info(f"Generating bin summary for {len(bins_df)} bins")
    
    # Apply bin flagging logic
    flagged_df = apply_bin_flagging(bins_df, flagging_config)
    
    # Get only flagged bins
    from app.bin_intelligence import get_flagged_bins
    flagged_bins = get_flagged_bins(flagged_df)
    
    logger.info(f"Found {len(flagged_bins)} flagged bins out of {len(bins_df)} total")
    
    # Group by segment
    segments = {}
    total_flagged = 0
    
    for segment_id in bins_df["segment_id"].unique():
        segment_bins = bins_df[bins_df["segment_id"] == segment_id]
        segment_flagged = flagged_bins[flagged_bins["segment_id"] == segment_id]
        
        # Format flagged bins for this segment
        bins_list = []
        for _, bin_row in segment_flagged.iterrows():
            bin_data = {
                "start_km": round(float(bin_row["start_km"]), 3),
                "end_km": round(float(bin_row["end_km"]), 3),
                "start_time": format_time_for_display(str(bin_row["t_start"])),
                "end_time": format_time_for_display(str(bin_row["t_end"])),
                "density": round(float(bin_row["density"]), 3),
                "rate": round(float(bin_row["rate"]), 3),
                "los": str(bin_row["los_class"]),
                "flag": bin_row["flag_reason"]
            }
            bins_list.append(bin_data)
        
        segments[segment_id] = {
            "meta": {
                "total_bins": len(segment_bins),
                "flagged_bins": len(segment_flagged)
            },
            "bins": bins_list
        }
        
        total_flagged += len(segment_flagged)
    
    # Generate summary
    segments_with_flags = sum(1 for seg in segments.values() if seg["meta"]["flagged_bins"] > 0)
    
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_bins": len(bins_df),
            "flagged_bins": total_flagged,
            "segments_with_flags": segments_with_flags
        },
        "segments": segments
    }
    
    logger.info(f"Generated summary: {total_flagged} flagged bins across {segments_with_flags} segments")
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
        
        # Generate summary
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


if __name__ == "__main__":
    main()
