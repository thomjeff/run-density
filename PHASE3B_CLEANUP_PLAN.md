# Phase 3B: Final Cleanup Plan

**Issue:** #544  
**Date:** December 19, 2025  
**Status:** 🔍 Investigation Complete - Ready for Cleanup

---

## Summary

After investigation, most low coverage is due to:
- Error handling paths (not executed in normal flow)
- CLI interfaces (not used during E2E tests)
- Conditional code paths (legitimately only executed under certain conditions)

**Actual unused code found:**
- `app/version.py`: CLI interface (~40 lines) - Not used during E2E tests, but useful for manual operations
- Other files: All functions appear to be used, low coverage is from conditional execution

---

## Cleanup Decisions

### 1. `app/version.py` (15.1% coverage)

**Status:** ⚠️ **MINIMAL CLEANUP** - CLI interface is unused during E2E but useful for manual operations

**Decision:** ✅ **KEEP CLI** - Useful for build scripts and manual version management

**No cleanup needed** - All functions are used by build scripts or other code paths.

---

### 2. `app/heatmap_generator.py` (10.9% coverage)

**Status:** ✅ **ALL FUNCTIONS USED**

**Functions:**
- `generate_heatmaps_for_run()` - ✅ Used by v2 pipeline (`app/core/v2/ui_artifacts.py`)
- `generate_segment_heatmap()` - ✅ Used by `generate_heatmaps_for_run()`
- `load_bin_data()` - ✅ Used by `generate_heatmaps_for_run()`
- `create_los_colormap()` - ✅ Used by `generate_segment_heatmap()`
- All helper functions - ✅ Used internally

**Low coverage reason:** Heatmaps are only generated for certain segments/conditions (expected behavior)

**No cleanup needed** - All code is actively used.

---

### 3. `app/api/map.py` (13.6% coverage)

**Status:** ✅ **ALL ACTIVE ENDPOINTS USED BY FRONTEND**

**Active Endpoints (Preserved):**
- `GET /api/map/manifest` - ✅ Used by frontend
- `GET /api/map/segments` - ✅ Used by frontend
- `GET /api/map/bins` - ✅ Used by frontend
- `GET /api/bins-data` - ✅ Used by frontend
- `POST /api/flow-bins` - ✅ Used by frontend
- `POST /api/export-bins` - ✅ Used by frontend
- `GET /api/map-config` - ✅ Used by frontend
- `GET /api/map-status` - ✅ Used by frontend

**Low coverage reason:** Endpoints have conditional logic and error handling (expected behavior)

**No cleanup needed** - All active endpoints are used by frontend.

---

### 4. `app/density_report.py` (23.7% coverage)

**Status:** ✅ **V2 FUNCTIONS PRESERVED, V1 CODE ALREADY REMOVED**

**v2 Pipeline Dependencies (Preserved):**
- `AnalysisContext` - ✅ Used by `app/core/v2/bins.py`
- `_generate_bin_dataset_with_retry` - ✅ Used by `app/core/v2/bins.py`
- `_save_bin_artifacts_and_metadata` - ✅ Used by `app/core/v2/bins.py`
- `_process_segments_from_bins` - ✅ Used by `app/core/v2/bins.py`
- `generate_map_dataset` - ✅ Used by `app/core/v2/pipeline.py`
- `generate_new_density_report_issue246` - ✅ Used by `app/core/v2/reports.py`

**Low coverage reason:** Large file with many conditional code paths and error handling (expected behavior)

**No cleanup needed** - v1-only code already removed, remaining code is used by v2.

---

## Conclusion

**After thorough investigation, no additional unused code found.**

All low coverage is due to:
- Error handling paths (important for robustness)
- CLI interfaces (useful for manual operations)
- Conditional code paths (legitimately only executed under certain conditions)

**Recommendation:** ✅ **DECLARE PHASE 3 COMPLETE**

**Total Lines Removed in Phase 3:** ~1,862 lines
**Coverage Improvement:** 40% → 41.8% (+1.8%)
**Status:** ✅ All high and medium priority files cleaned

---

## Next Steps

1. ✅ Run final E2E test to verify no regressions
2. ✅ Commit Phase 3B investigation results
3. ✅ Declare Phase 3 complete
4. ⏭️ Move to other priorities or Phase 4 (if desired)

