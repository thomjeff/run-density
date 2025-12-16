# Issue #537 Assessment: test-v2 Deprecation Analysis

**Date:** December 16, 2025  
**Issue:** #537 - Makefile test-v2 'Error 1' thrown  
**Status:** Assessment Complete

---

## Issue Summary

**Problem:** Running `make test-v2` a second time throws "Error 1" because:
1. Script uses `docker-compose run --rm -d --name run-density-test` (line 22)
2. Container from first run remains running (not stopped by `docker-compose down`)
3. Second run fails when trying to create container with same name
4. Script has `set -e` so exits immediately on error

**Root Cause:** 
- `docker-compose run` creates containers outside the compose project
- `docker-compose down` (line 17) doesn't stop containers created with `docker-compose run`
- Container name collision on subsequent runs

---

## test-v2 vs e2e-v2 Comparison

### test-v2 (`scripts/test_v2_analysis.sh`)

**Purpose:** Simple smoke test for v2 analysis API

**What it does:**
1. Starts container without hot reload (`docker-compose run`)
2. Waits for health check
3. Calls `/runflow/v2/analyze` with hardcoded payload
4. Checks HTTP 200 status
5. Extracts and displays run_id
6. Leaves container running for inspection

**What it doesn't do:**
- ❌ No output file validation
- ❌ No day isolation checks
- ❌ No golden file comparison
- ❌ No schema validation
- ❌ No comprehensive test coverage

**Lines of code:** 123 lines (bash script)

**Execution time:** ~2-3 minutes (API call only)

---

### e2e-v2 (`tests/v2/e2e.py`)

**Purpose:** Comprehensive end-to-end test suite for v2 analysis

**What it does:**
1. Uses `docker-compose up -d` (proper container management)
2. Calls `/runflow/v2/analyze` with same payload
3. **Validates all output files exist:**
   - Density.md, Flow.csv, Flow.md
   - bins.parquet, metadata.json
   - All UI artifacts (meta.json, flags.json, flow.json, etc.)
   - Segments.geojson, heatmaps
4. **Validates day isolation:**
   - bins.parquet contains only expected events per day
   - Flow.csv contains only expected event pairs
   - segments.geojson contains only expected seg_ids
5. **Validates same-day interactions**
6. **Validates cross-day isolation**
7. **Golden file regression tests**
8. **Schema validation**

**Lines of code:** 865 lines (pytest suite)

**Execution time:** ~30 minutes (full validation)

**Test scenarios:**
- `test_saturday_only_scenario`
- `test_sunday_only_scenario`
- `test_mixed_day_scenario`
- `test_cross_day_isolation`
- `test_same_day_interactions`
- Golden file regression tests (3 scenarios)

---

## Overlap Analysis

### ✅ **Complete Overlap**

Both test suites:
- Call the same API endpoint: `/runflow/v2/analyze`
- Use the same payload (Saturday + Sunday events)
- Test the same v2 analysis pipeline
- Generate the same outputs

### ❌ **test-v2 Provides No Additional Value**

Everything `test-v2` does is already covered by `e2e-v2`:
- ✅ API call → Covered by e2e-v2
- ✅ HTTP 200 check → Covered by e2e-v2 (asserts status_code == 200)
- ✅ Run ID extraction → Covered by e2e-v2 (validates run_id in response)
- ✅ Output generation → Covered by e2e-v2 (validates all outputs exist)

**e2e-v2 does MORE:**
- Validates output correctness (not just existence)
- Validates day isolation (critical for v2)
- Validates data integrity
- Regression testing with golden files

---

## Assessment: Should test-v2 be Deprecated?

### ✅ **YES - Deprecate test-v2**

**Reasons:**

1. **Complete Functional Overlap**
   - e2e-v2 does everything test-v2 does and more
   - No unique functionality in test-v2

2. **Bug-Prone Implementation**
   - Container name collision issue (#537)
   - Uses `docker-compose run` which creates orphaned containers
   - Poor error handling (`set -e` causes immediate exit)

3. **Maintenance Burden**
   - Two test suites doing the same thing
   - Confusion about which one to use
   - Duplicate code to maintain

4. **Project Standardization**
   - Issue #537 explicitly states: "the project _must_ standardize on one test suite / harness"
   - e2e-v2 is the comprehensive, production-ready test suite
   - test-v2 is a legacy smoke test

5. **Session Notes Already Suggest Deprecation**
   - From `cursor/sessions/2025-12-16-issue-535.md` line 194:
     > "`make test-v2` - Run v2 analysis (generates outputs) and this might be considered for `archive` as it appears to overlap with e2e test suite."

---

## Recommended Action Plan

### Phase 1: Fix Immediate Bug (Optional)
If we want to keep test-v2 temporarily, fix the container collision:
```bash
# Add before docker-compose run:
docker stop run-density-test 2>/dev/null || true
docker rm run-density-test 2>/dev/null || true
```

### Phase 2: Deprecate test-v2 (Recommended)

1. **Update Makefile:**
   - Remove `test-v2` target
   - Update help text to recommend `e2e-v2` instead

2. **Archive test-v2 script:**
   - Move `scripts/test_v2_analysis.sh` to `archive/`
   - Add deprecation notice

3. **Update Documentation:**
   - Remove references to `test-v2` from README
   - Update session notes
   - Add migration guide: "Use `make e2e-v2` instead of `make test-v2`"

4. **Update Issue #537:**
   - Close issue with resolution: "Deprecated test-v2 in favor of e2e-v2"
   - Add comment explaining deprecation decision

---

## Migration Guide for Users

**Old way:**
```bash
make test-v2  # Simple smoke test
```

**New way:**
```bash
# Full E2E test suite (recommended)
make e2e-v2

# Or run individual scenarios (faster iteration)
make e2e-v2-sat   # Saturday-only test (~2 min)
make e2e-v2-sun   # Sunday-only test (~2 min)
```

**Benefits:**
- ✅ Comprehensive validation
- ✅ Day isolation checks
- ✅ Regression testing
- ✅ Proper container management
- ✅ No bugs

---

## Conclusion

**Recommendation: DEPRECATE test-v2**

**Rationale:**
- Complete functional overlap with e2e-v2
- Bug-prone implementation (Issue #537)
- Maintenance burden
- Project standardization requirement
- e2e-v2 is production-ready and comprehensive

**Action:** Archive test-v2 and standardize on e2e-v2 as the single test harness for v2 analysis.

---

**Assessment completed:** December 16, 2025  
**Next step:** User approval → Deprecation implementation

