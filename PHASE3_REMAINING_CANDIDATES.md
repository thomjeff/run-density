# Phase 3: Remaining Cleanup Candidates

**Issue:** #544  
**Date:** December 19, 2025  
**Coverage Report:** Run ID `RQ8sSt6Q6YfJhQwKFFcBYS`  
**Status:** 🔍 Ready for Review

---

## Summary

**Total Files with 10-49% Coverage:** 30 files  
**Files Already Cleaned:** 14 files  
**New Candidates:** 1 file (`app/version.py`)  
**Files Requiring Further Review:** 3 files (already cleaned but still very low coverage)

---

## 🔴 Priority 1: New Candidate (Not Yet Reviewed)

### `app/version.py` (15.1% coverage, 114 statements, 94 missing)

**Status:** ⏭️ **NOT YET INVESTIGATED**

**Coverage Details:**
- **Coverage:** 15.1%
- **Statements:** 114
- **Missing:** 94
- **Executed:** 20

**Purpose:** Handles automated versioning for releases

**Investigation Needed:**
- [ ] Check which functions are actually called
- [ ] Verify if version detection logic is needed
- [ ] Check if used by build scripts (already noted as used)
- [ ] Simplify if possible

**Risk:** ✅ **Low** - Small file, mostly version detection logic

**Estimated Impact:** ~20-50 lines if unused functions found

**Recommendation:** 🔍 **INVESTIGATE** - Low risk, potential for simplification

---

## 🟡 Priority 2: Already-Cleaned Files (May Need Further Review)

These files were cleaned in earlier batches but still show very low coverage. May have additional unused code:

### 1. `app/heatmap_generator.py` (10.9% coverage, 165 statements, 143 missing)

**Status:** ✅ **CLEANED** (removed 1 function + legacy code path)

**Coverage Details:**
- **Coverage:** 10.9%
- **Statements:** 165
- **Missing:** 143
- **Executed:** 22

**Previous Cleanup:**
- Removed `get_heatmap_files()` function
- Removed `load_segments_metadata()` function
- Removed legacy date format support in `load_bin_data()`
- Removed unused imports (`json`, `load_rulebook`)

**Investigation Needed:**
- [ ] Review remaining functions for unused code
- [ ] Check if all functions are actually called
- [ ] Verify if helper functions are used

**Risk:** ✅ **Low** - Already cleaned once, may have more unused code

**Estimated Impact:** ~20-50 lines if more unused code found

**Recommendation:** 🔍 **REVIEW** - Large file with very low coverage

---

### 2. `app/api/map.py` (13.6% coverage, 272 statements, 225 missing)

**Status:** ✅ **CLEANED** (removed 7 endpoints + unused imports)

**Coverage Details:**
- **Coverage:** 13.6%
- **Statements:** 272
- **Missing:** 225
- **Executed:** 47

**Previous Cleanup:**
- Removed `GET /api/map-data` endpoint (broken)
- Removed 6 cache management endpoints
- Removed unused `get_global_cache_manager` import
- Removed `/historical-trends`, `/compare-segments`, `/export-advanced` endpoints

**Active Endpoints (Preserved):**
- `GET /api/map/manifest` - Used by frontend
- `GET /api/map/segments` - Used by frontend
- `GET /api/map/bins` - Used by frontend
- `GET /api/bins-data` - Used by frontend
- `POST /api/flow-bins` - Used by frontend
- `POST /api/export-bins` - Used by frontend
- `GET /api/map-config` - Used by frontend
- `GET /api/map-status` - Used by frontend

**Investigation Needed:**
- [ ] Review helper functions within active endpoints
- [ ] Check if all endpoint logic is necessary
- [ ] Verify if there are unused helper functions

**Risk:** ✅ **Low** - Already cleaned once, active endpoints are used by frontend

**Estimated Impact:** ~50-100 lines if more unused code found

**Recommendation:** 🔍 **REVIEW** - Large file with low coverage, but active endpoints are used

---

### 3. `app/density_report.py` (23.7% coverage, 1,535 statements, 1,126 missing)

**Status:** ✅ **CLEANED** (removed 413 lines of v1-only code)

