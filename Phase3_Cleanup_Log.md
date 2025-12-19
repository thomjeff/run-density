# Phase 3 Cleanup Log

**Issue:** #544  
**Started:** December 18, 2025  
**Branch:** `phase3-cleanup`  
**Status:** 🟢 In Progress

---

## Cleanup Decisions

| File | Function/Code | Coverage | Decision | Reason | Date |
|------|---------------|----------|----------|--------|------|
| app/api/density.py | Entire file | 23.2% | ✅ **REMOVED** | Router imported but commented out, endpoints unused | 2025-12-18 |
| app/api/flow.py | Entire file | 19.6% | ✅ **RETAINED** | Used via app/routes/api_flow.py wrapper (imports all) | 2025-12-18 |
| app/paths.py | Entire file | 36.4% | ✅ **RETAINED** | Used by v2 pipeline via report_utils.py → location_report.py | 2025-12-18 |
| app/utils/auth.py | Entire file | 28.1% | ✅ **RETAINED** | Used by app/routes/ui.py for password protection (require_auth) | 2025-12-18 |
| app/routes/api_dashboard.py | count_runners_for_events() | 0% | ✅ **REMOVED** | Never called, replaced by metadata.json reading | 2025-12-18 |
| app/routes/api_dashboard.py | load_bins_flagged_count() | 0% | ✅ **REMOVED** | Never called, replaced by flags.json reading | 2025-12-18 |
| app/heatmap_generator.py | get_heatmap_files() | 0% | ✅ **REMOVED** | Imported but never called | 2025-12-18 |
| app/los.py | get_los_color() | 0% | ✅ **REMOVED** | Not imported (main.py has own _get_los_color) | 2025-12-18 |
| app/los.py | summarize_los_distribution() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/los.py | get_worst_los() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/los.py | filter_by_los_threshold() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/core/bin/geometry.py | generate_bin_polygons_for_segment() | 0% | ✅ **REMOVED** | Only used by unused generate_all_bin_polygons | 2025-12-18 |
| app/core/bin/geometry.py | generate_all_bin_polygons() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/core/bin/geometry.py | validate_bin_polygon() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/core/bin/geometry.py | export_to_geojson() | 0% | ✅ **REMOVED** | Not imported anywhere | 2025-12-18 |
| app/routes/reports.py | _extract_timestamp_from_filename() | 0% | ✅ **REMOVED** | Never called | 2025-12-18 |
| app/routes/reports.py | _preview_storage_content_archived() | 0% | ✅ **REMOVED** | GCS-specific, archived, not needed | 2025-12-18 |
| app/routes/api_bins.py | format_time_for_display() | 0% | ✅ **REMOVED** | Never called | 2025-12-18 |
| app/routes/api_bins.py | GET /api/bins/summary endpoint | 0% | ✅ **REMOVED** | Not called by frontend or E2E tests | 2025-12-19 |
| app/routes/api_locations.py | Unreachable code blocks | 0% | ✅ **REMOVED** | Dead code after raise HTTPException | 2025-12-18 |
| app/bin_analysis.py | analyze_historical_trends() | 3.4% | ✅ **REMOVED** | Imported by /historical-trends endpoint but never called | 2025-12-18 |
| app/bin_analysis.py | compare_segments() | 2.9% | ✅ **REMOVED** | Imported by /compare-segments endpoint but never called | 2025-12-18 |
| app/bin_analysis.py | export_bin_data() | 5.3% | ✅ **REMOVED** | Imported by /export-advanced endpoint but never called | 2025-12-18 |
| app/api/map.py | /historical-trends endpoint | 0% | ✅ **REMOVED** | Endpoint never called by frontend or E2E tests | 2025-12-18 |
| app/api/map.py | /compare-segments endpoint | 0% | ✅ **REMOVED** | Endpoint never called by frontend or E2E tests | 2025-12-18 |
| app/api/map.py | /export-advanced endpoint | 0% | ✅ **REMOVED** | Endpoint never called by frontend or E2E tests | 2025-12-18 |
| app/routes/api_segments.py | load_reporting import | 0% | ✅ **REMOVED** | Imported but never used | 2025-12-18 |
| app/routes/api_segments.py | json import | 0% | ✅ **REMOVED** | Imported but never used | 2025-12-18 |
| app/geo_utils.py | validate_geojson() | 5.0% | ✅ **REMOVED** | Only used by get_geojson_bounds (also unused) | 2025-12-18 |
| app/geo_utils.py | get_geojson_bounds() | 2.9% | ✅ **REMOVED** | Never imported or called | 2025-12-18 |
| app/storage.py | mtime() | 33.3% | ✅ **REMOVED** | Never called, code uses stat.st_mtime directly | 2025-12-18 |
| app/storage.py | size() | 33.3% | ✅ **REMOVED** | Never called, code uses stat.st_size directly | 2025-12-18 |
| app/storage.py | list_paths() | 10.0% | ✅ **REMOVED** | Never called | 2025-12-18 |
| app/storage.py | copy_file() | 16.7% | ✅ **REMOVED** | Never called | 2025-12-18 |
| app/storage.py | read_csv() | 9.1% | ✅ **REMOVED** | Never called, code uses pd.read_csv() directly | 2025-12-18 |
| app/storage.py | read_geojson() | 10.0% | ✅ **REMOVED** | Never called, code uses json.loads() directly | 2025-12-18 |
| app/storage.py | create_storage_from_env() | 7.1% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_latest_run_id() | 16.7% | ✅ **REMOVED** | Never imported (use get_latest_run_id() directly) | 2025-12-18 |
| app/storage.py | list_reports() | 7.1% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_segments_geojson() | 16.7% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_segment_metrics() | 16.7% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_flags() | 16.7% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_meta() | 16.7% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/storage.py | load_bin_details_csv() | 16.7% | ✅ **REMOVED** | Never imported | 2025-12-18 |
| app/cache_manager.py | CloudStorageCacheManager_archived | 13.2% | ✅ **REMOVED** | Already archived, GCS-specific, not used | 2025-12-18 |
| app/cache_manager.py | Entire file | 18.6% | ✅ **REMOVED** | Not imported anywhere, all cache endpoints removed | 2025-12-19 |
| app/heatmap_generator.py | Legacy date format support in load_bin_data() | 0% | ✅ **REMOVED** | Legacy path never executed, get_storage_service() undefined | 2025-12-18 |
| app/heatmap_generator.py | load_segments_metadata() | 0% | ✅ **REMOVED** | Called but result never used | 2025-12-19 |
| app/heatmap_generator.py | json import | 0% | ✅ **REMOVED** | Imported but never used | 2025-12-19 |
| app/heatmap_generator.py | load_rulebook import | 0% | ✅ **REMOVED** | Imported but never used | 2025-12-19 |
| app/routes/reports.py | reports_list() endpoint | 0% | ✅ **REMOVED** | Legacy endpoint, not used by frontend | 2025-12-19 |
| app/routes/reports.py | open_report() endpoint | 0% | ✅ **REMOVED** | Legacy endpoint, not used by frontend | 2025-12-19 |
| app/routes/reports.py | preview_report() endpoint | 0% | ✅ **REMOVED** | Legacy endpoint, not used by frontend | 2025-12-19 |
| app/routes/reports.py | _scan_reports() | 0% | ✅ **REMOVED** | Only used by removed reports_list() | 2025-12-19 |
| app/routes/reports.py | _scan_runflow_reports() | 0% | ✅ **REMOVED** | Only used by removed _scan_reports() | 2025-12-19 |
| app/routes/reports.py | _scan_local_reports() | 0% | ✅ **REMOVED** | Only used by removed _scan_reports() | 2025-12-19 |
| app/routes/reports.py | _build_report_row() | 0% | ✅ **REMOVED** | Only used by removed scan functions | 2025-12-19 |
| app/routes/reports.py | _determine_report_kind() | 0% | ✅ **REMOVED** | Only used by removed _build_report_row() | 2025-12-19 |
| app/routes/reports.py | _safe_join() | 0% | ✅ **REMOVED** | Only used by removed open_report() and preview_report() | 2025-12-19 |
| app/routes/reports.py | _preview_local_file() | 0% | ✅ **REMOVED** | Only used by removed preview_report() | 2025-12-19 |
| **INVESTIGATION** | **app/bin_analysis.py** | **12.8%** | ✅ **RETAINED** | All functions used by app/api/map.py and app/geo_utils.py | 2025-12-19 |
| app/api/map.py | GET /api/map-data endpoint | 0% | ✅ **REMOVED** | Broken (undefined get_storage_service()), not used | 2025-12-19 |
| app/api/map.py | POST /api/clear-cache endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | GET /api/cache-management endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | POST /api/invalidate-segment endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | GET /api/cache-status endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | GET /api/cached-analysis endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | POST /api/cleanup-cache endpoint | 0% | ✅ **REMOVED** | Admin endpoint, not used by frontend or E2E tests | 2025-12-19 |
| app/api/map.py | get_global_cache_manager import | 0% | ✅ **REMOVED** | Only used by removed cache endpoints | 2025-12-19 |
| **E2E Test Results** | **Run ID: nuvzH9hYnawQrnBAFknZAm** | **43%** | ✅ **PASSED** | All endpoints UP, reports generated successfully | 2025-12-19 |
| **HIGH PRIORITY BATCH - Phase 3** | | | | | |
| app/density_report.py | generate_density_report() | 22.1% | ✅ **REMOVED** | v1 API only, not used by v2 E2E tests | 2025-12-19 |
| app/density_report.py | generate_simple_density_report() | 22.1% | ✅ **REMOVED** | v1 API only, calls generate_density_report() | 2025-12-19 |
| app/density_report.py | _regenerate_report_with_intelligence() | 0% | ✅ **REMOVED** | Only called by generate_density_report() (v1) | 2025-12-19 |
| app/density_report.py | _generate_new_report_format() | 0% | ✅ **REMOVED** | Orphaned wrapper, v2 calls generate_new_density_report_issue246() directly | 2025-12-19 |
| app/density_report.py | _generate_legacy_report_format() | 0% | ✅ **REMOVED** | Only called by _regenerate_report_with_intelligence() (v1) | 2025-12-19 |
| app/density_report.py | _generate_tooltips_json() | 0% | ✅ **REMOVED** | Only called by _regenerate_report_with_intelligence() (v1) | 2025-12-19 |
| app/density_report.py | _execute_bin_dataset_generation() | 0% | ✅ **REMOVED** | Only called by generate_density_report() (v1), v2 calls _generate_bin_dataset_with_retry() directly | 2025-12-19 |
| app/density_report.py | _setup_runflow_output_dir() | 0% | ✅ **REMOVED** | Only called by generate_density_report() (v1) | 2025-12-19 |
| app/density_report.py | _finalize_run_metadata() | 0% | ✅ **REMOVED** | Only called by generate_density_report() (v1) | 2025-12-19 |
| app/density_report.py | _generate_and_upload_heatmaps() | 0% | ✅ **REMOVED** | Only called by generate_density_report() (v1) | 2025-12-19 |
| app/bin_intelligence.py | (entire file) | 20.7% | ✅ **RETAINED** | All functions used by v2 pipeline via app/core/bin/summary.py | 2025-12-19 |
| app/canonical_segments.py | (entire file) | 20.9% | ✅ **RETAINED** | All functions used by v2 via generate_map_dataset() in density_report.py | 2025-12-19 |
| **E2E Test Results** | **Run ID: WT6Bcq26F9Tswi3zzj5BU3** | **PASS** | ✅ **PASSED** | All endpoints UP, reports generated, no errors from cleanup | 2025-12-19 |

