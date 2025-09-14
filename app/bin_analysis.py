"""
Bin-Level Analysis Module

This module provides bin-level density and flow analysis capabilities
for map visualization. It implements the technical strategy from Issue #146.

Key Features:
- Bin-level density calculations
- Bin-level flow analysis (overtakes, co-presence)
- Caching and persistence for historical analysis
- Integration with existing density.py and flow.py modules
"""

from __future__ import annotations
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from .constants import DISTANCE_BIN_SIZE_KM, METERS_PER_KM
    from .density import analyze_density_segments
    from .flow import analyze_temporal_flow_segments
    from .io.loader import load_runners, load_segments
except ImportError:
    from constants import DISTANCE_BIN_SIZE_KM, METERS_PER_KM
    from density import analyze_density_segments
    from flow import analyze_temporal_flow_segments
    from io.loader import load_runners, load_segments

logger = logging.getLogger(__name__)

@dataclass
class BinData:
    """Data structure for individual bin information."""
    bin_index: int
    start_km: float
    end_km: float
    density: float
    density_level: str
    overtakes: Dict[str, int]
    co_presence: Dict[str, int]
    rsi_score: float
    convergence_point: bool
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None

@dataclass
class SegmentBinData:
    """Data structure for segment with bin-level data."""
    segment_id: str
    segment_label: str
    bins: List[BinData]
    total_bins: int
    bin_size_m: float
    generated_at: datetime

class BinAnalysisCache:
    """Cache for bin-level analysis results."""
    
    def __init__(self):
        self._cache: Dict[str, SegmentBinData] = {}
    
    def _generate_cache_key(self, segment_id: str, dataset_hash: str, bin_size: float) -> str:
        """Generate cache key for bin data."""
        return f"{segment_id}|{dataset_hash}|{bin_size}"
    
    def get(self, segment_id: str, dataset_hash: str, bin_size: float) -> Optional[SegmentBinData]:
        """Get cached bin data."""
        key = self._generate_cache_key(segment_id, dataset_hash, bin_size)
        return self._cache.get(key)
    
    def set(self, segment_id: str, dataset_hash: str, bin_size: float, data: SegmentBinData) -> None:
        """Cache bin data."""
        key = self._generate_cache_key(segment_id, dataset_hash, bin_size)
        self._cache[key] = data
    
    def invalidate(self, dataset_hash: str) -> None:
        """Invalidate cache entries for a specific dataset."""
        keys_to_remove = [key for key in self._cache.keys() if dataset_hash in key]
        for key in keys_to_remove:
            del self._cache[key]

# Global cache instance
_bin_cache = BinAnalysisCache()

def calculate_dataset_hash(pace_csv: str, segments_csv: str, start_times: Dict[str, int]) -> str:
    """Calculate hash for dataset to enable cache invalidation."""
    content = f"{pace_csv}|{segments_csv}|{start_times}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

def create_bins_for_segment(segment_data: Dict[str, Any], bin_size_km: float) -> List[BinData]:
    """Create bins for a segment based on its length and bin size."""
    from_km = segment_data.get('from_km', 0.0)
    to_km = segment_data.get('to_km', 0.0)
    segment_length = to_km - from_km
    
    if segment_length <= 0:
        return []
    
    bins = []
    num_bins = int(segment_length / bin_size_km) + 1
    
    for i in range(num_bins):
        start_km = from_km + (i * bin_size_km)
        end_km = min(from_km + ((i + 1) * bin_size_km), to_km)
        
        if start_km >= to_km:
            break
            
        bins.append(BinData(
            bin_index=i,
            start_km=start_km,
            end_km=end_km,
            density=0.0,
            density_level="A",
            overtakes={},
            co_presence={},
            rsi_score=0.0,
            convergence_point=False
        ))
    
    return bins

