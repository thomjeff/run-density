# Phase 2 Analysis: Low Coverage Files (<10%)

**Date:** December 17, 2025  
**Branch:** `cleanup/dead-code-removal`  
**Coverage Threshold:** <10% coverage

---

## Executive Summary

**9 files identified** with <10% coverage. All are imported/used, but **not hit during E2E tests** (which use v2 routes).

**Key Finding:** Most are **v1 API routes and legacy code** that are still registered but not used by the v2 E2E test suite.

---

## Detailed Analysis

### 🔴 High Priority: Safe to Remove (2 files)

#### 1. `app/routes/api_e2e.py` (9.7%, 577 lines)
- **Status:** ✅ Active route registered in `main.py`
- **Endpoints:** `/api/e2e/run`, `/api/e2e/upload`, `/api/e2e/status`, `/api/export-ui-artifacts`
- **Analysis:** 
  - **Explicitly marked as "INTERNAL / EXPERIMENTAL" and "NOT used in CI"**
  - Header comment states: "🚧 INTERNAL / EXPERIMENTAL" and "it is **NOT used in CI** due to deadlock risks"
- **Recommendation:** ❌ **SAFE TO REMOVE** - Explicitly documented as experimental/unused
- **Risk:** Low - Not used in CI, marked as experimental

#### 2. `app/io_bins.py` (8.4%, 371 lines)
- **Status:** Imported by `app/canonical_density_report.py`
- **Usage:** `load_bins()`, `get_bins_metadata()` functions
- **Analysis:** 
  - Legacy I/O functions for bins
  - v2 uses `app/core/v2/loader.py` for loading bins
  - Only imported by `canonical_density_report.py` (which itself has 6.8% coverage)
- **Recommendation:** ❌ **Likely safe to remove** - Replaced by v2 loader
- **Risk:** Medium - Need to verify `canonical_density_report.py` dependency chain

---

### 🟡 Medium Priority: Investigate Further (3 files)

#### 3. `app/canonical_density_report.py` (6.8%, 522 lines)
- **Status:** Imported by `app/density_report.py`
- **Usage:** `generate_tooltips_json()` function
- **Analysis:** 
  - Legacy v1 density report code
  - v2 uses `generate_density_report_v2()` in `app/core/v2/reports.py`
  - However, `density_report.py` is still used by `generate_density_report_endpoint()` in `main.py`
- **Recommendation:** ⚠️ **Investigate** - Check if `density_report.py` endpoints are still needed
- **Risk:** Medium - May be used by v1 API endpoints

#### 4. `app/flow_density_correlation.py` (7.1%, 439 lines)
- **Status:** Imported by `app/flow_report.py`
- **Usage:** `analyze_flow_density_correlation()` function
- **Analysis:** 
  - Legacy v1 flow analysis code
  - `flow_report.py` is still used by `generate_temporal_flow_report_endpoint()` in `main.py`
- **Recommendation:** ⚠️ **Investigate** - Check if `flow_report.py` endpoints are still needed
- **Risk:** Medium - May be used by v1 API endpoints

#### 5. `app/api/report.py` (8.9%, 253 lines)
- **Status:** Imported by `app/main.py`
- **Usage:** `generate_combined_report()`, `generate_combined_narrative()` functions
- **Analysis:** 
  - Legacy report API code
  - Used in `main.py` but not hit during E2E tests
- **Recommendation:** ⚠️ **Investigate** - Check if replaced by v2 or still needed for v1 API
- **Risk:** Medium - May be used by v1 API endpoints

---

### 🟢 Low Priority: Keep if v1 API Needed (4 files)

#### 6. `app/routes/api_density.py` (7.3%, 566 lines)
- **Status:** ✅ Active route registered in `main.py`
- **Endpoints:** 
  - `GET /api/density/segments`
  - `GET /api/density/segment/{seg_id}`
- **Analysis:** 
  - v1 API routes for density data
  - E2E tests use v2 routes (`POST /runflow/v2/analyze`)
  - May be needed for frontend compatibility
- **Recommendation:** ⚠️ **Keep if v1 API still needed** for frontend
- **Risk:** Low - Only remove if frontend fully migrated to v2

