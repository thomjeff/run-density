# Phase 3 High Priority Investigation Results

**Date:** December 19, 2025  
**Status:** ✅ Investigation Complete - Ready for Cleanup

---

## Summary

### File 1: `app/density_report.py` (22.1%, 1,695 statements)

**v2 Pipeline Dependencies (MUST PRESERVE):**
- ✅ `AnalysisContext` class - Used by `app/core/v2/bins.py`
- ✅ `_generate_bin_dataset_with_retry()` - Used by `app/core/v2/bins.py`
- ✅ `_save_bin_artifacts_and_metadata()` - Used by `app/core/v2/bins.py`
- ✅ `_process_segments_from_bins()` - Used by `app/core/v2/bins.py`
- ✅ `generate_map_dataset()` - Used by `app/core/v2/pipeline.py` (also uses `canonical_segments`)
- ✅ `generate_new_density_report_issue246()` - Used by `app/core/v2/reports.py`
- ✅ Helper functions used by above: `is_hotspot()`, `coarsen_plan()`, `log_bins_event()`, `check_time_budget()`, `_initialize_bin_generation_params()`, `_apply_temporal_first_coarsening()`, `_try_bin_generation_with_coarsening()`, `_regenerate_report_with_intelligence()`, `_execute_bin_dataset_generation()`, `_setup_runflow_output_dir()`, `_finalize_run_metadata()`, `_generate_new_report_format()`, `_generate_and_upload_heatmaps()`, `save_map_dataset()`, `save_map_dataset_to_storage()`, `_determine_zone()`, `_build_segment_catalog_from_results()`, `_create_time_windows_for_bins()`, `_apply_flagging_to_bin_features()`, `_add_geometries_to_bin_features()`, `generate_bin_dataset()`, `generate_bin_features_with_coarsening()`, `build_runner_window_mapping()`, `_build_geojson_from_bin_data()`, `_convert_geometry_to_wkb()`, `_build_parquet_row_from_feature()`, `_write_parquet_file()`, `save_bin_dataset()`, `_build_segment_ranges_per_event()`, `_precompute_runner_data()`, `_calculate_window_duration_seconds()`, `_calculate_window_midpoint_seconds()`, `_ensure_empty_mapping_entry()`, `_calculate_runner_positions_for_segment_window()`, `_process_event_windows_and_segments()`, `generate_bins_geojson_with_temporal_windows()`, `save_bin_artifacts_legacy()`

**v1 API Dependencies (CAN REMOVE - v1 API deprecated):**
- ❌ `generate_density_report()` - Only used by `/api/density-report` endpoint (lazy import in main.py)
- ❌ `generate_simple_density_report()` - Only used by v1 API (calls `generate_density_report()`)
- ❌ `generate_markdown_report()` - Only used by `generate_density_report()` (v1 API)
- ❌ `generate_segment_section()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `generate_template_narratives()` - Only used by `generate_segment_section()` (v1 API)
- ❌ `generate_combined_view()` - Only used by `generate_segment_section()` (v1 API)
- ❌ `generate_per_event_analysis()` - Only used by `generate_segment_section()` (v1 API)
- ❌ `generate_operational_intelligence_summary()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `generate_combined_sustained_periods()` - Only used by `generate_segment_section()` (v1 API)
- ❌ `generate_event_active_window_table()` - Only used by `generate_per_event_analysis()` (v1 API)
- ❌ `generate_event_los_scores_table()` - Only used by `generate_per_event_analysis()` (v1 API)
- ❌ `generate_event_sustained_periods_table()` - Only used by `generate_per_event_analysis()` (v1 API)
- ❌ `_generate_report_header()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_quick_reference_section()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_operational_intelligence_content()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_methodology_section()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_event_start_times_table()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_appendix_content()` - Only used by `generate_markdown_report()` (v1 API)
- ❌ `_generate_tooltips_json()` - Only used by `_regenerate_report_with_intelligence()` (but `_regenerate_report_with_intelligence()` is only called by `generate_density_report()`)
- ❌ `_generate_legacy_report_format()` - Only used by `_regenerate_report_with_intelligence()` (v1 API)
- ❌ Helper functions: `classify_los_areal()`, `format_los_with_color()`, `generate_summary_table()`, `generate_key_takeaway()`, `_determine_los_from_thresholds()`, `_render_metrics_table_v2()`, `_render_key_takeaways_v2()`, `_render_operational_implications_v2()`, `_render_mitigations_and_notes_v2()`, `_render_definitions_v2()`, `render_segment_v2()`, `_render_v2_schema_content()`, `_collect_triggered_actions()`, `_render_event_factors_v2()`, `_render_legacy_content()`, `render_segment()`, `render_methodology()`, `_determine_schema_for_segment()`, `_map_segment_id_to_type()`, `_trigger_matches()`, `get_los_score()`, `format_duration()`

