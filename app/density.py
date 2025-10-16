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


def classify_density(value, rulebook, schema_name="on_course_open"):
    """
    Returns LOS letter (A-F) based on density value and schema.
    Uses the rulebook thresholds verbatim (units must match computed metric).
    """
    # Handle v2.0 rulebook structure
    if "schemas" in rulebook:
        # v2.0 rulebook - use schema-specific or global LOS thresholds
        schemas = rulebook.get("schemas", {})
        schema_config = schemas.get(schema_name, {})
        los_thresholds = schema_config.get("los_thresholds", 
                                         rulebook.get("globals", {}).get("los_thresholds", {}))
        
        if not los_thresholds:
            return "F"  # Default to worst case
        
        # Map density to LOS letter
        for letter in ["A", "B", "C", "D", "E", "F"]:
            rng = los_thresholds.get(letter, {})
            mn = rng.get("min", float("-inf"))
            mx = rng.get("max", float("inf"))
            if value >= mn and value < mx:
                return letter
        return "F"
    else:
        # Legacy v1.x rulebook structure
        th = rulebook["templates"]["thresholds"]
        high = float(th.get("high_density", 0.5))
        med  = float(th.get("medium_density", 0.2))
        low  = float(th.get("low_density", 0.1))
        if value >= high:
            return "high_density"
        if value >= med:
            return "medium_density"
        if value >= low:
            return "low_density"
        return None


def build_segment_context(seg, metrics, rulebook):
    ctx = {
        "segment_id": seg["id"],
        "segment_label": seg["label"],
        "event_type": metrics.get("event_type"),
        "density_value": metrics.get("density_value"),
        "flow_type": seg.get("flow_type"),  # e.g. 'merge', 'overtake'
    }
    ctx["density_class"] = classify_density(ctx["density_value"], rulebook)
    ctx["is_high_density"] = (ctx["density_class"] == "high_density")
    return ctx


def build_segment_context_v2(segment_id: str, segment_data: dict, summary_dict: dict, rulebook: dict) -> dict:
    """
    Build v2 segment context with schema binding, flow calculations, and trigger evaluation.
    
    This is the key integration function that connects v2 functionality to the main analysis pipeline.
    
    Args:
        segment_id: Segment identifier (e.g., "A1", "F1")
        segment_data: Segment configuration from density_cfg
        summary_dict: Density analysis summary data
        rulebook: v2 rulebook configuration
        
    Returns:
        dict: Complete v2 segment context ready for rendering
    """
    from .density_template_engine import resolve_schema, resolve_schema_with_flow_type, get_schema_config, compute_flow_rate, evaluate_triggers
    
    # Resolve schema for this segment
    # Try segment_type first, then fall back to flow_type
    segment_type = segment_data.get("segment_type", "road")
    flow_type = segment_data.get("flow_type", "default")
    
    if segment_type != "road" or segment_id == "A1":
        # Use segment_type for explicit cases
        schema_name = resolve_schema(segment_id, segment_type, rulebook)
    else:
        # Use flow_type for segments without explicit segment_type
        schema_name = resolve_schema_with_flow_type(segment_id, flow_type, rulebook)
    
    schema_config = get_schema_config(schema_name, rulebook)
    
    # Get flow rate if enabled for this segment
    flow_rate = None
    flow_enabled = segment_data.get("flow_enabled", "n")
    if flow_enabled == "y" or flow_enabled is True:
        # Calculate flow rate from peak concurrency
        # Use active_peak_concurrency which is the correct field name
        peak_concurrency = summary_dict.get("active_peak_concurrency", 0)
        width_m = segment_data.get("width_m", 1.0)
        bin_seconds = 60  # Default bin size
        flow_rate = compute_flow_rate(peak_concurrency, width_m, bin_seconds)
        
        # For merge segments, add flow-specific analysis
        if segment_data.get("flow_type") in ["merge", "parallel", "counterflow"]:
            # Add flow capacity analysis for merge segments
            flow_capacity = width_m * 60  # Theoretical max flow (runners/min/m)
            flow_utilization = (flow_rate / flow_capacity) * 100 if flow_capacity > 0 else 0
            logger.info(f"Merge segment {segment_id}: flow_rate={flow_rate:.1f} p/min/m, capacity={flow_capacity:.1f}, utilization={flow_utilization:.1f}%")
    
    # Evaluate triggers
    metrics = {
        "density": summary_dict.get("peak_areal_density", 0.0),
        "flow": flow_rate
    }
    fired_actions = evaluate_triggers(segment_id, metrics, schema_name, schema_config, rulebook)
    
    # Build complete v2 context
    v2_context = {
        # Basic segment info
        "segment_id": segment_id,
        "seg_label": segment_data.get("seg_label", "Unknown"),
        "segment_type": segment_type,
        "flow_type": segment_data.get("flow_type", "default"),
        
        # Schema information
        "schema_name": schema_name,
        "schema_config": schema_config,
        
        # Density metrics
        "peak_areal_density": summary_dict.get("peak_areal_density", 0.0),
        "peak_crowd_density": summary_dict.get("peak_crowd_density", 0.0),
        "peak_concurrency": summary_dict.get("peak_concurrency", 0),
        "active_duration_s": summary_dict.get("active_duration_s", 0),
        "active_start": summary_dict.get("active_start", "N/A"),
        "active_end": summary_dict.get("active_end", "N/A"),
        
        # Flow metrics
        "flow_rate": flow_rate,
        "flow_enabled": flow_enabled == "y" or flow_enabled is True,
        "flow_capacity": flow_capacity if 'flow_capacity' in locals() else None,
        "flow_utilization": flow_utilization if 'flow_utilization' in locals() else None,
        
        # Trigger results
        "fired_actions": fired_actions,
        
        # Events included
        "events_included": list(segment_data.get("events", [])),
        
        # Additional v2 data
        "width_m": segment_data.get("width_m", 1.0),
        "direction": segment_data.get("direction", "uni"),
        "notes": segment_data.get("notes", ""),
    }
    
    return v2_context


