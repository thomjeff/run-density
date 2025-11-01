# Archived: Legacy GitHub Workflows

**Archived Date:** November 1, 2025  
**Archived By:** AI Assistant (v1.7.1 architecture cleanup)  
**Original Location:** `.github/workflows/`  
**Reason:** Replaced by consolidated `ci-pipeline.yml` workflow

---

## Why These Were Archived

### Summary
These workflow files represent an older architecture where CI/CD tasks were split across multiple workflows. The v1.7 architecture reset (Issue #425) consolidated all functionality into a single, comprehensive `ci-pipeline.yml` workflow.

### Evidence of Obsolescence

**1. Backup Files (2 files):**
- `ci-pipeline.yml.backup` - Pre-v1.7 backup from Oct 29
- `ci-pipeline.yml.backup-phase3.3` - Phase 3.3 backup from Oct 29
- **Status:** Git history preserves all versions, backups redundant

**2. Legacy Split Workflows (5 files):**
- `validate.yml` - Data validation
- `dashboard.yml` - Dashboard generation
- `map.yml` - Map generation
- `reports.yml` - Report building
- `ui-artifacts-qc.yml` - UI artifacts quality checks

**Status of Legacy Workflows:**
```
Last run: October 23, 2025
Recent runs: All FAILURES
Reason: Dependencies and scripts updated for v1.7 architecture
```

**3. Current Active Workflow:**
- ✅ `ci-pipeline.yml` - Consolidated workflow handling:
  - Stage 0: Complexity standards check
  - Stage 1: Build & Deploy (Docker → Artifacts)
  - Stage 2: E2E Testing (Density/Flow)
  - Stage 3: E2E Testing (Bin Datasets)
  - Stage 4: Automated Release
  - **Status:** Running successfully since v1.7 deployment

---

## Archived Contents

```
archive/github-workflows/legacy-split-workflows-2025-11/
├── README.md (this file)
├── ci-pipeline.yml.backup (25KB - Oct 29 backup)
├── ci-pipeline.yml.backup-phase3.3 (25KB - Phase 3.3 backup)
├── validate.yml (884B - Data validation workflow)
├── dashboard.yml (1KB - Dashboard build workflow)
├── map.yml (1.5KB - Map generation workflow)
├── reports.yml (1KB - Report build workflow)
└── ui-artifacts-qc.yml (846B - UI QC workflow)
```

### Workflow Purposes (Historical Reference)

**validate.yml**
- Purpose: Validate data contracts and YAML schemas
- Trigger: Push to main, PRs
- Status: Deprecated - validation now in ci-pipeline.yml

**dashboard.yml**
- Purpose: Generate dashboard artifacts
- Trigger: Push to main
- Status: Deprecated - dashboard generation moved to app/core/artifacts/

**map.yml**
- Purpose: Generate map visualizations
- Trigger: Push to main
- Status: Deprecated - map generation consolidated

**reports.yml**
- Purpose: Build density reports
- Trigger: Push to main
- Status: Deprecated - report generation consolidated

**ui-artifacts-qc.yml**
- Purpose: Quality check UI artifacts
- Trigger: Push to main, PRs
- Status: Deprecated - QC now integrated in ci-pipeline.yml

---

## Migration Path

All functionality from these workflows was migrated to `.github/workflows/ci-pipeline.yml` during the v1.7 architecture reset:

**Old Architecture (6 separate workflows):**
```
validate.yml → Data validation
dashboard.yml → Dashboard build
map.yml → Map generation
reports.yml → Report generation
ui-artifacts-qc.yml → QC checks
ci-pipeline.yml → Deployment only
```

**New Architecture (1 consolidated workflow):**
```
ci-pipeline.yml → All stages consolidated:
  ├── Stage 0: Complexity & Standards
  ├── Stage 1: Build & Deploy
  ├── Stage 2: E2E Tests (Density/Flow)
  ├── Stage 3: E2E Tests (Bin Datasets)
  └── Stage 4: Automated Release
```

---

## Restoration Instructions

**Note:** Restoration is not recommended. The consolidated workflow is more maintainable and reliable.

If you need to reference old workflow logic:

```bash
# View an archived workflow
cat archive/github-workflows/legacy-split-workflows-2025-11/validate.yml

# Compare with current ci-pipeline
diff archive/github-workflows/legacy-split-workflows-2025-11/validate.yml .github/workflows/ci-pipeline.yml

# Restore a workflow (NOT recommended)
cp archive/github-workflows/legacy-split-workflows-2025-11/validate.yml .github/workflows/
git add .github/workflows/validate.yml
git commit -m "Restore validate.yml from archive"
```

---

## Related Documentation

- **Current CI Pipeline:** `.github/workflows/ci-pipeline.yml`
- **v1.7 Architecture:** `/docs/architecture/v1.7-reset-rationale.md`
- **CI Documentation:** `/docs/architecture/testing.md`
- **Issue #425:** Track 3 - CI/CD consolidation

---

## Git History

These workflows were last active on October 23, 2025. To view their history:

```bash
# View commit history for a specific workflow
git log --all --full-history -- .github/workflows/validate.yml

# View the workflow at its last active commit
git show <commit-hash>:.github/workflows/validate.yml
```

---

## Verification Checklist

Before archival was completed:

- ✅ `ci-pipeline.yml` running successfully
- ✅ All legacy workflows failing consistently
- ✅ No dependencies on legacy workflows
- ✅ All functionality consolidated in ci-pipeline.yml
- ✅ Git history preserves all backup versions
- ✅ v1.7 architecture deployment successful

---

**Archived as part of v1.7.1 architecture cleanup - November 2025**
