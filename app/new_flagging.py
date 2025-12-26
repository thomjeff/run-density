from __future__ import annotations

"""
New Flagging Logic for Issue #246 - New Density Report

DEPRECATED: This module is marked as deprecated and scheduled for replacement in Phase 2.
Please use `flagging.py` or `rulebook.py` as the primary entry point.

This module now acts as a thin wrapper around rulebook.py to maintain
backward compatibility during the transition.
"""

import warnings
warnings.warn(
    "This module is marked as deprecated and scheduled for replacement in Phase 2. "
    "Please use `flagging.py` or `rulebook.py` as the primary entry point.",
    DeprecationWarning
)
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import pandas as pd
import numpy as np

# Issue #254: Use centralized rulebook for all flagging
from . import rulebook
from .schema_resolver import resolve_schema

logger = logging.getLogger(__name__)


@dataclass
class NewFlaggingConfig:
    """Configuration for new flagging logic per Issue #246 spec."""
    # Density thresholds (LOS-based)
    density_watch_los: str = 'C'      # density ≥ C → watch
    density_critical_los: str = 'E'   # density ≥ E → critical
    
    # Rate thresholds (rate_per_m_per_min)
    rate_warn_threshold: float = 0.0  # Will be set from rulebook
    rate_critical_threshold: float = 0.0  # Will be set from rulebook
    
    # Minimum bin length to consider
    require_min_bin_len_m: float = 10.0


def get_los_thresholds() -> Dict[str, float]:
    """Get LOS density thresholds from rulebook."""
    # These match the current LOS_AREAL_THRESHOLDS
    return {
        'A': 0.0,
        'B': 0.36,
        'C': 0.54,
        'D': 0.72,
        'E': 1.08,
        'F': 1.63
    }


def classify_density_los(density: float) -> str:
    """Classify density into LOS level (A-F)."""
    thresholds = get_los_thresholds()
    
    if density < thresholds['B']:
        return 'A'
    elif density < thresholds['C']:
        return 'B'
    elif density < thresholds['D']:
        return 'C'
    elif density < thresholds['E']:
        return 'D'
    elif density < thresholds['F']:
        return 'E'
    else:
        return 'F'


def meets_density_threshold(density: float, los_threshold: str) -> bool:
    """Check if density meets or exceeds LOS threshold."""
    thresholds = get_los_thresholds()
    threshold_value = thresholds.get(los_threshold, float('inf'))
    return density >= threshold_value


def calculate_rate_per_m_per_min(rate: float, width_m: float) -> float:
    """Calculate rate per meter per minute: (rate / width_m) × 60"""
    if width_m <= 0:
        return 0.0
    return (rate / width_m) * 60.0


def classify_flag_reason_new(
    density: float,
    rate_per_m_per_min: float,
    config: NewFlaggingConfig
) -> Tuple[str, str]:
    """
    Classify flag reason and severity based on new Issue #246 logic.
    
    Args:
        density: Areal density (p/m²)
        rate_per_m_per_min: Rate per meter per minute (p/m/min)
        config: Flagging configuration
        
    Returns:
        Tuple of (reason, severity)
        - reason: 'los_high', 'rate_high', 'both', or 'none'
        - severity: 'critical', 'watch', or 'none'
    """
    # Check density conditions
    density_watch = meets_density_threshold(density, config.density_watch_los)
    density_critical = meets_density_threshold(density, config.density_critical_los)
    
    # Check rate conditions
    rate_watch = rate_per_m_per_min >= config.rate_warn_threshold
    rate_critical = rate_per_m_per_min >= config.rate_critical_threshold
    
    # Determine reason and severity
    if density_critical and rate_critical:
        return 'both', 'critical'
    elif density_critical or rate_critical:
        return 'both', 'critical'  # Either condition critical = critical
    elif density_watch and rate_watch:
        return 'both', 'watch'
    elif density_watch:
        return 'los_high', 'watch'
    elif rate_watch:
        return 'rate_high', 'watch'
    else:
        return 'none', 'none'


