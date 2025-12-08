# 🧭 Runflow v2 Developer Guide

This document defines the architecture, naming standards, core modeling principles, and distance/time logic for the Runflow v2 system.

---


## 📘 Glossary of Key Terms

- **Event**: A single race instance with a unique name, start time, and assigned day (e.g., full, half, 10k, elite and open are event names for 2026).
- **Runner**: A participant in an event. A runner inherits the event start time plus their own start offset.\
- **Offset**: not all runners cross the start line at exactly the start time, and `offset` is the time the runner took to reach the start line from their placement in the corral.
- **Segment (`seg`)**: A contiguous portion of the course (e.g., seg_id=A1) used to measure flow and density. May be shared across events.
- **Location (`loc`)**: A unique fixed point used for timing analysis, density validation, or operational markers.
- **Bin**: A fixed time interval (e.g., 30s) over a fixed distance (e.g., .2km) used to group runner positions for density and flow computation.
- **Density**: The number of runners per meter in a segment during a bin. Used to classify course congestion levels.
- **Flow**: The transfer or co-presence of runners between events within a shared segment and bin window.

## Runflow v2 Metrics Reference


### Density Metrics
The following metrics are computed per time bin within each segment:

| Metric | Description |
|--------|-------------|
| **Density (ρ)** | Areal density in persons per square meter (p/m²). |
| **Rate (q)** | Flow rate in persons per second (p/s). |
| **Rate per meter per minute** | Normalized rate: (rate / width_m) × 60 (p/m/min). |
| **Utilization (%)** | Real-time rate / critical (reference) rate. |
| **LOS (Level of Service)** | Comfort class (A–F) based on density thresholds (p/m²) and defined in `rulebook` |
| **Bin** | Discrete unit defined by: `[seg_id, start_distance–end_distance, t_start–t_end]`. |


### Flow Metrics
These represent temporal-spatial interactions between runners from different events within the same segment and time bin:

| Metric | Description |
|--------|-------------|
| **Overtake Count** | Number of runners from Event A passing runners from Event B in the same segment/time bin. |
| **Co-presence Count** | Count of runners from Events A and B occupying a segment/bin simultaneously. |
| **Flow Intensity** | Ratio of interaction runners to total runners in bin (0–1). |
| **Flow Types** | Currently modeled: `overtake`, `co-presence`; others can be added as scenario types evolve. |

---

## 🏗️ Architecture Overview

# Run-Density v2 Architecture Assessment

## 1. v1 Limitations Blocking Multi-Day, Multi-Event Support
- **Single global timeline anchored to earliest start**: Location report computes `loc_start` from the minimum start time across all events, which forces every scenario to share one timeline and enables cross-day interactions.【F:app/location_report.py†L520-L523】
- **Event lists hardcoded to Sunday trio**: Binning logic only inspects `['full', 'half', '10K']`, preventing Saturday-only event selection and forcing 5K runs to inherit Sunday segment spans.【F:app/bin_analysis.py†L152-L201】
- **Density configuration bound to Full/Half/10K**: Event interval lookups and warnings are hardcoded to the three Sunday events, so new event names cannot resolve distances or schemas.【F:app/core/density/compute.py†L31-L60】
- **Flow tied to Sunday event pairs**: Flow analysis documentation and conversion logic assume event columns `eventa/eventb` come from the fixed Sunday set, with start-time expectations that collapse all events into one start-time map.【F:app/core/flow/flow.py†L2540-L2579】
- **Static day mapping without architecture**: Constants define Saturday/Sunday event groupings but no structures consume `day`, so cross-day disabling is impossible and timelines are implicitly global.【F:app/utils/constants.py†L80-L98】

## 2. Components Requiring Rewrite vs. Salvage

### Must Be Rewritten or Heavily Refactored
- **Timeline & bin generation**: Replace global min-start timeline and fixed event list binning with day-scoped timelines and event-aware segment spans.【F:app/location_report.py†L520-L523】【F:app/bin_analysis.py†L152-L201】
- **Density analysis**: Generalize event interval resolution and segment filtering to accept arbitrary `Event` objects with `day` and `start_time` rather than fixed Sunday names.【F:app/core/density/compute.py†L31-L60】
- **Flow analysis**: Rebuild pair generation and segment conversions to operate per-day, restricting interactions to events sharing a day and deriving distances from event-specific metadata, not fixed columns.【F:app/core/flow/flow.py†L2540-L2579】
- **Configuration & constants**: Replace static event/day dictionaries with configuration-driven event discovery and remove assumptions embedded in defaults (start times, event sets).【F:app/utils/constants.py†L80-L98】
- **Artifact/report generators** (`density_report.py`, `flow_report.py`, `map_data_generator.py`): audit for embedded event lists/timeline assumptions and move to day-scoped inputs (not explicitly cited, but required for consistency with new models).