---

## Test Results

### app/api/density.py Removal
- **E2E Test:** ✅ PASS (Run ID: ZTARPErEHMRfZDB2JNGUPZ)
- **Status:** All endpoints UP, no errors/warnings
- **Verification:** No references found, main.py imports successfully
- **Date:** 2025-12-18

### Phase 3 Cleanup Batch (app/api/density.py + 3 functions)
- **E2E Test:** ✅ PASS (Run ID: aSzikhKuet45VNyQmCD8Ee, DAY=both)
- **Status:** All endpoints UP, no errors/warnings
- **Coverage:** 39.4% (improved from 35.3% baseline)
- **Reports:** ✅ Generated for both sat and sun
- **UI Artifacts:** ✅ Complete for both days
- **Heatmaps:** ✅ Generated (6 sat, 20 sun)
- **UI Test:** ✅ User verified functional
- **Date:** 2025-12-18

### Phase 3 Cleanup Batch (los.py + geometry.py - 8 functions)
- **E2E Test:** ✅ PASS (Run ID: gP4TmPrjm4u8kErXNcNTKK, DAY=both)
- **Status:** All endpoints UP, no errors/warnings
- **Reports:** ✅ Generated for both sat and sun
- **Removed Code:** ✅ No import errors or references found
- **Pre-existing Errors:** 4 ERROR entries from app.density_report (unrelated)
- **Date:** 2025-12-18

