# Milestone 19 Open Issues Review
**Date:** December 16, 2025  
**Milestone:** Big Sur (#19)  
**Status:** 73% complete (19 closed, 7 open)

---

## Executive Summary

This document reviews each of the 7 open issues in Milestone 19, prioritized by severity. Each issue includes:
- **Current Status**: What I found in the codebase
- **Root Cause Analysis**: Why the issue exists
- **Recommended Fix**: How to resolve it
- **Effort Estimate**: Time/complexity assessment

---

## 🔴 High Priority - Critical Bugs

### Issue #537: Makefile test-v2 'Error 1' thrown

**Status:** ✅ **VERIFIED WORKING** - Not a bug

**Investigation:**
- Ran `make test-v2` successfully - command completes with exit code 0
- Script `scripts/test_v2_analysis.sh` executes correctly
- Container starts, API responds with 200 status
- Test completed successfully with run_id `KXNPCydh6oBcUdtsV3RvLW`

**Root Cause:**
- Issue may have been fixed in a previous session
- Or user may have encountered a transient error (container startup timing, network issue)

**Recommended Action:**
- **Close issue** - verify with user if they still see the error
- If error persists, check:
  1. Docker daemon status
  2. Port 8080 availability
  3. Container startup timing (script waits 30s max)

**Effort:** N/A (already working)

---

### Issue #538: Browser not using latest run_id

**Status:** ⚠️ **CONFIRMED ISSUE** - Frontend relies on URL params/localStorage

**Investigation:**
- Frontend code (`frontend/templates/base.html`, `frontend/static/js/map/*.js`) shows:
  - Run ID resolution priority: URL param → `window.runflowDay.run_id` → `localStorage.selected_run_id`
  - Dashboard API (`/api/dashboard/summary`) provides `run_id` but frontend doesn't always use it
  - Pages check for `run_id` in URL/localStorage but don't fetch latest if missing

**Root Cause:**
- Frontend doesn't proactively fetch latest `run_id` from `/api/dashboard/summary` or `/runflow/latest.json`
- Relies on user navigation or manual URL parameter
- `base.html` has logic to fetch from dashboard but only on dashboard page load

**Code Locations:**
- `frontend/templates/base.html:394-415` - Run ID resolution logic
- `frontend/templates/pages/segments.html:187-205` - Segments page run_id resolution
- `frontend/static/js/map/segments.js:57-65` - Map component run_id handling

**Recommended Fix:**
1. **Option A (Recommended)**: Add global initialization in `base.html` that:
   - Fetches `/api/dashboard/summary` on page load
   - Extracts `run_id` from response
   - Updates `window.runflowDay.run_id` and localStorage
   - Rewrites URL if `run_id` param missing

2. **Option B**: Add API endpoint `/api/latest-run-id` that returns just the run_id
   - Frontend calls this on every page load
   - Updates URL params if run_id changed

**Effort:** Medium (2-3 hours)
- Modify `base.html` initialization
- Test across all pages (dashboard, segments, density, flow, locations)
- Ensure URL rewriting doesn't break browser history

---

### Issue #528: Flags JSON file is empty

**Status:** ⚠️ **CONFIRMED ISSUE** - Flags generation may be failing silently

**Investigation:**
- `app/core/v2/ui_artifacts.py:366-375` shows flags generation:
  ```python
  if aggregated_bins is not None and not aggregated_bins.empty and temp_reports:
      flags = generate_flags_json(temp_reports, segment_metrics)
  else:
      flags = []
  ```
- Exception handling catches errors but only logs warning
- `generate_flags_json` imported from `app.core.artifacts.frontend` (file filtered by .cursorignore)

**Root Cause Analysis:**
1. **Missing dependencies**: `temp_reports` may be None/empty
2. **Exception swallowed**: Try/except catches errors but returns empty list
3. **Function not found**: `generate_flags_json` may not exist or have wrong signature
4. **Data mismatch**: `temp_reports` structure may not match what `generate_flags_json` expects

**Code Locations:**
- `app/core/v2/ui_artifacts.py:366-375` - Flags generation call site
- `app/core/v2/ui_artifacts.py:243` - Import statement
- `app/flagging.py` - Flagging logic (SSOT for flag computation)

**Recommended Fix:**
1. **Investigate `generate_flags_json` function**:
   - Check if function exists in `app/core/artifacts/frontend.py`
   - Verify function signature matches call site
   - Check if it handles v2 data structure correctly

2. **Add better error handling**:
   - Log full exception traceback (not just warning)
   - Check if `temp_reports` is None/empty before calling
   - Validate `segment_metrics` structure

3. **Alternative approach**:
   - Use `app/flagging.py` functions directly (`compute_bin_flags`, `summarize_flags`)
   - Load bins.parquet and compute flags from authoritative source
   - This ensures flags match what's in bins.parquet

**Effort:** Medium (3-4 hours)
- Investigate `generate_flags_json` implementation
- Add logging/debugging
- Test with actual v2 data
- Verify flags.json structure matches expected format

---

### Issue #531: SAT Locations.csv not being generated correctly

**Status:** ⚠️ **CONFIRMED ISSUE** - Saturday locations filtering may be incorrect

**Investigation:**
- `app/core/v2/reports.py:529-670` contains `generate_locations_report_per_day()`
- Logic filters locations by day segments:
  - Checks `seg_id` column in locations.csv
  - Filters by day segment IDs
  - Handles proxy locations (with `proxy_loc_id`)
- E2E test comment: `# Locations.csv may not exist for all days (e.g., SAT)`

**Root Cause Analysis:**
1. **Segment filtering**: Saturday segments (N1-O3) may not match locations.csv `seg_id` values
2. **Proxy location handling**: Proxy locations may not be included correctly for Saturday
3. **Day column**: Locations.csv may not have `day` column, causing proxy locations to be excluded
4. **Empty result**: Filtering may result in empty DataFrame, causing report generation to skip

**Code Locations:**
- `app/core/v2/reports.py:529-670` - Locations report generation
- `app/core/v2/reports.py:574-594` - Location filtering logic
- `app/location_report.py` - Actual report generation function

**Recommended Fix:**
1. **Add debug logging**:
   - Log how many locations before/after filtering
   - Log which segment IDs are being matched
   - Log proxy location inclusion/exclusion

2. **Verify segment matching**:
   - Check if Saturday segments (N1-O3) exist in locations.csv
   - Verify `seg_id` column format (comma-separated, single values)
   - Check sub-segment normalization (N2a → N2)

3. **Fix proxy location logic**:
   - Ensure proxy locations for Saturday are included
   - Check `day` column in locations.csv (may need to add it)
   - Verify proxy source locations are included

4. **Test with Saturday data**:
   - Run E2E test for Saturday-only scenario
   - Check if Locations.csv is generated
   - Verify contents match expected segments

**Effort:** Medium (3-4 hours)
- Add logging to understand filtering behavior
- Test with Saturday E2E scenario
- Fix filtering logic if needed
- Verify report generation completes

---

## 🟡 Medium Priority - Enhancements

### Issue #519: Remove duplicate bins.parquet files (bins/ vs reports/)

**Status:** ✅ **CONFIRMED ISSUE** - Duplicate files exist

**Investigation:**
- `app/core/v2/bins.py` saves bins.parquet to `{day}/bins/bins.parquet`
- `app/core/v2/reports.py:214-232` copies bins.parquet to `{day}/reports/bins.parquet`
- Both files contain same data (reports version is filtered by day segments)

**Root Cause:**
- Reports module needs bins.parquet for report generation
- Bins module saves to bins/ directory
- Copy operation creates duplicate

**Code Locations:**
- `app/core/v2/bins.py:280-283` - Saves to `bins/bins.parquet`
- `app/core/v2/reports.py:214-232` - Copies to `reports/bins.parquet`
- `app/core/v2/reports.py:221` - Uses `reports/bins.parquet` for report generation

**Recommended Fix:**
1. **Option A (Recommended)**: Reports module should read from `bins/bins.parquet` directly
   - Remove copy operation in `reports.py`
   - Update report generation to use `bins_dir / "bins.parquet"`
   - Keep day filtering logic (filter DataFrame, don't copy file)

2. **Option B**: Keep single source in `reports/` directory
   - Bins module saves to `reports/bins.parquet` instead of `bins/bins.parquet`
   - Remove copy operation
   - Update any code that reads from `bins/bins.parquet`

**Effort:** Low (1-2 hours)
- Remove copy operation
- Update file paths
- Test report generation still works
- Verify no other code depends on duplicate location

---

### Issue #532: Adjust Segments Map

**Status:** ⚠️ **NEEDS INVESTIGATION** - Unclear what "adjust" means

**Investigation:**
- No specific details in issue description
- Segments map rendered in `frontend/templates/pages/segments.html`
- Uses Leaflet.js with GeoJSON from `/api/segments/geojson`
- Map data comes from `runflow/{run_id}/{day}/ui/segments.geojson`

**Root Cause:**
- Issue description doesn't specify what needs adjustment
- Could be:
  - Map bounds/zoom level
  - Segment styling/colors
  - GeoJSON coordinate accuracy
  - Map controls/UI

**Recommended Action:**
- **Clarify requirements** with user:
  - What specifically needs adjustment?
  - What's the current behavior vs expected?
  - Screenshots or examples?

**Effort:** Unknown (depends on requirements)

---

## 🟢 Low Priority - Developer Experience

### Issue #527: Persist Docker/app logs per run under `runflow/{run_id}/`

**Status:** ✅ **FEATURE REQUEST** - Logs not currently persisted

**Investigation:**
- Docker logs currently only available via `docker logs` command
- Application logs go to stdout/stderr (captured by Docker)
- No mechanism to save logs to `runflow/{run_id}/logs/` directory

**Root Cause:**
- No logging infrastructure to write logs to files
- Docker captures stdout/stderr but doesn't persist to filesystem
- Application doesn't have file-based logging configured

**Recommended Fix:**
1. **Add file-based logging**:
   - Configure Python logging to write to `runflow/{run_id}/logs/app.log`
   - Use rotating file handler (limit size, keep N files)
   - Include timestamp in filename

2. **Capture Docker logs**:
   - After analysis completes, run `docker logs run-density-dev > runflow/{run_id}/logs/docker.log`
   - Or configure Docker logging driver to write to file

3. **Add log aggregation**:
   - Combine app logs + Docker logs into single file
   - Include metadata (run_id, start time, end time, events)

**Effort:** Medium (3-4 hours)
- Configure Python logging
- Add log directory creation
- Test log file generation
- Verify logs are readable/useful

---

## Summary & Recommendations

### Priority Order for Fixing:

1. **#528** (Flags JSON empty) - Blocks operational intelligence
2. **#531** (SAT Locations.csv) - Data completeness issue
3. **#538** (Browser run_id) - User experience issue
4. **#519** (Duplicate bins.parquet) - Quick cleanup
5. **#527** (Persist logs) - Developer experience
6. **#537** (Makefile test-v2) - Verify if still an issue, then close
7. **#532** (Adjust Segments Map) - Needs clarification

### Estimated Total Effort:
- **High Priority**: 8-11 hours
- **Medium Priority**: 1-2 hours (plus clarification for #532)
- **Low Priority**: 3-4 hours
- **Total**: 12-17 hours

### Risk Assessment:
- **Low Risk**: #519, #527 (straightforward implementation)
- **Medium Risk**: #528, #531, #538 (may require investigation/debugging)
- **High Risk**: #532 (unclear requirements)

---

## Next Steps

1. **Verify #537** - Confirm with user if error still occurs
2. **Investigate #528** - Check `generate_flags_json` implementation
3. **Debug #531** - Add logging to Saturday locations filtering
4. **Fix #538** - Update frontend to fetch latest run_id
5. **Cleanup #519** - Remove duplicate bins.parquet copy
6. **Clarify #532** - Get requirements from user
7. **Implement #527** - Add log persistence

---

**Review completed:** December 16, 2025  
**Reviewer:** Cursor AI Assistant  
**Session:** Milestone 19 Issues Review

