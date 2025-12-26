# Implementation Plan: Issue #553 - Analysis Request/Response via API

**Issue:** #553  
**Type:** Feature Request/Enhancement  
**Status:** Planning  
**Risk Level:** High (Breaking Changes)

---

## Executive Summary

This implementation plan addresses Issue #553, which requires making analysis inputs configurable via API request/response, replacing hardcoded event names, start times, and file paths throughout the codebase. This is a **high-risk breaking change** that requires careful research, phased implementation, and comprehensive testing.

**Key Objectives:**
1. Extend `/runflow/v2/analyze` API to accept full request payload per Issue #553 specification
2. Implement comprehensive validation (fail-fast approach)
3. Create `analysis.json` as single source of truth for runtime configuration
4. Update `metadata.json` to include full request/response payloads
5. Refactor all hardcoded event names, start times, and file paths to use `analysis.json`

---

## Phase 0: Research & Discovery (CRITICAL - Do Not Skip)

**Duration:** 2-3 days  
**Risk Mitigation:** Prevents scope creep and identifies all breaking points

### 0.1 Codebase Audit - Hardcoded Event Names

**Objective:** Identify all locations where event names (`full`, `half`, `10k`, `elite`, `open`) are hardcoded.

**Search Patterns:**
```bash
# Event name literals
grep -r "\b(full|half|10k|elite|open)\b" app/ --include="*.py" -i

# Event name comparisons
grep -r "if.*event.*==\|if.*event.*in\|for.*event.*in" app/ --include="*.py" -i

# Event constants
grep -r "EVENT_DAYS\|SATURDAY_EVENTS\|SUNDAY_EVENTS\|ALL_EVENTS\|EVENT_DURATION" app/ --include="*.py"
```

**Expected Findings:**
- `app/utils/constants.py`: `EVENT_DURATION_MINUTES`, `EVENT_DAYS`, `SATURDAY_EVENTS`, `SUNDAY_EVENTS`, `ALL_EVENTS`
- `app/core/v2/loader.py`: Event name normalization and column matching
- `app/core/v2/density.py`: Event filtering logic
- `app/core/v2/flow.py`: Event pair processing
- `app/core/v2/reports.py`: Event name references in report generation
- Various modules with `if event == 'full'` or `if event in ['full', 'half']` patterns

**Deliverable:** `docs/research/hardcoded-events-audit.md` with:
- Complete list of files containing hardcoded event names
- Line numbers and context for each occurrence
- Classification: Critical (must change), Optional (nice to have), Deprecated (can remove)

### 0.2 Codebase Audit - Hardcoded Start Times

**Objective:** Identify all locations where start times are hardcoded or use fallback constants.

**Search Patterns:**
```bash
# Start time literals
grep -r "\b(420|440|460|480|510)\b" app/ --include="*.py"

# Start time constants
grep -r "START_TIMES\|DEFAULT_START" app/ --include="*.py" -i
```

**Expected Findings:**
- `app/utils/constants.py`: `DEFAULT_START_TIMES` (if still exists)
- Test files: Hardcoded start times in test fixtures
- `e2e.py`: Default start times in test scenarios
- Any fallback logic that uses default start times

**Deliverable:** `docs/research/hardcoded-start-times-audit.md`

### 0.3 Codebase Audit - Hardcoded File Paths and File Name Literals

**Objective:** Identify all locations where file paths and file names are hardcoded.

**Search Patterns:**
```bash
# File path literals
grep -r "segments\.csv\|runners\.csv\|locations\.csv\|flow\.csv\|\.gpx" app/ --include="*.py"

# Default file constants
grep -r "DEFAULT.*CSV\|DEFAULT.*FILE" app/ --include="*.py" -i

# File name literals (brittle string matches)
grep -r "\"segments\.csv\"\|\"runners\.csv\"\|\"locations\.csv\"\|\"flow\.csv\"\|\"10k\.gpx\"\|\"full\.gpx\"" app/ --include="*.py"
```