def load_density_cfg(path: str) -> Dict[str, dict]:
    """
    Load density configuration from segments_new.csv.
    
    Args:
        path: Path to segments_new.csv file
        
    Returns:
        Dictionary mapping segment_id to configuration dict
    """
    from .io.loader import load_segments
    df = load_segments(path)
    
    def y(row, col): 
        return str(row.get(col, "")).strip().lower() == "y"
    
    cfg = {}
    for _, r in df.iterrows():
        events = tuple(e for e, col in [
            ("Full", "full"), ("Half", "half"), ("10K", "10K")
        ] if y(r, col))
        
        cfg[r["seg_id"]] = dict(
            seg_label=str(r.get("seg_label", "")),
            width_m=float(r["width_m"]),
            direction=str(r.get("direction", "uni")),
            flow_type=str(r.get("flow_type", "default")),
            flow_enabled=str(r.get("flow_enabled", "n")),
            events=events,
            full_from_km=float(r.get("full_from_km", 0)) if r.get("full_from_km") != "" else None,
            full_to_km=float(r.get("full_to_km", 0)) if r.get("full_to_km") != "" else None,
            half_from_km=float(r.get("half_from_km", 0)) if r.get("half_from_km") != "" else None,
            half_to_km=float(r.get("half_to_km", 0)) if r.get("half_to_km") != "" else None,
            tenk_from_km=float(r.get("10K_from_km", 0)) if r.get("10K_from_km") != "" else None,
            tenk_to_km=float(r.get("10K_to_km", 0)) if r.get("10K_to_km") != "" else None,
            notes=str(r.get("notes", ""))
        )
    
    return cfg


class WidthProvider(Protocol):
    """Protocol for pluggable width calculation providers."""
    
    def get_width(self, segment_id: str, from_km: float, to_km: float) -> float:
        """Get width for a segment."""
        ...


class StaticWidthProvider:
    """Static width provider using flow.csv data."""
    
    def __init__(self, segments_df: pd.DataFrame):
        self.widths = dict(zip(segments_df['seg_id'], segments_df['width_m']))
    
    def get_width(self, segment_id: str, from_km: float, to_km: float) -> float:
        """Get width from flow.csv data."""
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
    step_km: float = 0.3  # Step size for sub-segment binning (300m bins)


