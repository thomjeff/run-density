# Phase 3: High-Impact Candidates → Next Steps Mapping

**Issue:** #544  
**Date:** December 19, 2025  
**Status:** 🟢 Action Plan

---

## Cross-Reference Matrix

| High-Impact Candidate | Coverage | Next Step Category | Specific Action | Priority |
|----------------------|----------|-------------------|-----------------|----------|
| `app/version.py` | 15.1% | **Step 1:** <20% Coverage Files | Simplify version detection logic | 🟡 Medium |
| `app/bin_intelligence.py` | 20.7% | **Step 2:** v1 API Dependencies | Review if v1 API needed, remove if not | 🔴 High |
| `app/canonical_segments.py` | 20.9% | **Step 2:** v1 API Dependencies | Review if v1 API needed, remove if not | 🔴 High |
| `app/density_report.py` | 22.1% | **Step 2:** v1 API Dependencies | Extract v2-used functions, remove v1-only code | 🔴 High |
| `app/overlap.py` | 29.6% | **Step 2:** v1 API Dependencies | Review if legacy, remove if replaced by v2 flow | 🟡 Medium |
| `app/density_template_engine.py` | 32.2% | **Step 2:** v1 API Dependencies | Review if v1 API needed, remove if not | 🟡 Medium |
| `app/routes/api_heatmaps.py` | 40.5% | **Step 3:** Frontend Usage Verification | Verify frontend usage, remove if unused | 🟡 Medium |

---

## Detailed Action Plan

### Step 1: Review Remaining <20% Coverage Files (1 file)

#### 1.1 `app/version.py` (15.1% coverage, 114 statements)

**Current Status:**
- ✅ Used by `app/main.py` (APP_VERSION)
- ✅ Used by report generation (version headers)
- ⚠️ Low coverage suggests most logic is unused

**Investigation Needed:**
- [ ] Check which functions are actually called
- [ ] Verify if version detection logic is needed
- [ ] Simplify if possible

**Action:**
- 🔍 **Review** - Check which version detection functions are used
- 🧹 **Simplify** - Remove unused version detection logic
- ✅ **Keep** - Core version reporting is needed

**Risk:** ✅ Low - Small file, mostly version detection

**Estimated Impact:** ~50-100 lines removable

---

### Step 2: Review v1 API Dependencies (5 files)

#### 2.1 `app/bin_intelligence.py` (20.7% coverage, 114 statements)

**Current Status:**
- ✅ Used by `app/density_report.py` (v1 API)
- ✅ Used by report generation
- ⚠️ Only used by v1 API (not v2 E2E tests)

**Investigation Needed:**
- [ ] Check if `density_report.py` is used by v2 pipeline
- [ ] Verify if v1 API endpoints are still needed
- [ ] Check if functions are used by v2 via `density_report.py`

**Action:**
- 🔍 **Review** - Check if v1 API is needed
- 🗑️ **Remove** - If only used by v1 API and v1 API is deprecated
- ✅ **Keep** - If used by v2 pipeline or reports

**Risk:** ⚠️ Medium - Used by v1 API

**Estimated Impact:** ~50-100 lines removable if v1 API not needed

---

#### 2.2 `app/canonical_segments.py` (20.9% coverage, 86 statements)

**Current Status:**
- ✅ Used by `app/density_report.py` (v1 API)
- ⚠️ Status: May be legacy
- ⚠️ Only used by v1 API (not v2 E2E tests)

**Investigation Needed:**
- [ ] Check if `density_report.py` is used by v2 pipeline
- [ ] Verify if v1 API endpoints are still needed
- [ ] Check if functions are used by v2 via `density_report.py`

**Action:**
- 🔍 **Review** - Check if v1 API is needed
- 🗑️ **Remove** - If only used by v1 API and v1 API is deprecated
- ✅ **Keep** - If used by v2 pipeline or reports

**Risk:** ⚠️ Medium - Used by v1 API

**Estimated Impact:** ~50-80 lines removable if v1 API not needed

---

#### 2.3 `app/density_report.py` (22.1% coverage, 1,695 statements)

**Current Status:**
- ✅ Used by `/api/density-report` endpoint (v1 API, lazy import)
- ✅ Used by v2 pipeline (via `app/core/v2/bins.py` - imports `AnalysisContext`, etc.)
- ⚠️ Large file, partially used
- ⚠️ Only 22.1% coverage suggests much unused code

**Investigation Needed:**
- [ ] Identify which functions are used by v2 pipeline
- [ ] Identify which functions are only used by v1 API
- [ ] Check if v1 API endpoints are still needed
- [ ] Map dependencies: v2 pipeline → density_report.py functions

**Action:**
- 🔍 **Review** - Identify v2-used vs v1-only functions
- ✂️ **Extract** - Move v2-used functions to separate module if needed
- 🗑️ **Remove** - Remove v1-only code if v1 API deprecated
- ✅ **Keep** - Core functions used by v2

**Risk:** ⚠️ Medium - Used by v2 pipeline for some functions

**Estimated Impact:** ~500-800 lines removable if v1-only code identified

**Priority:** 🔴 **HIGH** - Largest file, highest potential impact

---

#### 2.4 `app/overlap.py` (29.6% coverage, 228 statements)

**Current Status:**
- ⚠️ Status: Legacy code, may be replaced by v2 flow
- ⚠️ Only 29.6% coverage suggests partial use

