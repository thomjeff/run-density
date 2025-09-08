# Unified Function Selector for Algorithm Consistency
# Ensures both Main Analysis and Flow Runner use identical path selection logic

from .normalization import NormalizedInputs
from .config_algo_consistency import FLAGS

def choose_path(segment_key: str, norm: NormalizedInputs) -> str:
    """
    Choose calculation path (BINNED vs ORIGINAL) using unified logic.
    
    Args:
        segment_key: Segment identifier (e.g., "M1:Half_vs_10K")
        norm: Normalized inputs with consistent units
    
    Returns:
        "BINNED" or "ORIGINAL" - the calculation path to use
    """
    if segment_key in FLAGS.FORCE_BIN_PATH_FOR_SEGMENTS:
        return "BINNED"
    
    # Canonical spatial rule – pick exactly one style for both systems
    # Using >= 100.0 to match Main Analysis behavior on M1
    return "BINNED" if norm.conflict_len_m >= 100.0 else "ORIGINAL"