@dataclass(frozen=True)
class SegmentMeta:
    """Metadata for a segment used in density calculations."""
    segment_id: str
    from_km: float
    to_km: float
    width_m: float
    direction: str  # "uni" | "bi"
    events: Tuple[str, ...] = ()  # DENSITY scope (e.g., ("Full","10K","Half"))
    # Flow fields retained for completeness (used by temporal_flow.py, not by density):
    event_a: str = ""  # First event for this segment
    event_b: str = ""  # Second event for this segment
    
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
class EventViewSummary:
    """Per-event summary of density analysis for a segment."""
    event: str
    n_event_runners: int
    active_start: Optional[str] = None
    active_end: Optional[str] = None
    active_duration_s: int = 0
    occupancy_rate: float = 0.0
    peak_concurrency_exp: int = 0
    peak_areal_exp: float = 0.0
    peak_crowd_exp: float = 0.0
    p95_areal_exp: float = 0.0
    p95_crowd_exp: float = 0.0
    active_mean_areal_exp: float = 0.0
    active_mean_crowd_exp: float = 0.0
    active_tot_areal_exp_sec: int = 0
    active_tot_crowd_exp_sec: int = 0
    events_at_peak: List[str] = None
    contrib_breakdown_at_peak: Dict[str, int] = None
    sustained_periods: List[Dict[str, Any]] = None
    flags: List[str] = None
    
    def __post_init__(self):
        if self.events_at_peak is None:
            object.__setattr__(self, 'events_at_peak', [])
        if self.contrib_breakdown_at_peak is None:
            object.__setattr__(self, 'contrib_breakdown_at_peak', {})
        if self.sustained_periods is None:
            object.__setattr__(self, 'sustained_periods', [])
        if self.flags is None:
            object.__setattr__(self, 'flags', [])


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

    # Active-window statistics (new)
    active_start: Optional[str] = None
    active_end: Optional[str] = None
    active_duration_s: int = 0
    occupancy_rate: float = 0.0
    low_occupancy_flag: bool = False
    active_peak_areal: float = 0.0
    active_peak_crowd: float = 0.0
    active_peak_concurrency: int = 0
    active_p95_areal: float = 0.0
    active_p95_crowd: float = 0.0
    active_mean_areal: float = 0.0
    active_mean_crowd: float = 0.0
    
    # TOT metrics for active window
    active_tot_areal_sec: int = 0
    active_tot_crowd_sec: int = 0
    
    # Peak timestamps for operational planning
    active_peak_areal_time: Optional[str] = None
    active_peak_crowd_time: Optional[str] = None


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
        # Updated LOS thresholds based on active-window density analysis
        # These thresholds are calibrated to the actual density ranges observed
        # in the race data with active window filtering applied
        self.los_areal_thresholds = {
            "A": (0.0, 0.11),      # Comfortable
            "C": (0.11, 0.17),     # Moderate  
            "E": (0.17, 0.20),     # Busy
            "F": (0.20, float('inf'))  # Critical
        }
        self.los_crowd_thresholds = {
            "A": (0.0, 0.22),      # Comfortable
            "C": (0.22, 0.35),     # Moderate
            "E": (0.35, 0.60),     # Busy  
            "F": (0.60, float('inf'))  # Critical
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
    
    def calculate_concurrent_runners_union(self, 
                                          segment: SegmentMeta,
                                          pace_data: pd.DataFrame,
                                          start_times: Dict[str, datetime],
                                          time_bin_start: datetime,
                                          density_cfg: dict = None) -> int:
        """
        Calculate concurrent runners using union-of-intervals approach to avoid overcounting.
        
        This method correctly counts unique runner_ids present in the segment at time t,
        rather than summing per-distance-bin counts which can double-count runners.
        
        Args:
            segment: Segment metadata
            pace_data: Runner pace data with start_offset
            start_times: Event start times
            time_bin_start: Start of the time bin
            density_cfg: Density configuration with event-specific km ranges
            
        Returns:
            Number of unique concurrent runners in the segment
        """
        time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
        
        # Filter runners to the density scope
        if not segment.events:
            return 0
        filtered_pace_data = pace_data[pace_data["event"].isin(segment.events)]
        
        if filtered_pace_data.empty:
            return 0
        
        # Convert to NumPy arrays for vectorized operations
        event_ids = filtered_pace_data['event'].values
        start_offsets = filtered_pace_data['start_offset'].values
        paces = filtered_pace_data['pace'].values
        
        # Calculate actual start times for all runners
        actual_starts = np.array([
            start_times[event_id] + timedelta(seconds=int(start_offset))
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
        
        # Build union of intervals for all events in this segment
        intervals = []
        if density_cfg:
            for event in segment.events:
                if event == "Full" and density_cfg.get("full_from_km") is not None:
                    intervals.append((density_cfg["full_from_km"], density_cfg["full_to_km"]))
                elif event == "Half" and density_cfg.get("half_from_km") is not None:
                    intervals.append((density_cfg["half_from_km"], density_cfg["half_to_km"]))
                elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
                    intervals.append((density_cfg["tenk_from_km"], density_cfg["tenk_to_km"]))
        
        if not intervals:
            return 0
        
        # Merge overlapping intervals
        intervals.sort()
        merged_intervals = []
        for start, end in intervals:
            if not merged_intervals or merged_intervals[-1][1] < start:
                merged_intervals.append((start, end))
            else:
                # Merge with previous interval
                merged_intervals[-1] = (merged_intervals[-1][0], max(merged_intervals[-1][1], end))
        
        # Check runner presence in any of the merged intervals
        in_any_interval = np.zeros(len(positions_start_km), dtype=bool)
        for interval_start, interval_end in merged_intervals:
            in_interval = (positions_start_km < interval_end) & (positions_end_km > interval_start)
            in_any_interval |= in_interval
        
        return int(np.sum(in_any_interval))
    
    def validate_population_bounds(self, 
                                 segment_id: str, 
                                 concurrent_runners: int, 
                                 included_events: List[str], 
                                 pace_data: pd.DataFrame) -> List[str]:
        """
        Validate that segment concurrency doesn't exceed total registered runners.
        
        Args:
            segment_id: Segment identifier
            concurrent_runners: Calculated concurrent runners
            included_events: List of events included in this segment
            pace_data: Full pace data to count total runners
            
        Returns:
            List of validation flags
        """
        flags = []
        
        # Count total registered runners for included events
        total_registered = len(pace_data[pace_data["event"].isin(included_events)])
        
        if concurrent_runners > total_registered:
            flags.append(f"overcount_suspected: {concurrent_runners} > {total_registered}")
            logger.warning(f"Segment {segment_id}: concurrent_runners ({concurrent_runners}) > total_registered ({total_registered})")
        
        return flags
    
    def make_distance_bins(self, intervals_km: List[Tuple[float, float]], step_km: float) -> List[Tuple[float, float]]:
        """
        Create distance bins from event-specific intervals using step_km.
        
        Args:
            intervals_km: List of (from_km, to_km) tuples for each event
            step_km: Step size for binning
            
        Returns:
            List of (bin_start_km, bin_end_km) tuples
        """
        if not intervals_km:
            return []
        
        # Merge overlapping intervals first
        ints = sorted((min(a, b), max(a, b)) for a, b in intervals_km)
        merged = [ints[0]]
        for a, b in ints[1:]:
            la, lb = merged[-1]
            if a <= lb:
                merged[-1] = (la, max(lb, b))
            else:
                merged.append((a, b))
        
        # Create bins within each merged interval
        bins = []
        for a, b in merged:
            x = a
            while x < b - self.config.epsilon:
                y = min(b, x + step_km)
                bins.append((x, y))
                x = y
        
        return bins
    
    def calculate_per_event_experienced_density(self,
                                              segment: SegmentMeta,
                                              pace_data: pd.DataFrame,
                                              start_times: Dict[str, datetime],
                                              time_bins: List[datetime],
                                              density_cfg: dict = None) -> Dict[str, EventViewSummary]:
        """
        Calculate per-event experienced density analysis for a segment.
        
        This method analyzes what each event's runners actually experience
        when co-present with other events in the same segment.
        
        Args:
            segment: Segment metadata
            pace_data: Runner pace data
            start_times: Event start times
            time_bins: List of time bin start times
            density_cfg: Density configuration with event-specific km ranges
            
        Returns:
            Dictionary mapping event names to EventViewSummary objects
        """
        if not segment.events or not density_cfg:
            return {}
        
        # Get event-specific intervals for distance binning
        intervals_km = []
        for event in segment.events:
            if event == "Full" and density_cfg.get("full_from_km") is not None:
                intervals_km.append((density_cfg["full_from_km"], density_cfg["full_to_km"]))
            elif event == "Half" and density_cfg.get("half_from_km") is not None:
                intervals_km.append((density_cfg["half_from_km"], density_cfg["half_to_km"]))
            elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
                intervals_km.append((density_cfg["tenk_from_km"], density_cfg["tenk_to_km"]))
        
        # Create distance bins
        distance_bins = self.make_distance_bins(intervals_km, self.config.step_km)
        
        # Precompute runner positions for all time bins (vectorized)
        all_events = list(segment.events)
        event_runner_counts = {}
        for event in all_events:
            event_runner_counts[event] = len(pace_data[pace_data["event"] == event])
        
        # Calculate per-event experienced metrics
        per_event_summaries = {}
        
        for event in all_events:
            # Filter to this event's runners
            event_pace_data = pace_data[pace_data["event"] == event]
            if event_pace_data.empty:
                continue
            
            # Calculate experienced density time series for this event
            event_results = []
            e_active_time_bins = []
            
            for time_bin_start in time_bins:
                time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
                
                # Calculate experienced concurrency (this event + all others)
                experienced_concurrency = self._calculate_experienced_concurrency(
                    event, segment, pace_data, start_times, time_bin_start, 
                    distance_bins, density_cfg
                )
                
                # Calculate self concurrency (this event only)
                self_concurrency = self._calculate_self_concurrency(
                    event, segment, pace_data, start_times, time_bin_start,
                    distance_bins, density_cfg
                )
                
                # Only process bins where this event has runners present
                if self_concurrency > 0:
                    e_active_time_bins.append(time_bin_start)
                    
                    # Calculate experienced densities
                    areal_density, crowd_density = self.calculate_density_metrics(
                        experienced_concurrency, segment, density_cfg
                    )
                    
                    # Classify LOS
                    los_areal, los_crowd = self.classify_los(areal_density, crowd_density)
                    
                    # Create result
                    result = DensityResult(
                        segment_id=segment.segment_id,
                        t_start=time_bin_start.strftime("%H:%M:%S"),
                        t_end=time_bin_end.strftime("%H:%M:%S"),
                        concurrent_runners=experienced_concurrency,
                        areal_density=areal_density,
                        crowd_density=crowd_density,
                        los_areal=los_areal,
                        los_crowd=los_crowd,
                        flags=[]
                    )
                    
                    event_results.append(result)
            
            if not event_results:
                continue
            
            # Calculate per-event summary
            event_summary = self._summarize_per_event_experienced(
                event, event_results, event_runner_counts[event], segment
            )
            
            per_event_summaries[event] = event_summary
        
        return per_event_summaries
    
    def _calculate_experienced_concurrency(self,
                                         target_event: str,
                                         segment: SegmentMeta,
                                         pace_data: pd.DataFrame,
                                         start_times: Dict[str, datetime],
                                         time_bin_start: datetime,
                                         distance_bins: List[Tuple[float, float]],
                                         density_cfg: dict) -> int:
        """
        Calculate experienced concurrency for a target event (includes all co-present runners).
        """
        time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
        
        # Filter to all events in this segment
        filtered_pace_data = pace_data[pace_data["event"].isin(segment.events)]
        if filtered_pace_data.empty:
            return 0
        
        # Convert to NumPy arrays for vectorized operations
        event_ids = filtered_pace_data['event'].values
        start_offsets = filtered_pace_data['start_offset'].values
        paces = filtered_pace_data['pace'].values
        
        # Calculate actual start times
        actual_starts = np.array([
            start_times[event_id] + timedelta(seconds=int(start_offset))
            for event_id, start_offset in zip(event_ids, start_offsets)
        ])
        
        # Convert to seconds since epoch
        time_bin_start_sec = time_bin_start.timestamp()
        time_bin_end_sec = time_bin_end.timestamp()
        actual_starts_sec = np.array([start.timestamp() for start in actual_starts])
        
        # Calculate time elapsed
        time_elapsed_start = time_bin_start_sec - actual_starts_sec
        time_elapsed_end = time_bin_end_sec - actual_starts_sec
        
        # Filter to started runners
        started_mask = time_elapsed_start >= 0
        if not np.any(started_mask):
            return 0
        
        # Calculate positions
        positions_start_km = paces[started_mask] * time_elapsed_start[started_mask] / 3600
        positions_end_km = paces[started_mask] * time_elapsed_end[started_mask] / 3600
        
        # Check presence in any distance bin (experienced concurrency)
        in_any_bin = np.zeros(len(positions_start_km), dtype=bool)
        for bin_start, bin_end in distance_bins:
            in_bin = (positions_start_km < bin_end) & (positions_end_km > bin_start)
            in_any_bin |= in_bin
        
        return int(np.sum(in_any_bin))
    
    def _calculate_self_concurrency(self,
                                  target_event: str,
                                  segment: SegmentMeta,
                                  pace_data: pd.DataFrame,
                                  start_times: Dict[str, datetime],
                                  time_bin_start: datetime,
                                  distance_bins: List[Tuple[float, float]],
                                  density_cfg: dict) -> int:
        """
        Calculate self concurrency for a target event (only that event's runners).
        """
        time_bin_end = time_bin_start + timedelta(seconds=self.config.bin_seconds)
        
        # Filter to target event only
        event_pace_data = pace_data[pace_data["event"] == target_event]
        if event_pace_data.empty:
            return 0
        
        # Convert to NumPy arrays
        start_offsets = event_pace_data['start_offset'].values
        paces = event_pace_data['pace'].values
        
        # Calculate actual start times
        actual_starts = np.array([
            start_times[target_event] + timedelta(seconds=int(start_offset))
            for start_offset in start_offsets
        ])
        
        # Convert to seconds since epoch
        time_bin_start_sec = time_bin_start.timestamp()
        time_bin_end_sec = time_bin_end.timestamp()
        actual_starts_sec = np.array([start.timestamp() for start in actual_starts])
        
        # Calculate time elapsed
        time_elapsed_start = time_bin_start_sec - actual_starts_sec
        time_elapsed_end = time_bin_end_sec - actual_starts_sec
        
        # Filter to started runners
        started_mask = time_elapsed_start >= 0
        if not np.any(started_mask):
            return 0
        
        # Calculate positions
        positions_start_km = paces[started_mask] * time_elapsed_start[started_mask] / 3600
        positions_end_km = paces[started_mask] * time_elapsed_end[started_mask] / 3600
        
        # Check presence in any distance bin (self concurrency)
        in_any_bin = np.zeros(len(positions_start_km), dtype=bool)
        for bin_start, bin_end in distance_bins:
            in_bin = (positions_start_km < bin_end) & (positions_end_km > bin_start)
            in_any_bin |= in_bin
        
        return int(np.sum(in_any_bin))
    
    def _summarize_per_event_experienced(self,
                                       event: str,
                                       event_results: List[DensityResult],
                                       n_event_runners: int,
                                       segment: SegmentMeta) -> EventViewSummary:
        """
        Summarize per-event experienced density analysis.
        """
        if not event_results:
            return EventViewSummary(
                event=event,
                n_event_runners=n_event_runners,
                flags=["no_data"]
            )
        
        # Calculate active window bounds
        active_start = min(r.t_start for r in event_results)
        active_end = max(r.t_end for r in event_results)
        
        # Calculate duration
        try:
            active_start_dt = datetime.strptime(active_start, "%H:%M:%S")
            active_end_dt = datetime.strptime(active_end, "%H:%M:%S")
            active_duration_s = int((active_end_dt - active_start_dt).total_seconds())
        except ValueError:
            active_duration_s = len(event_results) * self.config.bin_seconds
        
        # Calculate occupancy rate (simplified - all bins are E-active by definition)
        occupancy_rate = 1.0
        
        # Calculate experienced metrics
        areal_densities = [r.areal_density for r in event_results]
        crowd_densities = [r.crowd_density for r in event_results]
        concurrent_runners = [r.concurrent_runners for r in event_results]
        
        # Peaks
        peak_concurrency_exp = max(concurrent_runners) if concurrent_runners else 0
        peak_areal_exp = max(areal_densities) if areal_densities else 0.0
        peak_crowd_exp = max(crowd_densities) if crowd_densities else 0.0
        
        # Percentiles and means
        p95_areal_exp = np.percentile(areal_densities, 95) if areal_densities else 0.0
        p95_crowd_exp = np.percentile(crowd_densities, 95) if crowd_densities else 0.0
        active_mean_areal_exp = np.mean(areal_densities) if areal_densities else 0.0
        active_mean_crowd_exp = np.mean(crowd_densities) if crowd_densities else 0.0
        
        # TOT calculations
        active_tot_areal_exp_sec = sum(
            self.config.bin_seconds for r in event_results
            if r.areal_density >= self.config.threshold_areal
        )
        active_tot_crowd_exp_sec = sum(
            self.config.bin_seconds for r in event_results
            if r.crowd_density >= self.config.threshold_crowd
        )
        
        # Find peak contribution breakdown - only include events that are actually present
        # at the time of the peak (not all events in the segment)
        events_at_peak = []
        contrib_breakdown_at_peak = {}
        
        # For now, we'll use a simplified approach - in a full implementation,
        # we would analyze the actual runner counts by event at the peak time
        # This is a placeholder that will be improved in future iterations
        for event in segment.events:
            events_at_peak.append(event)
            contrib_breakdown_at_peak[event] = 0
        
        # Generate sustained periods for this event
        sustained_periods = self.smooth_narrative_transitions(event_results)
        
        return EventViewSummary(
            event=event,
            n_event_runners=n_event_runners,
            active_start=active_start,
            active_end=active_end,
            active_duration_s=active_duration_s,
            occupancy_rate=occupancy_rate,
            peak_concurrency_exp=peak_concurrency_exp,
            peak_areal_exp=peak_areal_exp,
            peak_crowd_exp=peak_crowd_exp,
            p95_areal_exp=p95_areal_exp,
            p95_crowd_exp=p95_crowd_exp,
            active_mean_areal_exp=active_mean_areal_exp,
            active_mean_crowd_exp=active_mean_crowd_exp,
            active_tot_areal_exp_sec=active_tot_areal_exp_sec,
            active_tot_crowd_exp_sec=active_tot_crowd_exp_sec,
            events_at_peak=events_at_peak,
            contrib_breakdown_at_peak=contrib_breakdown_at_peak,
            sustained_periods=sustained_periods,
            flags=["per_event_analysis"]
        )
    
    def calculate_concurrent_runners(self, 
                                   segment: SegmentMeta,
                                   pace_data: pd.DataFrame,
                                   start_times: Dict[str, datetime],
                                   time_bin_start: datetime,
                                   density_cfg: dict = None) -> int:
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
        
        # Filter runners to the density scope
        if not segment.events:
            logging.debug(f"Segment {segment.segment_id}: No events configured, returning 0 runners")
            return 0
        filtered_pace_data = pace_data[pace_data["event"].isin(segment.events)]
        
        # Log physical dimensions and runner counts for debugging
        logging.debug(f"Segment {segment.segment_id}: Physical length={segment.length_m:.1f}m, width={segment.width_m:.1f}m, area={segment.length_m * segment.width_m:.1f}m²")
        logging.debug(f"Segment {segment.segment_id}: Events={segment.events}, filtered runners={len(filtered_pace_data)}")
        
        if filtered_pace_data.empty:
            logging.debug(f"Segment {segment.segment_id}: No runners in filtered data, returning 0")
            return 0
        
        # Convert to NumPy arrays for vectorized operations
        event_ids = filtered_pace_data['event'].values
        start_offsets = filtered_pace_data['start_offset'].values
        paces = filtered_pace_data['pace'].values
        
        # Calculate actual start times for all runners
        actual_starts = np.array([
            start_times[event_id] + timedelta(seconds=int(start_offset))
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
        
        # Get event-specific km ranges from density configuration
        if density_cfg:
            total_concurrent = 0
            
            # Check each event's specific cumulative distance range
            for event in segment.events:
                if event == "Full" and density_cfg.get("full_from_km") is not None:
                    from_km = density_cfg["full_from_km"]
                    to_km = density_cfg["full_to_km"]
                elif event == "Half" and density_cfg.get("half_from_km") is not None:
                    from_km = density_cfg["half_from_km"]
                    to_km = density_cfg["half_to_km"]
                elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
                    from_km = density_cfg["tenk_from_km"]
                    to_km = density_cfg["tenk_to_km"]
                else:
                    continue  # Skip events without km ranges
                
                # Filter to this event's runners
                event_mask = event_ids[started_mask] == event
                if not np.any(event_mask):
                    continue
                
                # Check if runners are in this event's segment range
                event_positions_start = positions_start_km[event_mask]
                event_positions_end = positions_end_km[event_mask]
                
                in_segment_mask = (event_positions_start < to_km) & (event_positions_end > from_km)
                total_concurrent += int(np.sum(in_segment_mask))
            
            return total_concurrent
        else:
            # Fallback to original logic if no density config
            in_segment_mask = (positions_start_km < segment.to_km) & (positions_end_km > segment.from_km)
            return int(np.sum(in_segment_mask))
    
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
    
    def calculate_density_metrics(self, concurrent_runners: int, segment: SegmentMeta, density_cfg: dict = None) -> Tuple[float, float]:
        """
        Calculate areal and crowd density metrics.
        
        Args:
            concurrent_runners: Number of concurrent runners
            segment: Segment metadata
            density_cfg: Density configuration with physical segment dimensions
            
        Returns:
            Tuple of (areal_density, crowd_density)
        """
        # Log density calculation inputs for debugging
        logging.debug(f"Segment {segment.segment_id}: Calculating density for {concurrent_runners} concurrent runners")
        if density_cfg:
            # Use physical segment dimensions from segments_new.csv
            # Calculate physical segment length as the maximum span of all events
            max_km = 0.0
            min_km = float('inf')
            
            for event in segment.events:
                if event == "Full" and density_cfg.get("full_from_km") is not None:
                    min_km = min(min_km, density_cfg["full_from_km"])
                    max_km = max(max_km, density_cfg["full_to_km"])
                elif event == "Half" and density_cfg.get("half_from_km") is not None:
                    min_km = min(min_km, density_cfg["half_from_km"])
                    max_km = max(max_km, density_cfg["half_to_km"])
                elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
                    min_km = min(min_km, density_cfg["tenk_from_km"])
                    max_km = max(max_km, density_cfg["tenk_to_km"])
            
            if min_km == float('inf'):
                min_km = 0.0
            
            physical_length_m = (max_km - min_km) * 1000
            physical_area_m2 = physical_length_m * segment.width_m
        else:
            # Fallback to segment metadata
            physical_length_m = segment.segment_length_m
            physical_area_m2 = segment.area_m2
        
        # Areal density: runners per square meter
        areal_density = concurrent_runners / physical_area_m2 if physical_area_m2 > 0 else 0.0
        
        # Crowd density: runners per meter of course length
        crowd_density = concurrent_runners / physical_length_m if physical_length_m > 0 else 0.0
        
        # Log density calculation results for debugging
        logging.debug(f"Segment {segment.segment_id}: Calculated densities - areal={areal_density:.3f} runners/m², crowd={crowd_density:.3f} runners/m")
        
        return areal_density, crowd_density
    
    def calculate_density_with_binning(self, 
                                     segment: SegmentMeta,
                                     pace_data: pd.DataFrame,
                                     start_times: Dict[str, datetime],
                                     time_bin_start: datetime,
                                     density_cfg: dict = None) -> Tuple[float, float, Dict]:
        """
        Calculate density using step-based binning for more accurate local density.
        
        This method subdivides the segment into bins of step_km size and calculates
        density for each bin, then returns the peak bin density and aggregated metrics.
        
        Args:
            segment: Segment metadata
            pace_data: Runner pace data
            start_times: Event start times
            time_bin_start: Start of the time bin
            density_cfg: Density configuration with event-specific km ranges
            
        Returns:
            Tuple of (peak_areal_density, peak_crowd_density, bin_details)
        """
        if not segment.events or not density_cfg:
            return 0.0, 0.0, {}
        
        # Calculate physical segment boundaries
        max_km = 0.0
        min_km = float('inf')
        
        for event in segment.events:
            if event == "Full" and density_cfg.get("full_from_km") is not None:
                min_km = min(min_km, density_cfg["full_from_km"])
                max_km = max(max_km, density_cfg["full_to_km"])
            elif event == "Half" and density_cfg.get("half_from_km") is not None:
                min_km = min(min_km, density_cfg["half_from_km"])
                max_km = max(max_km, density_cfg["half_to_km"])
            elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
                min_km = min(min_km, density_cfg["tenk_from_km"])
                max_km = max(max_km, density_cfg["tenk_to_km"])
        
        if min_km == float('inf'):
            return 0.0, 0.0, {}
        
        # Create bins within the physical segment
        step_km = self.config.step_km
        bin_starts = []
        bin_ends = []
        
        current_km = min_km
        while current_km < max_km:
            bin_start = current_km
            bin_end = min(current_km + step_km, max_km)
            
            # Only add bins with meaningful length (avoid floating-point precision issues)
            if bin_end - bin_start > self.config.epsilon:
                bin_starts.append(bin_start)
                bin_ends.append(bin_end)
            
            current_km = bin_end
        
        if not bin_starts:
            return 0.0, 0.0, {}
        
        # Calculate density for each bin
        bin_densities = []
        bin_details = {
            "bins": [],
            "peak_bin_index": 0,
            "total_concurrent": 0
        }
        
        peak_areal_density = 0.0
        peak_crowd_density = 0.0
        total_concurrent = 0
        
        for i, (bin_start, bin_end) in enumerate(zip(bin_starts, bin_ends)):
            # Create a temporary segment for this bin
            bin_segment = SegmentMeta(
                segment_id=f"{segment.segment_id}_bin_{i}",
                from_km=bin_start,
                to_km=bin_end,
                width_m=segment.width_m,
                direction=segment.direction,
                events=segment.events
            )
            
            # Calculate concurrent runners in this bin
            bin_concurrent = self.calculate_concurrent_runners(
                bin_segment, pace_data, start_times, time_bin_start, density_cfg
            )
            
            # Calculate bin dimensions
            bin_length_m = (bin_end - bin_start) * 1000
            bin_area_m2 = bin_length_m * segment.width_m
            
            # Calculate densities for this bin
            bin_areal_density = bin_concurrent / bin_area_m2 if bin_area_m2 > 0 else 0.0
            bin_crowd_density = bin_concurrent / bin_length_m if bin_length_m > 0 else 0.0
            
            bin_densities.append({
                "bin_index": i,
                "from_km": bin_start,
                "to_km": bin_end,
                "length_m": bin_length_m,
                "area_m2": bin_area_m2,
                "concurrent_runners": bin_concurrent,
                "areal_density": bin_areal_density,
                "crowd_density": bin_crowd_density
            })
            
            total_concurrent += bin_concurrent
            
            # Track peak densities
            if bin_areal_density > peak_areal_density:
                peak_areal_density = bin_areal_density
                bin_details["peak_bin_index"] = i
            if bin_crowd_density > peak_crowd_density:
                peak_crowd_density = bin_crowd_density
        
        bin_details["bins"] = bin_densities
        bin_details["total_concurrent"] = total_concurrent
        
        return peak_areal_density, peak_crowd_density, bin_details
    
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
        los_areal = "A"  # Default to A (Comfortable)
        for level, (min_val, max_val) in self.los_areal_thresholds.items():
            if min_val <= areal_density < max_val:
                los_areal = level
                break
        
        # Classify crowd density
        los_crowd = "A"  # Default to A (Comfortable)
        for level, (min_val, max_val) in self.los_crowd_thresholds.items():
            if min_val <= crowd_density < max_val:
                los_crowd = level
                break
        
        return los_areal, los_crowd
    
    def smooth_narrative_transitions(self, results: List[DensityResult]) -> List[Dict[str, Any]]:
        """
        Smooth narrative transitions to avoid per-bin noise.
        
        CRITICAL: Reports sustained periods rather than per-bin fluctuations.
        Only processes active bins (where concurrent_runners > 0) to avoid spurious tails.
        
        Args:
            results: List of DensityResult objects
            
        Returns:
            List of sustained period summaries
        """
        if not results:
            return []
        
        # Filter to active bins only (avoids spurious 13:40:30 tails)
        active_results = [r for r in results if r.concurrent_runners > 0]
        
        if not active_results:
            return []
        
        sustained_periods = []
        min_sustained_bins = (self.config.min_sustained_period_minutes * 60) // self.config.bin_seconds
        
        # Group consecutive bins with same LOS
        current_areal_los = None
        current_crowd_los = None
        current_start_idx = 0
        
        for i, result in enumerate(active_results):
            # Check for LOS changes
            if (result.los_areal != current_areal_los or 
                result.los_crowd != current_crowd_los):
                
                # If we have a sustained period, add it
                if (current_areal_los is not None and 
                    i - current_start_idx >= min_sustained_bins):
                    
                    sustained_periods.append({
                        "start_time": active_results[current_start_idx].t_start,
                        "end_time": active_results[i-1].t_end,
                        "duration_minutes": (i - current_start_idx) * self.config.bin_seconds / 60,
                        "los_areal": current_areal_los,
                        "los_crowd": current_crowd_los,
                        "avg_areal_density": np.mean([
                            r.areal_density for r in active_results[current_start_idx:i]
                        ]),
                        "avg_crowd_density": np.mean([
                            r.crowd_density for r in active_results[current_start_idx:i]
                        ]),
                        "peak_concurrent_runners": max([
                            r.concurrent_runners for r in active_results[current_start_idx:i]
                        ])
                    })
                
                # Start new period
                current_areal_los = result.los_areal
                current_crowd_los = result.los_crowd
                current_start_idx = i
        
        # Handle final period
        if (current_areal_los is not None and 
            len(active_results) - current_start_idx >= min_sustained_bins):
            
            sustained_periods.append({
                "start_time": active_results[current_start_idx].t_start,
                "end_time": active_results[-1].t_end,
                "duration_minutes": (len(active_results) - current_start_idx) * self.config.bin_seconds / 60,
                "los_areal": current_areal_los,
                "los_crowd": current_crowd_los,
                "avg_areal_density": np.mean([
                    r.areal_density for r in active_results[current_start_idx:]
                ]),
                "avg_crowd_density": np.mean([
                    r.crowd_density for r in active_results[current_start_idx:]
                ]),
                "peak_concurrent_runners": max([
                    r.concurrent_runners for r in active_results[current_start_idx:]
                ])
            })
        
        return sustained_periods
    
    def compute_density_timeseries(self,
                                 segment: SegmentMeta,
                                 pace_data: pd.DataFrame,
                                 start_times: Dict[str, datetime],
                                 time_bins: List[datetime],
                                 density_cfg: dict = None) -> List[DensityResult]:
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
            
            # Calculate segment concurrency using union-of-intervals (avoids overcounting)
            concurrent_runners = self.calculate_concurrent_runners_union(
                segment, pace_data, start_times, time_bin_start, density_cfg
            )
            
            # Validate population bounds
            validation_flags = self.validate_population_bounds(
                segment.segment_id, concurrent_runners, list(segment.events), pace_data
            )
            
            # Calculate density metrics using segment-level concurrency
            areal_density, crowd_density = self.calculate_density_metrics(
                concurrent_runners, segment, density_cfg
            )
            
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
                flags=flags.copy() + validation_flags
            )
            
            results.append(result)
        
        return results
    
    def summarize_density(self, results: List[DensityResult], 
                         smooth_window: str = "120s",
                         min_active_bins: int = 3,
                         min_active_duration_s: int = 120,
                         tot_from: str = "active") -> DensitySummary:
        """
        Summarize density analysis results for a segment.
        
        Args:
            results: List of DensityResult objects
            smooth_window: Time window for smoothing (e.g., "120s")
            min_active_bins: Minimum number of active bins required
            min_active_duration_s: Minimum active duration in seconds
            tot_from: TOT calculation source ("active" or "full")
            
        Returns:
            DensitySummary object with both full-window and active-window statistics
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
        
        # -------------------------
        # FULL-WINDOW (existing)
        # -------------------------
        # Find peak densities from all results
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
        
        # Calculate TOT (Time Over Threshold) from full window
        tot_areal_sec = sum(
            self.config.bin_seconds for result in results
            if result.areal_density >= self.config.threshold_areal
        )
        
        tot_crowd_sec = sum(
            self.config.bin_seconds for result in results
            if result.crowd_density >= self.config.threshold_crowd
        )
        
        # Calculate LOS distributions from full window
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
        
        # -------------------------
        # ACTIVE-WINDOW (new)
        # -------------------------
        # Filter to active bins (concurrent_runners > 0)
        active_results = [r for r in results if r.concurrent_runners > 0]
        
        if active_results:
            # Calculate active window bounds
            active_start = min(r.t_start for r in active_results)
            active_end = max(r.t_end for r in active_results)
            
            # Convert to datetime objects for duration calculation
            try:
                active_start_dt = datetime.strptime(active_start, "%H:%M:%S")
                active_end_dt = datetime.strptime(active_end, "%H:%M:%S")
                active_duration = (active_end_dt - active_start_dt).total_seconds()
            except ValueError:
                # Fallback if time format is different
                active_duration = len(active_results) * self.config.bin_seconds
            
            # Calculate occupancy rate using datetime comparison
            # Occupancy rate = active bins / total bins in the active time window
            active_start_dt = datetime.strptime(active_start, "%H:%M:%S")
            active_end_dt = datetime.strptime(active_end, "%H:%M:%S")
            
            window_results = []
            for r in results:
                r_start_dt = datetime.strptime(r.t_start, "%H:%M:%S")
                r_end_dt = datetime.strptime(r.t_end, "%H:%M:%S")
                if r_start_dt >= active_start_dt and r_end_dt <= active_end_dt:
                    window_results.append(r)
            
            occupancy_rate = len(active_results) / len(window_results) if window_results else 0.0
            
            # Guardrails
            low_occupancy = (len(active_results) < min_active_bins) or (active_duration < min_active_duration_s)
            
            # Calculate active-window statistics
            active_areal_densities = [r.areal_density for r in active_results]
            active_crowd_densities = [r.crowd_density for r in active_results]
            active_concurrent_runners = [r.concurrent_runners for r in active_results]
            
            # Active-window peaks and statistics
            active_peak_areal = max(active_areal_densities) if active_areal_densities else 0.0
            active_peak_crowd = max(active_crowd_densities) if active_crowd_densities else 0.0
            active_peak_concurrency = max(active_concurrent_runners) if active_concurrent_runners else 0
            
            # Find peak timestamps
            active_peak_areal_time = None
            active_peak_crowd_time = None
            if active_areal_densities:
                peak_areal_idx = active_areal_densities.index(active_peak_areal)
                active_peak_areal_time = active_results[peak_areal_idx].t_start
            if active_crowd_densities:
                peak_crowd_idx = active_crowd_densities.index(active_peak_crowd)
                active_peak_crowd_time = active_results[peak_crowd_idx].t_start
            
            # Calculate percentiles
            active_p95_areal = np.percentile(active_areal_densities, 95) if active_areal_densities else 0.0
            active_p95_crowd = np.percentile(active_crowd_densities, 95) if active_crowd_densities else 0.0
            
            # Calculate active means
            active_mean_areal = np.mean(active_areal_densities) if active_areal_densities else 0.0
            active_mean_crowd = np.mean(active_crowd_densities) if active_crowd_densities else 0.0
            
            # Calculate TOT from active window if requested
            if tot_from == "active":
                tot_areal_sec = sum(
                    self.config.bin_seconds for result in active_results
                    if result.areal_density >= self.config.threshold_areal
                )
                
                tot_crowd_sec = sum(
                    self.config.bin_seconds for result in active_results
                    if result.crowd_density >= self.config.threshold_crowd
                )
            
            # Always calculate active TOT metrics for reporting
            active_tot_areal_sec = sum(
                self.config.bin_seconds for result in active_results
                if result.areal_density >= self.config.threshold_areal
            )
            
            active_tot_crowd_sec = sum(
                self.config.bin_seconds for result in active_results
                if result.crowd_density >= self.config.threshold_crowd
            )
            
            # Add active-window flags
            active_flags = ["active_window_available"]
            if low_occupancy:
                active_flags.append("low_occupancy")
            if occupancy_rate < 0.5:
                active_flags.append("low_occupancy_rate")
                
        else:
            # No active results
            active_start = None
            active_end = None
            active_duration = 0
            occupancy_rate = 0.0
            low_occupancy = True
            active_peak_areal = 0.0
            active_peak_crowd = 0.0
            active_peak_concurrency = 0
            active_p95_areal = 0.0
            active_p95_crowd = 0.0
            active_mean_areal = 0.0
            active_mean_crowd = 0.0
            active_tot_areal_sec = 0
            active_tot_crowd_sec = 0
            active_peak_areal_time = None
            active_peak_crowd_time = None
            active_flags = ["no_active_bins"]
        
        # Collect all flags
        all_flags = set()
        for result in results:
            all_flags.update(result.flags)
        all_flags.update(active_flags)
        
        # Create enhanced DensitySummary with active-window data
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
            flags=list(all_flags),
            # Active-window data
            active_start=active_start,
            active_end=active_end,
            active_duration_s=int(active_duration),
            occupancy_rate=occupancy_rate,
            low_occupancy_flag=low_occupancy,
            active_peak_areal=active_peak_areal,
            active_peak_crowd=active_peak_crowd,
            active_peak_concurrency=active_peak_concurrency,
            active_p95_areal=active_p95_areal,
            active_p95_crowd=active_p95_crowd,
            active_mean_areal=active_mean_areal,
            active_mean_crowd=active_mean_crowd,
            # TOT metrics for active window
            active_tot_areal_sec=active_tot_areal_sec,
            active_tot_crowd_sec=active_tot_crowd_sec,
            # Peak timestamps
            active_peak_areal_time=active_peak_areal_time,
            active_peak_crowd_time=active_peak_crowd_time
        )


def analyze_density_segments(pace_data: pd.DataFrame,
                             start_times: Dict[str, datetime],
                             config: DensityConfig = None,
                             density_csv_path: str = "data/segments_new.csv") -> Dict[str, Any]:
    """
    Analyze density for all segments using segments_new.csv configuration.
    
    Args:
        pace_data: DataFrame with runner pace data
        start_times: Dictionary of event start times
        config: Density analysis configuration
        density_csv_path: Path to density.csv file
        
    Returns:
        Dictionary with density analysis results
    """
    config = config or DensityConfig()
    analyzer = DensityAnalyzer(config, None)  # No width provider needed - using density.csv
    
    # Load density configuration
    density_cfg = load_density_cfg(density_csv_path)
    
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
            "total_segments": len(density_cfg),
            "processed_segments": 0,
            "skipped_segments": 0,
            "analysis_start": analysis_start.isoformat(),
            "analysis_end": analysis_end.isoformat(),
            "time_bin_seconds": config.bin_seconds
        },
        "segments": {}
    }
    
    for seg_id, d in density_cfg.items():
        # Calculate physical segment dimensions from all events
        max_km = 0.0
        min_km = float('inf')
        
        for event in d["events"]:
            if event == "Full" and d.get("full_from_km") is not None:
                min_km = min(min_km, d["full_from_km"])
                max_km = max(max_km, d["full_to_km"])
            elif event == "Half" and d.get("half_from_km") is not None:
                min_km = min(min_km, d["half_from_km"])
                max_km = max(max_km, d["half_to_km"])
            elif event == "10K" and d.get("tenk_from_km") is not None:
                min_km = min(min_km, d["tenk_from_km"])
                max_km = max(max_km, d["tenk_to_km"])
        
        if min_km == float('inf'):
            min_km = 0.0
        
        # Create segment metadata from segments_new.csv
        segment = SegmentMeta(
            segment_id=seg_id,
            from_km=min_km,  # Physical segment start
            to_km=max_km,    # Physical segment end
            width_m=d["width_m"],
            direction=d["direction"],
            events=d["events"],
            event_a="",  # Not used in density analysis
            event_b=""   # Not used in density analysis
        )
        
        # Compute density time series
        density_results = analyzer.compute_density_timeseries(
            segment, pace_data, start_times, time_bins, density_cfg[seg_id]
        )
        
        if density_results:
            # Summarize results
            summary = analyzer.summarize_density(density_results)
            
            # Generate narrative smoothing
            sustained_periods = analyzer.smooth_narrative_transitions(density_results)
            
            # Calculate per-event experienced density analysis
            per_event_summaries = analyzer.calculate_per_event_experienced_density(
                segment, pace_data, start_times, time_bins, density_cfg[seg_id]
            )
            
            # Load rulebook for v2 schema resolution
            try:
                import yaml
                
                with open("config/density_rulebook.yml", 'r') as f:
                    rulebook = yaml.safe_load(f)
                
                # Convert summary to dict first
                summary_dict = summary.__dict__.copy()
                
                # Build v2 context using the new integration function
                v2_context = build_segment_context_v2(seg_id, d, summary_dict, rulebook)
                
                # Add v2 data to summary_dict for backward compatibility
                summary_dict["schema_name"] = v2_context["schema_name"]
                summary_dict["flow_rate"] = v2_context["flow_rate"]
                summary_dict["fired_actions"] = v2_context["fired_actions"]
                
                logger.info(f"Segment {seg_id}: schema_name={v2_context['schema_name']}, flow_enabled={v2_context['flow_enabled']}, flow_rate={v2_context['flow_rate']}")
                
            except Exception as e:
                logger.warning(f"Failed to load v2 rulebook for segment {seg_id}: {e}")
                summary_dict = summary.__dict__.copy()
                summary_dict["schema_name"] = "on_course_open"
                summary_dict["flow_rate"] = None
                summary_dict["fired_actions"] = []
            
            results["segments"][segment.segment_id] = {
                "summary": summary_dict,
                "time_series": density_results,
                "sustained_periods": sustained_periods,
                "events_included": list(d["events"]),
                "seg_label": d["seg_label"],
                "flow_type": d["flow_type"],
                "per_event": per_event_summaries,
                "v2_context": v2_context if 'v2_context' in locals() else None
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