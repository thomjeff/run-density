# Minimal Telemetry for Algorithm Consistency
# Provides grep-able decision logs for quick parity verification

from typing import Tuple

def pub_decision_log(segment_key: str, chosen_path: str,
                     norm_conflict_m: float, norm_overlap_s: float,
                     strict: Tuple[int, int], raw: Tuple[int, int]) -> str:
    """
    Generate a single-line decision log for algorithm consistency verification.
    
    Args:
        segment_key: Segment identifier
        chosen_path: "BINNED" or "ORIGINAL"
        norm_conflict_m: Normalized conflict length in meters
        norm_overlap_s: Normalized overlap duration in seconds
        strict: (strict_a, strict_b) counts
        raw: (raw_a, raw_b) counts
    
    Returns:
        Single-line log string for grep-able comparison
    """
    return (f"PUB_DECISION seg={segment_key} path={chosen_path} "
            f"cm={norm_conflict_m:.3f} od={norm_overlap_s:.3f} "
            f"strict={strict[0]}/{strict[1]} raw={raw[0]}/{raw[1]}")