### Can Be Salvaged with Isolation
- **Mathematical helpers**: Density/flow calculations, LOS classification, and bin data structures remain valid if fed day-scoped data (e.g., `BinData`, density metrics, LOS thresholds).【F:app/bin_analysis.py†L152-L201】【F:app/core/density/compute.py†L63-L115】
- **GPX processing and slicing**: Distance interpolation and cumulative distance helpers are event-agnostic and can be reused to build per-event segment geometry once events carry their own GPX references.【F:app/core/gpx/processor.py†L1-L89】
- **Output formats**: CSV/GeoJSON/Markdown artifacts can persist with updated schema tags indicating day and event scope.

## 3. Architectural Constraints Preventing Multi-Day Support
- **Earliest-start anchoring** enforces one timeline for all events, so Saturday/Sunday coexist in the same bins and location windows.【F:app/location_report.py†L520-L523】
- **Fixed segment span aggregation** across `['full','half','10k']` builds bins that include segments irrelevant to requested events (e.g., 5K-only runs still iterate over 28 segments).【F:app/bin_analysis.py†L152-L201】
- **Event-name whitelisting** in density interval resolution prevents new events from being analyzed or even warned correctly, blocking configuration-driven event sets.【F:app/core/density/compute.py†L31-L60】
- **Flow analysis assumes uniform day** because start times are a flat dict and every loaded segment is processed without day filtering, enabling cross-day interactions by default.【F:app/core/flow/flow.py†L2540-L2579】
- **Static event/day constants unused**: presence of `EVENT_DAYS`, `SATURDAY_EVENTS`, `SUNDAY_EVENTS` without enforcement illustrates missing event encapsulation and day-scoped pipelines.【F:app/utils/constants.py†L80-L98】

## 4. Proposed v2 Architecture Outline

### Event & Segment Model
<!-- ADDED: Canonical source for segment usage -->
**Note:** All per-event segment distances and associations are stored directly in `segments.csv`. No auxiliary mapping file is used — this file is the single source of truth for segment definitions and per-event spans.
<!-- END ADDED -->

```python
@dataclass
class Segment:
    id: str                        # e.g., "A3"
    name: str                      # Optional verbose name
    start_distance: float          # in meters
    end_distance: float            # in meters
    gpx_polyline: List[LatLng]     # reused across events
    used_by_event_names: List[str] # still a reference list, e.g., ["Full", "Half", "10K"], no per-event copies
```
- Minor Revisions:
1. Use meters instead of float-based km to align with GPX raw data and segment distance normalization.
2. Be explicit in naming (used_by_event_names) to clarify it’s a string list, not Event objects.

```python
from enum import Enum

class Day(str, Enum):
    FRI = 'fri'
    SAT = 'sat'
    SUN = 'sun'
    MON = 'mon'

@dataclass
class Event:
    name: str                     # e.g., "Half"
    day: Day                     # Enum-backed (but serializes as 'sat', etc.)
    start_time: int              # minutes after midnight
    gpx_file: str                # GPX filepath or object
    seg_ids: List[str]       # references to global Segment IDs
    runners: List[Runner]        # populated dynamically
```
- Minor Revisions:
1. day: Day: replaces ambiguous string with an enum — easier to test, sort, validate
2. Enum values like 'sat': match naming convention plans for files, inputs, flags
3. Clarify seg_ids as references: avoids any confusion about duplication
4. Clarify runners is populated dynamically: reinforces that this is a runtime structure, not a filename list


### Day Timelines
<!-- ADDED: Timeline normalization logic -->
### 🕒 Timeline Normalization with Event Start Times

Timeline bin participation is calculated per-runner using the event's start time and their pace-adjusted arrival at segment distances:

```
arrival_time = event.start_time + (segment_start_distance / runner_speed)
```

This ensures that runners from different events — even if they share segments — are binned into the correct timeline window based on when they actually arrive, preventing density bleed across start offsets.
<!-- END ADDED -->

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
2. **Timeline/bin rewrite**: Replace earliest-start logic with per-day timelines and event-aware bin spans; keep existing bin math. Each runner’s timeline participation is offset by their event’s start_time, and segment presence is calculated using normalized event-relative distances mapped to global time bins. Shared segments across events (e.g., F1) must honor:
- Different distance spans per event (Full enters at 5.2km, Half at 3.8km),
- Different arrival times based on pacing + start offset,
- Different runners reaching bins at overlapping times but different progressions.
Bin math (width, thresholds, LOS, etc.) can be reused, but segment entry/exit window mapping must incorporate start time and normalized distances per event.

