# Supplemental Configuration Audit (Issue #616)

## 1) Legacy CLI / Utility Inventory (Hardcoded Paths & Production Risk)
These scripts/tools are not part of the active runtime but still hardcode `data/*.csv` or GPX filenames. If run against a live environment (or pointed at prod data), they could bypass SSOT configuration and cause confusing or stale outputs.

### Legacy CLI utilities (non-runtime, informational only)
- The scripts under `archive/` reference hardcoded data paths, but they are **not used at runtime** and are **not considered high-risk** per current guidance. They are listed here purely for completeness and should not be treated as remediation targets unless they are reactivated for production workflows.

### Notes
- There are **no Jupyter notebooks** (`.ipynb`) in the repo, so notebook risks appear minimal.
### High-risk legacy CLI utilities (hardcoded data paths)
- `archive/smoke_testing.py` posts API payloads with `data/runners.csv` + `data/segments.csv` and other hardcoded defaults. (`archive/smoke_testing.py:88-118`)
- `archive/integration_testing.py` executes multiple API calls with `data/runners.csv` + `data/segments.csv` across density/flow endpoints. (`archive/integration_testing.py:77-111`)
- `archive/legacy-scripts/e2e-v1.py` hardcodes `data/runners.csv`/`data/segments.csv` payloads for density and flow checks. (`archive/legacy-scripts/e2e-v1.py:49-60`)
- `archive/scripts/obsolete-validation-2025-11/generate_frontend_data.py` loads `data/segments.csv` directly for GeoJSON generation. (`archive/scripts/obsolete-validation-2025-11/generate_frontend_data.py:27-56`)
- `archive/gpx_processor.py` hardcodes `10K.gpx`, `Half.gpx`, `Full.gpx` in a legacy course loader. (`archive/gpx_processor.py:353-377`)
- `archive/generate_temporal_flow_report.py` documents example CLI usage with `data/segments.csv` and `data/your_pace_data.csv` (likely to be copy-pasted). (`archive/generate_temporal_flow_report.py:20-35`)

### Notes
- There are **no Jupyter notebooks** (`.ipynb`) in the repo, so notebook risks appear minimal.
- Most hardcoded legacy scripts live in `archive/` and should be explicitly labeled or moved to a non-discoverable path if they must remain.

---

## 2) Bin + Metrics Generation: Redundant Config Reloading
Multiple modules reload segments metadata independently, risking inconsistent configuration when analysis.json provides alternate files.

### Observed reload patterns
- `app/density_report.py` repeatedly loads segments from `analysis_context.segments_csv_path` in helper functions and fallback paths; there are multiple reloads during bin artifact creation and flagging. (`app/density_report.py:2068-2144`, `app/density_report.py:2217-2231`)
- `app/new_density_report.py` loads `segments.parquet` from reports, then **falls back** to `data/segments.csv` if missing, bypassing any run-specific config. (`app/new_density_report.py:85-105`)
- `app/core/artifacts/frontend.py` re-reads segments from analysis.json in `generate_segments_geojson`, even if upstream already loaded segments. (`app/core/artifacts/frontend.py:585-666`)
- `app/core/v2/bins.py` accepts `segments_df`, but still uses `segments_csv_path` for downstream `AnalysisContext` and can default to `data/segments.csv`. (`app/core/v2/bins.py:126-187`)

### Risk
- When `analysis.json` points to a non-default segments file, some reporting/metrics pipelines may still reload `data/segments.csv` or assume a default schema.

---

## 3) Config Failure Test Coverage (Gaps)

### Existing coverage
- Validation covers **missing segments.csv** and invalid file extensions (fail-fast). (`tests/v2/test_validation.py:150-215`)
- Flow metadata tests explicitly **allow missing flow.csv** and expect an empty DataFrame, indicating non-fail-fast behavior. (`tests/v2/test_flow.py:115-135`)

### Missing or weak coverage
- No tests explicitly verify failure when `segments_csv_path` is omitted in schema resolution or bin generation (e.g., `schema_resolver.resolve_schema`, `generate_bins_v2`).
- No integration tests appear to validate alternate `analysis.json` configurations (e.g., pointing to `segments_616.csv`) through the full report or artifact pipeline.

---

## 4) Schema Resolution Touchpoints (SSOT Wiring Check)

### Modules resolving or defaulting schema
- `app/schema_resolver.py` loads schema from CSV but defaults to `on_course_open` on invalid/missing segments. (`app/schema_resolver.py:25-153`)
- `app/density_template_engine.py` resolves schema via `schema_resolver`, allowing optional `segments_csv_path` but not enforcing it. (`app/density_template_engine.py:128-176`)
- `app/core/density/compute.py` uses schema from segment_data, else falls back to `schema_resolver` if `segments_csv_path` is provided (or defaults to `on_course_open`). (`app/core/density/compute.py:146-167`)
- `app/density_report.py` prefers schema from `segments_dict` (SSOT) and falls back to `resolve_schema` with `analysis_context.segments_csv_path`. (`app/density_report.py:2111-2144`)
- `app/routes/api_density.py` calls `resolve_schema` **without** a `segments_csv_path` in some paths, which can default to `data/segments.csv`. (`app/routes/api_density.py:637-668`)
- `app/api/map.py` uses `segment_type` fallback and defaults to `on_course_open` and static widths without using analysis context. (`app/api/map.py:95-114`)
- `app/new_flagging.py` uses schema from `segments_df` when available, otherwise defaults to `on_course_open`. (`app/new_flagging.py:54-113`)
- `app/core/artifacts/frontend.py` assigns schema defaults when bins lack schema_key, again defaulting to `on_course_open`. (`app/core/artifacts/frontend.py:500-556`)

