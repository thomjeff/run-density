# Issue #504: Deprecation & Cleanup - Bucketization Plan

**Date:** 2025-12-14  
**Status:** Planning Phase  
**Issue:** #504 - Phase 10: Deprecation & Clean-Up

## Overview

This document categorizes all files, endpoints, and constants into three buckets:
- **DELETE**: Remove entirely (v1-only, unused, or replaced by v2)
- **ARCHIVE**: Move to `archive/v1/` for reference only (if explicitly needed)
- **KEEP/REFACTOR**: Keep but ensure v2 compliance (read from runflow artifacts, no /data dependencies)

---

## 1. V1 ANALYSIS ENDPOINTS → DELETE

These endpoints compute outputs from `/data` inputs rather than serving artifacts from `runflow/{run_id}/{day}`.

### Endpoints in `app/main.py`:
- ✅ **DELETE** `POST /api/temporal-flow` (lines 262-296)
  - Computes from `paceCsv`, `segmentsCsv`, `startTimes`
  - Replaced by: `POST /runflow/v2/analyze`

- ✅ **DELETE** `POST /api/temporal-flow-single` (lines 298-350)
  - Computes from `/data` inputs
  - Replaced by: v2 flow analysis

- ✅ **DELETE** `POST /api/density-report` (lines 352-450)
  - Computes from `paceCsv`, `densityCsv`, `startTimes`
  - Replaced by: v2 pipeline generates Density.md

- ✅ **DELETE** `POST /api/temporal-flow-report` (lines 452-550)
  - Computes from `/data` inputs
  - Replaced by: v2 pipeline generates Flow.md/Flow.csv

- ✅ **DELETE** `POST /api/pdf-report` (lines 644-693)
  - Computes from `/data` inputs
  - No v2 replacement (PDF generation not in v2 scope)

- ✅ **DELETE** `POST /api/flow-audit` (lines 552-642)
  - Computes from `/data` inputs
  - No v2 replacement (audit functionality not in v2 scope)

- ✅ **DELETE** `GET /data/runners.csv` (lines 149-155)
  - Serves `/data` files directly
  - Replaced by: v2 uses `{event}_runners.csv` from API payload

- ✅ **DELETE** `GET /data/segments.csv` (lines 157-163)
  - Serves `/data` files directly
  - Replaced by: v2 reads from `data/segments.csv` internally (not served)

- ✅ **DELETE** `GET /data/flow_expected_results.csv` (lines 165-171)
  - Serves `/data` files directly
  - No v2 replacement (test data only)

### Pydantic Models in `app/main.py` (DELETE if only used by deleted endpoints):
- ✅ **DELETE** `AnalysisRequest` (lines 39-45) - only used by deleted endpoints
- ✅ **DELETE** `TemporalFlowRequest` (lines 47-53) - only used by deleted endpoints
- ✅ **DELETE** `SingleSegmentFlowRequest` (lines 55-64) - only used by deleted endpoints
- ✅ **DELETE** `ReportRequest` (lines 66-75) - only used by deleted endpoints
- ✅ **DELETE** `DensityReportRequest` (lines 77-86) - only used by deleted endpoints
- ✅ **DELETE** `TemporalFlowReportRequest` (lines 88-95) - only used by deleted endpoints
- ✅ **DELETE** `FlowAuditRequest` (lines 97-106) - only used by deleted endpoints
- ✅ **DELETE** `PDFReportRequest` (lines 108-125) - only used by deleted endpoints

---

## 2. UI-SERVING ENDPOINTS → KEEP/REFACTOR

These endpoints serve UI artifacts and should read from `runflow/{run_id}/{day}` only.

### Already v2-compliant (read from runflow):
- ✅ **KEEP** `/api/dashboard/*` (`app/routes/api_dashboard.py`)
  - Already uses `get_latest_run_id()`, `resolve_selected_day()`, `create_runflow_storage()`
  - Reads from `runflow/{run_id}/{day}/ui/*`

- ✅ **KEEP** `/api/segments/*` (`app/routes/api_segments.py`)
  - Already uses `get_latest_run_id()`, `resolve_selected_day()`, `create_runflow_storage()`
  - Reads from `runflow/{run_id}/{day}/ui/segments.geojson`

- ✅ **KEEP** `/api/density/*` (`app/routes/api_density.py`)
  - Already uses `get_latest_run_id()`, `resolve_selected_day()`, `create_runflow_storage()`
  - Reads from `runflow/{run_id}/{day}/ui/*` and `runflow/{run_id}/{day}/bins/*`

- ✅ **KEEP** `/api/locations/*` (`app/routes/api_locations.py`)
  - Already uses `get_latest_run_id()`, `resolve_selected_day()`, `create_runflow_storage()`
  - Reads from `runflow/{run_id}/{day}/reports/Locations.csv`

