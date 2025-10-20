#!/usr/bin/env python3
"""
CSV Export Utilities

Provides standardized CSV export functions with consistent decimal precision
to ensure human-readable exports are properly formatted.
"""

import pandas as pd
from pathlib import Path
from typing import Optional


DECIMAL_PRECISION = 4  # Standard precision for all numeric exports


def export_bins_to_csv(parquet_path: str, csv_path: Optional[str] = None) -> str:
    """
    Export bins.parquet to CSV with consistent 4 decimal place formatting.
    
    Args:
        parquet_path: Path to bins.parquet file
        csv_path: Optional output path. If None, uses same name with .csv extension
        
    Returns:
        Path to exported CSV file
    """
    parquet_file = Path(parquet_path)
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
    
    # Read parquet
    df = pd.read_parquet(parquet_file)
    
    # Round numeric columns to standard precision
    numeric_cols = ['start_km', 'end_km', 'density', 'rate', 'bin_size_km']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].round(DECIMAL_PRECISION)
    
    # Determine output path
    if csv_path is None:
        csv_path = parquet_file.parent / f"{parquet_file.stem}_readable.csv"
    
    # Export with consistent float formatting
    df.to_csv(csv_path, index=False, float_format=f'%.{DECIMAL_PRECISION}f')
    
    return str(csv_path)


def export_segment_windows_to_csv(parquet_path: str, csv_path: Optional[str] = None) -> str:
    """
    Export segment_windows_from_bins.parquet to CSV with consistent formatting.
    
    Args:
        parquet_path: Path to segment_windows_from_bins.parquet file
        csv_path: Optional output path. If None, uses same name with .csv extension
        
    Returns:
        Path to exported CSV file
    """
    parquet_file = Path(parquet_path)
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
    
    # Read parquet
    df = pd.read_parquet(parquet_file)
    
    # Round numeric columns to standard precision
    numeric_cols = ['density_mean', 'density_peak', 'n_bins']
    for col in numeric_cols:
        if col in df.columns:
            if col == 'n_bins':
                # Keep n_bins as integer
                df[col] = df[col].astype(int)
            else:
                df[col] = df[col].round(DECIMAL_PRECISION)
    
    # Determine output path
    if csv_path is None:
        csv_path = parquet_file.parent / f"{parquet_file.stem}_readable.csv"
    
    # Export with consistent float formatting
    df.to_csv(csv_path, index=False, float_format=f'%.{DECIMAL_PRECISION}f')
    
    return str(csv_path)


def export_all_parquet_to_csv(report_dir: str) -> dict:
    """
    Export all parquet files in a report directory to CSV format.
    
    Args:
        report_dir: Path to report directory (e.g., reports/2025-10-15)
        
    Returns:
        Dictionary mapping parquet filenames to exported CSV paths
    """
    report_path = Path(report_dir)
    if not report_path.exists():
        raise FileNotFoundError(f"Report directory not found: {report_dir}")
    
    exported = {}
    
    # Export bins.parquet
    bins_parquet = report_path / "bins.parquet"
    if bins_parquet.exists():
        csv_path = export_bins_to_csv(str(bins_parquet))
        exported['bins.parquet'] = csv_path
        print(f"✅ Exported: {csv_path}")
    
    # Export segment_windows_from_bins.parquet
    seg_parquet = report_path / "segment_windows_from_bins.parquet"
    if seg_parquet.exists():
        csv_path = export_segment_windows_to_csv(str(seg_parquet))
        exported['segment_windows_from_bins.parquet'] = csv_path
        print(f"✅ Exported: {csv_path}")
    
    return exported


if __name__ == '__main__':
    # CLI usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python csv_export_utils.py <report_directory>")
        print("Example: python csv_export_utils.py reports/2025-10-15")
        sys.exit(1)
    
    report_dir = sys.argv[1]
    
    print(f"📊 Exporting parquet files from: {report_dir}\n")
    print("="*80)
    
    exported = export_all_parquet_to_csv(report_dir)
    
    print("="*80)
    print(f"\n✅ Exported {len(exported)} files with {DECIMAL_PRECISION} decimal precision")

