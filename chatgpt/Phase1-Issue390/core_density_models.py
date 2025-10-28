"""
Density Analysis Data Models

Contains dataclasses and data structures for density analysis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


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
