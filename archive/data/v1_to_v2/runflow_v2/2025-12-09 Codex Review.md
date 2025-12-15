# Run-Density v2 Architecture Assessment

## 1. v1 Limitations Blocking Multi-Day, Multi-Event Support
- **Single global timeline anchored to earliest start**: Location report computes `loc_start` from the minimum start time across all events, which forces every scenario to share one timeline and enables cross-day interactions.【F:app/location_report.py†L520-L523】
- **Event lists hardcoded to Sunday trio**: Binning logic only inspects `['full', 'half', '10K']`, preventing Saturday-only event selection and forcing 5K runs to inherit Sunday segment spans.【F:app/bin_analysis.py†L152-L201】
- **Density configuration bound to Full/Half/10K**: Event interval lookups and warnings are hardcoded to the three Sunday events, so new event names cannot resolve distances or schemas.【F:app/core/density/compute.py†L31-L60】
- **Temporal flow tied to Sunday event pairs**: Flow analysis documentation and conversion logic assume event columns `eventa/eventb` come from the fixed Sunday set, with start-time expectations that collapse all events into one start-time map.【F:app/core/flow/flow.py†L2540-L2579】
- **Static day mapping without architecture**: Constants define Saturday/Sunday event groupings but no structures consume `day`, so cross-day disabling is impossible and timelines are implicitly global.【F:app/utils/constants.py†L80-L98】

## 2. Components Requiring Rewrite vs. Salvage

### Must Be Rewritten or Heavily Refactored
- **Timeline & bin generation**: Replace global min-start timeline and fixed event list binning with day-scoped timelines and event-aware segment spans.【F:app/location_report.py†L520-L523】【F:app/bin_analysis.py†L152-L201】
- **Density pipeline**: Generalize event interval resolution and segment filtering to accept arbitrary `Event` objects with `day` and `start_time` rather than fixed Sunday names.【F:app/core/density/compute.py†L31-L60】
- **Temporal flow analysis**: Rebuild pair generation and segment conversions to operate per-day, restricting interactions to events sharing a day and deriving distances from event-specific metadata, not fixed columns.【F:app/core/flow/flow.py†L2540-L2579】
- **Configuration & constants**: Replace static event/day dictionaries with configuration-driven event discovery and remove assumptions embedded in defaults (start times, event sets).【F:app/utils/constants.py†L80-L98】
- **Artifact/report generators** (`density_report.py`, `flow_report.py`, `map_data_generator.py`): audit for embedded event lists/timeline assumptions and move to day-scoped inputs (not explicitly cited, but required for consistency with new models).

### Can Be Salvaged with Isolation
- **Mathematical helpers**: Density/flow calculations, LOS classification, and bin data structures remain valid if fed day-scoped data (e.g., `BinData`, density metrics, LOS thresholds).【F:app/bin_analysis.py†L152-L201】【F:app/core/density/compute.py†L63-L115】
- **GPX processing and slicing**: Distance interpolation and cumulative distance helpers are event-agnostic and can be reused to build per-event segment geometry once events carry their own GPX references.【F:app/core/gpx/processor.py†L1-L89】
- **Output formats**: CSV/GeoJSON/Markdown artifacts can persist with updated schema tags indicating day and event scope.

## 3. Architectural Constraints Preventing Multi-Day Support
- **Earliest-start anchoring** enforces one timeline for all events, so Saturday/Sunday coexist in the same bins and location windows.【F:app/location_report.py†L520-L523】
- **Fixed segment span aggregation** across `['full','half','10K']` builds bins that include segments irrelevant to requested events (e.g., 5K-only runs still iterate over 28 segments).【F:app/bin_analysis.py†L152-L201】
- **Event-name whitelisting** in density interval resolution prevents new events from being analyzed or even warned correctly, blocking configuration-driven event sets.【F:app/core/density/compute.py†L31-L60】
- **Flow analysis assumes uniform day** because start times are a flat dict and every loaded segment is processed without day filtering, enabling cross-day interactions by default.【F:app/core/flow/flow.py†L2540-L2579】
- **Static event/day constants unused**: presence of `EVENT_DAYS`, `SATURDAY_EVENTS`, `SUNDAY_EVENTS` without enforcement illustrates missing event encapsulation and day-scoped pipelines.【F:app/utils/constants.py†L80-L98】

## 4. Proposed v2 Architecture Outline

### Event & Segment Models
```python
@dataclass
class Segment:
    id: str
    name: str
    distance_start: float
    distance_end: float
    gpx_polyline: List[LatLng]
    used_by_events: List[str]   # references only (no per-event copies)


@dataclass
class Event:
    name: str
    day: str               # e.g., 'Saturday', 'Sunday'
    start_time: int        # minutes after midnight
    gpx_file: str
    segment_ids: List[str] # references to globally defined segments
    runners: List[Runner]
```

