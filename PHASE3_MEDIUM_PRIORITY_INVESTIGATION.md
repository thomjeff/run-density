# Phase 3 Medium Priority Investigation Results

**Date:** December 19, 2025  
**Status:** 🔍 Investigation Complete - Ready for Cleanup Decisions

---

## Summary

### File 1: `app/density_template_engine.py` (32.2%, 244 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `resolve_schema()` - Used by `app/core/density/compute.py` (v2 pipeline)
- ✅ `resolve_schema_with_flow_type()` - Used by `app/core/density/compute.py` (v2 pipeline)
- ✅ `get_schema_config()` - Used by `app/core/density/compute.py` (v2 pipeline)
- ✅ `compute_flow_rate()` - Used by `app/core/density/compute.py` (v2 pipeline)
- ✅ `evaluate_triggers()` - Used by `app/core/density/compute.py` (v2 pipeline)

**v1 API Dependencies (CAN REMOVE):**
- ⚠️ `DensityTemplateEngine` class - Used by `app/density_report.py` (v1 API, but we removed those functions)
- ⚠️ `create_template_context()` - Used by `app/density_report.py` (v1 API, but we removed those functions)
- ⚠️ `map_los()` - May be unused or only used by v1

**Investigation Needed:**
- [ ] Check if `DensityTemplateEngine` class is used anywhere else
- [ ] Check if `create_template_context()` is used anywhere else
- [ ] Check if `map_los()` is used anywhere else

**Result:** ✅ **RETAIN** - Core functions used by v2 pipeline, but can remove unused v1-only functions

**Estimated Impact:** ~50-100 lines removable (if v1-only functions identified)

---

### File 2: `app/overlap.py` (29.6%, 228 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `calculate_true_pass_detection()` - Used by `app/core/flow/flow.py` (v2 pipeline)
- ✅ `calculate_convergence_point()` - Used by `app/core/flow/flow.py` (v2 pipeline, aliased as `calculate_co_presence`)

**v1 API Dependencies (CAN REMOVE):**
- ⚠️ `analyze_overlaps()` - May be v1-only
- ⚠️ `detect_overlaps_at_km()` - May be v1-only
- ⚠️ `generate_overlap_narrative()` - May be v1-only
- ⚠️ `generate_overlap_trace()` - May be v1-only
- ⚠️ `generate_overlap_narrative_convergence()` - May be v1-only
- ⚠️ `_segment_totals()` - May be v1-only
- ⚠️ `calculate_convergence_zone_overlaps()` - May be v1-only
- ⚠️ `format_bib_range()` - May be v1-only

**Investigation Needed:**
- [ ] Check if other functions are used by v2 or only by v1 API
- [ ] Verify if v1 API endpoints using these functions are still needed

**Result:** ✅ **RETAIN** - Core functions used by v2 pipeline, but can remove unused v1-only functions

**Estimated Impact:** ~100-150 lines removable (if v1-only functions identified)

---

### File 3: `app/version.py` (15.1%, 114 statements)

**Build Script Dependencies (MUST PRESERVE):**
- ✅ `get_current_version()` - Used by `scripts/bump_version.sh` (build script)
- ✅ `get_next_version()` - Used by `scripts/bump_version.sh` (build script)
- ✅ `update_version_in_code()` - Used by `scripts/bump_version.sh` (build script)
- ✅ `parse_version()` - Used by other functions
- ✅ `format_version()` - Used by other functions
- ✅ `validate_version_consistency()` - May be used by CI/CD
- ✅ `create_version_bump_script()` - Used to generate build script

**v1 API Dependencies (CAN REMOVE):**
- ⚠️ Used by `app/density_report.py` (v1 API, but we removed those functions)
- ⚠️ Used by `app/flow_report.py` (v1 API)

**Investigation Needed:**
- [ ] Check if `app/flow_report.py` is still used (v1 API)
- [ ] Verify if all functions are needed for build scripts

**Result:** ✅ **RETAIN** - Used by build scripts, but can simplify if unused functions exist

**Estimated Impact:** ~20-30 lines removable (if unused functions identified)

---

### File 4: `app/routes/api_heatmaps.py` (40.5%, 33 statements)

**Current Status:**
- ✅ Router registered in `main.py`: `app.include_router(api_heatmaps_router, prefix="/api/generate", tags=["heatmaps"])`
- ✅ Endpoint: `POST /api/generate/heatmaps`
- ⚠️ Frontend uses static file serving: `/heatmaps/<run_id>/<seg_id>.png` (not API endpoint)
- ⚠️ No frontend calls to `/api/generate/heatmaps` found

**Investigation Needed:**
- [ ] Check if endpoint is called by E2E tests
- [ ] Check if endpoint is called by any other code
- [ ] Verify if endpoint is needed for on-demand heatmap generation

**Result:** ⚠️ **INVESTIGATE** - Router exists but may not be used

**Estimated Impact:** ~33 lines removable (entire file) if unused

---

## Cleanup Plan

### Action Items:

1. **`app/density_template_engine.py`**: Remove v1-only functions (~50-100 lines)
   - Check if `DensityTemplateEngine` class is used
   - Check if `create_template_context()` is used
   - Check if `map_los()` is used
   - Preserve all v2-used functions

2. **`app/overlap.py`**: Remove v1-only functions (~100-150 lines)
   - Check which functions are only used by v1 API
   - Preserve `calculate_true_pass_detection()` and `calculate_convergence_point()`

3. **`app/version.py`**: Simplify if possible (~20-30 lines)
   - Check if all functions are needed for build scripts
   - Remove unused functions if any

4. **`app/routes/api_heatmaps.py`**: Remove if unused (~33 lines)
   - Verify endpoint is not called by E2E tests or other code
   - Remove router registration if unused

---

## Risk Assessment

- **Low Risk:** Removing v1-only functions from `app/density_template_engine.py` and `app/overlap.py` since v2 functions are preserved
- **Low Risk:** Simplifying `app/version.py` if unused functions identified
- **Medium Risk:** Removing `app/routes/api_heatmaps.py` - need to verify it's truly unused

---

## Next Steps

1. Investigate each file to identify unused functions
2. Remove unused code
3. Run `make e2e-coverage-lite DAY=sat` to verify
4. Commit if tests pass

