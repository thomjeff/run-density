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
