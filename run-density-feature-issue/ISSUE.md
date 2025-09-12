# Enhancement: Density + Flow Operational Intelligence (Start-corral schema, Flow metric, Dual triggers, Scenario overrides)

**Labels:** `enhancement` `density-reporting` `rulebook`  
**Component:** `run-density` (Density/Flow engines, report rendering)  
**Owner:** Race Analytics / Ops Intelligence  

## Product Context (PM)

### Why this matters
A running event’s safety and participant experience hinge on how we manage **crowd density** (how tightly packed runners are) and **flow rate** (throughput across a control line). The **start** behaves like a **crowd** (staged, pulsed release), while **on-course** behaves like **throughput on a corridor**. Operational hot-spots (merges, funnels, bridges, tight turns, finish chutes) can be high-risk even when average density looks reasonable.

### What this feature does
This enhancement turns `run-density` from a metrics-only report into **operational intelligence** by adding:
1) **Start-corral LOS schema (A1 only)** — a context-specific interpretation of the same density values that is slightly more tolerant (safer classification for managed starts).  
2) **Flow rate metric** — `runners/min/m`, shown where it matters (A1 + selected narrow/merge segments).  
3) **Dual triggers** — mitigations that fire on **density OR flow** with debounce/cooldown to avoid noise.  
4) **Scenario overrides (optional)** — `wave_size`, `wave_gap`, `gate_width` via CLI/env for “what-if” start-release planning. *(No persistence; baseline unchanged unless explicitly set.)*

### Research basis (not invented here)
- **Start-corrals:** Peer-reviewed work shows that start-corrals with waved releases materially **lower density** (≈0.5–1.2 runners/m²) and **cap throughput** (≈36–59 runners/min/m per meter), improving safety/satisfaction vs unmanaged releases (densities up to ≈1.5–3.0 and flows >100).  
- **On-course:** The widely used **Fruin A–F LOS** scale from pedestrian engineering applies once runners are moving along the course (bridges, streets, trails).  

> In short: **same density unit (runners/m²), different interpretation** at the **start** vs **on-course**.

### What’s included (by “chunk”)
- **Chunk 1 — Start-corral thresholds (A1 only)**  
  Apply a start-specific LOS schema to A1 (e.g., D: 0.95–1.20; E: 1.20–1.60; F: >1.60). On-course retains Fruin-derived thresholds.

- **Chunk 2 — Flow rate metric**  
  Compute and render `Peak Flow (runners/min/m)` at A1 and selective segments (merges/funnels/bridges/finish).

- **Chunk 3 — Dual triggers (density OR flow)**  
  YAML-driven triggers with `density_gte` / `flow_gte`, evaluated against the active schema. Debounce/cooldown to prevent flapping.

- **Chunk 4 — Scenario overrides (Option A)**  
  Optional CLI/env overrides for `wave_size`, `wave_gap`, `gate_width` (A1 by default, or any listed segment). No persistence.

### Acceptance Criteria
- [ ] **Start (A1)** uses **start-corral LOS schema**; other segments use on-course schema.  
- [ ] **Peak Flow** appears in A1 and for flagged narrow/merge segments.  
- [ ] **Mitigations** can trigger on **density OR flow**; triggers honor debounce/cooldown.  
- [ ] Units are correct and consistent: **runners/m²** for density, **runners/min/m** for flow.  
- [ ] With **no CLI/env overrides**, outputs match current baseline.  
- [ ] With overrides set, only targeted segments are recomputed; others remain baseline.  
- [ ] Basic tests pass: LOS mapping sanity, flow computation, trigger evaluation, report rendering.

### Future Enhancements (deferred)
- **Option B — `scenario.yml` file** for repeatable planning runs (keeps rulebook stable).  
- **Option C — UI + API** for scenario preview/save/clear, writing to `scenario.yml` with server-side validation.

---

## Technical Notes (Architect)

### Code changes (high level)
- **`app/density.py`**: Parse **Option A** overrides from CLI/env → in-memory `scenario`.  
- **`app/flow.py` / arrivals**: Add per-segment **count-line flow** calculation (if `flow_enabled`).  
- **`app/density_template_engine.py`**:  
  - Load `Density_Rulebook_v2.yml`.  
  - Bind `segment_type` → **schema** (`start_corral`, `on_course_narrow`, `on_course_open`).  
  - Map density → **LOS**; compute **flow** where enabled.  
  - Evaluate **dual triggers** (`density_gte`, `flow_gte`) using per-schema thresholds with debounce/cooldown.  
- **`app/density_report.py`**: Render `Peak Flow` line when enabled; list fired mitigations under each segment.

### Snippets (conceptual)
- **Option A parser (CLI/env)** → see `samples/patches/option_a_parser.py`.  
- **Flow computation** (reuse arrivals):  
  ```python
  flow = runners_crossing / (width_m * minutes_in_bin)  # runners/min/m
  ```
- **Trigger evaluation** (density OR flow): see `samples/patches/density_template_engine_patch.py`.

### Risks & mitigations
- **Risk:** Threshold confusion.  
  **Mitigation:** Centralize thresholds in YAML; add a note that **`gte` = “greater than or equal to.”**

- **Risk:** Noisy trigger flapping on boundary conditions.  
  **Mitigation:** Use **debounce** (N consecutive bins to fire) and **cooldown** (N clear bins to clear).

- **Risk:** Scenario overrides accidentally persist.  
  **Mitigation:** Option A is **in-memory only**; do not write to disk.

- **Risk:** Width assumptions at start.  
  **Mitigation:** Use **effective width** (subtract emergency lane) when computing both density and flow at A1.

### Testing strategy
- **Unit tests** (`tests/unit`):  
  - `test_los_mapping.py`: 1.01 → D/E under correct schema; enforce runners/m².  
  - `test_flow_rate_calc.py`: verify units & edge bins.  
  - `test_triggers.py`: density-only, flow-only, and both; debounce/cooldown paths.

- **Integration**: Build a small fixture with A1 + F1 and verify rendering includes Peak Flow and fired mitigations.

- **E2E** (`tests/e2e`):  
  - Baseline vs scenario CLI run; assert only A1 differs and report appendix renders scenario deltas.

### References
- Fruin, J. J. *Pedestrian Planning and Design* (1971).  
- Start-corral crowd research (e.g., PMC9500882): controlled corral designs reduce density and cap throughput at release.

---

## Attachments & Samples
See **`/samples`** in this issue bundle for:
- **`Density_Rulebook_v2.yml`** (updated with start-corral schema, dual triggers, debounce/cooldown, `gte` note).  
- **`LOS_Tables.md`** (start-corral vs on-course with “what it means operationally”).  
- **Patches**: Option A parser; flow & triggers outline; report rendering diff.  
- **Schema suggestion**: `segments_schema_diff.md` (optional `flow_rate_required` flag).