- ✅ **KEEP** `/api/bins/*` (`app/routes/api_bins.py`)
  - Already uses `get_latest_run_id()`, `resolve_selected_day()`, `create_runflow_storage()`
  - Reads from `runflow/{run_id}/{day}/bins/*`

- ✅ **KEEP** `/api/reports/*` (`app/routes/api_reports.py`)
  - Already uses `get_latest_run_id()`, `get_available_days()`, `get_run_directory()`
  - Reads from `runflow/{run_id}/{day}/reports/*`
  - ⚠️ **REFACTOR**: Lines 75-76 still reference `data/runners.csv` and `data/segments.csv` in metadata (non-functional, just documentation)

- ✅ **KEEP** `/api/heatmaps/*` (`app/routes/api_heatmaps.py`)
  - Already reads from `runflow/{run_id}/*`

- ✅ **KEEP** `/api/health/*` (`app/routes/api_health.py`)
  - Health check endpoints (no data dependencies)

### Needs verification:
- ⚠️ **VERIFY** `/api/flow/*` (`app/routes/api_flow.py` → `app/api/flow.py`)
  - `app/routes/api_flow.py` is a redirect to `app/api/flow.py`
  - `app/api/flow.py` appears to read from `runflow/{run_id}/{day}/reports/Flow.csv`
  - **Action**: Verify it doesn't read from `/data`, then keep

