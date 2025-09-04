"""
Density Analysis Module

This module provides spatial concentration analysis for runners within segments.
It calculates areal density (runners/m²) and crowd density (runners/m) to complement
temporal flow analysis.

CRITICAL: This module calculates its own runner counts (ALL runners in segment)
and is completely independent of temporal flow calculations.

Author: AI Assistant
Version: 1.6.0
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Protocol
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WidthProvider(Protocol):
    """Protocol for pluggable width calculation providers."""
    
    def get_width(self, segment_id: str, from_km: float, to_km: float) -> float:
        """Get width for a segment."""
        ...


class StaticWidthProvider:
    """Static width provider using segments.csv data."""
    
    def __init__(self, segments_df: pd.DataFrame):
        self.widths = dict(zip(segments_df['segment_id'], segments_df['width_m']))
    
    def get_width(self, segment_id: str, from_km: float, to_km: float) -> float:
        """Get width from segments.csv data."""
        return self.widths.get(segment_id, 0.0)


class DynamicWidthProvider:
    """Future: Dynamic width provider using GPX data."""
    
    def get_width(self, segment_id: str, from_km: float, to_km: float) -> float:
        """Get width from GPX data (placeholder for future implementation)."""
        # This would integrate with GPX data for dynamic width calculation
        # For now, return a default width
        return 3.0  # Default 3m width


@dataclass(frozen=True)
class DensityConfig:
    """Configuration for density analysis calculations."""
    bin_seconds: int = 30
    threshold_areal: float = 1.2  # runners/m^2
    threshold_crowd: float = 2.0  # runners/m
    min_segment_length_m: float = 50.0  # Skip segments shorter than this
    epsilon: float = 1e-6  # For float comparisons
    min_sustained_period_minutes: int = 2  # For narrative smoothing


@dataclass(frozen=True)
class SegmentMeta:
    """Metadata for a segment used in density calculations."""
    segment_id: str
    from_km: float
    to_km: float
    width_m: float
    direction: str  # "uni" | "bi"
    
    @property
    def segment_length_m(self) -> float:
        """Calculate segment length in meters."""
        return (self.to_km - self.from_km) * 1000
    
    @property
    def area_m2(self) -> float:
        """Calculate segment area in square meters."""
        return self.segment_length_m * self.width_m


@dataclass(frozen=True)
class DensityResult:
    """Result of density analysis for a single time bin."""
    segment_id: str
    t_start: str
    t_end: str
    concurrent_runners: int
    areal_density: float
    crowd_density: float
    los_areal: str
    los_crowd: str
    flags: List[str]


@dataclass(frozen=True)
class DensitySummary:
    """Summary of density analysis for a segment."""
    segment_id: str
    peak_areal_density: float
    peak_areal_time_window: List[str]
    peak_crowd_density: float
    peak_crowd_time_window: List[str]
    tot_areal_sec: int
    tot_crowd_sec: int
    los_areal_distribution: Dict[str, float]
    los_crowd_distribution: Dict[str, float]
    flags: List[str]


class DensityAnalyzer:
    """
    Main class for density analysis calculations.
    
    CRITICAL: This class calculates its own runner counts (ALL runners in segment)
    and is completely independent of temporal flow calculations.
    """
    
    def __init__(self, config: DensityConfig = None, width_provider: WidthProvider = None):
        """Initialize the density analyzer with configuration."""
        self.config = config or DensityConfig()
        self.width_provider = width_provider
        self.los_areal_thresholds = {
            "Comfortable": (0.0, 1.0),
            "Busy": (1.0, 1.8),
            "Constrained": (1.8, float('inf'))
        }
        self.los_crowd_thresholds = {
            "Low": (0.0, 1.5),
            "Medium": (1.5, 3.0),
            "High": (3.0, float('inf'))
        }
    
    def validate_segment(self, segment: SegmentMeta) -> Tuple[bool, List[str]]:
        """
        Validate a segment for density analysis.
        
        Returns:
            Tuple of (is_valid, flags)
        """
        flags = []
        
        # Check segment length
        if segment.segment_length_m < self.config.min_segment_length_m:
            flags.append("short_segment")
            logger.warning(f"Segment {segment.segment_id} too short: {segment.segment_length_m}m")
            return False, flags
        
        # Check width_m
        if pd.isna(segment.width_m) or segment.width_m <= 0:
            flags.append("width_missing")
            logger.warning(f"Segment {segment.segment_id} has invalid width_m: {segment.width_m}")
            return False, flags
        
        # Check for edge cases
        if segment.segment_length_m < 100:
            flags.append("edge_case")
            logger.info(f"Segment {segment.segment_id} is edge case: {segment.segment_length_m}m")
        
        return True, flags
    
    def calculate_concurrent_runners(self, 
                                   segment: SegmentMeta,
                                   pace_data: pd.DataFrame,
                                   start_times: Dict[str, datetime],
                                   time_bin_start: datetime) -> int:
        """
        Calculate concurrent runners in segment at a specific time.
        
        CRITICAL: This calculates ALL runners present in the segment,
        not just those involved in interactions (different from temporal flow).
        
        PERFORMANCE: Uses NumPy vectorized operations for better performance.
        
        Args:
            segment: Segment metadata
            pace_data: Runner pace data with start_offset
            start_times: Event start times
            time_bin_start: Start of the time bin
            
        Returns:
            Number of concurrent runners in the segment
        """
        time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
        
        # Convert to NumPy arrays for vectorized operations
        event_ids = pace_data['event_id'].values
        start_offsets = pace_data['start_offset'].values
        paces = pace_data['pace'].values
        
        # Calculate actual start times for all runners
        actual_starts = np.array([
            start_times[event_id] + timedelta(seconds=start_offset)
            for event_id, start_offset in zip(event_ids, start_offsets)
        ])
        
        # Convert to seconds since epoch for vectorized operations
        time_bin_start_sec = time_bin_start.timestamp()
        time_bin_end_sec = time_bin_end.timestamp()
        actual_starts_sec = np.array([start.timestamp() for start in actual_starts])
        
        # Calculate time elapsed for each runner
        time_elapsed_start = time_bin_start_sec - actual_starts_sec
        time_elapsed_end = time_bin_end_sec - actual_starts_sec
        
        # Filter runners who have started
        started_mask = time_elapsed_start >= 0
        if not np.any(started_mask):
            return 0
        
        # Calculate positions for started runners
        positions_start_km = paces[started_mask] * time_elapsed_start[started_mask] / 3600
        positions_end_km = paces[started_mask] * time_elapsed_end[started_mask] / 3600
        
        # Vectorized check for runners in segment
        in_segment_mask = (positions_start_km < segment.to_km) & (positions_end_km > segment.from_km)
        
        return np.sum(in_segment_mask)
    
    def _runner_in_segment(self, pos_start_km: float, pos_end_km: float, segment: SegmentMeta) -> bool:
        """
        Check if a runner is in the segment during the time bin.
        
        Args:
            pos_start_km: Runner's position at start of time bin
            pos_end_km: Runner's position at end of time bin
            segment: Segment metadata
            
        Returns:
            True if runner is in segment during time bin
        """
        # Runner is in segment if any part of their movement overlaps with segment
        return (pos_start_km < segment.to_km and pos_end_km > segment.from_km)
    
    def calculate_density_metrics(self, concurrent_runners: int, segment: SegmentMeta) -> Tuple[float, float]:
        """
        Calculate areal and crowd density metrics.
        
        Args:
            concurrent_runners: Number of concurrent runners
            segment: Segment metadata
            
        Returns:
            Tuple of (areal_density, crowd_density)
        """
        # Areal density: runners per square meter
        areal_density = concurrent_runners / segment.area_m2 if segment.area_m2 > 0 else 0.0
        
        # Crowd density: runners per meter of course length
        crowd_density = concurrent_runners / segment.segment_length_m if segment.segment_length_m > 0 else 0.0
        
        return areal_density, crowd_density
    
    def classify_los(self, areal_density: float, crowd_density: float) -> Tuple[str, str]:
        """
        Classify Level of Service for areal and crowd density.
        
        Args:
            areal_density: Areal density value
            crowd_density: Crowd density value
            
        Returns:
            Tuple of (los_areal, los_crowd)
        """
        # Classify areal density
        los_areal = "Comfortable"
        for level, (min_val, max_val) in self.los_areal_thresholds.items():
            if min_val <= areal_density < max_val:
                los_areal = level
                break
        
        # Classify crowd density
        los_crowd = "Low"
        for level, (min_val, max_val) in self.los_crowd_thresholds.items():
            if min_val <= crowd_density < max_val:
                los_crowd = level
                break
        
        return los_areal, los_crowd
    
    def smooth_narrative_transitions(self, results: List[DensityResult]) -> List[Dict[str, Any]]:
        """
        Smooth narrative transitions to avoid per-bin noise.
        
        CRITICAL: Reports sustained periods rather than per-bin fluctuations.
        
        Args:
            results: List of DensityResult objects
            
        Returns:
            List of sustained period summaries
        """
        if not results:
            return []
        
        sustained_periods = []
        min_sustained_bins = (self.config.min_sustained_period_minutes * 60) // self.config.bin_seconds
        
        # Group consecutive bins with same LOS
        current_areal_los = None
        current_crowd_los = None
        current_start_idx = 0
        
        for i, result in enumerate(results):
            # Check for LOS changes
            if (result.los_areal != current_areal_los or 
                result.los_crowd != current_crowd_los):
                
                # If we have a sustained period, add it
                if (current_areal_los is not None and 
                    i - current_start_idx >= min_sustained_bins):
                    
                    sustained_periods.append({
                        "start_time": results[current_start_idx].t_start,
                        "end_time": results[i-1].t_end,
                        "duration_minutes": (i - current_start_idx) * self.config.bin_seconds / 60,
                        "los_areal": current_areal_los,
                        "los_crowd": current_crowd_los,
                        "avg_areal_density": np.mean([
                            r.areal_density for r in results[current_start_idx:i]
                        ]),
                        "avg_crowd_density": np.mean([
                            r.crowd_density for r in results[current_start_idx:i]
                        ]),
                        "peak_concurrent_runners": max([
                            r.concurrent_runners for r in results[current_start_idx:i]
                        ])
                    })
                
                # Start new period
                current_areal_los = result.los_areal
                current_crowd_los = result.los_crowd
                current_start_idx = i
        
        # Handle final period
        if (current_areal_los is not None and 
            len(results) - current_start_idx >= min_sustained_bins):
            
            sustained_periods.append({
                "start_time": results[current_start_idx].t_start,
                "end_time": results[-1].t_end,
                "duration_minutes": (len(results) - current_start_idx) * self.config.bin_seconds / 60,
                "los_areal": current_areal_los,
                "los_crowd": current_crowd_los,
                "avg_areal_density": np.mean([
                    r.areal_density for r in results[current_start_idx:]
                ]),
                "avg_crowd_density": np.mean([
                    r.crowd_density for r in results[current_start_idx:]
                ]),
                "peak_concurrent_runners": max([
                    r.concurrent_runners for r in results[current_start_idx:]
                ])
            })
        
        return sustained_periods
    
    def compute_density_timeseries(self,
                                 segment: SegmentMeta,
                                 pace_data: pd.DataFrame,
                                 start_times: Dict[str, datetime],
                                 time_bins: List[datetime]) -> List[DensityResult]:
        """
        Compute density time series for a segment.
        
        Args:
            segment: Segment metadata
            pace_data: Runner pace data
            start_times: Event start times
            time_bins: List of time bin start times
            
        Returns:
            List of DensityResult objects
        """
        # Validate segment first
        is_valid, flags = self.validate_segment(segment)
        if not is_valid:
            logger.warning(f"Skipping segment {segment.segment_id} due to validation failures")
            return []
        
        results = []
        
        for time_bin_start in time_bins:
            time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
            
            # Calculate concurrent runners (CRITICAL: density context, not flow context)
            concurrent_runners = self.calculate_concurrent_runners(
                segment, pace_data, start_times, time_bin_start
            )
            
            # Calculate density metrics
            areal_density, crowd_density = self.calculate_density_metrics(concurrent_runners, segment)
            
            # Classify LOS
            los_areal, los_crowd = self.classify_los(areal_density, crowd_density)
            
            # Create result
            result = DensityResult(
                segment_id=segment.segment_id,
                t_start=time_bin_start.strftime("%H:%M:%S"),
                t_end=time_bin_end.strftime("%H:%M:%S"),
                concurrent_runners=concurrent_runners,
                areal_density=areal_density,
                crowd_density=crowd_density,
                los_areal=los_areal,
                los_crowd=los_crowd,
                flags=flags.copy()
            )
            
            results.append(result)
        
        return results
    
    def summarize_density(self, results: List[DensityResult]) -> DensitySummary:
        """
        Summarize density analysis results for a segment.
        
        Args:
            results: List of DensityResult objects
            
        Returns:
            DensitySummary object
        """
        if not results:
            return DensitySummary(
                segment_id="",
                peak_areal_density=0.0,
                peak_areal_time_window=[],
                peak_crowd_density=0.0,
                peak_crowd_time_window=[],
                tot_areal_sec=0,
                tot_crowd_sec=0,
                los_areal_distribution={},
                los_crowd_distribution={},
                flags=["no_data"]
            )
        
        # Find peak densities
        peak_areal_idx = max(range(len(results)), key=lambda i: results[i].areal_density)
        peak_crowd_idx = max(range(len(results)), key=lambda i: results[i].crowd_density)
        
        peak_areal_density = results[peak_areal_idx].areal_density
        peak_areal_time_window = [
            results[peak_areal_idx].t_start,
            results[peak_areal_idx].t_end
        ]
        
        peak_crowd_density = results[peak_crowd_idx].crowd_density
        peak_crowd_time_window = [
            results[peak_crowd_idx].t_start,
            results[peak_crowd_idx].t_end
        ]
        
        # Calculate TOT (Time Over Threshold)
        tot_areal_sec = sum(
            self.config.bin_seconds for result in results
            if result.areal_density >= self.config.threshold_areal
        )
        
        tot_crowd_sec = sum(
            self.config.bin_seconds for result in results
            if result.crowd_density >= self.config.threshold_crowd
        )
        
        # Calculate LOS distributions
        los_areal_counts = {}
        los_crowd_counts = {}
        
        for result in results:
            los_areal_counts[result.los_areal] = los_areal_counts.get(result.los_areal, 0) + 1
            los_crowd_counts[result.los_crowd] = los_crowd_counts.get(result.los_crowd, 0) + 1
        
        # Convert to proportions
        total_bins = len(results)
        los_areal_distribution = {
            level: count / total_bins for level, count in los_areal_counts.items()
        }
        los_crowd_distribution = {
            level: count / total_bins for level, count in los_crowd_counts.items()
        }
        
        # Collect all flags
        all_flags = set()
        for result in results:
            all_flags.update(result.flags)
        
        return DensitySummary(
            segment_id=results[0].segment_id,
            peak_areal_density=peak_areal_density,
            peak_areal_time_window=peak_areal_time_window,
            peak_crowd_density=peak_crowd_density,
            peak_crowd_time_window=peak_crowd_time_window,
            tot_areal_sec=tot_areal_sec,
            tot_crowd_sec=tot_crowd_sec,
            los_areal_distribution=los_areal_distribution,
            los_crowd_distribution=los_crowd_distribution,
            flags=list(all_flags)
        )


def analyze_density_segments(segments_df: pd.DataFrame,
                           pace_data: pd.DataFrame,
                           start_times: Dict[str, datetime],
                           config: DensityConfig = None,
                           width_provider: WidthProvider = None) -> Dict[str, Any]:
    """
    Analyze density for all segments.
    
    Args:
        segments_df: DataFrame with segment information
        pace_data: DataFrame with runner pace data
        start_times: Dictionary of event start times
        config: Density analysis configuration
        width_provider: Pluggable width provider (defaults to StaticWidthProvider)
        
    Returns:
        Dictionary with density analysis results
    """
    config = config or DensityConfig()
    width_provider = width_provider or StaticWidthProvider(segments_df)
    analyzer = DensityAnalyzer(config, width_provider)
    
    # Generate time bins (same as temporal flow for alignment)
    earliest_start = min(start_times.values())
    latest_start = max(start_times.values())
    
    # Add buffer for analysis
    analysis_start = earliest_start - timedelta(hours=1)
    analysis_end = latest_start + timedelta(hours=6)  # Assume max 6-hour race
    
    time_bins = []
    current_time = analysis_start
    while current_time <= analysis_end:
        time_bins.append(current_time)
        current_time += timedelta(seconds=config.bin_seconds)
    
    results = {
        "summary": {
            "total_segments": len(segments_df),
            "processed_segments": 0,
            "skipped_segments": 0,
            "analysis_start": analysis_start.isoformat(),
            "analysis_end": analysis_end.isoformat(),
            "time_bin_seconds": config.bin_seconds
        },
        "segments": {}
    }
    
    for _, segment_row in segments_df.iterrows():
        # Use width provider for pluggable width calculation
        width_m = width_provider.get_width(
            segment_row['segment_id'],
            segment_row['from_km'],
            segment_row['to_km']
        )
        
        segment = SegmentMeta(
            segment_id=segment_row['segment_id'],
            from_km=segment_row['from_km'],
            to_km=segment_row['to_km'],
            width_m=width_m,
            direction=segment_row['direction']
        )
        
        # Compute density time series
        density_results = analyzer.compute_density_timeseries(
            segment, pace_data, start_times, time_bins
        )
        
        if density_results:
            # Summarize results
            summary = analyzer.summarize_density(density_results)
            
            # Generate narrative smoothing
            sustained_periods = analyzer.smooth_narrative_transitions(density_results)
            
            results["segments"][segment.segment_id] = {
                "summary": summary,
                "time_series": density_results,
                "sustained_periods": sustained_periods
            }
            results["summary"]["processed_segments"] += 1
        else:
            results["summary"]["skipped_segments"] += 1
            logger.warning(f"Skipped segment {segment.segment_id}")
    
    return results


# Example usage and testing
if __name__ == "__main__":
    # This would be used for testing the module
    print("Density Analysis Module - Ready for testing")