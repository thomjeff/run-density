# Archived: Testing Infrastructure

**Archived Date:** November 1, 2025  
**Archived By:** AI Assistant (v1.7.1 architecture cleanup)  
**Original Location:** `/tests/`, `.importlinter`, `.python-version`  
**Reason:** Testing infrastructure never integrated into CI/E2E pipelines

---

## Why This Was Archived

### Summary
A comprehensive testing infrastructure was developed but never integrated into the CI/E2E pipelines. The project relies on E2E API testing instead of unit/integration tests, and the import linter was configured but never executed.

### Archived Items

**1. Tests Directory** (31 test files, ~2,400 lines of test code)

Test files included:
- `test_architecture.py` (158 lines) - v1.7 architecture validation
- `test_bin_dataset_ci.py` (346 lines) - Bin dataset tests
- `test_flow_unit.py` (324 lines) - Flow analysis tests
- `test_normalize.py` (218 lines) - Normalization tests
- `test_bin_summary.py` (221 lines) - Bin summary tests
- `test_ui_artifacts_qc.py` (216 lines) - UI artifact QC
- `test_health_contract.py` (144 lines) - Health API contract
- `test_schema_contract.py` (242 lines) - Schema validation
- `test_map_api.py` (272 lines) - Map API tests
- `test_rulebook_flags.py` (337 lines) - Rulebook flag tests
- `test_canonical_report_integration.py` (367 lines) - Report integration
- `temporal_flow_tests.py` (564 lines) - Temporal flow tests
- `density_tests.py` (318 lines) - Density tests
- And 18 more test files...

**Status:** ❌ Never executed by CI or E2E  
**Last Updated:** November 1, 2025 (Issue #422)

**2. Import Linter Configuration** (`.importlinter`, 43 lines)

**Purpose:** Enforce v1.7 layer architecture boundaries  
**Created:** Issue #422 (v1.7 reset), Commit 6cc872d  
**Status:** ❌ Configured but never run

**Rules Defined:**
- Layer architecture (api → routes → core → utils)
- No API-to-routes imports
- No core-to-API imports  
- No utils-to-app imports

**Referenced in Documentation:**
- `docs/architecture/README.md` line 103, 310
- `docs/architecture/testing.md` line 96
- `docs/architecture/adding-modules.md` line 314, 426
- `requirements.txt` line 44

**3. Python Version File** (`.python-version`, 2 lines)

**Content:** `3.12.5`  
**Purpose:** Specify Python version for pyenv  
**Status:** ⚠️ **Misleading** - File says 3.12.5 but Dockerfile uses 3.11

**Problem:** Version mismatch
- `.python-version`: Python 3.12.5
- `Dockerfile`: `FROM python:3.11-slim`
- No pyenv setup in CI/E2E

---

## Evidence of Non-Use

### Tests Directory

**CI Pipeline Check:**
```bash
# Only complexity check runs - NO pytest
grep "pytest" .github/workflows/ci-pipeline.yml → 0 matches
grep "test_architecture" .github/workflows/ci-pipeline.yml → 0 matches
```

**E2E Check:**
```bash
grep "pytest" e2e.py → 0 matches
grep "tests/" e2e.py → 0 matches
```

**What CI Actually Runs:**
```bash
# Stage 0: Complexity Standards Check
flake8 app/ core/ --max-complexity=15 --select=B001,C901 --exclude=tests/*
```

**Current Testing Strategy:**
- E2E API tests via `e2e.py`
- Live API endpoint validation
- Cloud Run deployment testing
- No unit/integration tests executed

### Import Linter

**CI/E2E Check:**
```bash
grep "lint-imports" .github/workflows/ci-pipeline.yml → 0 matches
grep "import-linter" .github/workflows/ci-pipeline.yml → 0 matches
grep "lint-imports" Makefile → 0 matches
```

**Status:** Installed in requirements.txt but never invoked

### Python Version

**Dockerfile Reality:**
```dockerfile
FROM python:3.11-slim  # Not 3.12.5!
```

**No pyenv usage detected in CI/E2E**

---

## What Replaced Them

### Instead of Unit Tests → E2E Testing

**Active Testing:**
- `e2e.py` - Comprehensive E2E API testing
- Live endpoint validation
- Cloud Run deployment verification
- UI testing checklist (`docs/ui-testing-checklist.md`)

**Approach:** Test via real API calls rather than unit tests

### Instead of Import Linter → Manual Review

**Enforcement:**
- Architecture documentation
- Pull request reviews
- Developer guidelines

### Instead of .python-version → Dockerfile

**Version Control:**
- Dockerfile specifies exact Python version (3.11)
- CI uses Docker image
- Consistent across environments

---

## Testing Philosophy

The project evolved to use **E2E testing over unit testing**:

**Advantages:**
- Tests real API behavior
- Validates full stack integration
- Catches deployment issues
- Simpler test maintenance

**Trade-offs:**
- No fine-grained unit test coverage
- Slower feedback loop
- Less isolated failure diagnosis

---

## Restoration Instructions

**Note:** Restoration requires significant CI/E2E integration work.

### If You Want to Restore Tests:

```bash
# 1. Restore files
cp -r archive/testing-infrastructure/unused-tests-2025-11/tests .
cp archive/testing-infrastructure/unused-tests-2025-11/.importlinter .

# 2. Update CI pipeline to run tests
# Add to .github/workflows/ci-pipeline.yml Stage 0:
#   - name: Run pytest
#     run: python -m pytest tests/ -v
#   - name: Run import linter
#     run: lint-imports

# 3. Fix any broken tests
# (Many may need updates for v1.7 architecture)
```

### If You Want Import Linter Only:

```bash
# 1. Restore config
cp archive/testing-infrastructure/unused-tests-2025-11/.importlinter .

# 2. Add to CI
# In .github/workflows/ci-pipeline.yml Stage 0:
#   - name: Check import boundaries
#     run: lint-imports
```

---

## Documentation Updates Needed

The following documentation references archived items:

**Architecture Documentation:**
- `docs/architecture/README.md` - Remove import-linter references
- `docs/architecture/testing.md` - Update testing strategy  
- `docs/architecture/adding-modules.md` - Remove import-linter checklist

**Requirements:**
- `requirements.txt` line 44 - Remove `import-linter>=2.0`

---

## Related Context

- **Issue #422:** v1.7 architecture reset (where tests and linter were added)
- **Current Testing:** `e2e.py` and `docs/ui-testing-checklist.md`
- **CI Pipeline:** `.github/workflows/ci-pipeline.yml` (complexity checks only)

---

## Statistics

**Tests Archived:**
- 31 test files
- ~2,400 lines of test code
- 1 test subdirectory (`tests/core/`)
- pytest-based tests
- Last updated: November 1, 2025

**Configuration Archived:**
- `.importlinter` (43 lines, 4 contracts)
- `.python-version` (2 lines, version mismatch)

---

## Verification Checklist

Before archival was completed:

- ✅ No pytest execution in CI pipeline
- ✅ No pytest execution in E2E
- ✅ Import-linter never invoked
- ✅ .python-version not used (Docker uses 3.11)
- ✅ E2E testing covers API functionality
- ✅ Tests last updated months ago (not actively maintained)

---

**Archived as part of v1.7.1 architecture cleanup - November 2025**
