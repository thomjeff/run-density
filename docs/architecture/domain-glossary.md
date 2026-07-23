# Domain glossary (Issue #798 Phase 3 stub)

**Status:** stub published in Phase 0 so agents have a single vocabulary target.  
**Phase 3** expands field maps (API / CSV / internal / frontend) and enforcement.

## Product vs repository

| Name | Use |
|------|-----|
| **Runflow** | Product / UX / runtime paths (`runflow/`, `/runflow/v2`) |
| **run-density** | GitHub repository name (historical). Do not introduce new runtime identifiers with this name. |

## Core nouns

| Term | Meaning |
|------|---------|
| **Course** | Named frozen distance snapshot (e.g. 10K University) composed from legs |
| **Leg** | Reusable route unit in the org (or package) library; may appear in multiple courses/recipes |
| **Segment** | Analysis interval along a course after export/build (often `seg_id` in artifacts) |
| **Zone** | Operational classification on a location after package build |
| **Location** | Point of interest on a leg/course (`loc_id` crew-facing; stable `location_key` internal) |
| **Configuration package** | Race package: assigned courses, runners, resources, analysis launch |
| **Run** | One analysis execution under `runflow/analysis/{run_id}/` |

## Units (prefer explicit suffixes in internal code)

| Prefer | Avoid as ambiguous |
|--------|--------------------|
| `window_seconds` | bare `window_s` at core boundaries (adapters may alias) |
| `event_duration_minutes` | bare `event_duration` when unit unclear |
| `step_km` / `bin_km` | mix without documenting which is spatial resolution |
| `start_time` | Minutes after midnight; **canonical range 300–1200** (05:00–20:00). SSOT: `app.core.v2.start_time` |

## ID pairs (not always synonyms)

- **leg_id** — library route identity  
- **seg_id** / **segment_id** — analysis segment identity (may derive from legs after build)  
- **loc_id** vs **location_id** — prefer `loc_id` in crew-facing CSV; document aliases at adapters  

Full alias tables land in Phase 3.
