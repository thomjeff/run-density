"""
Single Source of Truth for Flagging Logic (Issue #283)

This module provides the canonical API for flag computation and summarization.
Both the Density report and UI artifacts consume from this SSOT to ensure parity.

Architecture:
- Reads authoritative flags from bins.parquet (with flag_severity, flag_reason, los)
- Does NOT recompute flags (trusts the upstream binning/flagging pipeline)
- Provides two public functions: compute_bin_flags() and summarize_flags()
- Tied to rulebook version/hash for reproducibility

Units:
- rate: persons per second (p/s) - canonical
- specific_flow_pms: persons per meter per second (p/(m·s)) - optional for ops
- rate_per_m_per_min: persons per meter per minute (p/(m·min)) - DEPRECATED, kept for one release

Field Names:
- Canonical: segment_id, flagged_bins, rate, severity, t_start, t_end
- Legacy aliases (one release): seg_id, flagged_bin_count, rate_per_m_per_min

Created: 2025-10-20
Issue: #283
Author: Cursor AI + ChatGPT Architecture
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
import numpy as np

@dataclass
class BinFlag:
    """
    Represents a single bin-level flag from the authoritative binning pipeline.
    
    Fields use canonical names. Legacy aliases provided in dict serialization.
    """
    segment_id: str
    t_start: str  # ISO 8601 with timezone
    t_end: str    # ISO 8601 with timezone
    density: float  # persons per m² (p/m²)
    rate: float  # persons per second (p/s) - CANONICAL
    los: str  # Level of Service (A-F)
    severity: str  # WATCH, ALERT, CRITICAL, or none
    reason: str  # Short code: utilization, density, rate, etc.
    
    # Optional metadata
    bin_id: Optional[str] = None
    start_km: Optional[float] = None
    end_km: Optional[float] = None
    
    def to_dict(self, include_legacy_aliases: bool = True) -> Dict[str, Any]:
        """
        Serialize to dict with optional legacy aliases for backwards compatibility.
        
        Args:
            include_legacy_aliases: If True, include seg_id, rate_per_m_per_min
        
        Returns:
            Dictionary with canonical names (and optionally legacy aliases)
        """
        d = {
            "segment_id": self.segment_id,
            "t_start": self.t_start,
            "t_end": self.t_end,
            "density": float(self.density),
            "rate": float(self.rate),  # p/s - canonical
            "los": self.los,
            "severity": self.severity,
            "reason": self.reason,
        }
        
        if self.bin_id:
            d["bin_id"] = self.bin_id
        if self.start_km is not None:
            d["start_km"] = float(self.start_km)
        if self.end_km is not None:
            d["end_km"] = float(self.end_km)
        
        # Legacy aliases (DEPRECATED - remove in next release)
        if include_legacy_aliases:
            d["seg_id"] = self.segment_id  # alias
        
        return d


def compute_bin_flags(bins: pd.DataFrame, rulebook: Optional[Dict[str, Any]] = None) -> List[BinFlag]:
    """
    Read bin-level flags from authoritative bins DataFrame.
    
    This function READS existing flags; it does NOT recompute them.
    Flags are computed upstream by the binning/flagging pipeline using the
    rulebook logic. This ensures consistency and ties flags to rulebook version.
    
    Args:
        bins: DataFrame with columns: segment_id, t_start, t_end, density, rate,
              los, flag_severity, flag_reason (+ optional: bin_id, start_km, end_km)
        rulebook: Optional rulebook config (for validation/metadata only)
    
    Returns:
        List of BinFlag objects (only bins with severity != 'none')
    
    Raises:
        ValueError: If required columns are missing
    """
    # Validate required columns
    required_cols = {'segment_id', 't_start', 't_end', 'density', 'rate', 'los', 'flag_severity', 'flag_reason'}
    missing = required_cols - set(bins.columns)
    if missing:
        raise ValueError(f"Missing required columns in bins DataFrame: {missing}")
    
    # Filter to flagged bins only (flag_severity != 'none')
    flagged = bins[bins['flag_severity'] != 'none'].copy()
    
    bin_flags = []
    for _, row in flagged.iterrows():
        flag = BinFlag(
            segment_id=str(row['segment_id']),
            t_start=str(row['t_start']),
            t_end=str(row['t_end']),
            density=float(row['density']),
            rate=float(row['rate']),  # Already in p/s (canonical)
            los=str(row['los']),
            severity=str(row['flag_severity']),
            reason=str(row['flag_reason']),
            bin_id=str(row.get('bin_id', '')),
            start_km=float(row.get('start_km')) if pd.notna(row.get('start_km')) else None,
            end_km=float(row.get('end_km')) if pd.notna(row.get('end_km')) else None
        )
        bin_flags.append(flag)
    
    return bin_flags


def summarize_flags(bin_flags: List[BinFlag]) -> Dict[str, Any]:
    """
    Aggregate bin-level flags into segment-level rollups for reports and artifacts.
    
    This is the SSOT for flagging statistics consumed by:
    - Density.md Executive Summary
    - flags.json (UI artifacts)
    - segment_metrics.json (UI artifacts)
    
    Args:
        bin_flags: List[BinFlag objects from compute_bin_flags()
    
    Returns:
        Dictionary with:
        - flagged_bin_total: int - total number of flagged bins
        - total_bins_analyzed: int - for context (if available)
        - segments_with_flags: List[str] - sorted list of segment IDs with flags
        - per_segment: List[Dict] - per-segment rollups with canonical fields
    """
    # Severity ordering for determining worst severity (handle both uppercase and lowercase)
    severity_order = {
        "none": 0, "NONE": 0,
        "watch": 1, "WATCH": 1, "CAUTION": 1, "caution": 1,
        "alert": 2, "ALERT": 2,
        "critical": 3, "CRITICAL": 3
    }
    
    per_segment: Dict[str, Dict[str, Any]] = {}
    
    for flag in bin_flags:
        seg_id = flag.segment_id
        
        if seg_id not in per_segment:
            per_segment[seg_id] = {
                "segment_id": seg_id,
                "flagged_bins": 0,
                "worst_severity": "none",
                "worst_los": "A",
                "peak_density": 0.0,
                "peak_rate": 0.0,  # p/s - canonical
            }
        
        d = per_segment[seg_id]
        d["flagged_bins"] += 1
        
        # Update worst severity
        current_rank = severity_order.get(d["worst_severity"], 0)
        flag_rank = severity_order.get(flag.severity, 0)
        if flag_rank > current_rank:
            d["worst_severity"] = flag.severity
        
        # Update worst LOS (F > E > D > C > B > A)
        if flag.los > d["worst_los"]:
            d["worst_los"] = flag.los
        
        # Update peak values
        if flag.density > d["peak_density"]:
            d["peak_density"] = flag.density
        if flag.rate > d["peak_rate"]:
            d["peak_rate"] = flag.rate
    
    # Add legacy aliases to per-segment dicts (DEPRECATED - remove in next release)
    for seg_id, data in per_segment.items():
        data["seg_id"] = seg_id  # alias
        data["flagged_bin_count"] = data["flagged_bins"]  # alias
    
    return {
        "flagged_bin_total": len(bin_flags),
        "segments_with_flags": sorted(per_segment.keys()),
        "per_segment": list(per_segment.values()),
    }


def get_flagging_summary_for_report(bins: pd.DataFrame, rulebook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for report generation.
    
    Returns summary statistics suitable for Density.md Executive Summary.
    
    Args:
        bins: Full bins DataFrame (flagged + unflagged)
        rulebook: Optional rulebook config
    
    Returns:
        Dictionary with:
        - flagged_bins: int - total flagged bins
        - total_bins: int - total bins analyzed
        - segments_with_flags_count: int - number of segments with flags
        - segments_total: int - total number of segments
        - worst_severity: str - worst flag severity across all bins
        - worst_los: str - worst LOS across all bins
        - peak_density: float - highest density (p/m²)
        - peak_rate: float - highest rate (p/s)
    """
    bin_flags = compute_bin_flags(bins, rulebook)
    summary = summarize_flags(bin_flags)
    
    # Calculate additional report statistics
    segments_total = bins['segment_id'].nunique()
    
    # Find worst severity and LOS across ALL bins (not just flagged)
    severity_order = {
        "none": 0, "NONE": 0,
        "watch": 1, "WATCH": 1, "CAUTION": 1, "caution": 1,
        "alert": 2, "ALERT": 2,
        "critical": 3, "CRITICAL": 3
    }
    if len(bin_flags) > 0:
        worst_severity = max(bin_flags, key=lambda f: severity_order.get(f.severity, 0)).severity
        worst_los = bins['los'].max() if 'los' in bins.columns else 'A'
    else:
        worst_severity = 'none'
        worst_los = 'A'
    
    peak_density = bins['density'].max() if len(bins) > 0 else 0.0
    peak_rate = bins['rate'].max() if len(bins) > 0 else 0.0  # p/s
    
    return {
        "flagged_bins": summary["flagged_bin_total"],
        "total_bins": len(bins),
        "segments_with_flags_count": len(summary["segments_with_flags"]),
        "segments_total": segments_total,
        "worst_severity": worst_severity,
        "worst_los": worst_los,
        "peak_density": float(peak_density),
        "peak_rate": float(peak_rate),  # p/s - canonical
    }


# Utility: Unit conversions (for one-release backwards compatibility)
def rate_to_rate_per_m_per_min(rate_p_s: float, width_m: float) -> float:
    """
    Convert canonical rate (p/s) to DEPRECATED rate_per_m_per_min.
    
    Formula: rate_per_m_per_min = (rate / width_m) * 60
    
    Args:
        rate_p_s: Rate in persons per second (canonical)
        width_m: Segment width in meters
    
    Returns:
        Rate in persons per meter per minute (DEPRECATED)
    
    Raises:
        ValueError: If width_m <= 0
    """
    if width_m <= 0:
        raise ValueError(f"width_m must be > 0, got {width_m}")
    return (rate_p_s / width_m) * 60.0


def rate_per_m_per_min_to_rate(rate_per_m_per_min: float, width_m: float) -> float:
    """
    Convert DEPRECATED rate_per_m_per_min to canonical rate (p/s).
    
    Formula: rate = (rate_per_m_per_min / 60) * width_m
    
    Args:
        rate_per_m_per_min: Rate in persons per meter per minute (DEPRECATED)
        width_m: Segment width in meters
    
    Returns:
        Rate in persons per second (canonical)
    
    Raises:
        ValueError: If width_m <= 0
    """
    if width_m <= 0:
        raise ValueError(f"width_m must be > 0, got {width_m}")
    return (rate_per_m_per_min / 60.0) * width_m

