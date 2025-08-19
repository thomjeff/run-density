# Stub: replace with your production implementation.
# Expected entry point:
# def analyze_overlaps(pace_csv: str, overlaps_csv: str, start_times: dict, step_km: float, time_window_s: float,
#                      eventA: str, eventB: str, from_km: float, to_km: float) -> dict:

from typing import Dict, Any, Optional

def analyze_overlaps(
    pace_csv: str,
    overlaps_csv: Optional[str],
    start_times: Dict[str, float],
    step_km: float,
    time_window_s: float,
    eventA: str,
    eventB: Optional[str],
    from_km: float,
    to_km: float,
) -> dict:
    # Minimal echo to prove wiring; replace with your real logic
    return {
        "ok": True,
        "engine": "overlap",
        "params": {
            "pace_csv": pace_csv,
            "overlaps_csv": overlaps_csv,
            "start_times": start_times,
            "step_km": step_km,
            "time_window_s": time_window_s,
            "eventA": eventA,
            "eventB": eventB,
            "from_km": from_km,
            "to_km": to_km,
        },
        "note": "Replace app/overlap.py with your implementation.",
    }