def analyze_bin_density(bins: List[BinData], density_results: Dict[str, Any], segment_id: str) -> List[BinData]:
    """Analyze density for each bin within a segment."""
    if not density_results.get('ok') or segment_id not in density_results.get('segments', {}):
        return bins
    
    segment_data = density_results['segments'][segment_id]
    time_series = segment_data.get('time_series', [])
    
    # Calculate density for each bin based on time series data
    for bin_data in bins:
        bin_density = 0.0
        bin_duration = 0.0
        
        for time_point in time_series:
            # Check if this time point falls within the bin's km range
            if bin_data.start_km <= time_point.get('km', 0) < bin_data.end_km:
                density = time_point.get('areal_density', 0.0)
                duration = time_point.get('duration_s', 0.0) / 3600.0  # Convert to hours
                
                bin_density += density * duration
                bin_duration += duration
        
        if bin_duration > 0:
            bin_data.density = bin_density / bin_duration
        else:
            bin_data.density = 0.0
        
        # Determine density level (simplified for now)
        if bin_data.density >= 1.5:
            bin_data.density_level = "F"
        elif bin_data.density >= 1.2:
            bin_data.density_level = "E"
        elif bin_data.density >= 0.8:
            bin_data.density_level = "D"
        elif bin_data.density >= 0.5:
            bin_data.density_level = "C"
        elif bin_data.density >= 0.2:
            bin_data.density_level = "B"
        else:
            bin_data.density_level = "A"
    
    return bins

def analyze_bin_flow(bins: List[BinData], flow_results: Dict[str, Any], segment_id: str) -> List[BinData]:
    """Analyze flow (overtakes, co-presence) for each bin within a segment."""
    if not flow_results.get('ok'):
        return bins
    
    # Find flow data for this segment
    segment_flow_data = None
    for segment in flow_results.get('segments', []):
        if segment.get('seg_id') == segment_id:
            segment_flow_data = segment
            break
    
    if not segment_flow_data:
        return bins
    
    # Process overtakes and co-presence data
    for bin_data in bins:
        # Initialize overtakes and co-presence
        bin_data.overtakes = {}
        bin_data.co_presence = {}
        
        # Get event pairs for this segment
        event_a = segment_flow_data.get('event_a')
        event_b = segment_flow_data.get('event_b')
        
        if event_a and event_b:
            # Calculate overtakes for this bin
            overtaking_a = segment_flow_data.get('overtaking_a', 0)
            overtaking_b = segment_flow_data.get('overtaking_b', 0)
            
            # Simple distribution across bins (in real implementation, this would be more sophisticated)
            num_bins = len(bins)
            if num_bins > 0:
                bin_data.overtakes[f"{event_a}_vs_{event_b}"] = overtaking_a // num_bins
                bin_data.overtakes[f"{event_b}_vs_{event_a}"] = overtaking_b // num_bins
            
            # Calculate co-presence
            co_presence_a = segment_flow_data.get('co_presence_a', 0)
            co_presence_b = segment_flow_data.get('co_presence_b', 0)
            
            if num_bins > 0:
                bin_data.co_presence[event_a] = co_presence_a // num_bins
                bin_data.co_presence[event_b] = co_presence_b // num_bins
        
        # Calculate RSI score (simplified)
        total_overtakes = sum(bin_data.overtakes.values())
        total_co_presence = sum(bin_data.co_presence.values())
        
        if total_co_presence > 0:
            bin_data.rsi_score = total_overtakes / total_co_presence
        else:
            bin_data.rsi_score = 0.0
        
        # Determine if this is a convergence point
        bin_data.convergence_point = bin_data.rsi_score > 0.1  # Threshold for convergence
    
    return bins

