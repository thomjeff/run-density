# Option A parser: CLI/env runtime overrides (no persistence)
import os
import argparse

def parse_scenario_from_cli_env(argv=None):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--scenario.wave_size", type=int)
    p.add_argument("--scenario.wave_gap", type=int)          # seconds
    p.add_argument("--scenario.gate_width", type=float)      # meters
    p.add_argument("--scenario.apply_to", type=str)          # e.g., "A1" or "A1,A2"
    args, _ = p.parse_known_args(argv)

    def env_int(k):  return int(os.getenv(k)) if os.getenv(k) else None
    def env_flt(k):  return float(os.getenv(k)) if os.getenv(k) else None
    def env_str(k):  return os.getenv(k)

    scenario = {
        "wave_size": args.scenario_wave_size or env_int("SCENARIO_WAVE_SIZE"),
        "wave_gap": args.scenario_wave_gap or env_int("SCENARIO_WAVE_GAP"),
        "gate_width": args.scenario_gate_width or env_flt("SCENARIO_GATE_WIDTH"),
        "apply_to": (args.scenario_apply_to or env_str("SCENARIO_APPLY_TO") or "A1").split(",")
    }

    # Disable if none of the numeric overrides are present
    if scenario["wave_size"] is None and scenario["wave_gap"] is None and scenario["gate_width"] is None:
        return None

    # Basic validation/clamping
    if scenario["wave_size"] is not None and scenario["wave_size"] <= 0:
        raise ValueError("scenario.wave_size must be >= 1")
    if scenario["wave_gap"] is not None and scenario["wave_gap"] < 0:
        raise ValueError("scenario.wave_gap must be >= 0 seconds")
    if scenario["gate_width"] is not None and scenario["gate_width"] < 1.0:
        raise ValueError("scenario.gate_width must be >= 1.0 m")

    return scenario