def _load_and_apply_segment_metadata(
    result_df: pd.DataFrame,
    segments_df: Optional[pd.DataFrame]
) -> pd.DataFrame:
    """Load and apply segment metadata (width_m, seg_label, schema_key)."""
    if segments_df is not None:
        segment_id_col = 'seg_id' if 'seg_id' in segments_df.columns else 'segment_id'
        
        if segment_id_col in segments_df.columns:
            seg_lookup_cols = [segment_id_col, 'width_m', 'seg_label']
            if 'segment_type' in segments_df.columns:
                seg_lookup_cols.append('segment_type')
            
            seg_lookup = segments_df[seg_lookup_cols].set_index(segment_id_col)
            result_df['width_m'] = result_df['segment_id'].map(seg_lookup['width_m']).fillna(3.0)
            result_df['seg_label'] = result_df['segment_id'].map(seg_lookup['seg_label']).fillna(result_df['segment_id'])
            
            # Resolve schema using schema_resolver (Issue #254)
            def get_schema(segment_id):
                segment_type = None
                if 'segment_type' in segments_df.columns and segment_id in seg_lookup.index:
                    try:
                        lookup = seg_lookup.loc[segment_id, 'segment_type']
                        segment_type = lookup if pd.notna(lookup) else None
                    except (KeyError, IndexError):
                        segment_type = None
                return resolve_schema(segment_id, segment_type)
            
            result_df['schema_key'] = result_df['segment_id'].apply(get_schema)
        else:
            result_df['width_m'] = 3.0
            result_df['seg_label'] = result_df['segment_id']
            result_df['schema_key'] = result_df['segment_id'].apply(lambda sid: resolve_schema(sid, None))
    else:
        result_df['width_m'] = 3.0
        result_df['seg_label'] = result_df['segment_id']
        result_df['schema_key'] = result_df['segment_id'].apply(lambda sid: resolve_schema(sid, None))
    
    return result_df