3. **Density refactor**: Adapt density compute to accept per-day event lists and segment metadata, reusing LOS/density math.
4. **Flow refactor**: Limit pair generation to same-day events and use event-specific distance ranges; stub deep-dive narrative if needed.
5. **Artifact pass**: Update reports to iterate days; mark schemas with day identifiers.
6. **Testing**: Add unit/E2E cases for Saturday-only, Sunday-only, and mixed-day inputs to confirm isolation (no cross-day bins or flows) and correct interactions within a day.

## 7. Major Risks / Blockers
- **Pervasive assumptions** across reports and validators may hide additional hardcoded event names; broad test coverage is required.
- **Inconsistent Results** while not expected, differences might result when the end-user compares results form v2 to v1. These differences could point to a logic error in v1 that is only uncovered in v2 and the end-user is cautioned on assuming v1 as the source of truth during manual QA.

## 8.Data Contract Principles
To define the authoritative source of truth for key fields (`event`, `day`, `segment`, `runner`) and clarify which entities are independent, derived, or shared in the run-density system.

1. Foundational Principles
- The **`Event`** object is the **single source of truth** for:
  - Event name and code
  - Start time (in minutes after midnight)
  - Assigned `day` (e.g., `"sat"`, `"sun"`)
  - Segments used by the event
  - List of participating runners

- **`Segments` and `Runners` are day-agnostic**.
  - They do not own or store `day` values.
  - Their behavior and timeline alignment depend solely on their linkage to the `Event` object.

2. Entity Ownership Matrix

| Field | Owned by | Notes |
|-------|----------|-------|
| `day` | ✅ `Event` | Canonical source. Use enum or constrained string (`"sat"`, `"sun"`, etc.) |
| `start_time` | ✅ `Event` | In minutes after midnight. Used for bin offsetting |
| `seg_ids` | ✅ `Event` → 🡒 `Segment.id` | Defines which segments are used by this event |
| `runners` | ✅ `Event` → 🡒 `Runner.event` | Runners are grouped under an event; inherit its day |
| `start_distance/end` | ✅ `Segment` | May differ per event — see next section |
| `used_by_events` | ✅ `Segment` | Reference list of event codes; for shared segment mapping only |
| `day` (in `runner.csv`) | ❌ Not permitted | Redundant. Use `runner.event` → `Event.day` |
| `day` (in `segments.csv`) | ❌ Not permitted | Redundant. Use `segment.used_by_events` → `Event.day` resolution |

3. Normalized Distance Behavior (Segment x Event)
Segments shared across events may:
- Appear at **different relative distances** within each event’s GPX.
- Begin/end at different points (e.g., Segment F1 starts at 5.2 km in the Full, 3.9 km in the Half).
- Therefore, **per-event segment spans must be defined externally**, not embedded in `Segment`.

**Proposed normalization source:**
A derived config or CSV such as:

```yaml
segment_distance_spans:
  F1:
    Full: [5200, 5800]
    Half: [3900, 4500]
    10K: null
```

> This decouples the **segment definition** from the **event-specific usage**, allowing flexible reuse and accurate bin windowing.

4. Derived Behavior During Pipeline Execution

| Derivation | Logic |
|------------|-------|
| Runner `day` | `runner.event` → `Event.day` |
| Segment timeline window | `Event.start_time` + (runner pace × `segment_start_distance/end`) |
| Bin participation | Based on segment entry/exit time for each runner, offset by `Event.start_time` |

5. Anti-Patterns (Do Not Do)

| Anti-Pattern | Why It’s Bad |
|--------------|--------------|
| Storing `day` in runner or segment rows | Introduces coupling and breaks mobility (e.g., moving 10K to Saturday requires rewriting multiple files) |
| Duplicating segment rows per event | Violates segment uniqueness; breaks shared flow modeling |
| Hardcoding `event -> day` in constants | Prevents dynamic configuration and limits testability |

6. Best Practices
- Define all `Event` objects in a central config (YAML, JSON, or Python).
- Do not place `day` in runner or segment input files.
- Ensure that pipeline builders (Codex or otherwise) derive all behavior from `Event` relationships — never raw fields.
- Codify all rules like these into a **data schema spec or validation layer**, if possible.


### 📆 Standard Day Codes

All `Event.day` values must use the following short-code vocabulary to ensure consistency and filtering correctness:

```
DAY_SHORT_CODES = ['fri', 'sat', 'sun', 'mon']
```

These must be used uniformly across all configs, CSVs, and pipeline logic.


---

## 🏷️ Naming Conventions (ADR-003)

### Context
In prior versions of Runflow, inconsistent naming across files, functions, and configs caused friction in integration, testing, and data parsing. Terms like `segment_id` vs `seg_id`, and `temporal flow` vs `flow` led to ambiguity. This ADR defines consistent naming rules for all internal and external interfaces in Runflow v2.

