# Implementation Plan: Configuration SSOT & Hardcoded Path Elimination (Issue #616)

## Goals
1. Eliminate runtime hardcoded paths to data files (segments, flow, locations, runners, GPX).
2. Enforce SSOT by loading analysis.json once per run and reusing resolved paths downstream.
3. Remove fallback logic that silently defaults when required metadata is missing.
4. Parameterize functions that currently re-resolve schema/flow/labels internally.
5. Add end-to-end test coverage to validate failure behavior and alternate config paths.

---

## Phase 0 — Prep & Baseline
- **Confirm entry points** for v2 pipeline (API + CLI) and identify the earliest point to resolve `analysis.json` into a canonical `ConfigLoader`/`AnalysisContext`.
- **Inventory all runtime loaders** that still read files directly (`data/*.csv`, `{event}.gpx`).
- **Define required config contract** for segments/flow/locations/runners/gpx plus required columns (schema, width_m, direction, spans).

Deliverable: a short “config contract” summary (schema/fields) included in code docstrings or module-level constants.

---

## Phase 1 — Centralized Config Loader
### 1.1 Create `ConfigLoader` (or extend `AnalysisContext`)
- Implement a loader in `app/core/v2/analysis_config.py` (or new `app/core/v2/config_loader.py`) that:
  - Reads `analysis.json` once.
  - Resolves `data_files.*` paths (segments/flow/locations/runners/gpx).
  - Normalizes data_dir + filename usage.
  - Exposes cached `segments_df`, `flow_df`, `locations_df`, `runners_df_by_event`, `gpx_paths`.
  - Provides explicit getters: `get_segments_path()`, `get_flow_path()`, etc.

### 1.2 Wire ConfigLoader into pipeline entrypoints
- Update v2 pipeline entrypoints to construct the loader once and pass into downstream modules.
- Ensure API handlers pass `analysis.json` path and receive a `ConfigLoader`/`AnalysisContext` instance.

---

## Phase 2 — Remove Hardcoded Runtime Paths
### 2.1 Replace hardcoded `data/*.csv` usage
Target modules:
- `app/api/map.py`
- `app/location_report.py`
- `app/routes/api_density.py`
- `app/validation/*` (if used in runtime)
- `app/core/v2/*` where defaults still reference `data/*.csv`

Actions:
- Replace path defaults with parameters or loader methods.
- Remove any implicit `Path("data/segments.csv")` usage.

### 2.2 Replace GPX hardcoding
Target modules:
- `app/core/gpx/processor.py`
- `app/core/artifacts/frontend.py`

Actions:
- Change GPX load to use `data_files.gpx` (analysis.json), not `{event}.gpx` scanning.
- Ensure event list is derived from analysis config, not fixed list.

---

## Phase 3 — Enforce SSOT and Remove Silent Fallbacks
### 3.1 Fail-fast on missing required metadata
Target modules:
- `app/schema_resolver.py`
- `app/core/density/compute.py`
- `app/new_flagging.py`
- `app/api/map.py` (schema/width defaults)

Actions:
- Replace default `on_course_open` with raised errors when schema missing.
- Replace width defaults (`3.0`, `5.0`, `10.0`) with explicit validation errors if missing.
- Ensure missing `flow.csv` fails if flow analysis is requested.

### 3.2 Eliminate internal reloading
Target modules:
- `app/density_report.py`
- `app/new_density_report.py`
- `app/core/artifacts/frontend.py`
- `app/core/v2/bins.py`

Actions:
- Require these functions to accept dataframes or a config/context object.
- Remove logic that re-reads segments/flow/locations CSVs from disk inside helper functions.

---

## Phase 4 — Parameterize Schema/Flow/Label Resolution
- Update schema resolution to require a `segments_csv_path` or preloaded `segments_df`.
- Replace `resolve_schema()` calls that omit `segments_csv_path` (e.g., `app/routes/api_density.py`).
- Ensure all label/length/width enrichment uses cached `segments_df` rather than re-reading.

---

## Phase 5 — Testing Strategy
### 5.1 Unit tests
- Add tests to ensure failure when:
  - `segments_csv_path` missing in schema resolution.
  - `schema` column missing or blank.
  - `width_m` missing for segments.
  - `flow.csv` missing when flow analysis requested.

### 5.2 Integration tests
- Add an integration test for alternate `analysis.json` that points to `segments_alt.csv` and `flow_alt.csv`.
- Ensure all outputs (bins, geojson, reports) reflect alternate config paths.

### 5.3 Regression tests
- Validate that legacy endpoints that rely on `data/*.csv` now error with clear messages instead of silently falling back.

---

## Tooling/Interface Updates
- [ ] Review and update `e2e.py` to align with updated config loading logic (no fallbacks).
- [ ] Validate that all `make` commands still function as expected with new SSOT design.
- [ ] Update `/postman` test collections (if applicable) to reflect expected payloads, especially where alternate config files are used.

---

## Expected Outcomes
- All runtime modules consume configuration from `analysis.json` via centralized loader.
- No hardcoded `data/*.csv` or `{event}.gpx` paths in runtime code.
- All missing required metadata results in explicit errors, not silent defaults.
- End-to-end tests validate that alternate configs work and fallback paths are removed.
