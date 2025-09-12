# Technical Implementation Notes

## 1) Option A — runtime overrides (CLI/env)
See `samples/patches/option_a_parser.py` for a drop-in parser. Precedence: CLI → env → none (baseline). Never persist. Clamp values and apply only to listed segments (default A1).

## 2) Flow rate computation
- Place a **count line** at the entrance of a segment where flow is enabled (A1, merges, funnels, bridges, finish).  
- Use existing arrival bins; no second pass needed.
```python
def compute_flow_rate(runners_crossing: int, width_m: float, bin_seconds: int) -> float:
    minutes = max(bin_seconds / 60.0, 1e-9)
    return runners_crossing / (width_m * minutes)   # runners/min/m
```
- Track **peak flow** as a moving max over 2–3 bins to avoid spikes (optional).

## 3) Schema binding
Bind a segment to a schema via rulebook inference:
- `start_corral` if `segment_type == "start"` or `segment_id == "A1"` override exists.
- `on_course_narrow` for types: `funnel`, `merge`, `bridge`, `finish` (flow enabled).
- `on_course_open` otherwise (density only).

## 4) Dual triggers
Evaluate triggers against the active schema. See `samples/patches/density_template_engine_patch.py` for outline:
- `density_gte: "E"` means compare against schema.los_thresholds["E"].min
- `flow_gte: "critical"` means compare against schema.flow_ref.critical
- Apply debounce/cooldown using per-segment state.

## 5) Rendering
Add lines in the per-segment block:
```
Peak Density: X.XX runners/m² [LOS Y]
Peak Flow:    ZZ runners/min/m   (only if flow is enabled)
Peak Window:  HH:MM–HH:MM
Mitigations:  • action 1
              • action 2
```
Ensure units are correct and bold labels match current style guidelines.

## 6) Tests
- Unit: LOS mapping, flow math, triggers.  
- E2E: baseline vs scenario (CLI flags).  
- Lint YAML: guarantee required keys exist and numeric ranges are sane.
