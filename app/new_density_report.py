from __future__ import annotations

"""
New Density Report Generator for Issue #246

DEPRECATED: This module is marked as deprecated and scheduled for replacement in Phase 2.
Please use `density_report.py` as the primary entry point.

Implements the new density report structure as specified in Issue #246.
Replaces the legacy density report with the new format.

Key Features:
- Uses Parquet sources only (bins.parquet, segments.parquet, segment_windows_from_bins.parquet)
- Implements new flagging logic (los_high, rate_high, both)
- Executive Summary with operational status tied to flags
- Complete flagged segments list (no truncation)
- New report structure per Issue #246 spec

Issue #600: Refactored to use segment_metrics.json and flags.json as SSOT instead of recalculating from bins.
"""

import warnings
warnings.warn(
    "This module is marked as deprecated and scheduled for replacement in Phase 2. "
    "Please use `density_report.py` as the primary entry point.",
    DeprecationWarning
)
import os
import time
import json
import functools
import logging
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


def load_parquet_sources(reports_dir: Path, bins_dir: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
    """
    Load all required Parquet sources for the new report.
    
    Args:
        reports_dir: Directory containing segments.parquet
        bins_dir: Optional directory containing bins.parquet and segment_windows_from_bins.parquet.
                  If None, reads from reports_dir (for backward compatibility).
                  Issue #519/542: Prefer reading from bins_dir to avoid duplicate files.
    """
    sources = {}
    
    # Issue #519/542: Read bins.parquet from bins_dir if provided, otherwise from reports_dir (backward compat)
    if bins_dir is not None:
        bins_path = bins_dir / "bins.parquet"
        segment_windows_path = bins_dir / "segment_windows_from_bins.parquet"
    else:
        bins_path = reports_dir / "bins.parquet"
        segment_windows_path = reports_dir / "segment_windows_from_bins.parquet"
    
    # Load bins.parquet
    if bins_path.exists():
        sources['bins'] = pd.read_parquet(bins_path)
        print(f"📊 Loaded {len(sources['bins'])} bins from {bins_path}")
    else:
        raise FileNotFoundError(f"bins.parquet not found at {bins_path}")
    
    # Load segment_windows_from_bins.parquet
    if segment_windows_path.exists():
        sources['segment_windows'] = pd.read_parquet(segment_windows_path)
        print(f"📊 Loaded {len(sources['segment_windows'])} segment windows from {segment_windows_path}")
    else:
        print(f"⚠️ segment_windows_from_bins.parquet not found at {segment_windows_path}")
        sources['segment_windows'] = pd.DataFrame()
    
    # Load segments.parquet from reports_dir (v2 saves day-filtered segments there)
    # NOTE: Do NOT fall back to data/segments.parquet as it's a legacy file and won't produce valid reports
    segments_parquet_path = reports_dir / "segments.parquet"
    
    if segments_parquet_path.exists():
        # v2 saves day-filtered segments.parquet in reports directory
        sources['segments'] = pd.read_parquet(segments_parquet_path)
        print(f"📊 Loaded {len(sources['segments'])} segments from {segments_parquet_path}")
    else:
        raise FileNotFoundError(
            f"segments.parquet not found at {segments_parquet_path}. "
            f"v2 pipeline must generate segments.parquet in reports directory."
        )
    
    return sources


def load_density_rulebook() -> Dict[str, Any]:
    """
    Load density rulebook configuration using SSOT loader.
    
    Issue #655: Uses app.common.config.load_rulebook() as SSOT.
    Removes hardcoded fallbacks to data/ directory and silent defaults.
    Fails fast if rulebook not found.
    
    Returns:
        dict: Parsed rulebook from config/density_rulebook.yml
        
    Raises:
        FileNotFoundError: If density_rulebook.yml not found at config/
    """
    from app.common.config import load_rulebook
    
    # Issue #655: Use SSOT loader which fails fast if rulebook missing
    rulebook = load_rulebook()
    logger = logging.getLogger(__name__)
    logger.info("📊 Loaded density rulebook using SSOT loader (app.common.config.load_rulebook)")
    return rulebook


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


# Issue #600: Helper functions to load JSON artifacts as SSOT
def load_segment_metrics_from_json(segment_metrics_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load segment_metrics.json file.
    
    Issue #600: JSON SSOT is mandatory - fails if file not found.
    
    Args:
        segment_metrics_path: Path to segment_metrics.json file
        
    Returns:
        Dictionary mapping segment_id to metrics dict
        
    Raises:
        FileNotFoundError: If segment_metrics.json file does not exist
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not segment_metrics_path.exists():
        raise FileNotFoundError(
            f"Issue #600: segment_metrics.json is required (SSOT) but not found at {segment_metrics_path}"
        )
    
    try:
        data = json.loads(segment_metrics_path.read_text(encoding='utf-8'))
        
        # Handle different formats:
        # 1. Dict with segment_id keys (direct format)
        # 2. Dict with 'items' key containing list
        # 3. List of segment dicts
        
        segment_metrics = {}
        
        if isinstance(data, dict):
            # Filter out summary fields (peak_density, peak_rate, segments_with_flags, etc.)
            summary_fields = {'peak_density', 'peak_rate', 'segments_with_flags', 'flagged_bins', 
                            'overtaking_segments', 'co_presence_segments'}
            
            if 'items' in data:
                # Format: {"items": [{segment_id: {...}, ...}]}
                for item in data['items']:
                    if isinstance(item, dict) and 'segment_id' in item:
                        seg_id = item['segment_id']
                        segment_metrics[seg_id] = {k: v for k, v in item.items() if k != 'segment_id'}
            else:
                # Direct dict format: {segment_id: {...}, ...}
                for seg_id, metrics in data.items():
                    if seg_id not in summary_fields and isinstance(metrics, dict):
                        segment_metrics[seg_id] = metrics
        elif isinstance(data, list):
            # Array format: [{segment_id: "...", ...}, ...]
            for item in data:
                if isinstance(item, dict) and 'segment_id' in item:
                    seg_id = item['segment_id']
                    segment_metrics[seg_id] = {k: v for k, v in item.items() if k != 'segment_id'}
        
        logger.info(f"✅ Loaded {len(segment_metrics)} segment metrics from {segment_metrics_path}")
        if not segment_metrics:
            raise ValueError(f"Issue #600: segment_metrics.json is empty or invalid at {segment_metrics_path}")
        return segment_metrics
        
    except FileNotFoundError:
        raise  # Re-raise FileNotFoundError
    except Exception as e:
        logger.error(f"Failed to load segment_metrics.json from {segment_metrics_path}: {e}", exc_info=True)
        raise RuntimeError(f"Issue #600: Failed to load segment_metrics.json from {segment_metrics_path}: {e}") from e


def load_flags_from_json(flags_path: Path) -> List[Dict[str, Any]]:
    """
    Load flags.json file.
    
    Issue #600: JSON SSOT is mandatory - fails if file not found.
    
    Args:
        flags_path: Path to flags.json file
        
    Returns:
        List of flag dicts
        
    Raises:
        FileNotFoundError: If flags.json file does not exist
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not flags_path.exists():
        raise FileNotFoundError(
            f"Issue #600: flags.json is required (SSOT) but not found at {flags_path}"
        )
    
    try:
        data = json.loads(flags_path.read_text(encoding='utf-8'))
        
        # flags.json is typically a list of flag entries
        if isinstance(data, list):
            logger.info(f"✅ Loaded {len(data)} flags from {flags_path}")
            return data
        elif isinstance(data, dict) and 'flagged_segments' in data:
            # Alternative format: {"flagged_segments": [...]}
            flags = data['flagged_segments']
            if not isinstance(flags, list):
                raise ValueError(f"Issue #600: flags.json has invalid format at {flags_path} (flagged_segments is not a list)")
            logger.info(f"✅ Loaded {len(flags)} flags from {flags_path}")
            return flags
        else:
            raise ValueError(f"Issue #600: flags.json has unexpected format at {flags_path} (expected list or dict with 'flagged_segments' key)")
            
    except FileNotFoundError:
        raise  # Re-raise FileNotFoundError
    except Exception as e:
        logger.error(f"Failed to load flags.json from {flags_path}: {e}", exc_info=True)
        raise RuntimeError(f"Issue #600: Failed to load flags.json from {flags_path}: {e}") from e


def convert_json_to_segment_summary(
    segment_metrics: Dict[str, Dict[str, Any]],
    flags: List[Dict[str, Any]],
    bins_df: pd.DataFrame,
    segments_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Convert segment_metrics.json and flags.json to segment_summary DataFrame format.
    
    Issue #600: This function creates a DataFrame matching the format expected by the template engine,
    using JSON artifacts as the SSOT for metrics, while still using bins.parquet for worst_bin details
    and total_bins count (which are not in the JSON files).
    
    Args:
        segment_metrics: Dict mapping segment_id to metrics from segment_metrics.json
        flags: List of flag dicts from flags.json
        bins_df: Bins DataFrame (used for worst_bin details and total_bins count)
        segments_df: Segments DataFrame (for seg_label)
        
    Returns:
        DataFrame with columns matching summarize_segment_flags_new() output
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Build flags lookup by segment_id
    flags_by_segment: Dict[str, Dict[str, Any]] = {}
    for flag in flags:
        seg_id = flag.get('segment_id') or flag.get('seg_id')
        if seg_id:
            flags_by_segment[seg_id] = flag
    
    # Get total_bins per segment from bins_df
    segment_col = 'segment_id' if 'segment_id' in bins_df.columns else 'seg_id'
    total_bins_per_segment = bins_df.groupby(segment_col).size().to_dict()
    
    # Get worst_bin details from bins_df (for flagged segments)
    # Find the worst bin (by severity, then density) for each flagged segment
    severity_rank = {'none': 0, 'watch': 1, 'caution': 1, 'alert': 2, 'critical': 3}
    
    def get_severity_rank(severity: str) -> int:
        return severity_rank.get(severity.lower(), 0)
    
    worst_bin_details = {}
    flagged_bins_df = bins_df[bins_df['flag_severity'] != 'none'].copy() if 'flag_severity' in bins_df.columns else pd.DataFrame()
    
    if len(flagged_bins_df) > 0:
        flagged_bins_df['severity_rank'] = flagged_bins_df['flag_severity'].apply(get_severity_rank)
        flagged_bins_sorted = flagged_bins_df.sort_values(
            ['severity_rank', 'density', 'rate'], 
            ascending=[False, False, False]
        )
        
        for seg_id, group in flagged_bins_sorted.groupby(segment_col):
            worst_bin = group.iloc[0]
            worst_bin_details[seg_id] = {
                'worst_bin_start_km': worst_bin.get('start_km', 0.0),
                'worst_bin_end_km': worst_bin.get('end_km', 0.0),
                'worst_bin_t_start': worst_bin.get('t_start'),
                'worst_bin_rate': worst_bin.get('rate', 0.0),
                'worst_bin_density': worst_bin.get('density', 0.0),
                'worst_bin_los': worst_bin['los_class']
            }
    
    # Build segment_summary DataFrame
    summaries = []
    
    # Get seg_label lookup from segments_df
    seg_label_col = 'seg_label' if 'seg_label' in segments_df.columns else 'label'
    segment_id_col = 'segment_id' if 'segment_id' in segments_df.columns else 'seg_id'
    seg_label_lookup = {}
    if segment_id_col in segments_df.columns and seg_label_col in segments_df.columns:
        seg_label_lookup = dict(zip(segments_df[segment_id_col], segments_df[seg_label_col]))
    
    # Process all segments (from segment_metrics + flags)
    all_segment_ids = set(segment_metrics.keys()) | set(flags_by_segment.keys())
    
    for seg_id in sorted(all_segment_ids):
        metrics = segment_metrics.get(seg_id, {})
        flag_data = flags_by_segment.get(seg_id, {})
        
        # Get total_bins from bins_df
        total_bins = total_bins_per_segment.get(seg_id, 0)
        
        # Get flagged_bins from flags.json (preferred) or calculate from bins_df
        flagged_bins = flag_data.get('flagged_bins', 0)
        if flagged_bins == 0 and seg_id in flagged_bins_df[segment_col].values if len(flagged_bins_df) > 0 else False:
            # Fallback: count from bins_df if not in flags.json
            flagged_bins = len(flagged_bins_df[flagged_bins_df[segment_col] == seg_id])
        
        flagged_percentage = (flagged_bins / total_bins * 100) if total_bins > 0 else 0.0
        
        # Get worst severity and reason from flags.json
        worst_severity = flag_data.get('worst_severity', 'none')
        worst_reason = flag_data.get('worst_reason', 'none')
        
        # Get worst_bin details (from bins_df)
        worst_bin = worst_bin_details.get(seg_id, {
            'worst_bin_start_km': 0.0,
            'worst_bin_end_km': 0.0,
            'worst_bin_t_start': None,
            'worst_bin_rate': 0.0,
            'worst_bin_density': 0.0,
            'worst_bin_los': 'A'
        })
        
        # Get metrics from segment_metrics.json
        peak_density = metrics.get('peak_density', 0.0)
        peak_rate = metrics.get('peak_rate', 0.0)  # p/s (canonical)
        worst_los = metrics.get('worst_los', 'A')
        
        # Convert peak_rate (p/s) to peak_rate_per_m_per_min
        # peak_rate_per_m_per_min = peak_rate (p/s) * 60 (s/min) / width_m (m)
        # But we don't have width_m here, so we'll need to get it from segments_df or calculate later
        # For now, set to 0 - will be calculated in template if needed
        peak_rate_per_m_per_min = 0.0  # Will be calculated if width_m available
        
        # Get seg_label
        seg_label = seg_label_lookup.get(seg_id, seg_id)
        
        # peak_los: use worst_los from metrics
        peak_los = worst_los
        
        summaries.append({
            'segment_id': seg_id,
            'seg_label': seg_label,
            'total_bins': total_bins,
            'flagged_bins': flagged_bins,
            'flagged_percentage': flagged_percentage,
            'worst_severity': worst_severity,
            'worst_reason': worst_reason,
            'worst_bin_start_km': worst_bin['worst_bin_start_km'],
            'worst_bin_end_km': worst_bin['worst_bin_end_km'],
            'worst_bin_t_start': worst_bin['worst_bin_t_start'],
            'worst_bin_rate': worst_bin['worst_bin_rate'],
            'worst_bin_density': worst_bin['worst_bin_density'],
            'worst_bin_los': worst_bin['worst_bin_los'],
            'peak_density': peak_density,
            'peak_rate_per_m_per_min': peak_rate_per_m_per_min,  # Will be recalculated if width_m available
            'peak_los': peak_los
        })
    
    df = pd.DataFrame(summaries)
    
    # Calculate peak_rate_per_m_per_min if width_m is available in segments_df
    if 'width_m' in segments_df.columns and segment_id_col in segments_df.columns:
        width_lookup = dict(zip(segments_df[segment_id_col], segments_df['width_m']))
        # Also need peak_rate from segment_metrics
        # peak_rate_per_m_per_min = peak_rate (p/s) * 60 (s/min) / width_m (m)
        for idx, row in df.iterrows():
            seg_id = row['segment_id']
            width_m = width_lookup.get(seg_id, 0.0)
            metrics = segment_metrics.get(seg_id, {})
            peak_rate = metrics.get('peak_rate', 0.0)  # p/s
            if width_m > 0 and peak_rate > 0:
                df.at[idx, 'peak_rate_per_m_per_min'] = (peak_rate * 60.0) / width_m
            else:
                df.at[idx, 'peak_rate_per_m_per_min'] = 0.0
    
    logger.info(f"✅ Converted JSON to segment_summary DataFrame: {len(df)} segments")
    return df


def generate_new_density_report(
    reports_dir: Path,
    segment_metrics_path: Path,  # Issue #600: Path to segment_metrics.json (SSOT - required)
    output_path: Optional[Path] = None,
    app_version: str = "1.0.0",
    events: Optional[Dict[str, Dict[str, Any]]] = None,
    event_groups_res: Optional[Dict[str, Dict[str, Any]]] = None,  # Issue #573: RES data for Executive Summary
    bins_dir: Optional[Path] = None  # Issue #519/542: Optional bins directory to avoid duplicate files
) -> Dict[str, Any]:
    """
    Generate the new density report per Issue #246 specification.
    
    Issue #600: Loads metrics from segment_metrics.json and flags.json as SSOT (mandatory).
    
    Args:
        reports_dir: Directory containing segments.parquet
        output_path: Path to save the report (optional)
        app_version: Application version
        events: Optional dict of event info
        event_groups_res: Optional event groups RES data (Issue #573)
        bins_dir: Optional directory containing bins.parquet and segment_windows_from_bins.parquet.
                  If None, reads from reports_dir (for backward compatibility).
                  Issue #519/542: Prefer reading from bins_dir to avoid duplicate files.
        segment_metrics_path: Path to segment_metrics.json file (Issue #600 - required).
                             Expected location: {day}/ui/metrics/segment_metrics.json
                             flags.json should be in the same directory.
        
    Raises:
        FileNotFoundError: If segment_metrics.json or flags.json files are not found
        RuntimeError: If JSON files cannot be loaded or are invalid
        
    Returns:
        Dictionary with report content and metadata
    """
    import logging
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    
    logger.info("🚀 Generating new density report (Issue #246)...")
    
    # Load all data sources
    sources = load_parquet_sources(reports_dir, bins_dir=bins_dir)
    bins_df = sources['bins']
    segments_df = sources['segments']
    segment_windows_df = sources['segment_windows']
    
    # Issue #600: Load metrics from JSON artifacts (SSOT - mandatory)
    logger.info(f"📊 Issue #600: Loading metrics from JSON SSOT: {segment_metrics_path}")
    
    # Load segment_metrics.json (mandatory - will raise FileNotFoundError if missing)
    segment_metrics = load_segment_metrics_from_json(segment_metrics_path)
    
    # Load flags.json (mandatory - will raise FileNotFoundError if missing)
    flags_path = segment_metrics_path.parent / "flags.json"
    flags = load_flags_from_json(flags_path)
    
    logger.info("✅ Issue #600: Loaded metrics from JSON artifacts (SSOT)")
    
    # Convert JSON to segment_summary DataFrame
    segment_summary = convert_json_to_segment_summary(
        segment_metrics, flags, bins_df, segments_df
    )
    
    # Get flagged bins (still needed for template)
    # Issue #600: Extract from bins_df using flag_severity (bins.parquet already has flags from pipeline)
    logger.info("📊 Getting flagged bins...")
    if 'flag_severity' in bins_df.columns:
        flagged_bins = bins_df[bins_df['flag_severity'] != 'none'].copy()
    else:
        # This should not happen if bins.parquet is properly generated by pipeline
        flagged_bins = pd.DataFrame()
        logger.warning("⚠️ flag_severity column not found in bins_df, using empty flagged_bins")
    
    logger.info(f"✅ Found {len(flagged_bins)} flagged bins")
    
    # Issue #283: Use SSOT for flagging statistics to ensure report/artifact parity
    # Issue #600: Calculate stats from segment_summary DataFrame (from JSON SSOT)
    logger.info("📈 Computing flagging statistics...")
    
    # Calculate stats from segment_summary DataFrame
    total_bins = segment_summary['total_bins'].sum()
    flagged_bins_count = segment_summary['flagged_bins'].sum()
    worst_severity = segment_summary['worst_severity'].apply(
        lambda x: {'none': 0, 'watch': 1, 'caution': 1, 'alert': 2, 'critical': 3}.get(x.lower(), 0)
    ).max()
    worst_severity_str = segment_summary.loc[
        segment_summary['worst_severity'].apply(
            lambda x: {'none': 0, 'watch': 1, 'caution': 1, 'alert': 2, 'critical': 3}.get(x.lower(), 0)
        ).idxmax(), 'worst_severity'
    ] if len(segment_summary) > 0 else 'none'
    worst_los = segment_summary['peak_los'].max() if len(segment_summary) > 0 else 'A'
    peak_density = segment_summary['peak_density'].max() if len(segment_summary) > 0 else 0.0
    peak_rate = segment_summary['peak_rate_per_m_per_min'].max() if len(segment_summary) > 0 else 0.0
    # Convert peak_rate_per_m_per_min to p/s (need width_m - use average or max)
    # For stats, we'll use the max peak_rate_per_m_per_min * average_width / 60
    # This is approximate, but stats are for summary only
    peak_rate_ps = peak_rate  # Keep as-is for now, will be converted in template if needed
    
    stats = {
        'total_bins': int(total_bins),
        'flagged_bins': int(flagged_bins_count),
        'flagged_percentage': (flagged_bins_count / total_bins * 100) if total_bins > 0 else 0,
        'worst_severity': worst_severity_str,
        'worst_los': worst_los,
        'peak_density': float(peak_density),
        'peak_rate': float(peak_rate_ps),
        'peak_rate_per_m_per_min': float(peak_rate)
    }
    logger.info(f"✅ Statistics computed: {stats.get('flagged_bins', 0)}/{stats.get('total_bins', 0)} flagged")
    
    # Create report context
    # Issue #600: Always load rulebook for context (needed for threshold display)
    rulebook = load_density_rulebook()
    flagging_config = create_flagging_config(rulebook, bins_df)
    
    context = {
        'schema_version': '1.0.0',
        'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'app_version': app_version,
        'window_s': 30,  # TODO: Get from actual data
        'bin_km': 0.2,   # TODO: Get from actual data
        'rulebook': rulebook,
        'rate_warn_threshold': flagging_config.rate_warn_threshold,
        'rate_critical_threshold': flagging_config.rate_critical_threshold,
        'events': events,  # Pass events for dynamic start times (v2)
        'event_groups_res': event_groups_res,  # Issue #573: RES data for Executive Summary
        # Issue #512: Removed hardcoded runner counts - must be calculated from actual data
    }
    
    # Generate report using new template engine
    logger.info("📝 Generating report content...")
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
        logger.info(f"✅ Report saved to: {output_path}")
    
    # Prepare results
    results = {
        'report_content': report_content,
        'stats': stats,
        'segment_summary': segment_summary,
        'flagged_bins': flagged_bins,
        'context': context,
        'generation_time': time.time() - start_time
    }
    
    return results
