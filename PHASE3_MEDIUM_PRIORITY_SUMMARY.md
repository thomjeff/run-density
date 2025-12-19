# Phase 3 Medium Priority Batch - Investigation Summary

**Date:** December 19, 2025  
**Status:** 🔍 Investigation Complete

---

## Findings

### File 1: `app/density_template_engine.py` (32.2%, 244 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `resolve_schema()` - Used by `app/core/density/compute.py`
- ✅ `resolve_schema_with_flow_type()` - Used by `app/core/density/compute.py`
- ✅ `get_schema_config()` - Used by `app/core/density/compute.py`
- ✅ `compute_flow_rate()` - Used by `app/core/density/compute.py`
- ✅ `evaluate_triggers()` - Used by `app/core/density/compute.py`

**Unused Functions (CAN REMOVE):**
- ❌ `map_los()` - Not imported anywhere (unused)
- ❌ `DensityTemplateEngine` class - Only imported by `app/density_report.py` (v1 API functions removed)
- ❌ `create_template_context()` - Only imported by `app/density_report.py` (v1 API functions removed)

**Result:** ✅ **RETAIN** core functions, remove unused ones

**Estimated Impact:** ~150-200 lines removable (DensityTemplateEngine class + create_template_context + map_los)

---

### File 2: `app/overlap.py` (29.6%, 228 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `calculate_true_pass_detection()` - Used by `app/core/flow/flow.py`
- ✅ `calculate_convergence_point()` - Used by `app/core/flow/flow.py`

**Unused Functions (CAN REMOVE):**
- ❌ `analyze_overlaps()` - Not imported anywhere
- ❌ `detect_overlaps_at_km()` - Only used internally by other unused functions
- ❌ `generate_overlap_narrative()` - Not imported anywhere
- ❌ `generate_overlap_trace()` - Not imported anywhere
- ❌ `generate_overlap_narrative_convergence()` - Not imported anywhere
- ❌ `_segment_totals()` - Only used by unused functions
- ❌ `calculate_convergence_zone_overlaps()` - Not imported (v2 has its own implementation)
- ❌ `format_bib_range()` - Not imported (v2 has its own implementation)

**Result:** ✅ **RETAIN** v2-used functions, remove unused ones

**Estimated Impact:** ~150-180 lines removable (7 unused functions)

---

### File 3: `app/version.py` (15.1%, 114 statements)

**Build Script Dependencies (MUST PRESERVE):**
- ✅ All functions used by `scripts/bump_version.sh` (build script)
- ✅ Used by v1 API (`app/flow_report.py` - still exists)

**Result:** ✅ **RETAIN** - Used by build scripts and v1 API

**Estimated Impact:** 0 lines (no cleanup needed)

---

### File 4: `app/routes/api_heatmaps.py` (40.5%, 33 statements)

**Current Status:**
- ✅ Router registered in `main.py`: `app.include_router(api_heatmaps_router, prefix="/api/generate", tags=["heatmaps"])`
- ✅ Endpoint: `POST /api/generate/heatmaps`
- ❌ No calls found in:
  - Frontend code (uses static file serving instead)
  - E2E tests
  - Other app code

**Result:** ⚠️ **LIKELY UNUSED** - Router exists but endpoint not called

**Estimated Impact:** ~33 lines removable (entire file + router registration)

---

## Cleanup Plan

### Priority 1: Safe Removals (High Confidence)
1. Remove `map_los()` from `app/density_template_engine.py` (~10 lines)
2. Remove unused functions from `app/overlap.py` (~150-180 lines)
3. Remove `app/routes/api_heatmaps.py` and router registration (~40 lines)

### Priority 2: Larger Removals (Requires More Care)
4. Remove `DensityTemplateEngine` class and `create_template_context()` from `app/density_template_engine.py` (~150-200 lines)
   - These are large, need to verify they're truly unused

---

## Next Steps

1. Remove safe candidates (map_los, overlap unused functions, api_heatmaps)
2. Run E2E test to verify
3. If successful, consider removing DensityTemplateEngine class
4. Commit if tests pass