def analyze_segment_bins(
    segment_id: str,
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, int],
    bin_size_km: Optional[float] = None
) -> SegmentBinData:
    """
    Analyze bin-level data for a specific segment.
    
    Args:
        segment_id: ID of the segment to analyze
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments data CSV
        start_times: Event start times in minutes from midnight
        bin_size_km: Bin size in kilometers (defaults to DISTANCE_BIN_SIZE_KM)
    
    Returns:
        SegmentBinData with bin-level analysis results
    """
    if bin_size_km is None:
        bin_size_km = DISTANCE_BIN_SIZE_KM
    
    # Check cache first
    dataset_hash = calculate_dataset_hash(pace_csv, segments_csv, start_times)
    cached_data = _bin_cache.get(segment_id, dataset_hash, bin_size_km)
    if cached_data:
        logger.info(f"Using cached bin data for segment {segment_id}")
        return cached_data
    
    logger.info(f"Computing bin-level analysis for segment {segment_id}")
    
    # Load segment data
    segments_df = load_segments(segments_csv)
    segment_row = segments_df[segments_df['seg_id'] == segment_id]
    
    if segment_row.empty:
        raise ValueError(f"Segment {segment_id} not found in segments data")
    
    segment_data = segment_row.iloc[0].to_dict()
    segment_label = segment_data.get('seg_label', segment_id)
    
    # Create bins for this segment
    bins = create_bins_for_segment(segment_data, bin_size_km)
    
    # Run density analysis
    density_results = analyze_density_segments(
        pace_csv=pace_csv,
        segments_csv=segments_csv,
        start_times=start_times
    )
    
    # Analyze bin density
    bins = analyze_bin_density(bins, density_results, segment_id)
    
    # Run flow analysis
    flow_results = analyze_temporal_flow_segments(
        pace_csv=pace_csv,
        segments_csv=segments_csv,
        start_times=start_times
    )
    
    # Analyze bin flow
    bins = analyze_bin_flow(bins, flow_results, segment_id)
    
    # Create result
    result = SegmentBinData(
        segment_id=segment_id,
        segment_label=segment_label,
        bins=bins,
        total_bins=len(bins),
        bin_size_m=bin_size_km * METERS_PER_KM,
        generated_at=datetime.now()
    )
    
    # Cache the result
    _bin_cache.set(segment_id, dataset_hash, bin_size_km, result)
    
    return result

def get_all_segment_bins(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, int],
    bin_size_km: Optional[float] = None
) -> Dict[str, SegmentBinData]:
    """
    Get bin-level data for all segments.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments data CSV
        start_times: Event start times in minutes from midnight
        bin_size_km: Bin size in kilometers (defaults to DISTANCE_BIN_SIZE_KM)
    
    Returns:
        Dictionary mapping segment_id to SegmentBinData
    """
    if bin_size_km is None:
        bin_size_km = DISTANCE_BIN_SIZE_KM
    
    # Load segments data
    segments_df = load_segments(segments_csv)
    segment_ids = segments_df['seg_id'].tolist()
    
    results = {}
    for segment_id in segment_ids:
        try:
            results[segment_id] = analyze_segment_bins(
                segment_id=segment_id,
                pace_csv=pace_csv,
                segments_csv=segments_csv,
                start_times=start_times,
                bin_size_km=bin_size_km
            )
        except Exception as e:
            logger.error(f"Error analyzing bins for segment {segment_id}: {e}")
            continue
    
    return results

def clear_bin_cache() -> None:
    """Clear all cached bin data."""
    _bin_cache._cache.clear()
    logger.info("Bin analysis cache cleared")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return {
        "cached_segments": len(_bin_cache._cache),
        "cache_keys": list(_bin_cache._cache.keys())
    }

