# Phase 8: Testing & Validation Plan

**Date:** 2025-12-25  
**Status:** In Progress  
**Issue:** #553

---

## Overview

Phase 8 provides comprehensive testing and validation for all Issue #553 changes:
- Phase 1: API Enhancement & Validation
- Phase 2: analysis.json Creation
- Phase 3: metadata.json Enhancement
- Phase 4: Refactor Hardcoded Event Names
- Phase 5: Refactor Hardcoded Start Times
- Phase 6: Refactor Hardcoded File Paths
- Phase 7: Update Pipeline Integration

---

## 8.1 Unit Tests

### 8.1.1 Validation Functions

**File:** `tests/v2/test_validation.py`

**Test Cases:**
- ✅ `test_validate_description_length()` - Description max length (254 chars)
- ✅ `test_validate_start_times()` - Start time range (300-1200 minutes)
- ✅ `test_validate_event_duration_range()` - Event duration (1-500 minutes)
- ✅ `test_validate_csv_file_extension()` - CSV file extension validation
- ✅ `test_validate_gpx_file_extension()` - GPX file extension validation
- ✅ `test_validate_event_name_consistency()` - Event names in all files
- ✅ `test_validate_segment_columns()` - Segment columns for events
- ✅ `test_validate_flow_event_pairs()` - Event pairs in flow.csv
- ✅ `test_validate_location_event_flags()` - Location flags for events
- ✅ `test_validate_runner_uniqueness()` - Unique runners across events

**Status:** Review existing tests, add missing coverage

### 8.1.2 analysis.json Generation & Reading

**File:** `tests/v2/test_analysis_config.py` (new)

**Test Cases:**
- ✅ `test_generate_analysis_json()` - Generate analysis.json from request
- ✅ `test_load_analysis_json()` - Load analysis.json from run_path
- ✅ `test_analysis_json_structure()` - Verify JSON structure matches schema
- ✅ `test_analysis_json_runner_counts()` - Verify runner counts are correct
- ✅ `test_analysis_json_data_files()` - Verify data_files paths are correct
- ✅ `test_get_event_names()` - Get event names from analysis.json
- ✅ `test_get_events_by_day()` - Get events filtered by day
- ✅ `test_get_event_duration_minutes()` - Get event duration from analysis.json
- ✅ `test_get_start_time()` - Get start time from analysis.json
- ✅ `test_get_all_start_times()` - Get all start times dictionary
- ✅ `test_get_segments_file()` - Get segments file path
- ✅ `test_get_flow_file()` - Get flow file path
- ✅ `test_get_locations_file()` - Get locations file path
- ✅ `test_get_runners_file()` - Get runners file path for event
- ✅ `test_get_gpx_file()` - Get GPX file path for event

**Status:** Create new test file

### 8.1.3 Helper Functions

**Files:** Various test files

**Test Cases:**
- ✅ Event name helpers (already tested in test_analysis_config.py)
- ✅ Start time helpers (already tested in test_analysis_config.py)
- ✅ File path helpers (already tested in test_analysis_config.py)

---

## 8.2 Integration Tests

### 8.2.1 Full API Request/Response Cycle

**File:** `tests/v2/test_api.py`

**Test Cases:**
- ✅ `test_analyze_v2_success()` - Successful analysis request
- ✅ `test_analyze_v2_response_structure()` - Response structure validation
- ✅ `test_analyze_v2_analysis_json_created()` - Verify analysis.json created
- ✅ `test_analyze_v2_metadata_json_updated()` - Verify metadata.json includes request/response
- ✅ `test_analyze_v2_output_paths()` - Verify output paths in response

**Status:** Review existing tests, add missing coverage

### 8.2.2 Validation Error Handling (Fail-Fast)

**File:** `tests/v2/test_validation_errors.py` (new)

**Test Cases:**
- ✅ `test_missing_file_404()` - Missing segments.csv (404)
- ✅ `test_invalid_start_time_400()` - Start time < 300 or > 1200 (400)
- ✅ `test_missing_event_in_segments_400()` - Event not in segments.csv (400)
- ✅ `test_missing_event_in_flow_400()` - Event not in flow.csv pairs (400)
- ✅ `test_missing_event_in_locations_400()` - Event with no locations (400)
- ✅ `test_malformed_gpx_406()` - Invalid GPX file structure (406)
- ✅ `test_invalid_csv_structure_422()` - Missing required columns (422)
- ✅ `test_invalid_event_duration_400()` - Event duration < 1 or > 500 (400)
- ✅ `test_description_too_long_400()` - Description > 254 chars (400)
- ✅ `test_missing_required_fields_400()` - Missing segments_file, etc. (400)

**Status:** Create new test file

### 8.2.3 analysis.json Validation

**File:** `tests/v2/test_analysis_json_validation.py` (new)

**Test Cases:**
- ✅ `test_analysis_json_matches_request()` - Verify analysis.json matches request exactly
- ✅ `test_analysis_json_runner_counts()` - Verify runner counts are accurate
- ✅ `test_analysis_json_event_durations()` - Verify event durations from request
- ✅ `test_analysis_json_start_times()` - Verify start times from request
- ✅ `test_analysis_json_data_files()` - Verify data_files paths are correct

**Status:** Create new test file

---

## 8.3 End-to-End Tests