### Phase 3 Cleanup Batch (reports.py + api_bins.py + api_locations.py)
- **E2E Test:** ✅ PASS (Run ID: jSF3nHLboV7xCpdwrMBFy2, DAY=sat)
- **Status:** All endpoints UP, no errors/warnings
- **Coverage:** 45.1% (improved from 39.4% baseline, +5.7%)
- **Reports:** ✅ Generated successfully
- **Removed Code:** ✅ No references found in coverage
- **Pre-existing Errors:** 4 ERROR entries from app.density_report (unrelated)
- **Date:** 2025-12-18

### Phase 3 Cleanup Batch (bin_analysis.py + map.py + api_segments.py)
- **E2E Test:** ✅ PASS (Run ID: X4mHKXDk3yX7Q8zbntwiKn, DAY=sat)
- **Status:** All endpoints UP, no errors/warnings
- **Coverage:** 40.0% (14,097 statements, 7,936 missing)
- **Reports:** ✅ Generated successfully
- **Removed Code:** ✅ No references found in coverage
- **Files Cleaned:**
  - `app/bin_analysis.py`: 16% coverage (removed 3 functions, ~290 lines)
  - `app/api/map.py`: 15% coverage (removed 3 endpoints, ~90 lines)
  - `app/routes/api_segments.py`: 5% coverage (removed 2 unused imports)