def _compute_window_idx_from_timestamp(t_start_str) -> int:
    """Compute window index from ISO timestamp."""
    from datetime import datetime
    
    try:
        if not t_start_str or pd.isna(t_start_str):
            return 0
        # Parse ISO timestamp
        dt = datetime.fromisoformat(t_start_str.replace('Z', '+00:00'))
        # Assume race starts at 07:00
        race_start = datetime(dt.year, dt.month, dt.day, 7, 0, 0, tzinfo=dt.tzinfo)
        elapsed_seconds = (dt - race_start).total_seconds()
        
        # Detect window duration from data (2-minute vs 30-second windows)
        # If time ends in :00, :02, :04, etc. it's 2-minute windows
        # Otherwise it's 30-second windows
        if dt.minute % 2 == 0 and dt.second == 0:
            window_duration = 120  # 2-minute windows
        else:
            window_duration = 30   # 30-second windows
        
        return max(0, int(elapsed_seconds // window_duration))
    except Exception:
        return 0


def _compute_utilization_percentile(result_df: pd.DataFrame) -> pd.DataFrame:
    """Compute utilization percentile before flagging (Issue #254)."""
    try:
        from .utilization import add_utilization_percentile, ensure_rpm
        
        # Validate required columns before flagging (Issue #556)
        required_cols = ['rate', 'width_m']
        missing_cols = [col for col in required_cols if col not in result_df.columns]
        if missing_cols:
            raise KeyError(f"Missing required columns for flagging: {missing_cols}. These are required to compute rate_per_m_per_min.")
        
        # Compute window_idx from t_start (if available)
        if 't_start' in result_df.columns:
            result_df['window_idx'] = result_df['t_start'].apply(_compute_window_idx_from_timestamp)
        else:
            result_df['window_idx'] = 0
        
        # First ensure rate_per_m_per_min exists (required by add_utilization_percentile)
        result_df = ensure_rpm(result_df)
        
        # Validate rate_per_m_per_min was computed successfully
        if 'rate_per_m_per_min' not in result_df.columns:
            raise KeyError("rate_per_m_per_min column was not created by ensure_rpm(). This is required for flagging.")
        
        # Now compute percentile
        result_df = add_utilization_percentile(result_df, cohort="window")
        logger.info(f"Computed utilization percentiles: P95={result_df['util_percentile'].quantile(0.95):.1f}")
    except Exception as util_error:
        logger.warning(f"Could not compute utilization percentile: {util_error}")
        result_df['util_percentile'] = None
        result_df['window_idx'] = 0
    
    return result_df


def _evaluate_row_with_rulebook(row: pd.Series) -> pd.Series:
    """Apply rulebook evaluation to a single row."""
    result = rulebook.evaluate_flags(
        density_pm2=row['density'],
        rate_p_s=row.get('rate'),
        width_m=row.get('width_m', 3.0),
        schema_key=row.get('schema_key', 'on_course_open'),
        util_percentile=row.get('util_percentile')
    )
    return pd.Series({
        'los': result.los_class,
        'rate_per_m_per_min': result.rate_per_m_per_min,
        'util_percent': result.util_percent,
        'util_percentile': result.util_percentile,
        'flag_severity': result.severity,
        'flag_reason': result.flag_reason
    })


def _apply_rulebook_evaluation(result_df: pd.DataFrame) -> pd.DataFrame:
    """Apply rulebook evaluation to all rows and update DataFrame."""
    eval_results = result_df.apply(_evaluate_row_with_rulebook, axis=1)
    result_df['los'] = eval_results['los']
    result_df['rate_per_m_per_min'] = eval_results['rate_per_m_per_min']
    result_df['util_percent'] = eval_results['util_percent']
    result_df['util_percentile'] = eval_results['util_percentile']
    result_df['flag_severity'] = eval_results['flag_severity']
    result_df['flag_reason'] = eval_results['flag_reason']
    
    return result_df


def _log_flagging_statistics(result_df: pd.DataFrame) -> None:
    """Log flagging statistics and schema distribution."""
    flagged = len(result_df[result_df['flag_severity'] != 'none'])
    critical = len(result_df[result_df['flag_severity'] == 'critical'])
    watch = len(result_df[result_df['flag_severity'] == 'watch'])
    
    logger.info(f"Rulebook flagging: {flagged}/{len(result_df)} flagged ({critical} critical, {watch} watch) = {flagged/len(result_df)*100:.1f}%")
    
    # Log schema distribution (Issue #254 telemetry)
    if 'schema_key' in result_df.columns:
        schema_counts = result_df['schema_key'].value_counts().to_dict()
        logger.info(f"Schema distribution: {schema_counts}")
        
        # Log flagging by schema
        for schema in schema_counts.keys():
            schema_bins = result_df[result_df['schema_key'] == schema]
            schema_flagged = len(schema_bins[schema_bins['flag_severity'] != 'none'])
            if schema_flagged > 0:
                logger.info(f"  {schema}: {schema_flagged}/{len(schema_bins)} flagged ({schema_flagged/len(schema_bins)*100:.1f}%)")


def apply_new_flagging(
    df: pd.DataFrame,
    config: NewFlaggingConfig = None,  # DEPRECATED - kept for compatibility
    segments_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Apply new flagging logic using centralized rulebook (Issue #254).
    
    Args:
        df: Bins DataFrame with columns: segment_id, density, rate
        config: DEPRECATED - thresholds now loaded from rulebook
        segments_df: Segments DataFrame with width_m, seg_label, segment_type
        
    Returns:
        DataFrame with rulebook-based flagging columns
    """
    result_df = df.copy()
    
    logger.info(f"apply_new_flagging (rulebook): {len(result_df)} rows")
    
    if 'segment_id' not in result_df.columns:
        raise ValueError("segment_id column required")
    
    # Load and apply segment metadata
    result_df = _load_and_apply_segment_metadata(result_df, segments_df)
    
    # Compute utilization percentile before flagging
    result_df = _compute_utilization_percentile(result_df)
    
    # Apply rulebook evaluation with percentile
    result_df = _apply_rulebook_evaluation(result_df)
    
    # Log flagging statistics
    _log_flagging_statistics(result_df)
    
    return result_df


def get_flagged_bins_new(df: pd.DataFrame) -> pd.DataFrame:
    """Get only flagged bins (non-none severity)."""
    return df[df['flag_severity'] != 'none'].copy()


def get_severity_rank_new(severity: str) -> int:
    """Get numeric rank for severity level (for sorting)."""
    ranks = {
        'critical': 2,
        'watch': 1,
        'none': 0
    }
    return ranks.get(severity, 0)


def summarize_segment_flags_new(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize flagging results by segment.
    
    Returns DataFrame with columns:
    - segment_id: Segment identifier
    - seg_label: Segment label (if available)
    - total_bins: Total bins in segment
    - flagged_bins: Number of flagged bins
    - flagged_percentage: Percentage of bins flagged
    - worst_severity: Highest severity in segment
    - worst_reason: Reason for worst severity
    - peak_density: Highest density in segment
    - peak_rate_per_m_per_min: Highest rate per m per min in segment
    """
    if len(df) == 0:
        return pd.DataFrame()
    
    # Group by segment
    segment_groups = df.groupby('segment_id')
    
    summaries = []
    for seg_id, group in segment_groups:
        total_bins = len(group)
        flagged = group[group['flag_severity'] != 'none']
        flagged_count = len(flagged)
        
        # Get worst severity and reason with bin details
        if flagged_count > 0:
            # Sort by severity rank, then by density, then by rate
            flagged_copy = flagged.copy()
            flagged_copy['severity_rank'] = flagged_copy['flag_severity'].apply(get_severity_rank_new)
            flagged_sorted = flagged_copy.sort_values(
                ['severity_rank', 'density', 'rate_per_m_per_min'], 
                ascending=[False, False, False]
            )
            worst_bin = flagged_sorted.iloc[0]
            worst_severity = worst_bin['flag_severity']
            worst_reason = worst_bin['flag_reason']
            worst_bin_start_km = worst_bin.get('start_km', 0)
            worst_bin_end_km = worst_bin.get('end_km', 0)
            worst_bin_t_start = worst_bin.get('t_start', None)
            worst_bin_rate = worst_bin.get('rate', 0)
            worst_bin_density = worst_bin['density']
            worst_bin_los = worst_bin['los']
        else:
            worst_severity = 'none'
            worst_reason = 'none'
            worst_bin_start_km = 0
            worst_bin_end_km = 0
            worst_bin_t_start = None
            worst_bin_rate = 0
            worst_bin_density = 0
            worst_bin_los = 'A'
        
        # Get segment label if available
        seg_label = group.iloc[0].get('seg_label', seg_id)
        
        summaries.append({
            'segment_id': seg_id,
            'seg_label': seg_label,
            'total_bins': total_bins,
            'flagged_bins': flagged_count,
            'flagged_percentage': (flagged_count / total_bins * 100) if total_bins > 0 else 0,
            'worst_severity': worst_severity,
            'worst_reason': worst_reason,
            'worst_bin_start_km': worst_bin_start_km,
            'worst_bin_end_km': worst_bin_end_km,
            'worst_bin_t_start': worst_bin_t_start,
            'worst_bin_rate': worst_bin_rate,
            'worst_bin_density': worst_bin_density,
            'worst_bin_los': worst_bin_los,
            'peak_density': group['density'].max(),
            'peak_rate_per_m_per_min': group['rate_per_m_per_min'].max(),
            'peak_los': group['los'].max()  # Highest LOS letter
        })
    
    return pd.DataFrame(summaries).sort_values('worst_severity', key=lambda x: x.map(get_severity_rank_new), ascending=False)


def get_flagging_statistics_new(df: pd.DataFrame) -> Dict[str, any]:
    """Get overall flagging statistics."""
    total_bins = len(df)
    flagged = df[df['flag_severity'] != 'none']
    flagged_count = len(flagged)
    
    critical_count = len(df[df['flag_severity'] == 'critical'])
    watch_count = len(df[df['flag_severity'] == 'watch'])
    
    # Get worst severity and LOS
    if flagged_count > 0:
        worst_severity = flagged.sort_values('flag_severity', key=lambda x: x.map(get_severity_rank_new), ascending=False).iloc[0]['flag_severity']
        worst_los = df['los'].max()
    else:
        worst_severity = 'none'
        worst_los = 'A'
    
    return {
        'total_bins': total_bins,
        'flagged_bins': flagged_count,
        'flagged_percentage': (flagged_count / total_bins * 100) if total_bins > 0 else 0,
        'critical_bins': critical_count,
        'watch_bins': watch_count,
        'worst_severity': worst_severity,
        'worst_los': worst_los,
        'peak_density': df['density'].max() if len(df) > 0 else 0,
        'peak_rate_per_m_per_min': df['rate_per_m_per_min'].max() if len(df) > 0 else 0
    }