### 8.3.1 Baseline Scenario (Five Events)

**File:** `tests/v2/e2e.py`

**Test Case:** `test_mixed_day_scenario()`
- Events: elite (sat), open (sat), full (sun), 10k (sun), half (sun)
- Verify: All reports generated, bins created, UI artifacts present
- Compare: Against golden files (regression test)

**Status:** Review existing test, verify it works with new API

### 8.3.2 Single Event Scenario

**Test Case:** `test_single_event_scenario()`
- Events: full (sun) only
- Verify: Single event analysis works correctly
- Verify: No flow.csv generated (requires 2+ events)

**Status:** Add new test case

### 8.3.3 Custom Event Names

**Test Case:** `test_custom_event_names()`
- Events: Custom event names (if supported)
- Verify: Dynamic event name handling works

**Status:** Add new test case (if applicable)

### 8.3.4 Different Start Times

**Test Case:** `test_different_start_times()`
- Events: Same events with different start times
- Verify: Start times from request are used correctly
- Verify: No hardcoded start time fallbacks

**Status:** Add new test case

### 8.3.5 Different File Names

**Test Case:** `test_different_file_names()`
- Request: Custom file names (if supported)
- Verify: File paths from request are used correctly
- Verify: No hardcoded file path constants

**Status:** Add new test case (if applicable)

### 8.3.6 Error Scenarios

**Test Cases:**
- `test_missing_file_error()` - Missing runners file
- `test_invalid_start_time_error()` - Invalid start time
- `test_missing_event_error()` - Event not in segments.csv

**Status:** Add new test cases

---

## 8.4 Regression Tests

### 8.4.1 Existing E2E Tests

**File:** `tests/v2/e2e.py`

**Test Cases:**
- ✅ `test_saturday_only_scenario()` - Saturday-only events
- ✅ `test_sunday_only_scenario()` - Sunday-only events
- ✅ `test_mixed_day_scenario()` - Mixed day events

**Status:** Run existing tests, verify they pass

### 8.4.2 Report Generation

**Verification:**
- ✅ Density.md structure unchanged
- ✅ Flow.csv structure unchanged
- ✅ Locations.csv structure unchanged
- ✅ Report content matches baseline (from Phase 5+6 testing)

**Status:** Compare against baseline run `4FdphgBQxhZkwfifoZktPY`

### 8.4.3 Density/Flow Calculations

**Verification:**
- ✅ Density calculations unchanged (compare bins.parquet)
- ✅ Flow calculations unchanged (compare Flow.csv)
- ✅ No regressions in analysis results

**Status:** Compare against baseline run

### 8.4.4 UI Artifacts Generation

**Verification:**
- ✅ All UI artifacts generated (meta.json, flags.json, etc.)
- ✅ Artifact structure unchanged
- ✅ Artifact content matches baseline

**Status:** Compare against baseline run

---

## 8.5 Update Test Harnesses

### 8.5.1 e2e.py

**File:** `e2e.py`

**Changes:**
- Update to use new v2 API format
- Use `/runflow/v2/analyze` endpoint
- Use new request structure (segments_file, flow_file, locations_file, events)
- Verify analysis.json is created
- Verify metadata.json includes request/response

**Status:** Review and update

### 8.5.2 tests/v2/e2e.py

**File:** `tests/v2/e2e.py`

**Changes:**
- Verify tests use new API format
- Update test scenarios if needed
- Add new test cases for Phase 8.3

**Status:** Review and update

### 8.5.3 Makefile

**File:** `Makefile`

**Changes:**
- Update `make e2e` to use new API format
- Verify test commands work correctly

**Status:** Review and update

---

## Test Execution Plan

### Step 1: Unit Tests (8.1)
1. Review existing validation tests
2. Create `test_analysis_config.py` for analysis.json tests
3. Create `test_validation_errors.py` for error handling tests
4. Run all unit tests: `pytest tests/v2/ -v`

### Step 2: Integration Tests (8.2)
1. Review existing API tests
2. Create `test_analysis_json_validation.py`
3. Run integration tests: `pytest tests/v2/test_api.py -v`

### Step 3: End-to-End Tests (8.3)
1. Run existing E2E tests: `pytest tests/v2/e2e.py -v`
2. Add new test cases for Phase 8.3 scenarios
3. Run all E2E tests

### Step 4: Regression Tests (8.4)
1. Run baseline comparison test (Phase 5+6 already done)
2. Verify all existing tests pass
3. Compare report outputs against baseline

### Step 5: Update Test Harnesses (8.5)
1. Update `e2e.py` to use new API format
2. Update `tests/v2/e2e.py` if needed
3. Update `Makefile` if needed

---

## Success Criteria

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ All E2E tests pass
- ✅ All regression tests pass (no changes to outputs)
- ✅ Test harnesses updated to use new API format
- ✅ analysis.json matches request exactly
- ✅ metadata.json includes request/response
- ✅ All validation errors return correct status codes
- ✅ No hardcoded values remain in code
- ✅ All file paths come from analysis.json

---

## Notes

- Baseline run: `4FdphgBQxhZkwfifoZktPY` (before Issue #553)
- All test results should match baseline (no regressions)
- Test harnesses must be updated to use new API format
- All tests should use the automated test scripts/modules

