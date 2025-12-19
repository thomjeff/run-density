# Phase 3: Detailed File Analysis (10-49% Coverage)

**Issue:** #544  
**Generated:** December 18, 2025  
**Coverage Source:** Latest E2E test run  
**Total Files:** 34 files

---

## Analysis Methodology

For each file, we analyze:
1. **Coverage Details:** Percentage, statements, covered/missing lines
2. **Purpose:** What the file does
3. **Usage:** Where it's imported/called
4. **Functions:** Which functions are covered vs not covered
5. **Risk Level:** Low/Medium/High based on usage
6. **Recommendation:** Keep, Remove, or Refactor

---

## Priority 1: Files with <20% Coverage (Highest Impact)

### 1. `app/routes/api_dashboard.py` (10.1%, 161 statements, 21 covered, 140 missing)

**Purpose:** API routes for dashboard KPI tiles (`/api/dashboard/summary`)

**Usage:**
- ✅ **Frontend dependency:** `frontend/templates/pages/dashboard.html` calls `/api/dashboard/summary`
- ✅ **Registered in main.py:** `app.include_router(api_dashboard_router)`
- ✅ **Used by:** Dashboard page, segments page (for day metadata)

**Functions:**
- `get_dashboard_summary()` - Main endpoint (covered)
- `count_runners_for_events()` - Helper (likely unused)
- `load_bins_flagged_count()` - Helper (likely unused)
- `calculate_peak_density_los()` - Helper (likely unused)
- `_load_ui_artifact_safe()` - Helper (covered)
- `_calculate_flags_metrics()` - Helper (likely unused)
- `_calculate_peak_metrics()` - Helper (likely unused)

**Risk:** ⚠️ **Medium** - Frontend dependency, but many helper functions unused

**Recommendation:** 
- ✅ **KEEP** - Main endpoint is used
- 🔍 **Review** - Remove unused helper functions (`count_runners_for_events`, `load_bins_flagged_count`, etc.)

---

### 2. `app/heatmap_generator.py` (10.5%, 192 statements, 25 covered, 167 missing)

**Purpose:** Generate PNG heatmaps for segments from bin data

**Usage:**
- ✅ **Used by v2 pipeline:** Called from `app/core/v2/ui_artifacts.py` (via `app/core/artifacts/heatmaps.py`)
- ✅ **Used by:** `app/density_report.py` (legacy v1 API)
- ✅ **Used by:** `app/routes/api_heatmaps.py` (v1 API endpoint)

**Functions:**
- `generate_heatmaps_for_run()` - Main function (covered)
- `generate_segment_heatmap()` - Core generation (covered)
- `load_bin_data()` - Data loading (covered)
- `create_los_colormap()` - Colormap creation (likely unused)
- `load_segments_metadata()` - Metadata loading (likely unused)
- `_get_time_field_value()` - Helper (likely unused)
- `_extract_times_and_distances()` - Helper (likely unused)
- `_create_density_matrix()` - Helper (covered)
- `_format_time_string()` - Helper (likely unused)
- `_get_segment_title()` - Helper (likely unused)
- `_setup_heatmap_axes()` - Helper (covered)
- `get_heatmap_files()` - Helper (likely unused)

**Risk:** ⚠️ **Medium** - Used by v2 pipeline, but many helper functions unused

**Recommendation:**
- ✅ **KEEP** - Core functionality used by v2
- 🔍 **Review** - Remove unused helper functions

---

### 3. `app/core/bin/geometry.py` (11.5%, 130 statements, 20 covered, 110 missing)

**Purpose:** Generate bin polygon geometries from centerlines

**Usage:**
- ✅ **Used by v2 pipeline:** Called from `app/core/v2/bins.py` (via `app/density_report.py`)
- ✅ **Used by:** Bin generation process

**Functions:**
- `generate_bin_polygon()` - Main function (covered)
- Other geometry helper functions (likely partially unused)

**Risk:** ⚠️ **Medium** - Used by v2 pipeline

**Recommendation:**
- ✅ **KEEP** - Core functionality
- 🔍 **Review** - Check which geometry functions are actually used

---

### 4. `app/routes/api_segments.py` (11.6%, 109 statements, 18 covered, 91 missing)

