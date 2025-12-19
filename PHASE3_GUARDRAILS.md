# Phase 3 Code Cleanup — Guardrails & Instructions

**Issue:** #544  
**Status:** ✅ Guardrails Acknowledged

---

## 🚫 DO NOT DELETE (Non-Negotiable)

### 1. Guard Clauses & Error Handlers
- ✅ `try/except` blocks, especially for common issues:
  - `KeyError`, `TypeError`, `NoneType`, `ValueError`
- ✅ `if x is None`, `if not data`, etc.
- ✅ Any `log.warning`, `log.error`, or `raise` statements inside fallbacks

### 2. Feature Flags, Config Toggles, or Conditional Feature Logic
- ✅ Any checks like `if config["flag"]` or `if settings.enable_x`
- ✅ These might be disabled during testing but active in production

### 3. User Input or Data Validation
- ✅ Conditional blocks that verify user inputs, file formats, or report data
- ✅ For example: `if not segments: return ...`

### 4. Rare Execution Paths
- ✅ Code that only runs during certain data anomalies, corrupted input, or edge scenarios
- ✅ Even if test data doesn't hit them, they protect production stability

---

## ✅ Safe Candidates for Deletion (Proceed with Caution)

Only remove if **none of the above applies**:

- ✅ **Truly orphaned functions:** Never imported or referenced anywhere
- ✅ **Fully deprecated classes or CLI entrypoints**
- ✅ **Commented-out legacy code blocks**
- ✅ **Placeholder implementations never used**
- ✅ **Redundant logic superseded by refactored modules** (e.g., old bin logic post-v2)

---

## 🔍 Decision Filter

**For every file marked for cleanup, ask:**

> **"Is this code logically unreachable, or just untested?"**

- **Logically unreachable** → Safe to delete
- **Just untested** → Keep (add comment/TODO)

---

## 📝 Optional (But Recommended)

If uncertain about a block:
- Add a short inline comment: `# low coverage but retained for error handling`
- Mark areas that could be tested later: `# TODO: test this fallback logic`

---

## 🎯 Goal

**Phase 3 is clean-up, not reduction at all costs.**

Focus on **confidence-driven refactoring**. Maintain stability while trimming truly unused logic.

---

---

## 📋 Clarifications & Actions

### 1. Imported but Never Called ✅
**Answer:** If imported but never invoked (router not registered, never called), it's functionally dead.
- 🟢 **Safe to remove**
- **Action:** Mark as "not integrated into runtime" → remove with note in cleanup log

**Example:** `app/api/flow.py` - If router not registered in `main.py` and no other code uses it → treat as orphaned

---

### 2. Helper Functions in Error Paths 🔒
**Answer:** KEEP helper functions used only in error-handling/fallback paths.
- **KEEP if used in:** `try/except` blocks, guard clauses (`if not results`), error logging
- **Action:** Add comment: `# Retained for fallback/error path — not hit by E2E tests`

---

### 3. V1 API Endpoints 🧹
**Answer:** 
- **Registered but unused:** If mounted in `main.py` but no clients hit them → mark for removal
- **Lazy/faulty imports:** If importing crashes due to unmet dependencies → remove unless fixed
- **Exception:** If kept for backward compatibility (CLI tools) → confirm before deletion

**Action:**
- If no known usage and no tests hit them → safe to delete
- If unsure, move to `legacy/` module with comment: `# Legacy route — retained pending CLI deprecation`

---

### 4. Documentation Approach 📝
**Use all three:**

**A. Cleanup Log** (`Phase3_Cleanup_Log.md`)
- Filename
- Line/function removed
- Reason (e.g., "Unused router", "Deprecated v1 endpoint", "Replaced by v2")
- Decision (Removed / Retained / Moved to legacy)

**B. Inline Comments**
For preserved but low-coverage logic:
```python
# Retained for error handling / edge case logic — not hit by current tests
```

**C. Update PHASE3_FILE_ANALYSIS.md**
Add final decisions per file:
```
app/api/dashboard.py
- count_runners_for_events: 0% → Retained (used in fallback path)
- get_dashboard_report: 0% → Removed (never imported/called)
```

---

### 5. Testing Before Removal 🧪
**Answer:**
- **Critical files/functions:** Test immediately after removal
- **Trivial/unused logic:** Batch into groups, then test
- **Final rule:** Never push cleanup commit without passing E2E + unit test run

**Action:** Structure cleanup in small commits by file/group:
```bash
git commit -m "Phase 3: Remove unused v1 endpoints (api_flow, api_density)"
make e2e-coverage-lite
```

---

## ✅ Summary: Cursor Instructions

**Proceed with Phase 3 cleanup using:**
- ❌ **Remove** code that is imported but never invoked
- 🔒 **Keep** any code used in guard/error paths, even if uncovered
- 🧹 **Delete** unused v1 routes unless legacy use is confirmed
- 🗂️ **Document** all decisions in cleanup log + analysis update
- ✅ **Test** after each meaningful cleanup group

---

## ✅ Acknowledgment

- [x] Guardrails understood
- [x] Clarifications received and documented
- [x] Will apply decision filter for each file
- [x] Will preserve error handling, validation, and edge cases
- [x] Will document all decisions in cleanup log
- [x] Will test after each meaningful cleanup group
- [x] Will never commit without passing tests