**Coverage Details:**
- **Coverage:** 23.7%
- **Statements:** 1,535
- **Missing:** 1,126
- **Executed:** 409

**Previous Cleanup:**
- Removed `generate_density_report()` (v1 API entry point)
- Removed `generate_simple_density_report()` (v1 API)
- Removed 11 v1-only helper functions (~413 lines)
- Preserved all v2-used functions

**v2 Pipeline Dependencies (MUST PRESERVE):**
- `AnalysisContext` - Used by `app/core/v2/bins.py`
- `_generate_bin_dataset_with_retry` - Used by `app/core/v2/bins.py`
- `_save_bin_artifacts_and_metadata` - Used by `app/core/v2/bins.py`
- `_process_segments_from_bins` - Used by `app/core/v2/bins.py`
- `generate_map_dataset` - Used by `app/core/v2/pipeline.py`
- `generate_new_density_report_issue246` - Used by `app/core/v2/reports.py`

**Investigation Needed:**
- [ ] Review for additional v1-only code paths
- [ ] Check if there are more unused helper functions
- [ ] Verify if all v2-used functions are fully utilized

**Risk:** ⚠️ **Medium** - Very large file, may have more v1-only code

**Estimated Impact:** ~100-200 lines if more v1-only code found

**Recommendation:** 🔍 **REVIEW** - Large file, may have more cleanup opportunities

---

## ✅ Files Retained (No Further Action Needed)

These files have been investigated and are essential:

| File | Coverage | Reason |
|------|----------|--------|
| `app/api/flow.py` | 19.6% | Used via `app/routes/api_flow.py` wrapper |
| `app/bin_intelligence.py` | 20.7% | All functions used by v2 pipeline |
| `app/canonical_segments.py` | 20.9% | All functions used by v2 |
| `app/main.py` | 21.9% | Essential application entry point |
| `app/utils/run_id.py` | 23.7% | Core utility |
| `app/routes/ui.py` | 28.0% | Frontend dependency |
| `app/utils/auth.py` | 28.1% | Used by UI routes |
| `app/utils/metadata.py` | 32.1% | Core utility |
| `app/density_template_engine.py` | 33.0% | Already cleaned, v2 functions preserved |
| `app/paths.py` | 36.4% | Used by v2 pipeline |
| `app/core/flow/flow.py` | 36.9% | Core v2 module |
| `app/routes/api_health.py` | 40.0% | Essential monitoring |
| `app/core/artifacts/frontend.py` | 40.4% | Core v2 module |
| `app/schema_resolver.py` | 40.7% | Core utility |
| `app/flagging.py` | 44.4% | Core utility (SSOT) |
| `app/core/bin/summary.py` | 44.8% | Core v2 module |
| `app/report_utils.py` | 47.8% | Core utility |

---

## Recommended Action Plan

### Phase 3B: Additional Cleanup (Optional)

**Priority Order:**

1. **`app/version.py`** (15.1%)
   - **Action:** Investigate and simplify
   - **Risk:** Low
   - **Estimated Impact:** ~20-50 lines

2. **`app/heatmap_generator.py`** (10.9%)
   - **Action:** Review for additional unused functions
   - **Risk:** Low
   - **Estimated Impact:** ~20-50 lines

3. **`app/api/map.py`** (13.6%)
   - **Action:** Review helper functions within active endpoints
   - **Risk:** Low
   - **Estimated Impact:** ~50-100 lines

4. **`app/density_report.py`** (23.7%)
   - **Action:** Review for additional v1-only code
   - **Risk:** Medium
   - **Estimated Impact:** ~100-200 lines

**Total Estimated Impact:** ~190-400 additional lines removable

---

## Success Criteria

- ✅ All new candidates investigated
- ✅ Additional cleanup opportunities identified
- ✅ E2E tests pass after each cleanup
- ✅ Coverage improves further (target: 45-50%)

---

## Notes

- **Phase 3 High and Medium Priority batches are complete**
- **Most low-coverage files have been addressed**
- **Remaining opportunities are lower priority**
- **Consider Phase 3 complete if remaining cleanup is not worth the effort**

