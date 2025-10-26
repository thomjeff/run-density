# Phase 1 Batch Cleanup Checklist Template

**Issue #342 - Phase 1: Codebase Cleanup**  
**Batch**: [BATCH_NUMBER] - [BATCH_NAME]  
**Date**: [DATE]  
**Branch**: `issue-342-phase1-cleanup`

## Pre-Batch Validation

### Environment Setup
- [ ] Virtual environment activated: `source test_env/bin/activate`
- [ ] Dependencies confirmed: `pip list | grep -E "(fastapi|pandas|pytest)"`
- [ ] Current branch confirmed: `git branch --show-current`

### Baseline Testing
- [ ] E2E tests pass: `python e2e.py --local`
- [ ] Unit tests baseline: `pytest tests/ --tb=short`
- [ ] No critical failures in existing test suite

### File Discovery
- [ ] Target files identified and verified
- [ ] Import analysis completed: `grep -r "filename" ./app/`
- [ ] CLI usage checked: `grep -r "filename" . --include="*.sh" --include="Makefile"`
- [ ] Documentation references checked: `grep -r "filename" README.md docs/`

## Batch Execution

### File Operations
- [ ] Create target directories if needed: `mkdir -p deprecated/[path]`
- [ ] Move files to deprecated: `mv [source] deprecated/[destination]`
- [ ] OR Delete files: `rm [file]`
- [ ] Update deprecated/README.md with file details

### Deprecation Warnings (for moved files)
- [ ] Add deprecation warning header to each moved file:
```python
import warnings
warnings.warn("This module is deprecated and will be removed after Phase 2", DeprecationWarning)
```

### Import Cleanup
- [ ] Remove any active imports from deprecated files
- [ ] Verify no broken import paths
- [ ] Check for dynamic imports or string-based imports

## Post-Batch Validation

### Testing
- [ ] E2E tests pass: `python e2e.py --local`
- [ ] Unit tests pass: `pytest tests/ --tb=short`
- [ ] No new test failures introduced

### Verification
- [ ] Application starts successfully: `python -m app.main`
- [ ] Health endpoint responds: `curl http://localhost:8081/health`
- [ ] No import errors in logs

### Documentation
- [ ] Update deprecated/README.md with batch results
- [ ] Record success metrics
- [ ] Note any issues or concerns

## Rollback Plan (if needed)

### If E2E Tests Fail
- [ ] Identify the specific failure
- [ ] Revert entire batch: `git checkout HEAD~1`
- [ ] Re-run E2E tests to confirm rollback
- [ ] Document the issue and resolution

### If Unit Tests Fail
- [ ] Check if failures are related to moved/deleted files
- [ ] If unrelated to batch changes, proceed with caution
- [ ] If related to batch changes, consider rollback

## Success Criteria

- [ ] All target files processed successfully
- [ ] E2E tests pass (primary validation)
- [ ] Unit tests pass (secondary validation)
- [ ] No functional regressions
- [ ] Deprecated files properly documented
- [ ] Ready for next batch

## Metrics Tracking

**Files Processed:**
- Moved to deprecated: [COUNT]
- Deleted: [COUNT]
- Total processed: [COUNT]

**Performance Impact:**
- E2E test runtime: [TIME]
- Unit test runtime: [TIME]
- App startup time: [TIME]

**Quality Metrics:**
- New test failures: [COUNT]
- Import errors: [COUNT]
- Deprecation warnings: [COUNT]

## Notes

**Issues Encountered:**
[Document any problems or unexpected behavior]

**Decisions Made:**
[Document any changes to the original plan]

**Next Batch Preparation:**
[Notes for the next batch execution]

---

**Template Usage:**
1. Copy this template for each batch
2. Fill in batch-specific details
3. Check off items as completed
4. Commit results to git
5. Update Issue #342 with progress
