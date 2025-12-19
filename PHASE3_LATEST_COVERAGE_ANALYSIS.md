# Phase 3: Latest Coverage Analysis (Run RQ8sSt6Q6YfJhQwKFFcBYS)

**Issue:** #544  
**Date:** December 19, 2025  
**Coverage Report:** Run ID `RQ8sSt6Q6YfJhQwKFFcBYS`  
**Status:** 🔍 Analysis Complete

---

## Executive Summary

**Total Files with 10-49% Coverage:** 30 files  
**Files Already Cleaned:** 14 files  
**New Candidates for Cleanup:** 8 files  
**Files Retained (Essential):** 8 files

**Coverage Improvement Since Baseline:**
- Baseline: 40% (before Phase 3)
- Current: 41.8% (Run RQ8sSt6Q6YfJhQwKFFcBYS)
- Improvement: +1.8%

---

## Files Already Cleaned (Still Low Coverage)

These files have been partially cleaned but still show low coverage. May need further investigation:

| File | Current Coverage | Previous Status | Notes |
|------|-----------------|-----------------|-------|
| `app/routes/api_segments.py` | 10.5% (107 stmts) | ✅ **CLEANED** (removed 2 unused imports) | May have more unused code |
| `app/heatmap_generator.py` | 10.9% (165 stmts) | ✅ **CLEANED** (removed 1 function + legacy code) | Large file, may have more unused functions |
| `app/geo_utils.py` | 11.0% (97 stmts) | ✅ **CLEANED** (removed 2 unused functions) | May have more unused functions |
| `app/routes/api_bins.py` | 12.3% (55 stmts) | ✅ **CLEANED** (removed 1 endpoint) | Small file, may be fully used |
| `app/routes/api_dashboard.py` | 12.4% (117 stmts) | ✅ **CLEANED** (removed 2 helper functions) | May have more unused helpers |
| `app/api/map.py` | 13.6% (272 stmts) | ✅ **CLEANED** (removed 7 endpoints) | Large file, may have more unused endpoints |
| `app/bin_analysis.py` | 16.3% (272 stmts) | ✅ **CLEANED** (removed 3 functions) | ✅ **RETAINED** - All remaining functions used |
| `app/core/bin/geometry.py` | 18.2% (57 stmts) | ✅ **CLEANED** (removed 4 functions) | Small file, may be fully used |
| `app/routes/api_locations.py` | 18.7% (73 stmts) | ✅ **CLEANED** (removed unreachable code) | May have more unused code |
| `app/storage.py` | 23.5% (71 stmts) | ✅ **CLEANED** (removed 6 methods + 8 helpers) | Core infrastructure, likely fully used now |
| `app/los.py` | 22.6% (39 stmts) | ✅ **CLEANED** (removed 4 functions) | Small file, may be fully used |
| `app/density_report.py` | 23.7% (1,535 stmts) | ✅ **CLEANED** (removed 413 lines v1-only) | Large file, may have more v1-only code |

**Recommendation:** Review these files for additional unused code, especially:
- `app/heatmap_generator.py` (10.9%, 165 stmts) - Large file with low coverage
- `app/api/map.py` (13.6%, 272 stmts) - Large file with low coverage
- `app/density_report.py` (23.7%, 1,535 stmts) - Very large file, may have more v1-only code

---

## New Candidates for Cleanup (Not Yet Reviewed)

These files have 10-49% coverage but haven't been investigated yet:

### 🔴 High Priority: <20% Coverage (3 files)

| File | Coverage | Statements | Missing | Risk | Recommendation |
|------|----------|------------|---------|------|----------------|
| `app/version.py` | 15.1% | 114 | 94 | ✅ Low | Review - Simplify version detection logic |
| `app/api/flow.py` | 19.6% | 43 | 33 | ✅ Low | ✅ **RETAINED** - Used via wrapper (already investigated) |

**Note:** `app/api/flow.py` was already investigated and retained (used via `app/routes/api_flow.py` wrapper).

### 🟡 Medium Priority: 20-35% Coverage (3 files)

| File | Coverage | Statements | Missing | Risk | Recommendation |
|------|----------|------------|---------|------|----------------|
| `app/bin_intelligence.py` | 20.7% | 114 | 86 | ⚠️ Medium | ✅ **RETAINED** - All functions used by v2 (already investigated) |
| `app/canonical_segments.py` | 20.9% | 86 | 65 | ⚠️ Medium | ✅ **RETAINED** - All functions used by v2 (already investigated) |
| `app/main.py` | 21.9% | 718 | 520 | ❌ High | ✅ **RETAINED** - Essential application entry point |

**Note:** `app/bin_intelligence.py` and `app/canonical_segments.py` were already investigated in High Priority Batch and retained.

### 🟢 Low Priority: 35-49% Coverage (2 files)

| File | Coverage | Statements | Missing | Risk | Recommendation |
|------|----------|------------|---------|------|----------------|
| `app/density_template_engine.py` | 33.0% | 236 | 146 | ⚠️ Medium | ✅ **CLEANED** - Removed v1-only code (already cleaned) |
| `app/paths.py` | 36.4% | 11 | 7 | ✅ Low | ✅ **RETAINED** - Used by v2 (already investigated) |

**Note:** `app/density_template_engine.py` was already cleaned in Medium Priority Batch.

---

## Files Retained (Essential - Do Not Clean)

