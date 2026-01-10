# Configuration Integrity Audit (Issue #616)

## Scope & Method
Searched the repo for hardcoded references to `segments.csv`, `flow.csv`, `locations.csv`, `runners.csv`, `segments_new.csv`, and `*.gpx` in runtime code, then inspected relevant modules for fallback/default behavior and SSOT violations. Focused on production code under `app/`, `config/`, and `frontend/` (tests and archived docs excluded unless directly used by runtime). Line references are provided for each finding.

---

## ✅ Confirmed Compliant or Improving Areas
These areas already use analysis.json or SSOT-style lookups and avoid hardcoded defaults in core paths:

- **analysis.json data_files resolution** for segments/flow/locations/runners/gpx is centralized in `app/core/v2/analysis_config.py` and supports `data_files.*` with `data_dir` fallback for filename-only fields, enforcing SSOT at the accessor layer. (`app/core/v2/analysis_config.py:549-759`)
- **v2 flow analysis fail-fast path** explicitly documents that `flow.csv` is authoritative and should be required for requested event pairs, with file existence validation in `analyze_temporal_flow_segments_v2`. (`app/core/v2/flow.py:459-520`)
- **Segments schema resolution via CSV** is centralized in `app/schema_resolver.py` (replacing hardcoded mappings). While it still has fallbacks (see below), the SSOT intent is present and implemented. (`app/schema_resolver.py:25-153`)

---

## ⚠️ (A) Hardcoded File Paths (SSOT Violations)
Hardcoded paths or default filenames that bypass analysis.json or injected config:

### Direct `data/...` paths or filename defaults
- `app/main.py` serves `/data/runners.csv` and `/data/segments.csv` with hardcoded filesystem paths. (`app/main.py:150-165`)
- `app/main.py` loads `data/segments.csv` directly for segments metadata and fallback responses. (`app/main.py:1218-1231`, `app/main.py:1318-1333`)
- `app/api/map.py` reads from hardcoded `data/segments.parquet` then falls back to `data/segments.csv`; also loads GPX from `data/`. (`app/api/map.py:95-105`, `app/api/map.py:186-202`)
- `app/location_report.py` defaults `locations_csv`, `runners_csv`, and `segments_csv` to `data/*.csv` and loads GPX from `data/`. (`app/location_report.py:642-684`)
- `app/validation/location_projection.py` defaults `locations_file` and `segments_file` to `data/*.csv`. (`app/validation/location_projection.py:31-35`)
- `app/validation/segment_references.py` defaults `locations_file` and `segments_file` to `data/*.csv`. (`app/validation/segment_references.py:21-25`)
- `app/validation/preflight.py` defaults `file_path` to `data/segments.csv` and uses it directly. (`app/validation/preflight.py:154-172`)
- `app/routes/api_density.py` defaults `segments_csv_path` to `data/segments.csv` for label enrichment. (`app/routes/api_density.py:177-184`)
- `app/core/v2/density.py` defaults `density_csv_path` to `data/segments.csv`. (`app/core/v2/density.py:264-270`)
- `app/io/loader.py` defaults `load_segments`, `load_runners`, and `load_locations` to `data/*.csv`. (`app/io/loader.py:9-29`, `app/io/loader.py:64-89`)
- `app/core/artifacts/heatmaps.py` falls back to `data/segments.csv` when analysis.json lookup fails. (`app/core/artifacts/heatmaps.py:663-667`)
- `app/new_density_report.py` falls back to `data/segments.csv` if `segments.parquet` missing. (`app/new_density_report.py:85-101`)
- `app/storage.py` pins `DATASET["runners"]` to `data/runners.csv` even though v2 uses per-event runners. (`app/storage.py:17-26`)

### Hardcoded GPX filenames and event list
- `app/core/gpx/processor.py` hardcodes event list and `{event}.gpx` mapping, independent of analysis.json `data_files.gpx`. (`app/core/gpx/processor.py:375-399`)
- `app/core/artifacts/frontend.py` loads GPX courses from hardcoded `data` directory. (`app/core/artifacts/frontend.py:626-629`)

---

## ⚠️ (B) Silent Fallbacks to Defaults
Instances where missing configuration is silently replaced with defaults (sometimes only warning logs) rather than failing fast:

### Schema and LOS defaults
- `app/schema_resolver.py` defaults invalid schema values to `on_course_open`, and if a segment is missing, falls back to type-based or default schema. (`app/schema_resolver.py:69-153`)
- `app/core/density/compute.py` defaults schema to `on_course_open` and returns `F` on errors, which can hide missing config. (`app/core/density/compute.py:92-108`, `app/core/density/compute.py:149-167`)
- `app/main.py` computes LOS using `rulebook.get_thresholds("on_course_open")` if no schema provided. (`app/main.py:1197-1201`)

### Width/length defaults
- `app/api/map.py` falls back to schema_key `on_course_open` and width `5.0` when segment metadata is incomplete. (`app/api/map.py:111-114`)
- `app/core/gpx/processor.py` assigns default `direction: "uni"` and `width_m: 10.0` in GeoJSON generation. (`app/core/gpx/processor.py:420-422`)
- `app/core/v2/flow.py` fallback flow segments use `width_m` default `0` and `flow_type` default `none`. (`app/core/v2/flow.py:441-444`)
- `app/core/artifacts/frontend.py` defaults `schema` to `on_course_open` and `direction` to `uni` when enrichment missing. (`app/core/artifacts/frontend.py:511-556`)