### Day Timelines
- Build **one bin timeline per day** by grouping events with the same `day` and generating bins from that day’s earliest start. Co-presence/overtake is permitted within a day only; cross-day interaction is structurally impossible.

### Event-Scoped Pipelines
- **Segment filtering without duplication**: Segments remain globally defined. Each event references shared segment IDs; per-day pipelines union only the segments used by events on that day but keep single segment definitions so co-located events accumulate in the same segment bins.
- **Density across shared segments**: Compute density per segment per bin by aggregating runners from all same-day events that occupy that segment/time window; offer per-event filtered views at the reporting layer without changing the shared-segment math.
- **Flow constrained to day and shared segments**: Generate event pairs only for events sharing a `day`, and only within segments common to those events. Use event-specific GPX alignment for timing/distances but preserve shared-segment identities.
- **Artifacts**: Report generators accept `List[DayAnalysis]` where each encapsulates bins, densities, flows, and visuals for that day.

### Configuration-Driven Wiring
- Discover events from input config/CSV (runners/segments metadata) and construct `Event` objects dynamically (no hardcoded lists or start times). Schema/rulebook selection keyed by event metadata.

## 5. Migration & Branching Strategy
- **Tag current state** as `v1.0.0`; create `v1-maintenance` for Sunday-only hotfixes.
- **Create `v2-dev`** branch for multi-day architecture.
- **Incremental extraction**: start by introducing the `Event` model and day grouping utilities, then refactor bin/timeline generation to consume them. Maintain adapters so v1 entry points can call v2 components with Sunday defaults.

## 6. Lowest-Risk Path to a v2 Prototype
1. **Model layer first**: Implement `Event` dataclass, day grouping, and loader that constructs events from config/CSV (stub if necessary).
2. **Timeline/bin rewrite**: Replace earliest-start logic with per-day timelines and event-aware bin spans; keep existing bin math.
3. **Density refactor**: Adapt density compute to accept per-day event lists and segment metadata, reusing LOS/density math.
4. **Flow refactor**: Limit pair generation to same-day events and use event-specific distance ranges; stub deep-dive narrative if needed.
5. **Artifact pass**: Update reports to iterate days; mark schemas with day identifiers; backfill adapters for v1 callers.
6. **Testing**: Add unit/E2E cases for Saturday-only, Sunday-only, and mixed-day inputs to confirm isolation (no cross-day bins or flows) and correct interactions within a day.

## 7. Major Risks / Blockers
- **Pervasive assumptions** across reports and validators may hide additional hardcoded event names; broad test coverage is required.
- **Data contract changes** (segments/runners CSV) needed to attach `day` and per-event distance ranges; must be coordinated with GPX loader.
- **Backwards compatibility**: v1 callers expect default start times and global outputs; adapters must preserve legacy behavior while enabling v2.

## 8. Decisions, Inputs, and Open Questions (Answered)
- **Event source of truth**: Events (name, day, start_time) arrive via the v2 API payload, not a separate `events.csv`; documentation in `docs/api_v2.md` should be treated as canonical.【F:docs/api_v2.md†L1-L120】
- **Segment spans**: `segments.csv` remains the canonical source and already contains per-event span columns such as `5k_from_km` and `5k_to_km`; no separate mapping file is required.【F:data/segments.csv†L1-L40】
- **Runner offsets**: Runner CSVs already include `start_offset`; no additional wave/corral fields are required immediately.【F:data/open_runners.csv†L1-L40】
- **Cross-day validation**: Cross-day interactions are forbidden in computation layers (binning/flow) and should be enforced there; the API contract does not permit cross-day flow/density even if payloads are malformed.
- **Artifact paths**: Outputs remain grouped under `run_id/` with per-day subfolders (e.g., `run_id/Saturday/Flow.md`, `run_id/Sunday/Density.md`) as proposed in `docs/output_v2.md` to keep day-scoped assets distinct.【F:docs/output_v2.md†L1-L80】
- **UI behavior**: Dashboards use day selection to drive timelines; aggregated cross-day views are **not** required for v2.
- **Performance target**: End-to-end multi-day runs should complete in under 5 minutes on the current Docker defaults (3 CPU / 4GB RAM); treat as a design target, not a hard cap.
- **Naming normalization**: Enforce lowercase event codes and `seg`/`loc` prefixes through schema validation and linting; legacy aliases can be dropped in v2, with `docs/field_names.csv` as the reference.【F:docs/field_names.csv†L1-L80】

