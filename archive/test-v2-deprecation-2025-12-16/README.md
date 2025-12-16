# Deprecated: test-v2 Script

**Date:** December 16, 2025  
**Issue:** #537  
**Reason:** Deprecated in favor of comprehensive e2e-v2 test suite

## Migration

Use `make e2e-v2` instead of `make test-v2`.

For faster iteration:
- `make e2e-v2-sat` - Saturday-only test (~2 min)
- `make e2e-v2-sun` - Sunday-only test (~2 min)

## Why Deprecated

- Complete functional overlap with e2e-v2
- Bug-prone implementation (container name collision)
- e2e-v2 provides comprehensive validation (day isolation, golden files, schema validation)
- Project standardization requirement (single test harness)

See: `cursor/sessions/issue-537-assessment.md` for full analysis.

