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

---

## Test Results

### app/api/density.py Removal
- **E2E Test:** ✅ PASS (Run ID: ZTARPErEHMRfZDB2JNGUPZ)
- **Status:** All endpoints UP, no errors/warnings
- **Verification:** No references found, main.py imports successfully
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
