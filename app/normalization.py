# Input Normalization for Algorithm Consistency
# Handles unit conversion and edge-case snapping to prevent threshold drift

from typing import NamedTuple

EPS_M = 0.001          # meters tolerance (~1 mm)
EPS_S = 1e-6           # seconds tolerance
M_TO_M: float = 1.0    # placeholder if any inputs arrive in km (then use 1000.0)
S_TO_S: float = 1.0    # placeholder if any inputs arrive in ms (then use 0.001)

class NormalizedInputs(NamedTuple):
    conflict_len_m: float
    overlap_dur_s: float

def normalize(conflict_len_value: float, conflict_len_unit: str,
              overlap_dur_value: float, overlap_dur_unit: str) -> NormalizedInputs:
    """
    Normalize inputs to consistent units and snap to critical edges.
    
    Args:
        conflict_len_value: Conflict length value
        conflict_len_unit: Unit ("m" or "km")
        overlap_dur_value: Overlap duration value  
        overlap_dur_unit: Unit ("s" or "ms")
    
    Returns:
        NormalizedInputs with consistent units and edge-snapped values
    """
    # Units: (m|km), (s|ms)
    m = conflict_len_value * (1000.0 if conflict_len_unit == "km" else 1.0)
    s = overlap_dur_value * (0.001 if overlap_dur_unit == "ms" else 1.0)
    
    # Snap tiny floating noise around the edge to the edge
    def snap(val: float, edge: float, eps: float) -> float:
        return edge if abs(val - edge) <= eps else val
    
    m = snap(m, 100.0, EPS_M)     # 100 m edge – **critical**
    s = snap(s, 600.0, EPS_S)     # 10 min edge (600 s) – if used
    
    return NormalizedInputs(m, s)
