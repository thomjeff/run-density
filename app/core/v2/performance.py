"""
Runflow v2 Performance Monitoring Module

Provides performance monitoring, timing instrumentation, guardrails, and coarsening suggestions.

Issue #503: Phase 9 - Performance & Optimization
"""

from __future__ import annotations
import time
import functools
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.utils.constants import (
    BIN_MAX_FEATURES,
    MAX_BIN_GENERATION_TIME_SECONDS,
    BIN_HARD_LIMIT_SECONDS
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single phase or operation."""
    phase_name: str
    start_time: float
    end_time: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    memory_mb: Optional[float] = None
    bin_count: Optional[int] = None
    feature_count: Optional[int] = None
    segment_count: Optional[int] = None
    event_count: Optional[int] = None
    runner_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, **kwargs):
        """Mark phase as complete and record final metrics."""
        self.end_time = time.monotonic()
        self.elapsed_seconds = self.end_time - self.start_time
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "phase": self.phase_name,
            "elapsed_seconds": round(self.elapsed_seconds, 3) if self.elapsed_seconds else None,
            "elapsed_ms": int(self.elapsed_seconds * 1000) if self.elapsed_seconds else None,
            "memory_mb": round(self.memory_mb, 2) if self.memory_mb else None,
            "bin_count": self.bin_count,
            "feature_count": self.feature_count,
            "segment_count": self.segment_count,
            "event_count": self.event_count,
            "runner_count": self.runner_count,
            "metadata": self.metadata
        }


class PerformanceMonitor:
    """Performance monitoring context manager and metrics collector."""
    
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id
        self.metrics: List[PerformanceMetrics] = []
        self.start_time = time.monotonic()
        self.total_memory_mb: Optional[float] = None
    
    def start_phase(self, phase_name: str) -> PerformanceMetrics:
        """Start timing a phase."""
        metrics = PerformanceMetrics(
            phase_name=phase_name,
            start_time=time.monotonic()
        )
        self.metrics.append(metrics)
        logger.info(f"⏱️  Starting phase: {phase_name}")
        return metrics
    
    def get_total_elapsed(self) -> float:
        """Get total elapsed time since monitor started."""
        return time.monotonic() - self.start_time
    
    def get_phase_metrics(self, phase_name: str) -> Optional[PerformanceMetrics]:
        """Get metrics for a specific phase."""
        for m in self.metrics:
            if m.phase_name == phase_name:
                return m
        return None
    
    def check_guardrails(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Check performance guardrails and return warnings/suggestions.
        
        Returns:
            Dict with 'warnings', 'suggestions', and 'passed' keys
        """
        warnings = []
        suggestions = []
        passed = True
        
        # Check feature count guardrail
        if metrics.feature_count and metrics.feature_count > BIN_MAX_FEATURES:
            warnings.append(
                f"Feature count ({metrics.feature_count:,}) exceeds threshold ({BIN_MAX_FEATURES:,})"
            )
            suggestions.append("Consider coarsening: increase bin size or time window")
            passed = False
        
        # Check bin generation time guardrail
        if metrics.elapsed_seconds:
            if metrics.elapsed_seconds > MAX_BIN_GENERATION_TIME_SECONDS:
                warnings.append(
                    f"Bin generation time ({metrics.elapsed_seconds:.1f}s) exceeds threshold ({MAX_BIN_GENERATION_TIME_SECONDS}s)"
                )
                suggestions.append("Consider coarsening: increase bin size or time window")
                passed = False
            
            if metrics.elapsed_seconds > BIN_HARD_LIMIT_SECONDS:
                warnings.append(
                    f"Bin generation time ({metrics.elapsed_seconds:.1f}s) exceeds hard limit ({BIN_HARD_LIMIT_SECONDS}s)"
                )
                suggestions.append("Immediate coarsening required: increase bin size to 0.2km+ and time window to 120s+")
                passed = False
        
        # Check total runtime (5 minute target)
        total_elapsed = self.get_total_elapsed()
        if total_elapsed > 300:  # 5 minutes
            warnings.append(
                f"Total runtime ({total_elapsed/60:.1f} min) exceeds target (5 min)"
            )
            suggestions.append("Review pipeline phases for optimization opportunities")
            passed = False
        
        return {
            "warnings": warnings,
            "suggestions": suggestions,
            "passed": passed
        }
    
    def suggest_coarsening(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """
        Suggest coarsening strategies based on performance metrics.
        
        Returns:
            Dict with 'bin_size_km', 'dt_seconds', and 'reason' keys
        """
        suggestions = {
            "bin_size_km": 0.1,  # Default
            "dt_seconds": 60,    # Default
            "reason": "No coarsening needed"
        }
        
        # Check if coarsening is needed
        if metrics.feature_count and metrics.feature_count > BIN_MAX_FEATURES:
            # Aggressive coarsening for high feature counts
            suggestions["bin_size_km"] = 0.2
            suggestions["dt_seconds"] = 120
            suggestions["reason"] = f"Feature count ({metrics.feature_count:,}) exceeds threshold ({BIN_MAX_FEATURES:,})"
        
        if metrics.elapsed_seconds and metrics.elapsed_seconds > MAX_BIN_GENERATION_TIME_SECONDS:
            # Time-based coarsening
            if metrics.elapsed_seconds > BIN_HARD_LIMIT_SECONDS:
                suggestions["bin_size_km"] = 0.2
                suggestions["dt_seconds"] = 120
                suggestions["reason"] = f"Generation time ({metrics.elapsed_seconds:.1f}s) exceeds hard limit"
            else:
                suggestions["bin_size_km"] = 0.15
                suggestions["dt_seconds"] = 90
                suggestions["reason"] = f"Generation time ({metrics.elapsed_seconds:.1f}s) exceeds threshold"
        
        return suggestions
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all performance metrics."""
        total_elapsed = self.get_total_elapsed()
        
        phase_summaries = []
        for m in self.metrics:
            if m.elapsed_seconds:
                phase_summaries.append({
                    "phase": m.phase_name,
                    "elapsed_seconds": round(m.elapsed_seconds, 3),
                    "elapsed_ms": int(m.elapsed_seconds * 1000),
                    "percentage": round((m.elapsed_seconds / total_elapsed) * 100, 1) if total_elapsed > 0 else 0,
                    "feature_count": m.feature_count,
                    "bin_count": m.bin_count
                })
        
        return {
            "run_id": self.run_id,
            "total_elapsed_seconds": round(total_elapsed, 3),
            "total_elapsed_minutes": round(total_elapsed / 60, 2),
            "phases": phase_summaries,
            "total_memory_mb": round(self.total_memory_mb, 2) if self.total_memory_mb else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def log_summary(self):
        """Log performance summary to logger."""
        summary = self.get_summary()
        logger.info("=" * 80)
        logger.info("📊 Performance Summary")
        logger.info("=" * 80)
        logger.info(f"Total runtime: {summary['total_elapsed_minutes']:.2f} minutes ({summary['total_elapsed_seconds']:.2f}s)")
        
        if summary['phases']:
            logger.info("\nPhase Breakdown:")
            for phase in summary['phases']:
                logger.info(
                    f"  {phase['phase']:20s}: {phase['elapsed_seconds']:6.3f}s "
                    f"({phase['percentage']:5.1f}%)"
                )
        
        if summary['total_memory_mb']:
            logger.info(f"\nPeak memory usage: {summary['total_memory_mb']:.2f} MB")
        
        logger.info("=" * 80)


def monitor_performance(phase_name: Optional[str] = None):
    """
    Decorator for monitoring function performance.
    
    Usage:
        @monitor_performance("density_analysis")
        def analyze_density(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = phase_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                elapsed = time.monotonic() - start
                logger.debug(f"⏱️  {name}: {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error(f"⏱️  {name}: {elapsed:.3f}s (FAILED: {e})")
                raise
        
        return wrapper
    return decorator


def get_memory_usage_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    except ImportError:
        # psutil not available, return None
        return 0.0
    except Exception:
        # Error getting memory, return None
        return 0.0