These files have been investigated and determined to be essential:

| File | Coverage | Statements | Reason for Retention |
|------|----------|------------|---------------------|
| `app/api/flow.py` | 19.6% | 43 | Used via `app/routes/api_flow.py` wrapper |
| `app/bin_intelligence.py` | 20.7% | 114 | All functions used by v2 pipeline via `app/core/bin/summary.py` |
| `app/canonical_segments.py` | 20.9% | 86 | All functions used by v2 via `generate_map_dataset()` |
| `app/main.py` | 21.9% | 718 | Essential application entry point |
| `app/utils/run_id.py` | 23.7% | 78 | Core utility for runflow structure |
| `app/routes/ui.py` | 28.0% | 102 | Frontend dependency |
| `app/utils/auth.py` | 28.1% | 47 | Used by `app/routes/ui.py` for password protection |
| `app/utils/metadata.py` | 32.1% | 154 | Core utility for runflow structure |
| `app/paths.py` | 36.4% | 11 | Used by v2 pipeline via `report_utils.py` → `location_report.py` |
| `app/core/flow/flow.py` | 36.9% | 1,394 | Core v2 module |
| `app/routes/api_health.py` | 40.0% | 28 | Essential monitoring endpoints |
| `app/core/artifacts/frontend.py` | 40.4% | 465 | Core v2 module |
| `app/schema_resolver.py` | 40.7% | 17 | Core utility for flagging |
| `app/flagging.py` | 44.4% | 85 | Core utility (SSOT) |
| `app/core/bin/summary.py` | 44.8% | 155 | Core v2 module |
| `app/report_utils.py` | 47.8% | 85 | Core utility for report generation |

---

## Recommended Next Steps

### 1. 🔍 Further Investigation of Already-Cleaned Files

**Priority:** Review files that were cleaned but still show very low coverage:

1. **`app/heatmap_generator.py`** (10.9%, 165 stmts)
   - **Action:** Review for additional unused functions
   - **Risk:** Low - Already cleaned once
   - **Estimated Impact:** ~20-50 lines if more unused code found

2. **`app/api/map.py`** (13.6%, 272 stmts)
   - **Action:** Review for additional unused endpoints or functions
   - **Risk:** Low - Already cleaned once
   - **Estimated Impact:** ~50-100 lines if more unused code found

3. **`app/density_report.py`** (23.7%, 1,535 stmts)
   - **Action:** Review for additional v1-only code paths
   - **Risk:** Medium - Large file, may have more v1-only code
   - **Estimated Impact:** ~100-200 lines if more v1-only code found

### 2. ✅ Review `app/version.py` (15.1% coverage)

**Status:** Not yet investigated  
**Risk:** ✅ Low - Small file, mostly version detection logic  
**Action:** 
- Check which functions are actually called
- Verify if version detection logic is needed
- Simplify if possible

**Estimated Impact:** ~20-50 lines if unused functions found

### 3. 📊 Coverage Analysis Summary

**Files with <20% Coverage:** 12 files
- 10 files already cleaned (may need further review)
- 1 file not yet investigated (`app/version.py`)
- 1 file retained (`app/api/flow.py`)

**Files with 20-35% Coverage:** 10 files
- 3 files already investigated and retained
- 7 files essential (core infrastructure)

**Files with 35-49% Coverage:** 8 files
- All essential core modules or utilities

---

## Coverage Trends

### Before Phase 3
- **Baseline Coverage:** 40%
- **Files with 10-49% Coverage:** 34 files

### After Phase 3 (Current)
- **Current Coverage:** 41.8% (Run RQ8sSt6Q6YfJhQwKFFcBYS)
- **Files with 10-49% Coverage:** 30 files
- **Improvement:** +1.8% coverage, 4 fewer low-coverage files

### Lines Removed
- **High Priority Batch:** ~413 lines
- **Medium Priority Batch:** ~605 lines
- **Earlier Batches:** ~844 lines
- **Total Removed:** ~1,862 lines

---

## Risk Assessment

### ✅ Low Risk (Safe to Review)
- `app/version.py` (15.1%) - Small file, version detection logic
- `app/heatmap_generator.py` (10.9%) - Already cleaned once
- `app/api/map.py` (13.6%) - Already cleaned once

### ⚠️ Medium Risk (Requires Careful Review)
- `app/density_report.py` (23.7%) - Large file, may have more v1-only code
- Files already cleaned but still low coverage

### ❌ High Risk (Do Not Clean)
- `app/main.py` (21.9%) - Essential application entry point
- `app/core/flow/flow.py` (36.9%) - Core v2 module
- All files marked as "Essential" in retention list

---

## Conclusion

**Status:** Phase 3 High and Medium Priority batches are **complete**. The latest coverage report shows:

1. **Most low-coverage files have been addressed** (14 files cleaned)
2. **Essential files are properly retained** (16 files)
3. **Remaining opportunities:**
   - Further cleanup of already-cleaned files (3 files)
   - Review `app/version.py` (1 file)

**Next Phase Options:**
1. **Phase 3B:** Further cleanup of already-cleaned files
2. **Phase 4:** Review files with 50%+ coverage for unused functions
3. **Complete:** Consider Phase 3 complete and move to other priorities

**Recommendation:** Review `app/version.py` and the 3 already-cleaned files with very low coverage for additional cleanup opportunities.