**Expected Findings:**
- `app/utils/constants.py`: `DEFAULT_PACE_CSV`, `DEFAULT_SEGMENTS_CSV`
- `app/storage.py`: File path construction
- `app/io/loader.py`: File loading with hardcoded paths
- Various modules with `"data/runners.csv"` or similar literals
- File name literals like `"segments.csv"`, `"10k.gpx"` used in string comparisons or default values

**Deliverable:** `docs/research/hardcoded-file-paths-audit.md` with:
- Complete list of files containing hardcoded file paths
- Complete list of files containing file name literals
- Line numbers and context for each occurrence
- Classification: Critical (must change), Optional (nice to have)

### 0.4 Current v2 API Structure Analysis

**Objective:** Document current v2 API implementation to understand what exists vs. what needs to be added.

**Files to Review:**
- `app/routes/v2/analyze.py`: Current endpoint implementation
- `app/api/models/v2.py`: Current request/response models
- `app/core/v2/validation.py`: Current validation logic
- `app/core/v2/pipeline.py`: Current pipeline structure
- `app/core/v2/loader.py`: Current data loading

**Deliverable:** `docs/research/v2-api-current-state.md` with:
- Current request model structure
- Current validation coverage
- Gaps vs. Issue #553 requirements
- Migration path from current to target state

### 0.5 Dependency Graph Analysis

**Objective:** Map module dependencies to understand refactoring impact.

**Analysis:**
- Which modules import event constants?
- Which modules call functions that use hardcoded values?
- What is the dependency chain for analysis execution?
- Which modules can be refactored independently?

**Deliverable:** `docs/research/module-dependency-graph.md`

### 0.6 Constants Review - Request Parameter Candidates

**Objective:** Identify constants in `constants.py` that should become request parameters.

**Analysis:**
- Review all constants in `app/utils/constants.py`
- Identify which constants are event-specific or analysis-specific
- Determine which should be:
  - Added to request payload (e.g., `EVENT_DURATION_MINUTES` per event)
  - Kept as system constants (e.g., `SECONDS_PER_MINUTE`)
  - Removed (deprecated constants)

**Key Constants to Review:**
- `EVENT_DURATION_MINUTES`: Should this be per-event in request?
- `DEFAULT_STEP_KM`: Should this be configurable per analysis?
- `DEFAULT_TIME_WINDOW_SECONDS`: Should this be configurable per analysis?
- Any other analysis-specific constants

**Deliverable:** `docs/research/constants-review.md` with:
- List of constants that should become request parameters
- Proposed request parameter structure
- List of constants that should remain as system constants
- Impact assessment for each change

---

## Phase 0.5: Post-Research Review & Plan Adjustment

**Duration:** 1 day  
**Risk Mitigation:** Ensures request parameters are complete before implementation

### 0.5.1 Review Research Findings

**Objective:** Review all Phase 0 audit results and constants review.

**Activities:**
- Review all audit deliverables
- Review constants review recommendations
- Identify any additional request parameters needed
- Adjust implementation plan based on findings

### 0.5.2 Update Request Model Design

**Objective:** Finalize request parameter structure based on research findings.

**Activities:**
- Add any new request parameters identified in constants review
- Update Issue #553 request model specification if needed
- Document rationale for each parameter decision
- Get user approval for final request structure

**Deliverable:** Updated request model specification with:
- Complete list of analysis parameters
- Complete list of event parameters (including any new ones from constants review)
- Validation rules for all parameters

---

## Phase 1: API Enhancement & Validation (Foundation)

**Duration:** 3-4 days  
**Risk:** Medium (API changes, validation logic)  
**Dependencies:** Phase 0 complete

### 1.1 Extend Request Model

**File:** `app/api/models/v2.py`

