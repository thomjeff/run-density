"""
New Density Report Generator for Issue #246

Implements the new density report structure as specified in Issue #246.
Replaces the legacy density report with the new format.

Key Features:
- Uses Parquet sources only (bins.parquet, segments.parquet, segment_windows_from_bins.parquet)
- Implements new flagging logic (los_high, rate_high, both)
- Executive Summary with operational status tied to flags
- Complete flagged segments list (no truncation)
- New report structure per Issue #246 spec
"""

from __future__ import annotations
import os
import time
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd

from .new_flagging import (
    NewFlaggingConfig, 
    apply_new_flagging, 
    get_flagged_bins_new,
    summarize_segment_flags_new,
    get_flagging_statistics_new
)
from .new_density_template_engine import NewDensityTemplateEngine

# Issue #283: Import SSOT for flagging logic parity
from . import flagging as ssot_flagging


def load_parquet_sources(reports_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load all required Parquet sources for the new report."""
    sources = {}
    
    # Load bins.parquet
    bins_path = reports_dir / "bins.parquet"
    if bins_path.exists():
        sources['bins'] = pd.read_parquet(bins_path)
        print(f"📊 Loaded {len(sources['bins'])} bins from {bins_path}")
    else:
        raise FileNotFoundError(f"bins.parquet not found at {bins_path}")
    
    # Load segment_windows_from_bins.parquet
    segment_windows_path = reports_dir / "segment_windows_from_bins.parquet"
    if segment_windows_path.exists():
        sources['segment_windows'] = pd.read_parquet(segment_windows_path)
        print(f"📊 Loaded {len(sources['segment_windows'])} segment windows from {segment_windows_path}")
    else:
        print(f"⚠️ segment_windows_from_bins.parquet not found at {segment_windows_path}")
        sources['segment_windows'] = pd.DataFrame()
    
    # Load segments.parquet (preferred) or fall back to segments.csv
    segments_parquet_path = Path("data/segments.parquet")
    segments_csv_path = Path("data/segments.csv")
    
    if segments_parquet_path.exists():
        sources['segments'] = pd.read_parquet(segments_parquet_path)
        print(f"📊 Loaded {len(sources['segments'])} segments from {segments_parquet_path}")
    elif segments_csv_path.exists():
        sources['segments'] = pd.read_csv(segments_csv_path)
        # Rename seg_id to segment_id for consistency
        if 'seg_id' in sources['segments'].columns:
            sources['segments'] = sources['segments'].rename(columns={'seg_id': 'segment_id'})
        print(f"📊 Loaded {len(sources['segments'])} segments from {segments_csv_path}")
    else:
        raise FileNotFoundError(f"Neither segments.parquet nor segments.csv found")
    
    return sources


def load_density_rulebook() -> Dict[str, Any]:
    """Load density rulebook configuration."""
    rulebook_path = Path("config/density_rulebook.yml")
    if not rulebook_path.exists():
        # Fallback to data directory
        rulebook_path = Path("data/density_rulebook.yml")
    
    if not rulebook_path.exists():
        print(f"⚠️ density_rulebook.yml not found, using defaults")
        return {
            'los': {
                'A': 0.0, 'B': 0.36, 'C': 0.54, 'D': 0.72, 'E': 1.08, 'F': 1.63
            },
            'flow_ref': {
                'warn': 0.0,  # Will be set based on data
                'critical': 0.0  # Will be set based on data
            }
        }
    
    import yaml
    with open(rulebook_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"📊 Loaded density rulebook from {rulebook_path}")
    return config


def create_flagging_config(rulebook: Dict[str, Any], bins_df: pd.DataFrame) -> NewFlaggingConfig:
    """Create flagging configuration from rulebook and data."""
    config = NewFlaggingConfig()
    
    # Set rate thresholds from rulebook or calculate from data
    flow_ref = rulebook.get('flow_ref', {})
    if 'warn' in flow_ref and 'critical' in flow_ref:
        config.rate_warn_threshold = flow_ref['warn']
        config.rate_critical_threshold = flow_ref['critical']
    else:
        # Calculate thresholds from data (top 10% and 5% of rate_per_m_per_min)
        # Only use occupied bins (density > 0) for threshold calculation
        occupied_bins = bins_df[bins_df['density'] > 0]
        if len(occupied_bins) > 0:
            # Calculate rate_per_m_per_min for threshold calculation
            # Assume 3.0m width for threshold calculation
            rate_per_m_per_min = (occupied_bins['rate'] / 3.0) * 60.0
            config.rate_warn_threshold = rate_per_m_per_min.quantile(0.90)  # Top 10%
            config.rate_critical_threshold = rate_per_m_per_min.quantile(0.95)  # Top 5%
            print(f"📊 Calculated rate thresholds from {len(occupied_bins)} occupied bins: warn={config.rate_warn_threshold:.2f}, critical={config.rate_critical_threshold:.2f}")
        else:
            # Fallback to defaults if no occupied bins
            config.rate_warn_threshold = 15.0
            config.rate_critical_threshold = 25.0
            print(f"⚠️ No occupied bins found, using default thresholds")
    
    return config


def generate_new_density_report(
    reports_dir: Path,
    output_path: Optional[Path] = None,
    app_version: str = "1.0.0"
) -> Dict[str, Any]:
    """
    Generate the new density report per Issue #246 specification.
    
    Args:
        reports_dir: Directory containing Parquet files
        output_path: Path to save the report (optional)
        app_version: Application version
        
    Returns:
        Dictionary with report content and metadata
    """
    start_time = time.time()
    
    print("🚀 Generating new density report (Issue #246)...")
    
    # Load all data sources
    sources = load_parquet_sources(reports_dir)
    bins_df = sources['bins']
    segments_df = sources['segments']
    segment_windows_df = sources['segment_windows']
    
    # Load rulebook
    rulebook = load_density_rulebook()
    
    # Create flagging configuration
    flagging_config = create_flagging_config(rulebook, bins_df)
    
    # Apply new flagging logic
    print("🔍 Applying new flagging logic...")
    bins_flagged = apply_new_flagging(bins_df, flagging_config, segments_df)
    
    # Get flagged bins only
    flagged_bins = get_flagged_bins_new(bins_flagged)
    
    # Issue #283: Use SSOT for flagging statistics to ensure report/artifact parity
    stats_ssot = ssot_flagging.get_flagging_summary_for_report(bins_flagged, rulebook)
    
    # Generate summaries (keep segment_summary for template compatibility)
    segment_summary = summarize_segment_flags_new(bins_flagged)
    
    # Map SSOT stats to expected format for template engine
    stats = {
        'total_bins': stats_ssot['total_bins'],
        'flagged_bins': stats_ssot['flagged_bins'],
        'flagged_percentage': (stats_ssot['flagged_bins'] / stats_ssot['total_bins'] * 100) if stats_ssot['total_bins'] > 0 else 0,
        'worst_severity': stats_ssot['worst_severity'],
        'worst_los': stats_ssot['worst_los'],
        'peak_density': stats_ssot['peak_density'],
        'peak_rate': stats_ssot['peak_rate'],  # Now in p/s (canonical)
        'peak_rate_per_m_per_min': 0  # Deprecated, computed on-demand if needed
    }
    
    # Create report context
    context = {
        'schema_version': '1.0.0',
        'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'app_version': app_version,
        'window_s': 30,  # TODO: Get from actual data
        'bin_km': 0.2,   # TODO: Get from actual data
        'rulebook': rulebook,
        'rate_warn_threshold': flagging_config.rate_warn_threshold,
        'rate_critical_threshold': flagging_config.rate_critical_threshold,
        'full_runners': 368,  # TODO: Get from actual data
        '10k_runners': 618,   # TODO: Get from actual data
        'half_runners': 912   # TODO: Get from actual data
    }
    
    # Generate report using new template engine
    print("📝 Generating report content...")
    template_engine = NewDensityTemplateEngine()
    report_content = template_engine.generate_report(
        context=context,
        bins_df=bins_df,
        segments_df=segments_df,
        segment_windows_df=segment_windows_df,
        flagged_bins_df=flagged_bins,
        segment_summary_df=segment_summary,
        stats=stats
    )
    
    # Save report if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report_content)
        print(f"✅ Report saved to: {output_path}")
    
    # Prepare results
    results = {
        'report_content': report_content,
        'stats': stats,
        'segment_summary': segment_summary,
        'flagged_bins': flagged_bins,
        'context': context,
        'generation_time': time.time() - start_time
    }
    
    print(f"✅ New density report generated in {results['generation_time']:.2f}s")
    print(f"📊 Summary: {stats['flagged_bins']} flagged bins, {len(segment_summary[segment_summary['flagged_bins'] > 0])} flagged segments")
    
    return results


def main():
    """Main function for testing the new density report."""
    # Find latest reports directory
    reports_base = Path("reports")
    if not reports_base.exists():
        print("❌ No reports directory found")
        return
    
    # Get latest date directory
    date_dirs = [d for d in reports_base.iterdir() if d.is_dir() and d.name.startswith("2025-")]
    if not date_dirs:
        print("❌ No date directories found in reports")
        return
    
    latest_dir = max(date_dirs, key=lambda d: d.name)
    print(f"📁 Using reports directory: {latest_dir}")
    
    # Generate report
    output_path = latest_dir / "Density_New.md"
    results = generate_new_density_report(latest_dir, output_path)
    
    print(f"\n🎉 New density report generated successfully!")
    print(f"📄 Report: {output_path}")
    print(f"⏱️ Generation time: {results['generation_time']:.2f}s")


if __name__ == "__main__":
    main()
