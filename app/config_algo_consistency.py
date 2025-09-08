# Algorithm Consistency Configuration
# Additive-only flags to control algorithm unification without touching existing code

from dataclasses import dataclass

@dataclass(frozen=True)
class AlgoConsistencyFlags:
    ENABLE_STRICT_FIRST_PUBLISH: bool = True
    ENABLE_BIN_SELECTOR_UNIFICATION: bool = True
    ENABLE_INPUT_NORMALIZATION: bool = True
    ENABLE_TELEMETRY_MIN: bool = True
    FORCE_BIN_PATH_FOR_SEGMENTS: tuple[str, ...] = ()  # e.g., ("M1:Half_vs_10K",)

FLAGS = AlgoConsistencyFlags()