### File path fallbacks
- `app/core/v2/flow.py` loads `flow.csv` but returns empty DataFrame and proceeds when missing/unreadable. (`app/core/v2/flow.py:109-135`)
- `app/core/v2/bins.py` defaults `segments_csv_path` to `data/segments.csv` if not provided and only logs a warning. (`app/core/v2/bins.py:132-138`)
- `app/new_density_report.py` falls back to `data/segments.csv` (and warns) if `segments.parquet` missing. (`app/new_density_report.py:85-101`)
- `app/new_density_report.py` uses a built-in rulebook if `density_rulebook.yml` missing. (`app/new_density_report.py:111-129`)

---

## ⚠️ (C) SSOT Breaches / Config Propagation Gaps
Places where config data is reloaded or implied deep in helpers instead of being injected from top-level analysis.json or a context object:

- **Map API endpoints** load `data/segments.csv` directly and call `load_all_courses("data")` rather than using analysis.json `data_files` or run-specific data. (`app/api/map.py:95-202`)
- **Location report** depends on default `data/*.csv` and `data/` GPX directory; no config object passed. (`app/location_report.py:642-684`)
- **v2 bins generation** creates a temporary `data/runners.csv` file to satisfy `build_runner_window_mapping()` which hardcodes that path, violating per-event runner SSOT. (`app/core/v2/bins.py:142-176`)
- **Schema resolution** depends on default `data/segments.csv` if `segments_csv_path` omitted; downstream callers frequently omit the path. (`app/schema_resolver.py:114-153`)
- **Artifacts**: heatmaps and segments geojson attempt to use analysis.json, but still fallback to hardcoded `data/segments.csv` and `load_all_courses("data")` for GPX. (`app/core/artifacts/heatmaps.py:620-667`, `app/core/artifacts/frontend.py:585-629`)
- **Validation**: `validate_v2_request_payload()` defaults file names to `segments.csv`, `locations.csv`, and `flow.csv` if missing, rather than requiring explicit config. (`app/core/v2/validation.py:576-615`)
- **Storage layer** hardcodes `data/runners.csv` in `DATASET`, but v2 expects per-event files (e.g., `{event}_runners.csv`). (`app/storage.py:17-26`)

---

## 🛠️ Suggestions for Cleanup / Refactoring
High-impact refactors to move toward SSOT with minimal disruption:

1. **Introduce a shared `AnalysisContext` or `DataFiles` object** that holds resolved file paths and is passed into map, location, density, flow, and artifact generation modules (avoid re-reading analysis.json in leaf functions).
2. **Replace hardcoded defaults with explicit required parameters** in:
   - `app/api/map.py` and `app/location_report.py`
   - `app/io/loader.py` (optional `data_dir` argument, no default to `data/` when called from pipeline)
   - `app/schema_resolver.resolve_schema()` (require `segments_csv_path`, fail if missing)
3. **Eliminate temporary `data/runners.csv` creation** by refactoring `build_runner_window_mapping()` to accept a DataFrame or path parameter, then wire from v2 pipeline. (`app/core/v2/bins.py`)
4. **Make `load_flow_csv` fail-fast** or return an error object if missing, to align with the “flow.csv is authoritative” contract (avoid `DataFrame()` fallback).
5. **Move GPX file mapping into analysis.json** (`data_files.gpx`) and update `load_all_courses()` to accept explicit event->GPX path mapping instead of hardcoded `{event}.gpx`.
6. **Centralize default widths/lengths and schema fallbacks** into config (analysis.json or rulebook) rather than inline literals (`5.0`, `10.0`, `on_course_open`).

---

## 🚫 Deprecated or Dangerous Fallback Patterns
These are the most likely to mask configuration errors and should be prioritized for elimination:

- **Silent `flow.csv` skip**: `load_flow_csv()` logs a warning but returns empty DataFrame, enabling downstream fallback paths that bypass authoritative flow definitions. (`app/core/v2/flow.py:109-135`)
- **Schema defaults to `on_course_open`** when segments are missing or schema invalid, hiding bad data. (`app/schema_resolver.py:69-153`, `app/core/density/compute.py:149-167`)
- **Hardcoded `data/runners.csv` shim** to satisfy legacy function; this is a hidden global dependency. (`app/core/v2/bins.py:142-176`)
- **Artifacts fallback to `data/segments.csv`** when analysis.json lookup fails, which can generate mismatched UI outputs. (`app/core/artifacts/heatmaps.py:663-667`)
- **Default GPX scan from `data/` directory** with fixed event list rather than analysis.json. (`app/core/gpx/processor.py:375-399`)

---

## 📌 Notes on Exclusions
- Archived documentation, tests, and migration artifacts contain many hardcoded examples but are not included in the violations list unless referenced by runtime code.
- `frontend/templates/pages/analysis.html` contains example defaults (`segments.csv`, `flow.csv`, `locations.csv`), which should be updated after backend SSOT decisions but are not runtime loaders.
