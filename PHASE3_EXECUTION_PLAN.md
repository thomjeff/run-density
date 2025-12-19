# Phase 3 Execution Plan

**Issue:** #544  
**Date:** December 19, 2025  
**Status:** 🟢 Approved - Ready to Execute

---

## Approved Workflow

### ✅ High Priority Batch (3 files)
1. Investigate each file
2. Make improvements (remove unused code)
3. Run `make e2e-coverage-lite DAY=sat` to verify
4. Commit if tests pass

### ✅ Medium Priority Batch (4 files)
1. Investigate each file
2. Make improvements (remove unused code)
3. Run `make e2e-coverage-lite DAY=sat` to verify
4. Commit if tests pass

---

## High Priority Batch (3 files)

### File 1: `app/density_report.py` (22.1%, 1,695 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `AnalysisContext` - Used by `app/core/v2/bins.py`
- ✅ `_generate_bin_dataset_with_retry` - Used by `app/core/v2/bins.py`
- ✅ `_save_bin_artifacts_and_metadata` - Used by `app/core/v2/bins.py`
- ✅ `_process_segments_from_bins` - Used by `app/core/v2/bins.py`
- ✅ `generate_map_dataset` - Used by `app/core/v2/pipeline.py`
- ✅ `generate_new_density_report_issue246` - Used by `app/core/v2/reports.py`

**v1 API Dependencies (CAN REMOVE IF v1 API DEPRECATED):**
- ⚠️ `generate_density_report` - Used by `/api/density-report` endpoint (lazy import in main.py)
- ⚠️ `generate_simple_density_report` - Used by v1 API
- ⚠️ All report generation functions used only by v1 API

**Investigation Plan:**
1. [ ] Identify all functions used by v2 pipeline (list above)
2. [ ] Identify all functions used only by v1 API
3. [ ] Check if v1 API endpoints are still needed
4. [ ] Remove v1-only functions if v1 API is deprecated
5. [ ] Test with E2E

**Estimated Impact:** ~500-800 lines removable (if v1 API deprecated)

---

### File 2: `app/bin_intelligence.py` (20.7%, 114 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `get_flagged_bins` - Used by `app/core/bin/summary.py` (v2 pipeline)
- ✅ `FlaggingConfig` - Used by `app/density_report.py` (which is used by v2)
- ✅ `apply_bin_flagging` - Used by `app/density_report.py`
- ✅ `summarize_segment_flags` - Used by `app/density_report.py`
- ✅ `get_flagging_statistics` - Used by `app/density_report.py`

**v1 API Dependencies (CAN REMOVE IF v1 API DEPRECATED):**
- ⚠️ Functions used only by `app/density_report.py` v1 API paths

**Investigation Plan:**
1. [ ] Verify which functions are used by v2 pipeline (via `app/core/bin/summary.py`)
2. [ ] Verify which functions are used only by v1 API (via `app/density_report.py`)
3. [ ] Remove v1-only functions if v1 API is deprecated
4. [ ] Test with E2E

**Estimated Impact:** ~50-100 lines removable (if v1 API deprecated)

---

### File 3: `app/canonical_segments.py` (20.9%, 86 statements)

**v1 API Dependencies (CAN REMOVE IF v1 API DEPRECATED):**
- ⚠️ `is_canonical_segments_available` - Used by `app/main.py` (v1 API endpoint)
- ⚠️ `get_canonical_segments_metadata` - Used by `app/main.py` (v1 API endpoint)
- ⚠️ `get_canonical_segments` - Used by `app/density_report.py` (v1 API)

**Investigation Plan:**
1. [ ] Check if used by v2 pipeline (grep for imports)
2. [ ] Check if v1 API endpoints using it are still needed
3. [ ] Remove if only used by v1 API and v1 API is deprecated
4. [ ] Test with E2E

**Estimated Impact:** ~50-80 lines removable (if v1 API deprecated)

---

## Medium Priority Batch (4 files)

### File 4: `app/density_template_engine.py` (32.2%, 244 statements)
- Used by `app/density_report.py` (v1 API)
- Review if v1 API needed
- **Estimated Impact:** ~100-150 lines

### File 5: `app/overlap.py` (29.6%, 228 statements)
- Legacy flow analysis code
- Review if replaced by v2 flow
- **Estimated Impact:** ~100-150 lines

### File 6: `app/version.py` (15.1%, 114 statements)
- Simplify version detection logic
- **Estimated Impact:** ~50-100 lines

### File 7: `app/routes/api_heatmaps.py` (40.5%, 33 statements)
- Verify frontend usage
- **Estimated Impact:** ~20-30 lines

---

## Execution Checklist

### High Priority Batch

- [ ] **Investigate `app/density_report.py`**
  - [ ] Map v2-used vs v1-only functions
  - [ ] Document dependencies
  - [ ] Plan removals

- [ ] **Investigate `app/bin_intelligence.py`**
  - [ ] Verify v2 pipeline usage
  - [ ] Identify v1-only functions
  - [ ] Plan removals

- [ ] **Investigate `app/canonical_segments.py`**
  - [ ] Check v2 pipeline usage
  - [ ] Verify v1 API dependency
  - [ ] Plan removals

- [ ] **Make improvements (remove unused code)**
  - [ ] Remove v1-only functions from all 3 files
  - [ ] Preserve v2-used functions
  - [ ] Update imports if needed

- [ ] **Test: `make e2e-coverage-lite DAY=sat`**
  - [ ] Verify all endpoints UP
  - [ ] Verify reports generated
  - [ ] Check coverage improvement
  - [ ] Review logs for errors

- [ ] **Commit if tests pass**
  - [ ] Commit message: "Phase 3: Remove v1-only code from high priority files"
  - [ ] Update cleanup log

### Medium Priority Batch

- [ ] **Investigate all 4 files**
  - [ ] Document usage and dependencies
  - [ ] Plan removals

- [ ] **Make improvements (remove unused code)**
  - [ ] Remove unused functions/code
  - [ ] Preserve active code

- [ ] **Test: `make e2e-coverage-lite DAY=sat`**
  - [ ] Verify all endpoints UP
  - [ ] Verify reports generated
  - [ ] Check coverage improvement
  - [ ] Review logs for errors

- [ ] **Commit if tests pass**
  - [ ] Commit message: "Phase 3: Remove unused code from medium priority files"
  - [ ] Update cleanup log

---

## Success Criteria

- ✅ All v2 pipeline dependencies preserved
- ✅ v1-only code removed (if v1 API deprecated)
- ✅ E2E tests pass after each batch
- ✅ Coverage improves to 45-50% target
- ✅ No functionality broken

---

## Notes

- **v1 API Status:** Need to determine if v1 API is deprecated or still needed
- **Surgical Approach:** Focus on removing unused functions, not entire files
- **Test After Each Batch:** Run E2E tests to verify no breakage
- **Documentation:** Update cleanup log after each successful batch