- ✅ **DELETE** `/api/e2e/*` (`app/routes/api_e2e.py`)
  - **Verified**: NOT used by v2 E2E suite (`tests/v2/e2e.py` doesn't reference it)
  - **Action**: Delete entire module

---

## 3. DEPRECATED MODULES → KEEP (v2 dependencies)

These modules are marked as "deprecated" but are actually used by v2 code paths.

### Keep (v2 dependencies):
- ✅ **KEEP** `app/new_density_report.py`
  - **Used by**: `app/core/v2/reports.py` (line 204), `app/density_report.py` (line 3441)
  - **Action**: Remove deprecation warnings, treat as v2 module

- ✅ **KEEP** `app/new_flagging.py`
  - **Used by**: `app/save_bins.py` (line 86)
  - **Action**: Remove deprecation warnings, treat as v2 module

- ✅ **KEEP** `app/new_density_template_engine.py`
  - **Used by**: `app/new_density_report.py` (line 41)
  - **Action**: Remove deprecation warnings, treat as v2 module

### Refactor/Remove:
- ⚠️ **REFACTOR** `app/routes/api_flow.py`
  - Currently redirects to `app/api/flow.py`
  - **Action**: Remove redirect, update `app/main.py` to import `app/api/flow.py` directly
  - **Then DELETE** `app/routes/api_flow.py`

---

## 4. DEPRECATED CONSTANTS → DELETE

### Constants in `app/utils/constants.py`:
- ✅ **DELETE** `EVENT_DAYS` (lines 85-91)
  - **References found**: None in active code (only in constants.py)
  - **Action**: Remove constant and all references

- ✅ **DELETE** `SATURDAY_EVENTS` (line 95)
  - **References found**: None in active code (only in constants.py)
  - **Action**: Remove constant and all references

- ✅ **DELETE** `SUNDAY_EVENTS` (line 96)
  - **References found**: None in active code (only in constants.py)
  - **Action**: Remove constant and all references

- ✅ **DELETE** `ALL_EVENTS` (line 97)
  - **References found**: None in active code (only in constants.py)
  - **Action**: Remove constant and all references

- ⚠️ **REFACTOR** `DEFAULT_PACE_CSV = "data/runners.csv"` (line 100)
  - **References found**: `app/api/map.py` (10 references)
  - **Action**: Refactor `app/api/map.py` to not use this constant, then delete

### Hardcoded event lists to remove:
- ✅ **SEARCH & REMOVE** any hardcoded lists like `['full', 'half', '10k']` or `['Elite', 'Open']`
  - **Action**: Grep for patterns, replace with dynamic event lists from API payload

---

## 5. DOCUMENTATION → ARCHIVE & REWRITE

### Archive (move to `archive/v1/docs/`):
- ✅ **ARCHIVE** `docs/GUARDRAILS.md`
  - **Action**: Copy to `archive/v1/docs/GUARDRAILS_v1.md`, then rewrite for v2

### Rewrite:
- ✅ **REWRITE** `docs/GUARDRAILS.md`
  - Update file references: `data/runners.csv` → `{event}_runners.csv`
  - Update output paths: `runflow/{run_id}/` → `runflow/{run_id}/{day}/`
  - Document v2 endpoints as primary
  - Reference v1 via `v1-maintenance` tag only

### Create new:
- ✅ **CREATE** `docs/migration_v1_to_v2.md`
  - High-level migration notes
  - Breaking changes
  - Endpoint migration guide

- ✅ **CREATE** `docs/deprecated.md`
  - List of removed endpoints/modules
  - Where to find v1 (tag reference)
  - Migration path

---

## 6. OTHER FILES → VERIFY

### Files to check:
- ⚠️ **REFACTOR** `app/api/map.py`
  - **Status**: Mixed - some endpoints are UI-serving, some are v1 analysis
  - **UI-serving endpoints** (read from old `reports/` structure, need refactoring):
    - `/map/manifest` - reads from `reports/` (should read from `runflow/{run_id}/{day}/bins/`)
    - `/map/segments` - reads from `reports/` (should read from `runflow/{run_id}/{day}/ui/`)
    - `/map/bins` - reads from `reports/` (should read from `runflow/{run_id}/{day}/bins/`)
  - **V1 analysis endpoints** (compute from `/data`, DELETE):
    - `/flow-bins` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/export-bins` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/historical-trends` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/compare-segments` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/export-advanced` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/cache-status` - uses `DEFAULT_PACE_CSV`, computes from `/data`
    - `/cached-analysis` - uses `DEFAULT_PACE_CSV`, computes from `/data`
  - **Action**: Split into two modules or delete v1 analysis endpoints, refactor UI-serving endpoints

- ⚠️ **VERIFY** `app/api/density.py`
  - Check if this is UI-serving or v1 analysis endpoint
  - **Action**: Verify usage, categorize accordingly

- ⚠️ **VERIFY** `app/api/report.py`
  - Check if this is UI-serving or v1 analysis endpoint
  - **Action**: Verify usage, categorize accordingly

---

## 7. IMPLEMENTATION ORDER

### PR 1: Runtime Cutover Cleanup
1. Delete v1 analysis endpoints from `app/main.py`
2. Delete Pydantic models for deleted endpoints
3. Remove `app/routes/api_flow.py` redirect, update `app/main.py` to import `app/api/flow.py` directly
4. Verify `/api/e2e/*` usage, delete if unused
5. Update root endpoint (`/`) to reflect v2-only endpoints

### PR 2: Remove/Deactivate v1 Modules
1. Remove deprecation warnings from `new_*` modules (they're v2 dependencies)
2. Delete `app/routes/api_e2e.py` (not used by v2 E2E suite)
3. Refactor `app/api/map.py`:
   - Delete v1 analysis endpoints (flow-bins, export-bins, historical-trends, compare-segments, export-advanced, cache-status, cached-analysis)
   - Refactor UI-serving endpoints to read from `runflow/{run_id}/{day}/` instead of `reports/`
4. Verify `app/api/density.py`, `app/api/report.py` usage
5. Archive or delete based on verification

### PR 3: Constants + Aliasing Cleanup
1. Remove `EVENT_DAYS`, `SATURDAY_EVENTS`, `SUNDAY_EVENTS`, `ALL_EVENTS` from `constants.py`
2. Refactor `app/api/map.py` to remove `DEFAULT_PACE_CSV` usage
3. Remove `DEFAULT_PACE_CSV` from `constants.py`
4. Search and remove hardcoded event lists
5. Standardize `seg_id` naming (verify no `segment_id` aliases in v2 outputs)

### PR 4: Documentation + Guardrails
1. Archive `docs/GUARDRAILS.md` to `archive/v1/docs/GUARDRAILS_v1.md`
2. Rewrite `docs/GUARDRAILS.md` for v2
3. Create `docs/migration_v1_to_v2.md`
4. Create `docs/deprecated.md`
5. Update `README.md` if needed (already updated for v2.0.0)

---

## 8. TESTING REQUIREMENTS

Each PR must pass:
- ✅ `make e2e-v2` passes
- ✅ UI smoke test: verify dashboard/segments/density/flow/locations pages load
- ✅ Day selector works for sat/sun
- ✅ No `/data` reads in UI endpoints (grep verification)

---

## Summary Statistics

- **Endpoints to DELETE**: ~16 (v1 analysis endpoints: 9 in main.py + 7 in map.py)
- **Endpoints to KEEP/REFACTOR**: ~13 (UI-serving endpoints: 10 already v2-compliant + 3 in map.py need refactoring)
- **Constants to DELETE**: 4 (`EVENT_DAYS`, `SATURDAY_EVENTS`, `SUNDAY_EVENTS`, `ALL_EVENTS`)
- **Constants to REFACTOR**: 1 (`DEFAULT_PACE_CSV`)
- **Modules to KEEP**: 3 (`new_*` modules are v2 dependencies)
- **Modules to DELETE**: 1 (`app/routes/api_flow.py` redirect)
- **Documentation files**: 1 archive, 1 rewrite, 2 create

---

## Next Steps

1. Review this bucketization plan
2. Proceed with PR 1: Runtime Cutover Cleanup
3. Each PR will be tested with `make e2e-v2` before merge