**Purpose:** API routes for segment data (`/api/segments.geojson`)

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(api_segments_router)`
- ⚠️ **Frontend usage:** Need to verify if used by frontend

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 5. `app/routes/reports.py` (11.6%, 170 statements, 26 covered, 144 missing)

**Purpose:** API routes for reports page

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(reports_router)`
- ⚠️ **Frontend usage:** Need to verify

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 6. `app/bin_analysis.py` (12.8%, 355 statements, 61 covered, 294 missing)

**Purpose:** Bin-level analysis functions (caching, trends, comparisons)

**Usage:**
- ✅ **Used by:** `app/api/map.py` (v1 map API)
- ⚠️ **May be used by:** Other analysis functions

**Risk:** ⚠️ **Medium** - Used by v1 map API (not used by frontend)

**Recommendation:**
- 🔍 **Review** - Check if v1 map API is needed
- ⚠️ **Consider removal** - If map API not used by frontend

---

### 7. `app/api/map.py` (12.9%, 429 statements, 69 covered, 360 missing)

**Purpose:** Map API endpoints (`/api/map/*`)

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(map_router)`
- ⚠️ **Frontend usage:** Need to verify

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 8. `app/routes/api_bins.py` (13.1%, 85 statements, 14 covered, 71 missing)

**Purpose:** API routes for bin data

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(api_bins_router)`
- ⚠️ **Frontend usage:** Need to verify

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 9. `app/los.py` (13.4%, 81 statements, 16 covered, 65 missing)

**Purpose:** Level of Service (LOS) calculation utilities

**Usage:**
- ✅ **Used by:** Multiple modules (density_report, flagging, etc.)
- ✅ **Core utility:** LOS calculations are fundamental

**Risk:** ⚠️ **Medium** - Core utility, but many functions unused

**Recommendation:**
- ✅ **KEEP** - Core functionality
- 🔍 **Review** - Remove unused LOS helper functions

---

### 10. `app/version.py` (15.1%, 114 statements, 20 covered, 94 missing)

**Purpose:** Version management and app version detection

**Usage:**
- ✅ **Used by:** `app/main.py` (APP_VERSION)
- ✅ **Used by:** Report generation (version headers)

**Risk:** ✅ **Low** - Small file, mostly version detection logic

**Recommendation:**
- ✅ **KEEP** - Needed for version reporting
- 🔍 **Review** - Simplify if possible

---

### 11. `app/storage.py` (15.9%, 178 statements, 33 covered, 145 missing)

**Purpose:** Storage abstraction layer (local filesystem)

**Usage:**
- ✅ **Used by:** v2 pipeline (`create_runflow_storage()`)
- ✅ **Used by:** Multiple routes and modules
- ✅ **Core infrastructure:** Essential for file operations

**Risk:** ❌ **High** - Core infrastructure

**Recommendation:**
- ✅ **KEEP** - Essential infrastructure
- 🔍 **Review** - Remove unused storage methods if any

---

### 12. `app/cache_manager.py` (18.6%, 221 statements, 50 covered, 171 missing)

**Purpose:** Cache management for analysis results

**Usage:**
- ✅ **Used by:** `app/api/map.py` (v1 map API)
- ⚠️ **May be used by:** Other modules

**Risk:** ⚠️ **Medium** - Used by v1 map API

**Recommendation:**
- 🔍 **Review** - Check if v1 map API is needed
- ⚠️ **Consider removal** - If map API not used by frontend

---

### 13. `app/routes/api_locations.py` (18.7%, 73 statements, 17 covered, 56 missing)

**Purpose:** API routes for location data

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(api_locations_router)`
- ⚠️ **Frontend usage:** Need to verify

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 14. `app/api/flow.py` (19.6%, 43 statements, 10 covered, 33 missing)

**Purpose:** Flow API endpoints (v1 API)

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(density_router)` (commented out)
- ⚠️ **Status:** May be legacy/unused

**Risk:** ✅ **Low** - Small file, likely legacy

**Recommendation:**
- 🔍 **Investigate** - Check if used
- ⚠️ **Consider removal** - If not used

---

## Priority 2: Files with 20-35% Coverage

### 15. `app/bin_intelligence.py` (20.7%, 114 statements, 28 covered, 86 missing)

**Purpose:** Bin flagging and operational intelligence