### ✅ Internal Naming Conventions (code, configs, data)
| Entity     | Abbreviation | Applies To                         | Examples                    |
|------------|--------------|-------------------------------------|-----------------------------|
| Segment    | `seg`        | Code, data models, CSVs             | `seg_id`, `seg_name`        |
| Location   | `loc`        | Code, data models, CSVs             | `loc_id`, `loc_name`        |
| Event Day  | `day`        | Short codes only                    | `sat`, `sun`, `mon`, `fri`  |
| Constants  | `UPPER_SNAKE`| Fixed vocab lists                   | `DAY_SHORT_CODES`           |
| Functions/Vars | `snake_case` | Python standard                 | `compute_flow_density`      |

**Note:** All event short names should be lowercase: `full`, `half`, `10k`, `5k`, `elite`, `open`.

### 🖥️ Presentation Layer (UI, Docs, Reports)
Use full names for clarity and accessibility:
- `segment` (e.g., “Segment A2: Queen Street”)
- `location` (e.g., “Location ID 12: Lincoln Road”)

### 🗓️ Day Codes
All event `day` fields use standardized short codes:
```python
DAY_SHORT_CODES = ['fri', 'sat', 'sun', 'mon']
```
These must be used consistently in all configs, filters, and groupings.

### 🔁 Terminology Alignment
| Deprecated Term     | Replacement | Notes                                  |
|---------------------|-------------|----------------------------------------|
| `temporal flow`     | `flow`      | Use `flow` consistently throughout v2  |

### 🔄 Segment Usage
`segments.csv` is the canonical source of segment usage and per-event distances. No auxiliary mapping file will be used. Columns should follow the convention:
- `seg_id`
- `used_by_events`: e.g., `full|half|10k`
- `dist_full`, `dist_half`, etc.

## Consequences
- Improves interoperability across modules and data pipelines
- Simplifies onboarding and documentation
- Enables automatic schema validation and prevents drift

## Related Documents
- ADR-002 Naming Normalization (legacy cleanup)
- Runflow Next Generation v2 (architecture)


---

## ⏱️ Distance and Time Handling (ADR-004)

### Context
In previous versions of Runflow, improper handling of distance and time introduced critical bugs, particularly as support expanded to multi-event and multi-day architectures. Issues included:
- Overlapping runners from events with different start times
- Misaligned flow calculations across shared segments
- Incorrect density values due to global (rather than event-relative) distance usage
- Confusion between absolute and relative time

This ADR defines standard practices for representing, storing, and using distance and time throughout the v2 system.

---

### 🧭 Definitions

| Concept               | Definition |
|-----------------------|------------|
| `start_time`    | Absolute start time of the event (in minutes after midnight) |
| `runner_offset`       | Offset from the event start time (e.g., wave/corral delay) |
| `normalized_distance` | Distance covered by a runner, relative to their event's GPX |
| `seg_start_distance` / `seg_end_distance` | Event-relative distance window of a segment |
| `bin_time`            | Absolute time bin index (minute-resolution from day's start) |
| `relative_time`       | Time since a specific runner's start (event + offset) |

---

### ⚙️ Core Principles

1. **Distance must be event-relative.**
   - Segments used by multiple events must define `start`/`end` distances **per event**.
   - Distance interpolation must always follow the event’s GPX track, not a global frame.

2. **Time must be normalized by event.**
   - All runner position calculations must factor `start_time`.
   - Additional `runner_offset` must be applied for wave-based models.

3. **Flow and density calculations must align to shared bin timelines**.
   - Only runners from the same day can share bins and interact.
   - Flow requires both time and distance alignment within shared segments.

---

### 💾 Metadata

**Authoritative event metadata** (event name, start time, day) must be supplied from a single canonical source.

This may be:
- A config structure passed via the API (preferred for dynamic modeling/scenario generation)
- A JSON or YAML config file
- A csv file for slowly changing dimensions, like segments.csv

---

### 📐 Calculation Patterns

**Runner Distance**
```python
# time since runner start
t_elapsed = bin_time - (start_time + runner_offset)

# estimated position
distance = runner_speed * t_elapsed
```

**Flow Eligibility**
- Only compare runners:
  - Within the same day
  - Sharing the same segment at the same bin time
  - With valid GPX alignment for that segment

---

### ✅ Consequences

- Prevents cross-event contamination in flow/density outputs
- Ensures segment geometry is respected per event GPX
- Enables accurate runner modeling with staggered starts
- Supports future expansion to wave/corral-level dynamics
- Keeps modeling logic centralized in code, not split across file sources

