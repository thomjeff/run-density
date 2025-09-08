# Algorithm Consistency Configuration
# Additive-only flags to control algorithm unification without touching existing code

from dataclasses import dataclass

@dataclass(frozen=True)
class AlgoConsistencyFlags:
    ENABLE_STRICT_FIRST_PUBLISH: bool = True  # Re-enabled with correct strict pass counts
    ENABLE_BIN_SELECTOR_UNIFICATION: bool = True  # Re-enabled with performance fixes
    ENABLE_INPUT_NORMALIZATION: bool = True
    ENABLE_TELEMETRY_MIN: bool = True
    FORCE_BIN_PATH_FOR_SEGMENTS: tuple[str, ...] = ("M1:Half_vs_10K",)  # Parity pin for M1
    SINGLE_SEGMENT_MODE: str = "M1"  # Process only M1 for debugging

FLAGS = AlgoConsistencyFlags()
