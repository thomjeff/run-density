# Domain glossary (Issue #798 Phase 3)

**Status:** canonical vocabulary for agents and humans.  
**Product rule:** prefer these names in new code; keep legacy wire names only at adapters.

## Product vs repository

| Name | Use |
|------|-----|
| **Runflow** | Product / UX / runtime paths (`runflow/`, `/runflow/v2`), env `RUNFLOW_*`, UI events (`runflow:*`) |
| **run-density** | GitHub repository name (historical). **Do not introduce new runtime identifiers with this name.** Existing Docker / Cloud Run / older GCS labels may still say `run-density` — treat as debt, rename opportunistically. |

## Core nouns

| Term | Meaning |
|------|---------|
| **Course** | Named frozen distance snapshot (e.g. 10K University) composed from legs |
| **Leg** | Reusable route unit in the org (or package) library; may appear in multiple courses/recipes |
| **Segment** | Analysis interval along a course after export/build (artifact key: `seg_id`) |
| **Zone** | Operational classification on a location after package build |
| **Location** | Point of interest on a leg/course (`loc_id` crew-facing; stable `location_key` for authoring) |
| **Configuration package** | Race package: assigned courses, runners, resources, analysis launch (`runflow/config/{config_id}/`) |
| **Run** | One analysis execution under `runflow/analysis/{run_id}/` |

## Units (prefer explicit suffixes in internal code)

| Prefer | Avoid as ambiguous |
|--------|--------------------|
| `window_seconds` / `dt_seconds` (core) | bare `window_s` at **new** core APIs (adapters may still emit `window_s` / `effective_window_s`) |
| `event_duration_minutes` | bare `event_duration` on API / analysis.json |
| `step_km` (config) | inventing a third spatial name; `bin_km` / `bin_size_km` are boundary aliases of step |
| `start_time` | Minutes after midnight; **canonical range 300–1200** (05:00–20:00). SSOT: `app.core.v2.start_time` |

## ID pairs (not synonyms)

| Identity | Meaning | Do not confuse with |
|----------|---------|---------------------|
| `leg_id` | Library route identity (legacy read: `chunk_id`) | `seg_id` — one leg can produce many analysis segments |
| `seg_id` | Analysis segment identity in CSV / flow / audit | `segment_id` — bins/UI adapter alias of `seg_id` |
| `loc_id` | Crew-facing numeric location id (CSV); package JSON often stores the same value as `id` | `location_key` — short authoring key, not crew CSV identity |
| `location_key` | Stable 5-char authoring key (`leg_loc_key` on leg-scoped rows) | `loc_id` |

## Field alias map

| Term (canonical internal) | Wire / CSV / API aliases | Frontend aliases | Adapter strategy | Example paths |
|---------------------------|--------------------------|------------------|------------------|---------------|
| `seg_id` | CSV/artifacts: `seg_id`. Bins / some JSON: `segment_id` | `seg_id`; local JS `segId` | Dual-read or rename **only** in bins/UI adapters. New CSV/exports stay `seg_id`. Do not invent new writers of `segment_id` as SSOT. | `app/core/artifacts/frontend.py`; `app/routes/api_density.py`; `app/core/v2/bins.py` |
| `leg_id` | Package/org API `{leg_id}`; segment rows may carry `leg_id` | `legId`; `source_leg_id` | Distinct noun. Resolve `leg_id` → current `seg_id` at apply/export. Never rename legs to segments. | `app/core/course/segment_library.py`; `app/core/config_package/legs.py` |
| `loc_id` | CSV: `loc_id`. Package JSON: numeric `id` (same value). Helpers may say `location_id` in function names | Map: `loc_id`; editor may use `id` | Export always `loc_id`. Function names may say `location_id` without changing the wire key. | `app/core/locations/schema.py`; `app/core/config_package/location_ids.py` |
| `location_key` | Authoring key; `leg_loc_key` on leg rows | Grid “Key” | Keep separate from `loc_id`. Match course↔leg by key; crew reports keep numeric `loc_id`. | `app/core/config_package/location_keys.py` |
| Temporal bin width | Core: `dt_seconds`. Metadata: `effective_window_s`, `window_s`, `time_window_s`. Map API may use `window_seconds` for display length | Report MD context `window_s` | Prefer `*_seconds` in new core APIs. Adapters may accept `window_s`. Phase 5 removes fabricated `window_s=30`. | `app/density_report.py`; `app/api/models/report.py`; `app/new_density_report.py` |
| `step_km` | Density config: `step_km`. v1 API: `stepKm`. Results often mirror as `bin_km` / `bin_size_km` | — | Canonical **config** name is `step_km`. Treat `bin_*` as boundary/result aliases until a dedicated rename. | `app/core/density/models.py`; `app/core/density/compute.py` |
| `runflow` | Paths `runflow/…`, API `/runflow/v2`, env `RUNFLOW_*`, GCS bucket `runflow` | `window.runflowDay`, `runflow:context-ready` | Canonical runtime namespace. Do not add new `run-density` runtime IDs. | `app/utils/constants.py`; `app/main.py` |
| `event_duration_minutes` | API + `analysis.json`: `event_duration_minutes`. Internal maps: `event_durations` (minutes) | Analysis forms use full name | Wire stays unit-suffixed. `actual_event_duration` (HH:MM) is a **different** derived metric. | `app/api/models/v2.py`; `app/core/v2/timings.py` |

## Guidance for agents

1. **Read this file before inventing synonyms** for course/leg/segment/location/run/package fields.  
2. **Preserve legacy wire names only at adapters** (bins UI, map payloads, temporary report metadata).  
3. **New core APIs** under `app/core/` should use unit-suffixed names (`*_seconds`, `*_minutes`, `*_km`).  
4. **Product name is Runflow**; repository may stay `run-density`.  
5. **`seg_id` ≠ `leg_id`**, **`location_key` ≠ `loc_id`**, **`actual_event_duration` ≠ `event_duration_minutes`**.  
6. Start-time range is **not** full-day 0–1439 — use `app.core.v2.start_time`.  
7. Cross-check [quick-reference.md](../reference/quick-reference.md) and [canonical-paths.md](canonical-paths.md).

## Light enforcement

- Regression: `tests/unit/test_issue798_phase3_glossary.py` asserts this doc stays present with required sections.  
- FastAPI app title is **Runflow** (not `run-density`).  
- Deeper renames of `bin_km` / Docker `run-density-dev` are deferred (Phases 4–6 / later).