**Note:** `generate_map_dataset()` uses `canonical_segments` functions, so those are indirectly used by v2.

**Estimated Impact:** ~800-1,200 lines removable (v1 report generation functions)

---

### File 2: `app/bin_intelligence.py` (20.7%, 114 statements)

**v2 Pipeline Dependencies (ALL FUNCTIONS USED):**
- ✅ `FlaggingConfig` class - Used by `app/core/bin/summary.py`
- ✅ `compute_utilization_threshold()` - Used by `app/core/bin/summary.py`
- ✅ `classify_flag_reason()` - Used by `app/core/bin/summary.py`
- ✅ `classify_severity()` - Used by `app/core/bin/summary.py`
- ✅ `get_severity_rank()` - Used by `app/core/bin/summary.py`
- ✅ `filter_by_min_bin_length()` - Used by `app/core/bin/summary.py`
- ✅ `apply_bin_flagging()` - Used by `app/core/bin/summary.py`
- ✅ `get_flagged_bins()` - Used by `app/core/bin/summary.py` and `app/density_report.py`
- ✅ `summarize_segment_flags()` - Used by `app/density_report.py` (which is used by v2 via `generate_map_dataset()`)
- ✅ `get_flagging_statistics()` - Used by `app/density_report.py` (which is used by v2 via `generate_map_dataset()`)

**Result:** ✅ **ALL FUNCTIONS ARE USED BY V2 PIPELINE** - No cleanup needed for this file

**Estimated Impact:** 0 lines (file is fully used)

---

### File 3: `app/canonical_segments.py` (20.9%, 86 statements)

**v2 Pipeline Dependencies (INDIRECTLY USED):**
- ✅ `is_canonical_segments_available()` - Used by `generate_map_dataset()` in `app/density_report.py` (which is used by v2)
- ✅ `get_canonical_segments_metadata()` - Used by `generate_map_dataset()` in `app/density_report.py` (which is used by v2)
- ✅ `get_segment_peak_densities()` - Used by `generate_map_dataset()` in `app/density_report.py` (which is used by v2)
- ✅ `get_segment_time_series()` - Used by `generate_map_dataset()` in `app/density_report.py` (which is used by v2)
- ✅ `find_latest_canonical_segments_file()` - Used by other functions (internal helper)
- ✅ `load_canonical_segments()` - Used by other functions (internal helper)

**v1 API Dependencies (ALSO USED BY v1):**
- ⚠️ `is_canonical_segments_available()` - Also used by `/api/canonical-segments` endpoint in `main.py` (v1 API)
- ⚠️ `get_canonical_segments_metadata()` - Also used by `/api/canonical-segments` endpoint in `main.py` (v1 API)
- ⚠️ `get_segment_peak_densities()` - Also used by `app/density_report.py` (v1 API path)
- ⚠️ `get_segment_time_series()` - Also used by `app/density_report.py` (v1 API path)

**Result:** ⚠️ **ALL FUNCTIONS ARE USED BY V2 (via generate_map_dataset)** - No cleanup needed for this file

**Estimated Impact:** 0 lines (file is fully used by v2, even if also used by v1)

---

## Cleanup Plan

### Action Items:

1. **`app/density_report.py`**: Remove v1-only report generation functions (~800-1,200 lines)
   - Remove `generate_density_report()` and `generate_simple_density_report()`
   - Remove all helper functions only used by v1 report generation
   - Preserve all v2-used functions

2. **`app/bin_intelligence.py`**: ✅ No cleanup needed (all functions used by v2)

3. **`app/canonical_segments.py`**: ✅ No cleanup needed (all functions used by v2 via `generate_map_dataset()`)

---

## Risk Assessment

- **Low Risk:** Removing v1-only functions from `app/density_report.py` since they're not used by v2 E2E tests
- **No Risk:** `app/bin_intelligence.py` and `app/canonical_segments.py` are fully used by v2, so no changes needed

---

## Next Steps

1. Remove v1-only functions from `app/density_report.py`
2. Run `make e2e-coverage-lite DAY=sat` to verify
3. Commit if tests pass