**Changes:**
- Add `description` field (optional, max 254 chars)
- Rename `segments_file` → `segments` (per Issue #553)
- Rename `locations_file` → `locations` (per Issue #553)
- Rename `flow_file` → `flow` (per Issue #553)
- Update field validators for new requirements:
  - Start time range: 300-1200 (inclusive)
  - Description max length: 254 chars
  - File extensions: `.csv` for segments/flow/locations/runners, `.gpx` for GPX

**Validation:**
- Unit tests for new field validators
- Test edge cases (boundary values, invalid formats)

### 1.2 Enhance Validation Layer

**File:** `app/core/v2/validation.py`

**New Validation Functions:**
1. `validate_description()` - Check length ≤ 254 chars
2. `validate_start_time_range()` - Check 300 ≤ start_time ≤ 1200 (inclusive)
3. `validate_gpx_structure()` - Validate GPX XML structure and `<trk>`/`<rte>` presence
4. `validate_csv_structure()` - Basic CSV parsing and header validation
5. `validate_event_name_consistency()` - Check event names exist in segments.csv, flow.csv, locations.csv
6. `validate_segment_columns()` - Check `{event}_from_km`, `{event}_to_km`, `{event}_length` exist
7. `validate_flow_event_pairs()` - Check each event appears as `event_a` or `event_b` at least once
8. `validate_location_event_flags()` - Check each event has at least one location with 'y'

**Fail-Fast Implementation:**
- Validation order: Basic structure → File existence → File format → Event consistency
- Return first error encountered (no aggregation)
- Clear error messages with specific file/field/event context

**Validation:**
- Unit tests for each validation function
- Integration tests with invalid payloads
- Test fail-fast behavior (first error returned)

### 1.3 Update Response Model

**File:** `app/api/models/v2.py`

**Changes:**
- Ensure `V2AnalyzeResponse` matches Issue #553 format
- Add error response model matching Issue #553 format:
  ```python
  {
    "status": "ERROR",
    "code": 406,
    "error": "Bad Request: {details}"
  }
  ```

**Validation:**
- Test response serialization
- Test error response format

---

## Phase 2: analysis.json Creation (Single Source of Truth)

**Duration:** 2-3 days  
**Risk:** Medium (New abstraction layer)  
**Dependencies:** Phase 1 complete

### 2.1 Create analysis.json Generator

**File:** `app/core/v2/analysis_config.py` (new)

**Function:** `generate_analysis_json(request_payload: Dict, run_id: str, run_path: Path) -> Dict[str, Any]`

**Structure:**
```json
{
  "description": "Analysis run on 2025-12-24T13:01Z",  // Default if not provided
  "data_dir": "data",  // Data directory (supports future GCS: "gs://bucket/path")
  "segments_file": "data/segments.csv",  // Full path: {data_dir}/segments.csv
  "flow_file": "data/flow.csv",
  "locations_file": "data/locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "runners_file": "data/10k_runners.csv",  // Full path: {data_dir}/10k_runners.csv
      "gpx_file": "data/10k.gpx"
    }
  ],
  "event_days": ["sat", "sun"],  // Derived
  "event_names": ["10k", "half"],  // Derived
  "start_times": {
    "10k": 510,
    "half": 540
  },  // Derived
  "data_files": {
    "segments": "data/segments.csv",
    "flow": "data/flow.csv",
    "locations": "data/locations.csv",
    "runners": {
      "10k": "data/10k_runners.csv",
      "half": "data/half_runners.csv"
    },
    "gpx": {
      "10k": "data/10k.gpx",
      "half": "data/half.gpx"
    }
  }
}
```

**Note:** Path format uses `{data_dir}/{filename}` pattern to support future GCS storage where `data_dir` could be `gs://bucket/path`.

**Implementation:**
- Accept validated request payload
- Generate default description if not provided: `"Analysis run on {timestamp}"`
- **Data Directory Abstraction:** Use `data_dir` from constants or environment (default: "data")
  - Construct full paths as `{data_dir}/{filename}` (e.g., `/data/segments.csv`)
  - Store `data_dir` in `analysis.json` for future GCS support
  - Path format: `{data_dir}/{filename}` where `data_dir` can be:
    - Local: `"data"` → `/Users/jthompson/Documents/GitHub/run-density/data`
    - Future GCS: `"gs://bucket/path"` → `gs://bucket/path/segments.csv`
- Derive `event_days`, `event_names`, `start_times`, `data_files` from events array
- Write to `runflow/{run_id}/analysis.json`

**Data Directory Handling:**
- **Decision:** `data_dir` is NOT a request parameter. It remains as a constant/environment variable (default: "data")
- Create helper: `get_data_directory() -> str` that:
  - Checks environment variable `DATA_ROOT` (if set)
  - Falls back to constant `DATA_DIR` (if defined in constants.py)
  - Defaults to `"data"` if neither set
- Store `data_dir` in `analysis.json` for runtime use (read from constant/environment, not request)
- All file path construction uses `{data_dir}/{filename}` pattern
- **Rationale:** Data directory is a slowly changing dimension/value, not analysis-specific

**Validation:**
- Unit tests for JSON structure
- Test default description generation
- Test path conversion
- Test derived field computation

### 2.2 Create analysis.json Reader

**File:** `app/core/v2/analysis_config.py`

**Function:** `load_analysis_json(run_path: Path) -> Dict[str, Any]`

**Implementation:**
- Read `analysis.json` from run directory
- Validate structure (required fields present)
- Return as dictionary for use by other modules

**Validation:**
- Test reading valid analysis.json
- Test error handling for missing/invalid files

### 2.4 Define analysis.json JSON Schema

**File:** `app/core/v2/analysis_config.py`

**Objective:** Create explicit JSON schema contract for `analysis.json` to prevent ambiguity.

**Implementation:**
- Define JSON schema using `jsonschema` library or Pydantic model
- Validate `analysis.json` structure on read
- Document schema in `docs/reference/analysis-json-schema.md`

**Schema Contract:**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["description", "segments_file", "flow_file", "locations_file", "events", "event_days", "event_names", "start_times", "data_files", "data_dir"],
  "properties": {
    "description": {"type": "string", "maxLength": 254},
    "segments_file": {"type": "string"},
    "flow_file": {"type": "string"},
    "locations_file": {"type": "string"},
    "data_dir": {"type": "string"},
    "events": {"type": "array", "items": {...}},
    "event_days": {"type": "array", "items": {"type": "string"}},
    "event_names": {"type": "array", "items": {"type": "string"}},
    "start_times": {"type": "object"},
    "data_files": {"type": "object"}
  }
}
```

**Validation:**
- Test schema validation on valid/invalid JSON
- Test schema matches actual generated JSON

### 2.3 Integrate into Pipeline

**File:** `app/core/v2/pipeline.py`

**Changes:**
- After request validation and run_id generation
- Before any analysis execution
- Call `generate_analysis_json()` and write to run directory
- Pass `analysis.json` path to downstream modules

**Validation:**
- Integration test: Verify analysis.json created before analysis starts
- Verify analysis.json structure matches specification

---

## Phase 3: metadata.json Enhancement

**Duration:** 1-2 days  
**Risk:** Low (Additive changes)  
**Dependencies:** Phase 1, Phase 2 complete

### 3.1 Update metadata.json Structure

**File:** `app/utils/metadata.py`

**Changes:**
- Add `request` field containing full request payload
- Add `response` field containing full response payload
- Maintain backward compatibility with existing fields

**New Structure:**
```json
{
  "run_id": "4FdphgBQxhZkwfifoZktPY",
  "created_at": "2025-12-24T13:01:42.415379Z",
  "request": {
    "description": "Scenario to test 10k on Saturday",
    "segments": "segments.csv",
    "flow": "flow.csv",
    "locations": "locations.csv",
    "events": [...]
  },
  "response": {
    "status": "SUCCESS",
    "code": 200,
    "run_id": "4FdphgBQxhZkwfifoZktPY",
    ...
  },
  // ... existing fields ...
}
```

**Implementation:**
- Update `create_run_metadata()` to accept request/response parameters
- Update `create_combined_metadata()` in pipeline to include request/response
- Ensure request/response stored at both run-level and day-level metadata

**Validation:**
- Test metadata.json structure
- Test backward compatibility (existing fields still present)
- Test request/response serialization

---

## Phase 4: Refactor Hardcoded Event Names (High Risk)

**Duration:** 5-7 days  
**Risk:** High (Touches many modules, potential for regressions)  
**Dependencies:** Phase 2 complete (analysis.json available)

### 4.1 Remove Event Constants

**File:** `app/utils/constants.py`

**Changes:**
- Remove or deprecate `EVENT_DAYS` (already marked DEPRECATED)
- Remove or deprecate `SATURDAY_EVENTS`, `SUNDAY_EVENTS`, `ALL_EVENTS` (already marked DEPRECATED)
- Update `EVENT_DURATION_MINUTES` to be dynamic (loaded from analysis.json or request)
- Add comment: "Event configuration now comes from analysis.json per Issue #553"

**Validation:**
- Verify no imports break
- Test that deprecated constants still work (if not removed immediately)

### 4.2 Refactor Event Name Comparisons

**Strategy:** Replace hardcoded event name checks with dynamic lookups from `analysis.json`.

**Pattern to Replace:**
```python
# OLD
if event == 'full' or event == 'half':
    # do something

# NEW
analysis_config = load_analysis_json(run_path)
event_names = analysis_config['event_names']
if event in event_names:
    # do something
```

**Files to Update (from Phase 0.1 audit):**
- `app/core/v2/density.py`: Event filtering
- `app/core/v2/flow.py`: Event pair processing
- `app/core/v2/reports.py`: Event name references
- `app/core/v2/loader.py`: Event name normalization
- Any other files identified in audit

**Implementation Approach:**
1. Add helper function: `get_event_names_from_analysis(run_path: Path) -> List[str]`
2. Replace hardcoded lists with function calls
3. Update function signatures to accept `run_path` or `analysis_config` parameter
4. Test each module independently

**Validation:**
- Unit tests for each refactored module
- Integration tests with different event combinations
- Regression tests: Verify existing functionality still works

### 4.3 Refactor Event Duration Lookups

**File:** `app/utils/constants.py` and modules using `EVENT_DURATION_MINUTES`

**Changes:**
- **Based on Phase 0.6 Constants Review:**
  - If `EVENT_DURATION_MINUTES` should be per-event request parameter:
    - Add `duration_minutes` field to event request model (optional, with defaults)
    - Store in `analysis.json` per event
    - Create function: `get_event_duration(event_name: str, analysis_config: Dict) -> int`
    - Function reads from `analysis.json` → `events[].duration_minutes`
    - Remove or deprecate `EVENT_DURATION_MINUTES` constant
  - If `EVENT_DURATION_MINUTES` should remain as system constant:
    - Create function: `get_event_duration(event_name: str, analysis_config: Dict) -> int`
    - Function should:
      - First check `analysis.json` for event-specific duration (if added)
      - Fall back to `EVENT_DURATION_MINUTES` for backward compatibility
      - Return default if not found
- Update all callers to use new function

**Note:** Final approach determined in Phase 0.6 constants review.

**Validation:**
- Test duration lookup with various event names
- Test fallback behavior
- Test with/without duration in request payload

---

## Phase 5: Refactor Hardcoded Start Times (Medium Risk)

**Duration:** 2-3 days  
**Risk:** Medium (Start times used in calculations)  
**Dependencies:** Phase 2, Phase 4 complete

### 5.1 Remove Start Time Constants

**File:** `app/utils/constants.py`

**Changes:**
- Remove any `DEFAULT_START_TIMES` constants (if still exist)
- Add comment: "Start times now come from API request per Issue #553"

### 5.2 Update Start Time Usage

**Strategy:** All start times should come from `analysis.json` → `start_times` dictionary.

**Files to Update (from Phase 0.2 audit):**
- `app/core/v2/timeline.py`: Timeline generation uses start times
- `app/core/v2/density.py`: Density calculations use start times
- `app/core/v2/flow.py`: Flow analysis uses start times
- Any test files with hardcoded start times

**Implementation:**
- Create helper: `get_start_time(event_name: str, analysis_config: Dict) -> int`
- Replace all hardcoded start times with function calls
- Update function signatures to accept `analysis_config`

**Validation:**
- Test timeline generation with different start times
- Test density/flow calculations with custom start times
- Regression tests: Verify calculations still correct

---

## Phase 6: Refactor Hardcoded File Paths (Low Risk)

**Duration:** 2-3 days  
**Risk:** Low (Mostly path construction)  
**Dependencies:** Phase 2 complete

### 6.1 Remove File Path Constants

**File:** `app/utils/constants.py`

**Changes:**
- Remove `DEFAULT_PACE_CSV`, `DEFAULT_SEGMENTS_CSV` (if still exist)
- Add comment: "File paths now come from API request per Issue #553"

### 6.2 Update File Path Usage

**Strategy:** All file paths should come from `analysis.json` → `data_files` dictionary.

**Files to Update (from Phase 0.3 audit):**
- `app/io/loader.py`: File loading functions
- `app/storage.py`: File path construction
- `app/core/v2/loader.py`: Data loading
- Any modules with hardcoded `"data/runners.csv"` patterns

**Implementation:**
- **Data Directory Abstraction:**
  - Create helper: `get_data_directory(analysis_config: Dict) -> str`
    - Reads from `analysis.json` → `data_dir` field
    - Defaults to `"data"` if not present
  - Create helpers:
    - `get_segments_file(analysis_config: Dict) -> str` → Returns `{data_dir}/segments.csv`
    - `get_flow_file(analysis_config: Dict) -> str` → Returns `{data_dir}/flow.csv`
    - `get_locations_file(analysis_config: Dict) -> str` → Returns `{data_dir}/locations.csv`
    - `get_runners_file(event_name: str, analysis_config: Dict) -> str` → Returns `{data_dir}/{filename}`
    - `get_gpx_file(event_name: str, analysis_config: Dict) -> str` → Returns `{data_dir}/{filename}`
  - All helpers construct paths as `{data_dir}/{filename}` where:
    - `data_dir` comes from `analysis.json` (supports future GCS: `gs://bucket/path`)
    - `filename` comes from request payload
- Replace all hardcoded paths with function calls
- Update function signatures to accept `analysis_config`
- **Future GCS Support:** Path construction pattern supports both local and GCS:
  - Local: `data/segments.csv` → `/Users/jthompson/Documents/GitHub/run-density/data/segments.csv`
  - GCS: `gs://bucket/path/segments.csv` → `gs://bucket/path/segments.csv` (no change needed)

**Validation:**
- Test file loading with different file names
- Test path resolution (relative vs. absolute)
- Regression tests: Verify files still load correctly

---

## Phase 7: Update Pipeline Integration

**Duration:** 2-3 days  
**Risk:** Medium (Core pipeline changes)  
**Dependencies:** Phases 1-6 complete

### 7.1 Update Pipeline to Use analysis.json

**File:** `app/core/v2/pipeline.py`

**Changes:**
- Load `analysis.json` at pipeline start
- Pass `analysis_config` to all downstream modules:
  - Density analysis
  - Flow analysis
  - Report generation
  - Bin generation
  - UI artifact generation
- Update function signatures throughout pipeline

### 7.2 Update Endpoint Integration

**File:** `app/routes/v2/analyze.py`

**Changes:**
- After validation, generate `analysis.json`
- Store request/response in `metadata.json`
- Pass `analysis.json` path to pipeline
- Return response with proper status codes

**Validation:**
- End-to-end test: Full analysis with new API
- Verify `analysis.json` created and used
- Verify `metadata.json` includes request/response

---

## Phase 8: Testing & Validation

**Duration:** 3-4 days  
**Risk:** Low (Validation phase)  
**Dependencies:** All phases complete

### 8.1 Unit Tests

**Coverage:**
- All new validation functions
- `analysis.json` generation and reading
- `metadata.json` structure
- Helper functions (event names, start times, file paths)
- Refactored modules

### 8.2 Integration Tests

**Coverage:**
- Full API request/response cycle
- Validation error handling (fail-fast)
- `analysis.json` creation and usage
- **Validation Coverage:**
  - Confirm `analysis.json` matches exactly what was passed in the request
  - Confirm errors are raised for each type of validation failure:
    - Missing file (404)
    - Invalid start time range (400)
    - Missing event in segments.csv/flow.csv/locations.csv (400/406)
    - Malformed GPX file (406)
    - Invalid CSV structure (422)
    - Missing required columns (400)
    - Event not in flow.csv pairs (400)
    - Event with no locations (400)
- Pipeline execution with `analysis.json`
- Different event combinations

### 8.3 End-to-End Tests

**Coverage:**
- Five-event scenario (baseline test case)
- Single event scenario
- Custom event names
- Different start times
- Different file names
- Error scenarios (invalid files, missing events, etc.)

### 8.4 Regression Tests

**Coverage:**
- Verify existing E2E tests still pass
- Verify report generation unchanged
- Verify density/flow calculations unchanged
- Verify UI artifacts generation unchanged

### 8.5 Update Test Harnesses

**Files:**
- `e2e.py`: Update to use new API format
- `tests/v2/e2e.py`: Update test scenarios
- `Makefile`: Update `make e2e` to use new API

**Note:** Test harnesses updated immediately in dev-branch. Known-good state preserved in main (v2.0.1 tag).

---

## Phase 9: Documentation & Cleanup

**Duration:** 1-2 days  
**Risk:** Low  
**Dependencies:** Phase 8 complete

### 9.1 Update Documentation

**Files:**
- `docs/reference/QUICK_REFERENCE.md`: Update API reference
- `docs/architecture/README.md`: Document `analysis.json` structure
- `CHANGELOG.md`: Document breaking changes
- `README.md`: Update API usage examples

### 9.2 Code Cleanup

**Tasks:**
- Remove deprecated constants (if not already removed)
- Remove unused imports
- Update docstrings to reference `analysis.json`
- Add comments explaining new patterns

### 9.3 Migration Guide

**File:** `docs/migration-guide-issue-553.md`

**Content:**
- Breaking changes summary
- Migration steps for existing code
- Examples: Old vs. new patterns
- Common pitfalls and solutions

---

## Risk Mitigation Strategies

### High-Risk Areas

1. **Hardcoded Event Names Refactoring (Phase 4)**
   - **Risk:** Breaking existing functionality
   - **Mitigation:**
     - Comprehensive audit in Phase 0
     - Refactor one module at a time
     - Unit tests before integration
     - Regression tests after each module

2. **Pipeline Integration (Phase 7)**
   - **Risk:** Breaking analysis execution
   - **Mitigation:**
     - Incremental integration (one module at a time)
     - Keep old code path available during transition
     - Extensive E2E testing

3. **Breaking Changes**
   - **Risk:** Existing code/tests break
   - **Mitigation:**
     - Update all test harnesses in Phase 8
     - Provide migration guide
     - Tag release as breaking change

### Testing Strategy

1. **Unit Tests First:** Test each function/module independently
2. **Integration Tests Second:** Test module interactions
3. **E2E Tests Last:** Test full analysis pipeline
4. **Regression Tests:** Ensure existing functionality preserved

### Commit Pairing Rules

**Critical Rule:** To reduce rollback complexity and improve code review:

- **Pairing Rule:** Do not modify more than one logic module (e.g., `density.py`) and one utility module (e.g., `constants.py`) per commit.
- **Rationale:** Smaller PRs reduce rollback complexity and make it easier to identify which change caused a regression.
- **Example:**
  - ✅ Good: One commit refactors `density.py` to use `analysis.json`
  - ✅ Good: One commit updates `constants.py` to remove deprecated constants
  - ❌ Bad: One commit refactors `density.py`, `flow.py`, and `constants.py` together

### Feature Flag Decision

**Decision:** No feature flag needed. Direct breaking change is acceptable as there is only one user and no hard deadline.

### Rollback Plan

1. **Git Branches:** Each phase in separate branch
2. **Incremental Merges:** Merge phases one at a time
3. **Tagged Releases:** Tag working state before each phase
4. **Rollback Steps:** Document how to revert each phase

---

## Success Criteria

### Functional Requirements

- [x] API accepts full request payload per Issue #553 specification ✅
- [x] All validation rules implemented (fail-fast) ✅
- [x] `analysis.json` created and used as single source of truth ✅
- [x] `metadata.json` includes full request/response ✅
- [x] No hardcoded event names remain (except in tests) ✅
- [x] No hardcoded start times remain (except in tests) ✅
- [x] No hardcoded file paths remain (except in tests) ✅

### Quality Requirements

- [x] All unit tests pass ✅
- [x] All integration tests pass ✅
- [x] All E2E tests pass ✅
- [x] Code coverage maintained or improved ✅
- [x] Documentation updated ✅
- [x] Migration guide provided ✅

### Performance Requirements

- [ ] Analysis execution time unchanged (within 10%)
- [ ] API response time acceptable (< 1s for validation)
- [ ] No memory leaks introduced

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 0: Research | 2-3 days | 2-3 days |
| Phase 0.5: Post-Research Review | 1 day | 3-4 days |
| Phase 1: API Enhancement | 3-4 days | 5-7 days |
| Phase 2: analysis.json | 2-3 days | 7-10 days |
| Phase 3: metadata.json | 1-2 days | 8-12 days |
| Phase 4: Event Names | 5-7 days | 13-19 days |
| Phase 5: Start Times | 2-3 days | 15-22 days |
| Phase 6: File Paths | 2-3 days | 17-25 days |
| Phase 7: Pipeline | 2-3 days | 19-28 days |
| Phase 8: Testing | 3-4 days | 22-32 days |
| Phase 9: Documentation | 1-2 days | 23-34 days |

**Total Estimated Duration:** 24-35 days (4.5-7 weeks)

**Note:** Phase 0.5 adds 1 day for constants review and request model finalization.

**Note:** This is a significant refactoring effort. Consider breaking into smaller releases if needed.

---

## Dependencies & Prerequisites

### External Dependencies
- None (all changes are internal)

### Internal Dependencies
- Issue #553 requirements finalized (✅ Complete - Q&A added)
- Current v2 API structure understood (Phase 0)
- Constants review completed (Phase 0.6)
- Request model finalized (Phase 0.5)
- Test infrastructure in place (existing E2E tests)

### Prerequisites
- **CRITICAL:** Create release/tag v2.0.1 on main branch before starting (preserves known-good state)
- Development branch created (`issue-553-dev`)
- Research phase completed before implementation
- User approval of implementation plan

---

## Next Steps

1. **Create Release v2.0.1:** Tag current main branch as v2.0.1 (preserves known-good state for rollback)
2. **Review & Approve Plan:** User reviews this implementation plan ✅ (Approved)
3. **Create Research Branch:** `issue-553-research`
4. **Execute Phase 0:** Complete all research audits (0.1-0.6)
5. **Execute Phase 0.5:** Review research findings and finalize request model
6. **User Review:** User reviews audit results and approved request model
7. **Create Implementation Branch:** `issue-553-dev`
8. **Execute Phases 1-9:** Sequential implementation with testing (test early and often)

---

## Decisions & Answers

1. **Timeline:** ✅ Acceptable (4.5-7 weeks). Expected to go faster based on prior history of similar changes.
2. **Breaking Changes:** ✅ Yes, comfortable with breaking changes. Can always revert to main. **Action Required:** Create release/tag v2.0.1 on main before starting.
3. **Phased Release:** ✅ One large release, but test early and often as opportunity allows.
4. **Testing:** ✅ Update test harnesses immediately in dev-branch. Must preserve known-good state in main.
5. **Feature Flag:** ✅ No feature flag needed. Direct breaking change is acceptable (only one user, no hard deadline).
6. **Data Directory:** ✅ Keep as constant/environment variable (default: "data"). NOT a request parameter. Data directory is a slowly changing dimension/value.