def analyze_historical_trends(
    segment_id: str,
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, int],
    bin_size_km: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyze historical trends for a segment's bins.
    
    This function provides historical analysis capabilities for understanding
    how bin-level data changes over time or across different scenarios.
    """
    if bin_size_km is None:
        bin_size_km = DISTANCE_BIN_SIZE_KM
    
    # Get current bin data
    current_data = analyze_segment_bins(
        segment_id=segment_id,
        pace_csv=pace_csv,
        segments_csv=segments_csv,
        start_times=start_times,
        bin_size_km=bin_size_km
    )
    
    # Calculate trend metrics
    bins = current_data.bins
    if not bins:
        return {
            "ok": False,
            "message": "No bins found for segment",
            "trends": {}
        }
    
    # Calculate density trends
    densities = [bin.density for bin in bins]
    avg_density = sum(densities) / len(densities) if densities else 0.0
    max_density = max(densities) if densities else 0.0
    min_density = min(densities) if densities else 0.0
    
    # Calculate RSI trends
    rsi_scores = [bin.rsi_score for bin in bins]
    avg_rsi = sum(rsi_scores) / len(rsi_scores) if rsi_scores else 0.0
    max_rsi = max(rsi_scores) if rsi_scores else 0.0
    
    # Count convergence points
    convergence_points = sum(1 for bin in bins if bin.convergence_point)
    convergence_rate = convergence_points / len(bins) if bins else 0.0
    
    # Calculate density level distribution
    density_levels = {}
    for bin in bins:
        level = bin.density_level
        density_levels[level] = density_levels.get(level, 0) + 1
    
    # Calculate overtake trends
    total_overtakes = {}
    for bin in bins:
        for event_pair, count in bin.overtakes.items():
            total_overtakes[event_pair] = total_overtakes.get(event_pair, 0) + count
    
    # Calculate co-presence trends
    total_co_presence = {}
    for bin in bins:
        for event, count in bin.co_presence.items():
            total_co_presence[event] = total_co_presence.get(event, 0) + count
    
    return {
        "ok": True,
        "segment_id": segment_id,
        "segment_label": current_data.segment_label,
        "total_bins": len(bins),
        "bin_size_km": bin_size_km,
        "trends": {
            "density": {
                "average": round(avg_density, 3),
                "maximum": round(max_density, 3),
                "minimum": round(min_density, 3),
                "range": round(max_density - min_density, 3)
            },
            "rsi": {
                "average": round(avg_rsi, 3),
                "maximum": round(max_rsi, 3)
            },
            "convergence": {
                "points": convergence_points,
                "rate": round(convergence_rate, 3)
            },
            "density_levels": density_levels,
            "overtakes": total_overtakes,
            "co_presence": total_co_presence
        },
        "generated_at": current_data.generated_at.isoformat()
    }

def compare_segments(
    segment_ids: List[str],
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, int],
    bin_size_km: Optional[float] = None
) -> Dict[str, Any]:
    """
    Compare bin-level data across multiple segments.
    
    This function provides comparative analysis capabilities for understanding
    how different segments perform relative to each other.
    """
    if bin_size_km is None:
        bin_size_km = DISTANCE_BIN_SIZE_KM
    
    if len(segment_ids) < 2:
        return {
            "ok": False,
            "message": "At least 2 segments required for comparison"
        }
    
    # Get data for all segments
    segment_data = {}
    for segment_id in segment_ids:
        try:
            segment_data[segment_id] = analyze_segment_bins(
                segment_id=segment_id,
                pace_csv=pace_csv,
                segments_csv=segments_csv,
                start_times=start_times,
                bin_size_km=bin_size_km
            )
        except Exception as e:
            logger.error(f"Error analyzing segment {segment_id}: {e}")
            continue
    
    if len(segment_data) < 2:
        return {
            "ok": False,
            "message": "Insufficient data for comparison"
        }
    
    # Calculate comparison metrics
    comparison = {
        "segments": {},
        "rankings": {},
        "summary": {}
    }
    
    # Analyze each segment
    for segment_id, data in segment_data.items():
        bins = data.bins
        if not bins:
            continue
        
        # Calculate segment metrics
        densities = [bin.density for bin in bins]
        rsi_scores = [bin.rsi_score for bin in bins]
        convergence_points = sum(1 for bin in bins if bin.convergence_point)
        
        avg_density = sum(densities) / len(densities) if densities else 0.0
        avg_rsi = sum(rsi_scores) / len(rsi_scores) if rsi_scores else 0.0
        convergence_rate = convergence_points / len(bins) if bins else 0.0
        
        comparison["segments"][segment_id] = {
            "segment_label": data.segment_label,
            "total_bins": len(bins),
            "avg_density": round(avg_density, 3),
            "avg_rsi": round(avg_rsi, 3),
            "convergence_rate": round(convergence_rate, 3),
            "convergence_points": convergence_points
        }
    
    # Calculate rankings
    segments_by_density = sorted(
        comparison["segments"].items(),
        key=lambda x: x[1]["avg_density"],
        reverse=True
    )
    segments_by_rsi = sorted(
        comparison["segments"].items(),
        key=lambda x: x[1]["avg_rsi"],
        reverse=True
    )
    segments_by_convergence = sorted(
        comparison["segments"].items(),
        key=lambda x: x[1]["convergence_rate"],
        reverse=True
    )
    
    comparison["rankings"] = {
        "by_density": [seg[0] for seg in segments_by_density],
        "by_rsi": [seg[0] for seg in segments_by_rsi],
        "by_convergence": [seg[0] for seg in segments_by_convergence]
    }
    
    # Calculate summary statistics
    all_densities = [seg[1]["avg_density"] for seg in comparison["segments"].items()]
    all_rsi = [seg[1]["avg_rsi"] for seg in comparison["segments"].items()]
    all_convergence = [seg[1]["convergence_rate"] for seg in comparison["segments"].items()]
    
    comparison["summary"] = {
        "total_segments": len(comparison["segments"]),
        "density_range": round(max(all_densities) - min(all_densities), 3) if all_densities else 0.0,
        "rsi_range": round(max(all_rsi) - min(all_rsi), 3) if all_rsi else 0.0,
        "convergence_range": round(max(all_convergence) - min(all_convergence), 3) if all_convergence else 0.0
    }
    
    return {
        "ok": True,
        "comparison": comparison,
        "generated_at": datetime.now().isoformat()
    }

def export_bin_data(
    segment_ids: List[str],
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, int],
    format: str = "csv",
    bin_size_km: Optional[float] = None
) -> Dict[str, Any]:
    """
    Export bin-level data for multiple segments.
    
    This function provides export capabilities for bin-level data
    in various formats for further analysis.
    """
    if bin_size_km is None:
        bin_size_km = DISTANCE_BIN_SIZE_KM
    
    # Get data for all segments
    all_bins = get_all_segment_bins(
        pace_csv=pace_csv,
        segments_csv=segments_csv,
        start_times=start_times,
        bin_size_km=bin_size_km
    )
    
    # Filter to requested segments
    if segment_ids:
        all_bins = {seg_id: data for seg_id, data in all_bins.items() if seg_id in segment_ids}
    
    if format.lower() == "csv":
        # Generate CSV data
        csv_data = []
        for segment_id, segment_data in all_bins.items():
            for bin_data in segment_data.bins:
                # Flatten overtakes and co-presence data
                overtakes_str = "; ".join([f"{k}:{v}" for k, v in bin_data.overtakes.items()])
                co_presence_str = "; ".join([f"{k}:{v}" for k, v in bin_data.co_presence.items()])
                
                csv_data.append({
                    "segment_id": segment_id,
                    "segment_label": segment_data.segment_label,
                    "bin_index": bin_data.bin_index,
                    "start_km": bin_data.start_km,
                    "end_km": bin_data.end_km,
                    "density": round(bin_data.density, 3),
                    "density_level": bin_data.density_level,
                    "overtakes": overtakes_str,
                    "co_presence": co_presence_str,
                    "rsi_score": round(bin_data.rsi_score, 3),
                    "convergence_point": bin_data.convergence_point,
                    "centroid_lat": bin_data.centroid_lat,
                    "centroid_lon": bin_data.centroid_lon
                })
        
        return {
            "ok": True,
            "format": "csv",
            "data": csv_data,
            "total_records": len(csv_data),
            "segments": list(all_bins.keys())
        }
    
    elif format.lower() == "geojson":
        # Generate GeoJSON data
        from .geo_utils import generate_bins_geojson
        geojson = generate_bins_geojson(all_bins)
        return {
            "ok": True,
            "format": "geojson",
            "data": geojson,
            "total_features": len(geojson.get("features", [])),
            "segments": list(all_bins.keys())
        }
    
    else:
        return {
            "ok": False,
            "message": f"Unsupported format: {format}"
        }
