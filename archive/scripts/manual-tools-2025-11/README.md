# Archived: Manual Tool Scripts

**Archived Date:** November 1, 2025  
**Archived By:** AI Assistant (v1.7.1 architecture cleanup)  
**Original Location:** `/scripts/`  
**Reason:** Manual tools no longer used; bin validation tools archived after Issue #198 completion

---

## Why These Were Archived

### Summary
These scripts were manual tools and validation helpers that are no longer needed after the v1.7 architecture reset and Issue #198 (bin datasets) completion.

### Archived Files

**1. Version Bumper Script** (1 file - 65 lines)
- `bump_version.sh`

**Purpose:** Manual version bumping (patch/minor/major)  
**Created:** September 10, 2025  
**Status:** ❌ No longer used  
**User Confirmed:** "No" - manual versioning not used anymore  
**Referenced in:**
- `app/version.py` line 257
- `docs/dev-guides/OPERATIONS.md` lines 185-191

**2. Bin Dataset Validation Tools** (1 directory, 5 files)
- `validation/README.md` (1,821 bytes)
- `validation/reconcile_bins_simple.py` (5,678 bytes)
- `validation/reconcile_canonical_segments_v2.py` (9,353 bytes)
- `validation/run_local_bins.sh` (1,050 bytes)
- `validation/verify_bins.py` (4,020 bytes)

**Purpose:** Manual validation tools for bin dataset generation (Issues #198, #217, #222)  
**Created:** September 18-20, 2025  
**Status:** ✅ Mission accomplished (Issue #198 complete, ENABLE_BIN_DATASET=false)  
**User Confirmed:** "Archive"  
**Referenced in:**
- `GUARDRAILS.md` line 441
- `CHANGELOG.md` line 1263
- `docs/dev-guides/OPERATIONS.md` line 344

**Note:** These were never used by CI/E2E pipelines, only manual validation tools

---

## What Remains in /scripts

**Active Tool:**
- `cleanup_cloud_run_revisions.sh` - Manual GCP revision cleanup tool

**User Confirmed:** "Yes, we should keep as the number of revisions grows and this is helpful. It is independent of any code, more of a dev tool for managing GCP"

---

## Historical Context

### Version Bumper

This script provided CLI commands for bumping semantic versions:
```bash
./scripts/bump_version.sh patch  # 1.0.0 → 1.0.1
./scripts/bump_version.sh minor  # 1.0.0 → 1.1.0
./scripts/bump_version.sh major  # 1.0.0 → 2.0.0
```

After v1.7 architecture reset, versioning approach appears to have changed.

### Bin Validation Tools

Created for Issues #198 (bin datasets), #217 (optimization), #222 (reconciliation).

**From validation/README.md:**
> This directory contains validation tools for the bin dataset generation feature

**Workflow:**
1. `run_local_bins.sh` - Generate bins locally
2. `verify_bins.py` - Verify artifacts
3. `reconcile_bins_simple.py` - Check consistency

**Status:** Issue #198 deployed with `ENABLE_BIN_DATASET=false` by default. Issue #216 created for future optimization. Validation complete, tools no longer needed.

---

## Restoration Instructions

**Note:** These tools are obsolete and restoration is not recommended.

```bash
# View archived version bumper
cat archive/scripts/manual-tools-2025-11/bump_version.sh

# View bin validation tools
ls archive/scripts/manual-tools-2025-11/validation/

# If absolutely needed, copy back (not recommended)
cp archive/scripts/manual-tools-2025-11/bump_version.sh scripts/
cp -r archive/scripts/manual-tools-2025-11/validation scripts/
```

---

## Documentation Updates Needed

The following documentation references these archived tools and should be updated:

**app/version.py** (line 257)
- References `scripts/bump_version.sh`
- Should be updated or removed

**docs/dev-guides/OPERATIONS.md**
- Lines 185-191: Version bumping instructions
- Line 344: Validation script reference

**docs/GUARDRAILS.md** (line 441)
- References `scripts/validation/verify_bins.py`
- Should be updated or removed

**CHANGELOG.md** (line 1263)
- Historical reference (can remain as-is)

---

## Related Issues

- **Issue #198:** Bin dataset generation (validation tools created)
- **Issue #217:** Bin dataset optimization
- **Issue #222:** Bin/segment reconciliation
- **Issue #216:** Future vectorization optimization (created for later work)

---

## Verification Checklist

Before archival was completed:

- ✅ `bump_version.sh` not used (user confirmed)
- ✅ Validation tools not called by CI/E2E
- ✅ Issue #198 complete (bin datasets deployed)
- ✅ Manual validation complete
- ✅ cleanup_cloud_run_revisions.sh kept (active GCP tool)

---

**Archived as part of v1.7.1 architecture cleanup - November 2025**
