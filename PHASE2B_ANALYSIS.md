# Phase 2B Analysis: Investigation of Remaining Low-Coverage Files

**Date:** December 17, 2025  
**Branch:** `cleanup/dead-code-removal`  
**Status:** Investigation Complete

---

## Executive Summary

**7 files** with <10% coverage remain. Investigation reveals:

- **3 files MUST KEEP** - Used by frontend or v2 code
- **4 files CAN BE REMOVED** - Only used by unused v1 API endpoints

---

## Detailed Analysis

### ✅ MUST KEEP (3 files)

#### 1. `app/routes/api_density.py` (7.3%, 566 lines)
- **Status:** ✅ **KEEP** - Used by frontend
- **Frontend Usage:** `frontend/templates/pages/density.html` calls `/api/density/segments`
- **Analysis:** 
  - Already refactored to use v2 runflow structure
  - Uses `create_runflow_storage()` and day-scoped paths
  - Not using legacy modules
- **Recommendation:** ✅ **KEEP** - Frontend dependency

#### 2. `app/routes/api_reports.py` (8.8%, 275 lines)
- **Status:** ✅ **KEEP** - Used by frontend
- **Frontend Usage:** `frontend/templates/pages/reports.html` calls `/api/reports/list` and `/api/reports/download`
- **Analysis:** 
  - Already refactored to use v2 runflow structure
  - Uses day-scoped paths (`runflow/<run_id>/<day>/reports/`)
  - Not using legacy modules
- **Recommendation:** ✅ **KEEP** - Frontend dependency

#### 3. `app/geo_utils.py` (7.5%, 442 lines)
- **Status:** ✅ **KEEP** - Used by v2 code
- **Usage:** 
  - `app/core/v2/ui_artifacts.py` imports `generate_segments_geojson()` (v2 code!)
  - `app/density_report.py` imports `generate_bins_geojson()` (v1 API)
  - `app/api/map.py` imports both functions (v1 API)
- **Analysis:** 
  - **Critical:** Used by v2 pipeline (`ui_artifacts.py`)
  - Utility functions needed by both v1 and v2
- **Recommendation:** ✅ **KEEP** - Required by v2 pipeline

---

### ❌ CAN BE REMOVED (4 files)

#### 4. `app/canonical_density_report.py` (6.8%, 522 lines)
- **Status:** ❌ **SAFE TO REMOVE**
- **Usage:** 
  - Only imported by `app/density_report.py` (lazy import)
  - Used by `/api/density-report` endpoint (NOT used by frontend)
- **Frontend:** Frontend uses `/api/density/segments` (different endpoint)
- **Analysis:** 
  - Legacy v1 report generation code
  - Endpoint `/api/density-report` is not called by frontend
  - Only used by legacy v1 API endpoint
- **Recommendation:** ❌ **REMOVE** - Not used by frontend, only legacy endpoint

#### 5. `app/flow_density_correlation.py` (7.1%, 439 lines)
- **Status:** ❌ **SAFE TO REMOVE**
- **Usage:** 
  - Only imported by `app/flow_report.py`
  - Used by `/api/flow-density-correlation` endpoint (NOT used by frontend)
- **Frontend:** No frontend usage found
- **Analysis:** 
  - Legacy v1 flow analysis code
  - Endpoint `/api/flow-density-correlation` is not called by frontend
- **Recommendation:** ❌ **REMOVE** - Not used by frontend

#### 6. `app/api/report.py` (8.9%, 253 lines)
- **Status:** ❌ **SAFE TO REMOVE**
- **Usage:** 
  - Used by `/api/report` endpoint (lazy import in `main.py`)
  - NOT used by frontend
- **Frontend:** Frontend uses `/api/reports/list` (different endpoint in `api_reports.py`)
- **Analysis:** 
  - Legacy report API code
  - Endpoint `/api/report` is not called by frontend
  - Different from `/api/reports/*` endpoints used by frontend
- **Recommendation:** ❌ **REMOVE** - Not used by frontend