### Summary
- Some components (density_report, density/compute) honor `analysis_context` and `segments_csv_path`.
- Others (api_density, api_map, frontend artifacts) still default without a path, which can bypass analysis.json SSOT.

---

## 5) Default Constants / Magic Numbers to Centralize
These defaults should likely be moved into configuration or explicitly documented as legacy fallbacks:

- `DEFAULT_SEGMENT_WIDTH_M = 5.0` and related defaults in `app/utils/constants.py`. (`app/utils/constants.py:145-148`)
- Map endpoints default segment width to `5.0` if missing. (`app/api/map.py:109-115`)
- GPX GeoJSON generation defaults width to `10.0` and direction to `uni`. (`app/core/gpx/processor.py:420-422`)
- `app/new_flagging.py` defaults width to `3.0` when segment metadata is missing. (`app/new_flagging.py:68-113`)
- `app/density_report.py` uses width defaults of `3.0` and `5.0` across several paths. (`app/density_report.py:253-2144`)
- `app/core/v2/res.py` falls back to `avg_width_m = 1.0` when invalid. (`app/core/v2/res.py:194-199`)

---

## 6) ConfigLoader Concept Evaluation
A dedicated `ConfigLoader` could centralize CSV/GPX/rulebook loading and enforce SSOT consistently:

### Proposed responsibilities
- Resolve `analysis.json` (including `data_files`) once and expose canonical paths.
- Load CSVs (segments/flow/locations/runners) with shared validation and caching (avoid redundant reads).
- Load GPX files from `data_files.gpx` rather than scanning `data/`.
- Expose schema lookup and rulebook thresholds with explicit failure handling.

### Candidates for immediate adoption
- Replace path defaults in `app/api/map.py`, `app/location_report.py`, and `app/routes/api_density.py` with injected config loader or context.
- Consolidate `segments_csv_path` logic in `app/core/v2/bins.py`, `app/core/artifacts/frontend.py`, and `app/new_density_report.py`.


---

## Final Research Questions Before Implementation Planning

### 1) Legacy CLI Tools & Notebooks
- **CLI/test scripts with legacy data paths:** Yes. Several archived utilities hardcode `data/runners.csv`/`data/segments.csv` and legacy GPX names, including `archive/smoke_testing.py`, `archive/integration_testing.py`, `archive/legacy-scripts/e2e-v1.py`, and `archive/scripts/obsolete-validation-2025-11/generate_frontend_data.py`. These remain upgrade candidates or should be clearly quarantined to avoid accidental production use. (`archive/smoke_testing.py:88-118`, `archive/integration_testing.py:77-111`, `archive/legacy-scripts/e2e-v1.py:49-60`, `archive/scripts/obsolete-validation-2025-11/generate_frontend_data.py:27-56`)
- **Jupyter notebooks:** None found in the repo (`.ipynb` absent). This reduces notebook-related risk.

### 2) Test Coverage for Config Failures & Silent Fallbacks
- **Existing coverage:** Validation tests cover missing `segments.csv` and extension validation (fail-fast). (`tests/v2/test_validation.py:150-215`)
- **Silent fallback coverage:** There is an explicit test that missing `flow.csv` returns an empty DataFrame, indicating fallback acceptance rather than failure. (`tests/v2/test_flow.py:115-135`)
- **Gaps:** No tests explicitly exercise missing `segments_csv_path` in schema resolution or bin generation; no integration tests assert behavior when `analysis.json` points to alternate `segments_*` files across the full pipeline. (See gaps in Section 3 above.)

### 3) Validation Strategy Recommendation
- **Recommendation:** Yes—introduce a configuration validator that checks **required fields and types** early in the pipeline (schema, width_m, direction, event span columns, data_files paths) and **fails fast** on missing critical fields rather than defaulting. This validator should run before density/flow/bin generation, and should be fed from `analysis.json`/`data_files` to ensure SSOT. (See Sections 2, 4, and 5 above for concrete default/fallback hotspots.)

### 4) SSOT Loader Recommendation
- **Recommendation:** Yes—introduce a centralized **ConfigLoader/SegmentManager** responsible for:
  - resolving `analysis.json` + `data_files` once,
  - loading and caching CSV/GPX inputs,
  - providing schema lookups and rulebook thresholds,
  - and standardizing error handling.
This would reduce redundant reloads and prevent hardcoded defaults in downstream modules. (See Sections 2 and 6 above for candidate integration points.)