**Usage:**
- ✅ **Used by:** `app/density_report.py` (v1 API)
- ✅ **Used by:** Report generation

**Risk:** ⚠️ **Medium** - Used by v1 API

**Recommendation:**
- 🔍 **Review** - Check if v1 API is needed
- ✅ **KEEP** - If used by reports

---

### 16. `app/canonical_segments.py` (20.9%, 86 statements, 21 covered, 65 missing)

**Purpose:** Canonical segments utilities

**Usage:**
- ✅ **Used by:** `app/density_report.py` (v1 API)
- ⚠️ **Status:** May be legacy

**Risk:** ⚠️ **Medium** - Used by v1 API

**Recommendation:**
- 🔍 **Review** - Check if v1 API is needed
- ⚠️ **Consider removal** - If v1 API deprecated

---

### 17. `app/density_report.py` (22.1%, 1695 statements, 422 covered, 1273 missing)

**Purpose:** Density report generation (v1 API)

**Usage:**
- ✅ **Used by:** `/api/density-report` endpoint (v1 API, lazy import)
- ✅ **Used by:** v2 pipeline (via `app/core/v2/bins.py` - imports `AnalysisContext`, etc.)
- ⚠️ **Status:** Large file, partially used

**Risk:** ⚠️ **Medium** - Used by v2 pipeline for some functions

**Recommendation:**
- ✅ **KEEP** - Core functions used by v2
- 🔍 **Review** - Extract v2-used functions, remove v1-only code

---

### 18. `app/main.py` (22.7%, 722 statements, 206 covered, 516 missing)

**Purpose:** Main FastAPI application entry point

**Usage:**
- ✅ **Core file:** Application entry point
- ✅ **Contains:** All route registrations, v1 API endpoints

**Risk:** ❌ **High** - Core application file

**Recommendation:**
- ✅ **KEEP** - Essential
- 🔍 **Review** - Remove unused v1 API endpoints (already done in Phase 2B)

---

### 19. `app/api/density.py` (23.2%, 70 statements, 19 covered, 51 missing)

**Purpose:** Density API endpoints (v1 API)

**Usage:**
- ✅ **Registered in main.py:** Commented out (`# app.include_router(density_router)`)
- ⚠️ **Status:** Likely legacy/unused

**Risk:** ✅ **Low** - Not registered, likely unused

**Recommendation:**
- ⚠️ **Consider removal** - If not used

---

### 20. `app/utils/run_id.py` (23.7%, 78 statements, 23 covered, 55 missing)

**Purpose:** Run ID utilities (UUID generation, latest run detection)

**Usage:**
- ✅ **Used by:** v2 pipeline
- ✅ **Used by:** Multiple routes (`api_dashboard`, `api_density`, `api_reports`)
- ✅ **Core utility:** Essential for runflow structure

**Risk:** ❌ **High** - Core utility

**Recommendation:**
- ✅ **KEEP** - Essential infrastructure
- 🔍 **Review** - Remove unused helper functions if any

---

### 21. `app/routes/ui.py` (28.0%, 102 statements, 33 covered, 69 missing)

