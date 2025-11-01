# Analytics Pipeline - Archived 2025-11-01

## Overview

This directory contains analytics pipeline modules created by Codex that were never integrated into core application functionality.

## Archived Files

### pipeline.py (248 lines)
- **Purpose:** Unified analytics pipeline orchestration
- **Created By:** Codex (Issue #414)
- **Status:** Experimental - never integrated into core app
- **Usage:** Only used by test_pipeline.py (also archived)
- **Why Archived:** Not used by app/, e2e.py, or CI pipeline

### test_pipeline.py (179 lines)
- **Purpose:** Unit tests for pipeline.py
- **Status:** Tests unused code
- **Why Archived:** Tests the archived pipeline.py module

## Migration Context

During v1.7.0 Architecture Reset (Issue #422), the /analytics directory was identified as sitting outside the layered architecture. Analysis revealed:

- ✅ export_frontend_artifacts.py - USED by CI pipeline and e2e.py → Migrated to app/core/artifacts/frontend.py
- ✅ export_heatmaps.py - USED by e2e.py for local testing → Migrated to app/core/artifacts/heatmaps.py
- ❌ pipeline.py - NOT USED anywhere in core functionality → Archived here
- ❌ test_pipeline.py - Tests unused code → Archived here

## Functionality Replacement

The application uses direct report generation instead of pipeline orchestration.

## Archival Details

- **Date:** 2025-11-01
- **Reason:** Unused experimental code outside v1.7 architecture
- **Migration:** Active modules moved to /app/core/artifacts/
- **Impact:** None (code was not in use)

**Archived as part of v1.7.1 architecture cleanup.**

## Additional Archived Files (Migrated to app/core/artifacts/)

### export_frontend_artifacts.py (1048 lines)
- **Purpose:** UI artifact generation (meta.json, segment_metrics.json, flags.json, flow.json, etc.)
- **Migration:** Moved to `app/core/artifacts/frontend.py`
- **Used By:** CI pipeline (.github/workflows/ci-pipeline.yml), e2e.py
- **Why Migrated:** Active code brought into v1.7 architecture

### export_heatmaps.py (648 lines)
- **Purpose:** PNG heatmap and captions.json generation
- **Migration:** Moved to `app/core/artifacts/heatmaps.py`
- **Used By:** e2e.py (local testing), frontend.py (heatmap generation)
- **Why Migrated:** Active code brought into v1.7 architecture

### __init__.py (0 lines)
- **Purpose:** Package marker for analytics/
- **Status:** No longer needed after migration

## Migration Complete

All functional code from `/analytics` has been migrated to `/app/core/artifacts/` as part of v1.7.1 cleanup.

**New Locations:**
- `app/core/artifacts/frontend.py` - UI artifact generation
- `app/core/artifacts/heatmaps.py` - Heatmap and caption generation
- `app/core/artifacts/__init__.py` - Package marker

**Updated References:**
- `e2e.py` - Uses `from app.core.artifacts.frontend import ...`
- `.github/workflows/ci-pipeline.yml` - Uses `python -m app.core.artifacts.frontend`
- `Dockerfile` - No longer copies `/analytics` directory

**Archive Date:** 2025-11-01