#### 7. `app/routes/api_reports.py` (8.8%, 275 lines)
- **Status:** ✅ Active route registered in `main.py`
- **Endpoints:** Report listing/download endpoints
- **Analysis:** 
  - v1 API routes for reports
  - v2 uses different report structure (day-partitioned)
  - May be needed for frontend compatibility
- **Recommendation:** ⚠️ **Keep if v1 API still needed** for frontend
- **Risk:** Low - Only remove if frontend fully migrated to v2

#### 8. `app/geo_utils.py` (7.5%, 442 lines)
- **Status:** Imported by `app/density_report.py` and `app/api/map.py`
- **Usage:** `generate_bins_geojson()`, `generate_segments_geojson()` functions
- **Analysis:** 
  - Utility functions for GeoJSON generation
  - Used by both v1 (`density_report.py`) and potentially v1 map API
- **Recommendation:** ⚠️ **Check if used by v2** - May be utility code needed by both
- **Risk:** Low - Utility functions, likely still needed

#### 9. `app/map_data_generator.py` (8.0%, 650 lines)
- **Status:** Imported by `app/api/map.py`
- **Usage:** `find_latest_reports()` function
- **Analysis:** 
  - Map data generation for v1 API
  - Used by `app/api/map.py` router
- **Recommendation:** ⚠️ **Check if v2 uses different map generation** - May be needed for v1 map API
- **Risk:** Low - Only remove if v1 map API is deprecated

---

## Recommended Action Plan

### Phase 2A: Immediate Removal (Low Risk)
1. **Remove `app/routes/api_e2e.py`** - Explicitly marked as experimental/unused
2. **Remove `app/io_bins.py`** - After verifying `canonical_density_report.py` dependency

**Expected Impact:** ~948 lines removed

### Phase 2B: Investigation Required
3. **Check v1 API usage:**
   - Are `generate_density_report_endpoint()` and `generate_temporal_flow_report_endpoint()` still used?
   - Is frontend still calling v1 API endpoints?
   - Can we deprecate v1 API routes?

4. **If v1 API can be deprecated:**
   - Remove `app/canonical_density_report.py`
   - Remove `app/flow_density_correlation.py`
   - Remove `app/api/report.py`
   - Remove `app/routes/api_density.py`
   - Remove `app/routes/api_reports.py`
   - Remove `app/geo_utils.py` (if only used by v1)
   - Remove `app/map_data_generator.py` (if only used by v1)

**Expected Impact:** ~3,000+ lines removed if v1 API fully deprecated

### Phase 2C: Keep if Needed
5. **Keep v1 API routes** if frontend still depends on them
6. **Document** which files are v1-only for future cleanup

---

## Risk Assessment

| File | Risk | Reason |
|------|------|--------|
| `api_e2e.py` | ✅ Low | Explicitly marked as experimental/unused |
| `io_bins.py` | ⚠️ Medium | Need to verify dependency chain |
| `canonical_density_report.py` | ⚠️ Medium | Used by v1 API endpoint |
| `flow_density_correlation.py` | ⚠️ Medium | Used by v1 API endpoint |
| `api/report.py` | ⚠️ Medium | Used by v1 API endpoint |
| `routes/api_density.py` | 🟢 Low | v1 API route, may be needed |
| `routes/api_reports.py` | 🟢 Low | v1 API route, may be needed |
| `geo_utils.py` | 🟢 Low | Utility functions, likely needed |
| `map_data_generator.py` | 🟢 Low | Used by v1 map API |

---

## Next Steps

1. ✅ **Complete Phase 1** - Verify E2E tests pass after removing 6 files
2. ⏭️ **Phase 2A** - Remove `api_e2e.py` and `io_bins.py` (after dependency check)
3. ⏭️ **Investigate v1 API usage** - Determine if v1 API can be deprecated
4. ⏭️ **Phase 2B** - Remove v1 API code if deprecated
5. ⏭️ **Document** - Mark v1-only files for future cleanup if keeping them

---

**Total Potential Removal:** ~4,000+ lines if v1 API fully deprecated