**Purpose:** UI route handlers

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(ui_router)`
- ✅ **Used by:** Frontend pages

**Risk:** ❌ **High** - Frontend dependency

**Recommendation:**
- ✅ **KEEP** - Frontend dependency
- 🔍 **Review** - Remove unused route handlers if any

---

### 22. `app/utils/auth.py` (28.1%, 47 statements, 16 covered, 31 missing)

**Purpose:** Authentication utilities

**Usage:**
- ⚠️ **Status:** Need to verify if used

**Risk:** ⚠️ **Medium** - May be unused

**Recommendation:**
- 🔍 **Investigate** - Check if authentication is used
- ⚠️ **Consider removal** - If not used

---

### 23. `app/overlap.py` (29.6%, 228 statements, 74 covered, 154 missing)

**Purpose:** Overlap analysis (legacy flow analysis)

**Usage:**
- ⚠️ **Status:** Legacy code, may be replaced by v2 flow

**Risk:** ⚠️ **Medium** - May be legacy

**Recommendation:**
- 🔍 **Review** - Check if used by v2 or legacy only
- ⚠️ **Consider removal** - If replaced by v2 flow

---

### 24. `app/utils/metadata.py` (32.1%, 154 statements, 56 covered, 98 missing)

**Purpose:** Metadata utilities (run metadata, latest.json)

**Usage:**
- ✅ **Used by:** v2 pipeline
- ✅ **Used by:** Multiple modules
- ✅ **Core utility:** Essential for runflow structure

**Risk:** ❌ **High** - Core utility

**Recommendation:**
- ✅ **KEEP** - Essential infrastructure
- 🔍 **Review** - Remove unused metadata functions if any

---

### 25. `app/density_template_engine.py` (32.2%, 244 statements, 91 covered, 153 missing)

**Purpose:** Template engine for density report generation

**Usage:**
- ✅ **Used by:** `app/density_report.py` (v1 API)
- ⚠️ **Status:** May be legacy

**Risk:** ⚠️ **Medium** - Used by v1 API

**Recommendation:**
- 🔍 **Review** - Check if v1 API is needed
- ⚠️ **Consider removal** - If v1 API deprecated

---

## Priority 3: Files with 35-49% Coverage

### 26. `app/paths.py` (36.4%, 11 statements, 4 covered, 7 missing)

**Purpose:** Path utilities

**Usage:**
- ⚠️ **Status:** Small file, need to verify usage

**Risk:** ✅ **Low** - Small file

**Recommendation:**
- 🔍 **Investigate** - Check if used
- ⚠️ **Consider removal** - If not used

---

### 27. `app/core/flow/flow.py` (36.9%, 1394 statements, 545 covered, 849 missing)

**Purpose:** Flow analysis core logic

**Usage:**
- ✅ **Used by:** v2 pipeline (`app/core/v2/flow.py`)
- ✅ **Core module:** Essential for flow analysis

**Risk:** ❌ **High** - Core v2 module

**Recommendation:**
- ✅ **KEEP** - Essential core module
- 🔍 **Review** - Remove unused flow analysis functions if any

---

### 28. `app/routes/api_health.py` (40.0%, 28 statements, 12 covered, 16 missing)

**Purpose:** Health check endpoints (`/health`, `/ready`)

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(api_health_router)`
- ✅ **Used by:** E2E tests, monitoring

**Risk:** ❌ **High** - Essential for monitoring

**Recommendation:**
- ✅ **KEEP** - Essential monitoring endpoints

---

### 29. `app/core/artifacts/frontend.py` (40.4%, 465 statements, 196 covered, 269 missing)

**Purpose:** Frontend artifact generation (UI artifacts)

**Usage:**
- ✅ **Used by:** v2 pipeline (`app/core/v2/ui_artifacts.py`)
- ✅ **Core module:** Essential for UI artifact generation

**Risk:** ❌ **High** - Core v2 module

**Recommendation:**
- ✅ **KEEP** - Essential core module
- 🔍 **Review** - Remove unused artifact generation functions if any

---

### 30. `app/routes/api_heatmaps.py` (40.5%, 33 statements, 15 covered, 18 missing)

**Purpose:** Heatmap API endpoints

**Usage:**
- ✅ **Registered in main.py:** `app.include_router(api_heatmaps_router)`
- ⚠️ **Frontend usage:** Need to verify

**Risk:** ⚠️ **Medium** - May be used by frontend

**Recommendation:**
- 🔍 **Investigate** - Check frontend usage
- ✅ **KEEP if used** - Otherwise consider removal

---

### 31. `app/schema_resolver.py` (40.7%, 17 statements, 8 covered, 9 missing)

**Purpose:** Schema resolution utilities

**Usage:**
- ✅ **Used by:** Flagging logic, rulebook evaluation
- ✅ **Core utility:** Used by operational intelligence

**Risk:** ⚠️ **Medium** - Core utility

**Recommendation:**
- ✅ **KEEP** - Core utility
- 🔍 **Review** - Small file, likely all used

---

### 32. `app/flagging.py` (44.4%, 85 statements, 47 covered, 38 missing)

**Purpose:** Flagging logic (SSOT for operational intelligence)

**Usage:**
- ✅ **Used by:** Multiple modules (density_report, bin_intelligence, etc.)
- ✅ **Core utility:** Essential for flagging

**Risk:** ❌ **High** - Core utility

