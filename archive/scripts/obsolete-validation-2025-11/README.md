# Archived: Obsolete Validation Scripts

**Archived Date:** November 1, 2025  
**Archived By:** AI Assistant (v1.7.1 architecture cleanup)  
**Original Location:** `/scripts/`  
**Reason:** One-time validation scripts no longer needed; broken import in frontend generator

---

## Why These Were Archived

### Summary
These scripts were created for specific one-time tasks and are no longer relevant after the v1.7 architecture reset and analytics migration (Issue #429).

### Archived Files

**1. Density/Flow Validation Scripts** (4 files - 1,061 lines total)
- `validate_density_refactoring.py` (323 lines)
- `test_density_validation.py` (106 lines)
- `validate_flow_refactoring.py` (406 lines)
- `test_flow_validation.py` (226 lines)

**Purpose:** One-time validation for Issue #390 Phase 1 refactoring  
**Created:** October 28, 2025  
**Status:** ✅ Validation completed, mission accomplished  
**Evidence:**
- Only mentioned in docs/CHANGELOG as historical reference
- Not used by CI/E2E pipelines
- Not imported by any active code

**2. Frontend Data Generator** (1 file - 190 lines)
- `generate_frontend_data.py`

**Purpose:** Generate frontend JSON artifacts from analytics outputs  
**Created:** October 20, 2025  
**Status:** ❌ BROKEN since Issue #429 (analytics migration)  
**Why Broken:**
```python
# Line 20: Imports from deleted module
from analytics.export_frontend_artifacts import (  # ❌ Module deleted
    write_segments_geojson,
    write_segment_metrics_json,
    write_flags_json,
    write_meta_json
)
```

**Replacement:** Functionality moved to `app/core/artifacts/frontend.py` in Issue #429

**3. Empty Directory**
- `complexity/` (0 files)

**Status:** Empty leftover directory from Phase 4 complexity work

---

## Historical Context

### Density/Flow Validation Scripts

These scripts were created during Issue #390 to validate that refactored density and flow reports matched the original output byte-for-byte. They served their purpose during the refactoring phase.

**From density-validation-guide.md:**
> The validation script compares baseline and new density reports to ensure
> refactoring changes do not alter the output.

**Usage Example (historical):**
```bash
python scripts/validate_density_refactoring.py \
    --baseline reports/2025-10-28-1538-Density.md \
    --new reports/2025-10-28-NEW-Density.md
```

### Frontend Data Generator

This script was a temporary proof-of-concept for converting analytics outputs to frontend JSON. It became obsolete when:
1. v1.7.0 consolidated architecture
2. Issue #429 migrated analytics to `app/core/artifacts/`
3. Frontend artifact generation moved to permanent modules

---

## What Replaced Them

**Validation Scripts → Native Testing**
- E2E tests now validate output consistency
- CI pipeline includes complexity checks
- No need for standalone validation scripts

**Frontend Generator → Permanent Modules**
- `app/core/artifacts/frontend.py` - Frontend artifact generation
- `app/core/artifacts/heatmaps.py` - Heatmap generation
- Called directly by `e2e.py` and CI pipeline

---

## Restoration Instructions

**Note:** These scripts are obsolete and restoration is not recommended.

If you need to reference the validation logic:

```bash
# View archived validation script
cat archive/scripts/obsolete-validation-2025-11/validate_density_refactoring.py

# The frontend generator is broken - use current modules instead
# See: app/core/artifacts/frontend.py
```

---

## Related Documentation

- **Issue #390:** Density/Flow refactoring (validation scripts created)
- **Issue #429:** Analytics migration (frontend generator broken)
- **Current Artifacts:** `/app/core/artifacts/`
- **E2E Testing:** `/e2e.py`

---

## Verification Checklist

Before archival was completed:

- ✅ No references in `ci-pipeline.yml`
- ✅ No references in `e2e.py`
- ✅ No imports in active application code
- ✅ Frontend generator imports deleted code (broken)
- ✅ Validation complete, scripts no longer needed
- ✅ Functionality replaced by permanent modules

---

**Archived as part of v1.7.1 architecture cleanup - November 2025**
