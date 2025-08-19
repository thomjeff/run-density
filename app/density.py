# Stub: replace with your production implementation.
# Expected entry point:
# def run_density(pace_csv: str, start_times: dict, segments: list, step_km: float, time_window_s: float) -> dict:

from typing import Dict, Any, List

def run_density(pace_csv: str, start_times: Dict[str, float], segments: List[dict], step_km: float, time_window_s: float) -> dict:
    # Minimal echo to prove wiring; replace with your real logic
    return {
        "ok": True,
        "engine": "density",
        "params": {
            "pace_csv": pace_csv,
            "start_times": start_times,
            "segments": segments,
            "step_km": step_km,
            "time_window_s": time_window_s,
        },
        "note": "Replace app/density.py with your implementation.",
    }