**Recommendation:**
- ✅ **KEEP** - Essential core utility
- 🔍 **Review** - Remove unused flagging functions if any

---

### 33. `app/core/bin/summary.py` (44.8%, 155 statements, 72 covered, 83 missing)

**Purpose:** Bin summary generation

**Usage:**
- ✅ **Used by:** v2 pipeline (`app/core/v2/bins.py`)
- ✅ **Core module:** Essential for bin summaries

**Risk:** ❌ **High** - Core v2 module

**Recommendation:**
- ✅ **KEEP** - Essential core module
- 🔍 **Review** - Remove unused summary functions if any

---

### 34. `app/report_utils.py` (47.8%, 85 statements, 48 covered, 37 missing)

**Purpose:** Report utility functions (path generation, formatting)

**Usage:**
- ✅ **Used by:** Multiple modules (density_report, flow_report, etc.)
- ✅ **Core utility:** Essential for report generation

**Risk:** ❌ **High** - Core utility

**Recommendation:**
- ✅ **KEEP** - Essential core utility
- 🔍 **Review** - Remove unused utility functions if any

---

## Summary by Risk Level

### ❌ High Risk (Must Keep) - 10 files
- `app/storage.py` - Core infrastructure
- `app/main.py` - Application entry point
- `app/utils/run_id.py` - Core utility
- `app/routes/ui.py` - Frontend dependency
- `app/utils/metadata.py` - Core utility
- `app/core/flow/flow.py` - Core v2 module
- `app/routes/api_health.py` - Monitoring endpoints
- `app/core/artifacts/frontend.py` - Core v2 module
- `app/flagging.py` - Core utility
- `app/core/bin/summary.py` - Core v2 module
- `app/report_utils.py` - Core utility

### ⚠️ Medium Risk (Investigate/Review) - 20 files
- `app/routes/api_dashboard.py` - Frontend dependency, but many unused helpers
- `app/heatmap_generator.py` - Used by v2, but many unused helpers
- `app/core/bin/geometry.py` - Used by v2
- `app/routes/api_segments.py` - Need to verify frontend usage
- `app/routes/reports.py` - Need to verify frontend usage
- `app/bin_analysis.py` - Used by v1 map API
- `app/api/map.py` - Need to verify frontend usage
- `app/routes/api_bins.py` - Need to verify frontend usage
- `app/los.py` - Core utility, but many unused functions
- `app/cache_manager.py` - Used by v1 map API
- `app/routes/api_locations.py` - Need to verify frontend usage
- `app/api/flow.py` - Legacy v1 API
- `app/bin_intelligence.py` - Used by v1 API
- `app/canonical_segments.py` - Used by v1 API
- `app/density_report.py` - Large file, partially used by v2
- `app/api/density.py` - Legacy v1 API
- `app/utils/auth.py` - Need to verify usage
- `app/overlap.py` - Legacy code
- `app/density_template_engine.py` - Used by v1 API
- `app/routes/api_heatmaps.py` - Need to verify frontend usage
- `app/schema_resolver.py` - Core utility

### ✅ Low Risk (Consider Removal) - 4 files
- `app/version.py` - Small file, mostly version detection
- `app/api/flow.py` - Legacy v1 API, not registered
- `app/api/density.py` - Legacy v1 API, not registered
- `app/paths.py` - Small file, need to verify usage

---

## Recommended Action Plan

### Step 1: Verify Frontend Dependencies
1. Check which API routes are actually called by frontend
2. Document frontend → API endpoint mapping
3. Identify unused API endpoints

### Step 2: Review High-Priority Files (<20% coverage)
1. Start with files that have most unused code
2. Identify unused functions within files
3. Remove unused functions (not entire files)

### Step 3: Investigate Medium-Risk Files
1. Check frontend usage for API routes
2. Verify v1 API usage
3. Document dependencies

### Step 4: Remove Unused Code
1. Remove unused functions from files
2. Remove entire files if all code unused
3. Test after each removal

---

## Expected Impact

- **Files to review:** 34 files
- **Files likely removable:** 4-7 files (low-risk category)
- **Functions likely removable:** TBD (needs per-file analysis)
- **Lines likely removable:** ~2,000-3,000 lines
- **Coverage improvement:** Increase from 35.3% baseline

