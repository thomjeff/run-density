# Outline: flow computation, LOS mapping, and dual triggers with debounce/cooldown

from dataclasses import dataclass

@dataclass
class Schema:
    los_thresholds: dict
    flow_ref: dict | None
    debounce_bins: int
    cooldown_bins: int

def compute_flow_rate(runners_crossing: int, width_m: float, bin_seconds: int) -> float:
    minutes = max(bin_seconds / 60.0, 1e-9)
    return runners_crossing / (width_m * minutes)  # runners/min/m

def map_los(density: float, los_thresholds: dict) -> str:
    for letter in ["A","B","C","D","E","F"]:
        rng = los_thresholds.get(letter, {})
        mn = rng.get("min", float("-inf"))
        mx = rng.get("max", float("inf"))
        if density >= mn and density < mx:
            return letter
    return "F"

def threshold_from_schema(schema: Schema, kind: str, key: str) -> float:
    if kind == "density":
        rng = schema.los_thresholds[key]
        return float(rng.get("min", 0.0))
    elif kind == "flow":
        return float(schema.flow_ref[key])
    raise KeyError(kind)

def should_fire(trigger: dict, metrics: dict, schema: Schema) -> bool:
    if "density_gte" in trigger:
        bound = threshold_from_schema(schema, "density", trigger["density_gte"])
        if metrics.get("density", 0.0) >= bound:
            return True
    if "flow_gte" in trigger and schema.flow_ref:
        bound = threshold_from_schema(schema, "flow", trigger["flow_gte"])
        if metrics.get("flow") is not None and metrics["flow"] >= bound:
            return True
    return False

class DebounceState:
    def __init__(self):
        self.hot_bins = 0
        self.cool_bins = 0
        self.active = False

    def update(self, fired: bool, debounce_bins: int, cooldown_bins: int):
        if not self.active:
            self.hot_bins = self.hot_bins + 1 if fired else 0
            if self.hot_bins >= debounce_bins and fired:
                self.active = True
                self.cool_bins = 0
        else:
            self.cool_bins = self.cool_bins + 1 if not fired else 0
            if self.cool_bins >= cooldown_bins and not fired:
                self.active = False
                self.hot_bins = 0
        return self.active