## 9. Data Contracts & Schemas (to add to dev guide)
- **Events (API payload)**: `{name, code, day, start_time, gpx_file, segment_ids, runners_ref}` with lowercase `code`; validated on ingest.
- **Segments (`segments.csv`)**: Global definitions with per-event span columns (e.g., `full_from_km`, `full_to_km`, `5k_from_km`, `5k_to_km`), plus geometry references; validated for missing spans per requested events.【F:data/segments.csv†L1-L40】
- **Runners (`*_runners.csv`)**: Must include `event_code`, `start_offset`, and course positions keyed to the event’s GPX; offsets remain required fields.【F:data/open_runners.csv†L1-L40】
- **Rulebook/schema enforcement**: Apply linting for naming, required fields, and forbidden cross-day pairings during CI to catch misconfigured payloads early.

## 10. Migration Plan from v1
- **Branching**: Keep `main` for v1; tag `v1.0.0` (current) and maintain hotfixes on `v1-maintenance` (e.g., `v1.8.1`). Develop v2 on long-lived `nextgen`/`v2-dev` as confirmed.
- **Adapters**: Provide shim entry points so v1 endpoints can call v2 components with Sunday-only defaults while v2 stabilizes; remove shims once v2 replaces v1.
- **No backward compatibility promise**: v2 endpoints and schemas can diverge; document deprecation timelines for v1 tests/endpoints.

## 11. API Surface Changes (v2 expectations)
- **Requests**: Explicit `day` and `events[]` arrays in payloads; event objects carry `start_time`, `segment_ids`, and runner references.
- **Responses**: Day-scoped outputs with event tags; flow/density results include `day`, `event_code`, `segment_id`, and bin metadata.
- **Validation posture**: Reject payloads that omit `day`, reference unknown segments, or violate naming rules; computation layer additionally blocks cross-day interactions.

## 12. Timeline & Binning Specification
- **Bin width**: 30 seconds; **bin length**: 0.2 km, per `app/utils/constants.py` defaults.【F:app/utils/constants.py†L30-L45】
- **Day start (`t0`)**: Earliest `start_time` among events on the same day; bins extend until the latest runner end for that day only.
- **Runner arrival mapping**: `absolute_time = day_start + event.start_time + runner.start_offset + segment_time_offset`; map to nearest 30s bin; discard/flag records mapped outside day boundaries.
- **Cross-day guard**: Bin generation never mixes events from different days; flows/densities are computed within day partitions only.

## 13. Segment Span Sourcing
- Use the per-event columns in `segments.csv` as the canonical span definitions; validation ensures every requested event has both `_from_km` and `_to_km` populated for all referenced segments.【F:data/segments.csv†L1-L40】
- Avoid secondary YAML/JSON span maps to prevent divergence; derive in-memory lookup tables from the CSV at load time.

## 14. Artifact Strategy
- **Directory layout**: `output/{run_id}/{day}/Density.md`, `Flow.md`, `Locations.csv`, `map.geojson`, etc., keeping day-scoped bundles isolated.【F:docs/output_v2.md†L1-L80】
- **Metadata**: Include `day` and `event_code` in tables and filenames; per-event filtered views live alongside aggregated same-day views.

## 15. Testing Strategy
- **Unit cases**: Saturday-only (Elite/Open), Sunday-only (Full/Half/10K), mixed-day to assert no cross-day bins/flows, and “new event” to prove config-driven discovery.
- **Golden files**: Per-day outputs for density/flow/location to catch regressions; include performance assertions for bin counts and runtime envelopes.
- **Integration/E2E**: Validate GPX slicing, segment span mapping from `segments.csv`, and API payload ingestion across days.

## 16. Performance & SLOs
- Target <5 minutes end-to-end on 3 CPU / 4GB RAM Docker baseline; flag workloads exceeding bin/feature thresholds and offer coarsening strategies (bin widening) if exceeded.

## 17. UI/UX Requirements
- Day and event selectors drive timeline rendering; dashboards default to day-scoped views with optional per-event filters.
- No cross-day aggregation views required for v2; ensure component state resets when switching days to avoid stale bins.

## 18. Validation & Linting
- Enforce lowercase event codes, `seg_`/`loc_` prefixes, required fields, and known-day values via schema validation.
- CI checks reject configs that introduce cross-day interactions or missing per-event spans; lint runner/segment files against `docs/field_names.csv` glossary.【F:docs/field_names.csv†L1-L80】

## 19. Ops / Runbook Notes
- Document local and containerized run commands, required env vars, and common failures (e.g., missing span columns) with remediation steps.
- Call out `segments.csv`/runner file expectations and where day-scoped outputs land; update once v2 CLI/API entry points are finalized.