- **Date:** 2025-12-18

---

## Investigation Results

### app/api/density.py (23.2% coverage, 70 statements)

**Endpoints:**
- `POST /api/density/analyze`
- `GET /api/density/segment/{segment_id}`
- `GET /api/density/summary`
- `GET /api/density/health`

**Status:**
- ✅ Router imported in `main.py` but **commented out**: `# app.include_router(density_router)`
- ✅ Comment says: `# Disabled - conflicts with api_density_router`
- ✅ Frontend uses `/api/density/segments` and `/api/density/segment/{seg_id}` from `app/routes/api_density.py`
- ✅ No usage found for endpoints in `app/api/density.py` (grep frontend, tests)
- ✅ **Decision:** 🟢 **SAFE TO REMOVE** - Truly orphaned, not integrated into runtime

**Action:** Remove file and import from main.py

---

### app/api/flow.py (19.6% coverage, 43 statements)

**Endpoints:**
- `GET /api/flow/segments`

**Status:**
- ✅ Router NOT directly registered in `main.py`
- ✅ BUT `app/routes/api_flow.py` imports everything: `from app.api.flow import *`
- ✅ `app/routes/api_flow.py` router IS registered in `main.py`
- ✅ Frontend uses `/api/flow/segments` which comes from `app/api/flow.py` via wrapper
- ✅ **Decision:** ✅ **RETAINED** - Used indirectly via deprecated wrapper

**Action:** Keep file (used via wrapper), but note that wrapper is deprecated

---

## Next Steps

1. ✅ Remove `app/api/density.py` and its import from `main.py`
2. ✅ Test with `make e2e-coverage-lite`
3. ✅ Document decision in PHASE3_FILE_ANALYSIS.md
4. ⏭️ Continue with next low-risk files

---

## Notes

- All removals tested with `make e2e-coverage-lite` before commit
- All retained code documented with inline comments
- All decisions reviewed against guardrails
