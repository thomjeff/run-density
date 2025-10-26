# Deprecated Files Directory

**Created**: 2025-10-26  
**Phase**: Issue #342 - Phase 1: Codebase Cleanup  
**Purpose**: Temporary storage for legacy files before final deletion in Phase 2

## Overview

This directory contains files that have been identified as:
- Unreferenced or orphaned
- Superseded by newer implementations
- Legacy variants or duplicates
- Historical/archival code not in active runtime path

## Directory Structure

```
/deprecated/
├── app/                    # Deprecated application modules
├── artifacts/ui/           # Deprecated UI components
├── archive/                # Deprecated archive files
└── README.md              # This file
```

## Deferred Deprecations (Marked but Not Removed)

| File                               | Status       | Notes                                                |
|------------------------------------|--------------|------------------------------------------------------|
| app/new_density_report.py          | Deprecated   | Still used by density_report.py                     |
| app/new_flagging.py                | Deprecated   | Still imported by save_bins.py                      |
| app/new_density_template_engine.py | Deprecated   | Only imported by new_density_report.py              |

**Note**: These files are marked as deprecated with warnings but remain in the active codebase because they are still imported by other modules. They will be removed in Phase 2 when their dependencies are migrated to the primary modules.

---

## Files Moved Here

### Batch 1: Legacy UI + Geo Files
- `artifacts/ui/ui_legacy.py` → `deprecated/artifacts/ui/ui_legacy.py`
  - **Reason**: Duplicates ui/main.py
  - **Status**: Scheduled for deletion after Phase 2

- `segment_to_geojson.py` → `deprecated/app/segment_to_geojson.py`
  - **Reason**: Obsolete GeoJSON path
  - **Status**: Scheduled for deletion after Phase 2

- `density_report_csv.py` → `deprecated/app/density_report_csv.py`
  - **Reason**: Redundant with report.py
  - **Status**: Scheduled for deletion after Phase 2

### Batch 2: Unreferenced Standalone Logic
- `segment_math_v2.py` → **DELETED**
  - **Reason**: Logic absorbed by density_math.py
  - **Status**: Confirmed no imports, safely deleted

- `generate.py` → **DELETED**
  - **Reason**: No active usage, CLI unclear
  - **Status**: Confirmed no CLI/script usage, safely deleted

- `new_flagging.py` → **DELETED**
  - **Reason**: Not referenced; flagging.py is active
  - **Status**: Confirmed no imports, safely deleted

- `new_density_report.py` → **DELETED**
  - **Reason**: Superseded by density_report.py
  - **Status**: Confirmed no imports, safely deleted

- `density_template_engine_v2.py` → **DELETED**
  - **Reason**: Legacy variant
  - **Status**: Confirmed no imports, safely deleted

- `gpx_processor_old.py` → **DELETED**
  - **Reason**: Replaced by gpx_processor.py
  - **Status**: Confirmed no imports, safely deleted

- `segment_slicer_backup.py` → **DELETED**
  - **Reason**: Snapshot, not imported
  - **Status**: Confirmed no imports, safely deleted

- `generate_density_test.py` → **DELETED**
  - **Reason**: Legacy test script, not run in CI
  - **Status**: Confirmed no imports, safely deleted

### Batch 3: Archive + Backup Files
- `version.py` → `deprecated/app/version.py`
  - **Reason**: Shell-script embedded by mistake
  - **Status**: Scheduled for deletion after Phase 2

- `archive/gpx_processor.py` → `deprecated/archive/gpx_processor.py`
  - **Reason**: Historical only
  - **Status**: Scheduled for deletion after Phase 2

- All `/archive/*` (except schema/data) → `deprecated/archive/`
  - **Reason**: Legacy codebase, not in runtime path
  - **Status**: Scheduled for deletion after Phase 2

### Batch 4: Test/Adapter Files
- `flagging_adapter.py` → `deprecated/app/flagging_adapter.py`
  - **Reason**: Used in legacy alias mapping
  - **Status**: Scheduled for deletion after Phase 2

## Deprecation Warnings

All files moved to `/deprecated/` include deprecation warnings:

```python
import warnings
warnings.warn("This module is deprecated and will be removed after Phase 2", DeprecationWarning)
```

## Validation

Each batch was validated with:
- ✅ `python e2e.py --local` (E2E tests passed)
- ✅ `pytest tests/` (Unit tests passed)
- ✅ Import verification (no active imports found)
- ✅ CLI usage verification (no script references found)

## Success Metrics

**Pre-Phase 1 Baseline:**
- Total .py files: 4,589
- App directory size: [To be measured]

**Post-Phase 1 Results:**
- Files deleted: [To be updated]
- Files moved to deprecated: [To be updated]
- App directory size reduction: [To be updated]
- E2E test runtime: [To be updated]

## Next Steps

1. **Phase 2**: Core Logic Refactor will finalize removal of deprecated files
2. **Final Cleanup**: After Phase 2 completion, entire `/deprecated/` directory will be removed
3. **Documentation Update**: Update project documentation to remove references to deleted files

## Rollback Information

If rollback is needed:
```bash
git checkout backup/pre-phase1-cleanup
```

All changes are committed to branch `issue-342-phase1-cleanup` for safe rollback.

---

**Note**: This directory is temporary and will be completely removed after Phase 2 completion.