**Investigation Needed:**
- [ ] Check if used by v2 flow analysis
- [ ] Verify if replaced by `app/core/flow/flow.py`
- [ ] Check imports/usages across codebase

**Action:**
- 🔍 **Review** - Check if used by v2 or legacy only
- 🗑️ **Remove** - If replaced by v2 flow
- ✅ **Keep** - If still used by v2

**Risk:** ⚠️ Medium - May be legacy

**Estimated Impact:** ~100-150 lines removable if legacy

---

#### 2.5 `app/density_template_engine.py` (32.2% coverage, 244 statements)

**Current Status:**
- ✅ Used by `app/density_report.py` (v1 API)
- ⚠️ Status: May be legacy
- ⚠️ Only used by v1 API (not v2 E2E tests)

**Investigation Needed:**
- [ ] Check if `density_report.py` is used by v2 pipeline
- [ ] Verify if v1 API endpoints are still needed
- [ ] Check if template engine is used by v2

**Action:**
- 🔍 **Review** - Check if v1 API is needed
- 🗑️ **Remove** - If only used by v1 API and v1 API is deprecated
- ✅ **Keep** - If used by v2 pipeline or reports

**Risk:** ⚠️ Medium - Used by v1 API

**Estimated Impact:** ~100-150 lines removable if v1 API not needed

---

### Step 3: Verify Frontend Usage (1 file)

#### 3.1 `app/routes/api_heatmaps.py` (40.5% coverage, 33 statements)

**Current Status:**
- ✅ Registered in main.py: `app.include_router(api_heatmaps_router)`
- ⚠️ Frontend usage: Need to verify
- ⚠️ Only 40.5% coverage suggests partial use

**Investigation Needed:**
- [ ] Check if frontend calls `/api/heatmaps` or `/heatmaps` endpoints
- [ ] Verify if heatmaps are served via static files instead
- [ ] Check if endpoint is used by E2E tests

**Action:**
- 🔍 **Investigate** - Check frontend usage
- 🗑️ **Remove** - If not used by frontend or E2E tests
- ✅ **Keep** - If used by frontend

**Risk:** ⚠️ Medium - May be used by frontend

**Estimated Impact:** ~20-30 lines removable if unused

---

## Prioritized Execution Order

### 🔴 High Priority (Immediate Impact)

1. **`app/density_report.py`** (1,695 statements)
   - Largest file, highest potential impact
   - Extract v2-used functions, remove v1-only code
   - **Estimated:** ~500-800 lines removable

2. **`app/bin_intelligence.py`** (114 statements)
   - Used by v1 API only
   - **Estimated:** ~50-100 lines removable

3. **`app/canonical_segments.py`** (86 statements)
   - Used by v1 API only
   - **Estimated:** ~50-80 lines removable

### 🟡 Medium Priority (Good Impact)

4. **`app/density_template_engine.py`** (244 statements)
   - Used by v1 API only
   - **Estimated:** ~100-150 lines removable

5. **`app/overlap.py`** (228 statements)
   - Legacy code, may be replaced
   - **Estimated:** ~100-150 lines removable

6. **`app/version.py`** (114 statements)
   - Simplify version detection
   - **Estimated:** ~50-100 lines removable

7. **`app/routes/api_heatmaps.py`** (33 statements)
   - Verify frontend usage
   - **Estimated:** ~20-30 lines removable

---

## Total Estimated Impact

| Category | Files | Estimated Lines Removable |
|----------|-------|---------------------------|
| **Step 1:** <20% Coverage | 1 file | ~50-100 lines |
| **Step 2:** v1 API Dependencies | 5 files | ~800-1,280 lines |
| **Step 3:** Frontend Usage | 1 file | ~20-30 lines |
| **TOTAL** | **7 files** | **~870-1,410 lines** |

**Combined with existing removals (~1,257 lines):**
- **Total Phase 3:** ~2,127-2,667 lines removed
- **Target:** 2,000-3,000 lines ✅ **ON TRACK**

---

## Investigation Checklist

### For Each v1 API Dependency File:

- [ ] Check if `app/density_report.py` is imported by v2 pipeline
- [ ] Verify which functions from `density_report.py` are used by v2
- [ ] Check if v1 API endpoints (`/api/density-report`, etc.) are called
- [ ] Verify if v1 API is needed for backward compatibility
- [ ] Check if functions are used by non-E2E code paths (CLI, admin scripts)

### For Frontend Usage Verification:

- [ ] Search frontend templates for API endpoint calls
- [ ] Check frontend JavaScript files for API calls
- [ ] Verify if functionality is served via static files instead
- [ ] Check E2E tests for endpoint usage

---

## Success Criteria

- ✅ All v1 API dependencies reviewed
- ✅ v2-used functions identified and preserved
- ✅ v1-only code removed (if v1 API deprecated)
- ✅ Frontend usage verified
- ✅ E2E tests pass after removals
- ✅ Coverage improves to 45-50% target

---

## Notes

- **v1 API Status:** Need to determine if v1 API is deprecated or still needed
- **v2 Pipeline Dependencies:** Some files may be used by v2 via `density_report.py`
- **Surgical Approach:** Focus on removing unused functions, not entire files
- **Test After Each Removal:** Run E2E tests to verify no breakage

