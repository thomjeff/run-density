# Phase 3 Scope: Review Medium Coverage Files

**Issue:** #544  
**Status:** 🟢 Low Priority  
**Target:** 34 files with 10-49% coverage

---

## Overview

Phase 3 focuses on reviewing files with **medium coverage (10-49%)** to identify:
- Unused functions within files
- Dead code paths
- Opportunities for refactoring

**Key Difference from Phase 1 & 2:**
- Phase 1 & 2: Removed entire files with 0% or <10% coverage
- Phase 3: Review files with partial coverage to remove unused code **within** files

---

## Scope

### Target Files
- **34 files** with 10-49% coverage
- Focus on files with **<20% coverage** first (highest priority)
- Case-by-case review (not wholesale removal)

### Approach

1. **Identify unused functions**
   - Functions that are never called
   - Functions imported but never invoked
   - Dead code paths within files

2. **Refactoring opportunities**
   - Remove unused helper functions
   - Simplify code paths
   - Consolidate duplicate logic

3. **Preserve active code**
   - Keep functions that are actually used
   - Maintain working functionality
   - Don't break existing features

---

## Priority Levels

### High Priority (<20% coverage)
- Files with very low coverage likely have more unused code
- Review these first for maximum impact

### Medium Priority (20-35% coverage)
- Moderate coverage suggests some active use
- Review for unused functions, but be more cautious

### Low Priority (35-49% coverage)
- Higher coverage suggests active use
- Focus on edge cases and dead code paths only

---

## Expected Outcomes

### Code Reduction
- **Target:** Remove 5-7 more files (~2,000-3,000 lines)
- **Method:** Remove entire files if all code is unused, OR remove unused functions within files

### Coverage Improvement
- Removing unused code increases overall coverage percentage
- Fewer total statements = higher coverage ratio

### Complexity Reduction
- Simpler codebase
- Fewer files to maintain
- Faster test execution

---

## Risk Assessment

### Low Risk ✅
- Functions with 0% coverage within files
- Functions never imported or called
- Dead code paths that can't be reached

### Medium Risk ⚠️
- Functions with low coverage that might be used in edge cases
- Functions used by non-E2E code paths (e.g., CLI tools, admin scripts)
- Functions that might be called dynamically

### High Risk ❌
- Functions with >20% coverage (likely actively used)
- Functions imported by v2 pipeline
- Core business logic functions

---

## Methodology

### Step 1: Identify Files
1. Load coverage report (`e2e-coverage.json`)
2. Filter files with 10-49% coverage
3. Sort by coverage percentage (lowest first)

### Step 2: Analyze Each File
1. Check which functions are covered
2. Check which functions are never hit
3. Verify imports/usages of unused functions
4. Check if functions are used by non-E2E paths

### Step 3: Remove Unused Code
1. Remove unused functions (if safe)
2. Remove dead code paths
3. Simplify remaining code
4. Test to ensure no breakage

### Step 4: Verify
1. Run E2E tests
2. Check coverage improvement
3. Verify no functionality broken

---

## Success Metrics

- **Files reviewed:** 34 files
- **Files removed:** 5-7 files (if all code unused)
- **Functions removed:** TBD (if partial cleanup)
- **Lines removed:** ~2,000-3,000 lines
- **Coverage improvement:** Increase from 35.3% baseline
- **Test execution:** Faster (fewer files to instrument)

---

## Notes

- **Not a wholesale removal phase** - This is about careful, surgical cleanup
- **Preserve working functionality** - Only remove code that's truly unused
- **Case-by-case basis** - Each file needs individual review
- **Low priority** - Can be done incrementally over time

---

## Related Phases

- **Phase 1:** ✅ Complete - Removed 6 files with 0% coverage
- **Phase 2A:** ✅ Complete - Removed 2 files with <10% coverage
- **Phase 2B:** ✅ Complete - Removed 4 files with <10% coverage
- **Phase 3:** 🟢 **Current** - Review 34 files with 10-49% coverage
- **Phase 4:** 🔵 Future - Improve coverage through testing

---

## Next Steps

1. ⏭️ Generate list of 34 files with 10-49% coverage
2. ⏭️ Prioritize files with <20% coverage
3. ⏭️ Review first file for unused functions
4. ⏭️ Remove unused code (function-by-function)
5. ⏭️ Test and verify
6. ⏭️ Repeat for remaining files