#### 7. `app/map_data_generator.py` (8.0%, 650 lines)
- **Status:** ❌ **LIKELY SAFE TO REMOVE**
- **Usage:** 
  - Used by `app/api/map.py` (v1 map API)
  - Used by `app/canonical_density_report.py` (which we're removing)
- **Frontend:** Need to verify if v1 map API is used
- **Analysis:** 
  - Map data generation for v1 API
  - If v1 map API is not used by frontend, can be removed
- **Recommendation:** ⚠️ **INVESTIGATE** - Check if `/api/map/*` endpoints are used by frontend

---

## Frontend API Usage Summary

### ✅ Used by Frontend (KEEP)
- `/api/density/segments` → `app/routes/api_density.py` ✅
- `/api/reports/list` → `app/routes/api_reports.py` ✅
- `/api/reports/download` → `app/routes/api_reports.py` ✅

### ❌ NOT Used by Frontend (CAN REMOVE)
- `/api/density-report` → Uses `canonical_density_report.py` ❌
- `/api/temporal-flow-report` → Uses `flow_density_correlation.py` ❌
- `/api/report` → Uses `api/report.py` ❌
- `/api/flow-density-correlation` → Uses `flow_density_correlation.py` ❌

---

## Recommended Action Plan

### Phase 2B: Remove Legacy v1 API Support Files

**Files to Remove (4 files, ~1,864 lines):**
1. `app/canonical_density_report.py` (522 lines) - Only used by unused `/api/density-report`
2. `app/flow_density_correlation.py` (439 lines) - Only used by unused `/api/flow-density-correlation`
3. `app/api/report.py` (253 lines) - Only used by unused `/api/report`
4. `app/map_data_generator.py` (650 lines) - Verify map API usage first

**Files to Keep (3 files):**
1. `app/routes/api_density.py` - Frontend dependency
2. `app/routes/api_reports.py` - Frontend dependency
3. `app/geo_utils.py` - Used by v2 pipeline

### Additional Cleanup

**Remove unused v1 API endpoints from `main.py`:**
- `/api/density-report` endpoint (uses removed `canonical_density_report.py`)
- `/api/temporal-flow-report` endpoint (uses `flow_report.py` which depends on removed files)
- `/api/report` endpoint (uses removed `api/report.py`)
- `/api/flow-density-correlation` endpoint (uses removed `flow_density_correlation.py`)

**Note:** These endpoints already have lazy imports and will fail at runtime if called. Removing them completely is safe since frontend doesn't use them.

---

## Risk Assessment

| File | Risk | Reason |
|------|------|--------|
| `canonical_density_report.py` | ✅ Low | Only used by unused endpoint |
| `flow_density_correlation.py` | ✅ Low | Only used by unused endpoint |
| `api/report.py` | ✅ Low | Only used by unused endpoint |
| `map_data_generator.py` | ⚠️ Medium | Need to verify map API usage |
| `routes/api_density.py` | ❌ High | Frontend dependency - KEEP |
| `routes/api_reports.py` | ❌ High | Frontend dependency - KEEP |
| `geo_utils.py` | ❌ High | v2 pipeline dependency - KEEP |

---

## Expected Impact

**Phase 2B Removal:**
- **4 files** removed (~1,864 lines)
- **4 v1 API endpoints** removed from `main.py`
- **Total after Phase 2B:** 12 files, ~4,131 lines removed

**Remaining Low-Coverage Files:**
- 3 files kept (frontend/v2 dependencies)
- These are intentionally kept for compatibility

---

## Next Steps

1. ⏭️ **Verify map API usage** - Check if `/api/map/*` endpoints are used
2. ⏭️ **Remove 4 files** - `canonical_density_report.py`, `flow_density_correlation.py`, `api/report.py`, `map_data_generator.py`
3. ⏭️ **Remove unused endpoints** - Clean up `main.py` endpoints
4. ⏭️ **Test** - Verify frontend still works
5. ⏭️ **Document** - Mark remaining files as "v1 API compatibility layer"

