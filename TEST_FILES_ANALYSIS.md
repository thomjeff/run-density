# Test Files Analysis - Legacy/Obsolete Review

**Date:** December 19, 2025  
**Issue:** #544 Phase 3  
**Purpose:** Identify legacy (v1) or obsolete test files for cleanup

---

## Summary

**Active Test Files:** All tests in `tests/v2/` are **actively used** and test v2 functionality.  
**Legacy Test Files:** All legacy tests are in `archive/` directories and are **already archived**.

---

## Active Test Files (✅ KEEP - All v2)

### `tests/v2/` Directory (All Active)

| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `e2e.py` | End-to-end tests for v2 API | ✅ **ACTIVE** | Used by `make e2e-full` and `make e2e-coverage-lite` |
| `test_api.py` | Unit tests for v2 API endpoint | ✅ **ACTIVE** | Tests `/runflow/v2/analyze` endpoint |
| `test_density.py` | Unit tests for v2 density pipeline | ✅ **ACTIVE** | Tests v2 density functions (mentions v1 only in comments about preserving calculations) |
| `test_flow.py` | Unit tests for v2 flow pipeline | ✅ **ACTIVE** | Tests v2 flow functions (mentions v1 only in comments about preserving calculations) |
| `test_bins.py` | Unit tests for v2 bin generation | ✅ **ACTIVE** | Tests v2 bin functions |
| `test_validation.py` | Unit tests for v2 validation | ✅ **ACTIVE** | Tests v2 validation functions |
| `test_models.py` | Unit tests for v2 data models | ✅ **ACTIVE** | Tests v2 models (Day, Event, Runner, Segment) |
| `test_loader.py` | Unit tests for v2 loader functions | ✅ **ACTIVE** | Tests v2 data loading |
| `test_timeline.py` | Unit tests for v2 timeline generation | ✅ **ACTIVE** | Tests v2 timeline functions |
| `test_hardcoded_values.py` | Tests for Issue #512 (no hardcoded values) | ✅ **ACTIVE** | Tests that constants are used, not hardcoded values |
| `conftest.py` | Pytest configuration | ✅ **ACTIVE** | Pytest fixtures for v2 tests |

**Key Findings:**
- ✅ No references to removed modules (`cache_manager`, `io_bins`, `canonical_density_report`, `map_data_generator`, `flow_density_correlation`, `api.density`, `api.report`)
- ✅ All tests focus on v2 functionality
- ✅ `test_density.py` and `test_flow.py` mention "v1" only in comments about preserving v1 calculations in v2
- ✅ `test_hardcoded_values.py` references `app.new_density_report` which **still exists** (used by v2 pipeline)

---

## Active Test Files in `app/tests/` (✅ KEEP)

| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `validate_output.py` | Output validation module (Issue #467 Phase 3) | ✅ **ACTIVE** | Used by `make validate-output` - validates run outputs, schemas, APIs |

---

## Utility Test Scripts (🔍 REVIEW)

| File | Purpose | Status | Recommendation |
|------|---------|--------|-----------------|
| `app/utils/test_uuid_infrastructure.py` | Test script for UUID infrastructure (Epic #444 Phase 1) | ⚠️ **REVIEW** | Standalone script (not pytest), tests UUID functions that are still actively used |

**Analysis:**
- This is a standalone script (not pytest), run with `python app/utils/test_uuid_infrastructure.py`
- Tests UUID generation, validation, metadata creation functions
- **UUID functions are still actively used** by:
  - `app/core/v2/pipeline.py` (uses `generate_run_id`)
  - `app/utils/run_id.py` (implements UUID functions)
  - `app/utils/metadata.py` (implements metadata functions)
- **Recommendation:** 
  - **Option 1:** Keep as utility script for manual validation of UUID infrastructure
  - **Option 2:** Convert to pytest test in `tests/v2/` if automated testing is desired
  - **Option 3:** Archive if no longer needed (but UUID infrastructure is still in use)

---

## Archived/Legacy Test Files (❌ Already Archived)

All legacy test files are in `archive/` directories:

### `archive/declouding-2025/testing-infrastructure/unused-tests-2025-11/`
- Contains 30+ archived test files from pre-v2 era
- **Status:** Already archived, not in active test suite

### `archive/` (various subdirectories)
- Multiple archived test files from different phases
- **Status:** Already archived, not in active test suite

---

## Recommendations

### ✅ **KEEP All Active Tests**
All tests in `tests/v2/` and `app/tests/validate_output.py` are actively used and should be retained.

### 🔍 **REVIEW One File**
- **`app/utils/test_uuid_infrastructure.py`**: Determine if this is still needed or if it was a one-time validation script from Epic #444 Phase 1.

### ❌ **No Action Needed for Archived Tests**
All legacy tests are already in `archive/` directories and not part of the active test suite.

---

## Test Coverage Verification

**No test files reference removed modules:**
- ✅ No references to `app.cache_manager` (removed in Phase 3)
- ✅ No references to `app.io_bins` (removed in Phase 2B)
- ✅ No references to `app.canonical_density_report` (removed in Phase 2B)
- ✅ No references to `app.map_data_generator` (removed in Phase 2B)
- ✅ No references to `app.flow_density_correlation` (removed in Phase 2B)
- ✅ No references to `app.api.density` (removed in Phase 3)
- ✅ No references to `app.api.report` (removed in Phase 2B)

**All active tests are v2-focused and clean.**

---

## Next Steps

1. ✅ **Verify `app/utils/test_uuid_infrastructure.py` usage**
   - Check if it's referenced in any documentation or scripts
   - Determine if it's still needed or can be archived

2. ✅ **No other cleanup needed** - All active tests are v2 and relevant

