# Architecture Testing Strategy - v1.7

**Last Updated:** 2025-11-01  
**Architecture:** v1.7.1  
**Testing Approach:** End-to-End (E2E) Testing

---

## Overview

The v1.7 architecture is validated through comprehensive end-to-end (E2E) testing rather than unit tests. This approach tests the full stack integration and real-world API behavior.

**Current Testing Strategy:**
1. **E2E API Tests** - Validate complete system via `e2e.py`
2. **Complexity Standards** - Enforced via CI pipeline (flake8)
3. **UI Testing** - Manual checklist for deployment verification
4. **Architecture Reviews** - Pull request reviews for structural compliance

---

## E2E Testing

**Primary Tool:** `e2e.py`  
**Scope:** Full system validation via API calls

### Running E2E Tests

**Local Docker:**
```bash
make dev-docker    # Start container
make e2e-docker    # Run E2E tests
```

**Cloud Run:**
```bash
TEST_CLOUD_RUN=true python e2e.py --cloud
```

### What E2E Tests Cover

- ✅ **Density Analysis** - POST /api/density-report
- ✅ **Flow Analysis** - POST /api/temporal-flow-report
- ✅ **Map Data** - GET /api/map/manifest
- ✅ **Dashboard** - GET /api/dashboard/summary
- ✅ **Segments** - GET /api/segments/summary
- ✅ **Reports** - GET /api/reports/list
- ✅ **Health Checks** - GET /health, /ready

### Expected Results

E2E tests verify:
- API endpoints respond correctly
- Data calculations match expected values
- Reports generate without errors
- GCS integration works (when enabled)
- Docker environment parity

---

## Complexity Standards

**Enforced in:** CI Pipeline Stage 0  
**Tool:** flake8 with flake8-bugbear

### Rules

**Cyclomatic Complexity (C901):**
- Threshold: ≤ 15
- Check: `flake8 app/ --max-complexity=15 --select=C901`

**Bare Exceptions (B001):**
- No `except:` without exception type
- Check: `flake8 app/ --select=B001`

### CI Enforcement

**GitHub Actions** (`.github/workflows/ci-pipeline.yml`):
```yaml
- name: Run Complexity Checks (B001 + C901)
  run: |
    flake8 app/ core/ --max-complexity=15 --select=B001,C901
```

**Blocking:** Pipeline fails if violations found

---

## UI Testing

**Tool:** Manual testing checklist  
**File:** `docs/ui-testing-checklist.md`

### Test All Pages

After deployment, verify:
- Dashboard loads with correct metrics
- Density page shows segments and flags
- Flow page displays interaction data
- Segments page renders map correctly
- Reports page lists available downloads
- Health check shows all systems operational

### Critical Checks

- No JavaScript console errors
- No broken images or 404s
- All data displays correctly
- No zero values in metrics
- Heatmaps load properly

**See:** `docs/ui-testing-checklist.md` for full checklist

---

## Architecture Compliance

**Enforced via:** Pull request reviews and documentation

### Import Patterns

**✅ Correct:**
```python
from app.core.density.compute import analyze_density_segments
from app.api.density import router as density_router
from app.utils.constants import DEFAULT_BIN_SIZE
```

**❌ Prohibited:**
```python
# No try/except import fallbacks
try:
    from density import analyze
except ImportError:
    from app.density import analyze

# No relative imports in main.py
from .density import analyze
```

### Layer Boundaries

**Rules:**
- API layer can import: Core, Utils
- Core layer can import: Utils only
- Utils layer: stdlib and third-party only
- No circular dependencies

**Enforcement:** Manual review during PR process

### Directory Structure

**Required:**
```
app/
├── api/          - FastAPI routes only
├── routes/       - Additional route handlers
├── core/         - Business logic, no HTTP
│   ├── artifacts/  - Frontend artifact generation
│   ├── bin/        - Bin analysis
│   ├── density/    - Density calculation
│   ├── flow/       - Flow analysis
│   └── gpx/        - GPX processing
├── common/       - Shared configuration
├── utils/        - Shared utilities
└── validation/   - Input validation
```

**See:** `docs/architecture/README.md` for full structure

---

## Deployment Testing

### Local Docker Testing

**Before creating PR:**
1. Build Docker image locally
2. Run E2E tests in Docker
3. Verify no linter errors
4. Test UI manually

**Commands:**
```bash
docker build -t run-density-test .
make dev-docker
make e2e-docker
```

### CI Pipeline Testing

**Automated stages:**
1. **Stage 0:** Complexity Standards Check
2. **Stage 1:** Build & Deploy Docker image
3. **Stage 2:** E2E Tests (Density/Flow)
4. **Stage 3:** E2E Tests (Bin Datasets)  
5. **Stage 4:** Automated Release

**All must pass before merge**

### Post-Deploy Validation

After merge to `main`:
1. Monitor CI pipeline completion
2. Check Cloud Run logs for errors
3. Run UI testing checklist
4. Verify all pages load correctly
5. Check for any console/network errors

---

## Testing Philosophy

### Why E2E Over Unit Tests?

**Current Approach:**
- Test via real API calls
- Validate full stack integration
- Catch deployment issues early
- Simpler test maintenance

**Trade-offs:**
- Less isolated failure diagnosis
- Slower feedback loop
- No fine-grained coverage metrics

**Decision:** E2E testing provides sufficient confidence for this project's needs.

---

## Quality Gates

### Before PR Creation

- ✅ Docker build succeeds locally
- ✅ E2E tests pass in Docker
- ✅ No complexity violations (flake8)
- ✅ No bare exceptions
- ✅ UI manually tested

### Before Merge

- ✅ CI Pipeline passes (all 5 stages)
- ✅ PR reviewed
- ✅ No merge conflicts
- ✅ Branch up to date with main

### After Deploy

- ✅ Cloud Run deployment healthy
- ✅ UI testing checklist complete
- ✅ No errors in Cloud Run logs
- ✅ All API endpoints responsive

---

## Troubleshooting

### E2E Test Failures

**Check:**
1. Docker container running?
2. Data files in `/data` correct?
3. Configuration files valid YAML?
4. Previous deployment successful?

**Debug:**
```bash
# Check container logs
docker logs <container-id>

# Run E2E with verbose output
python e2e.py --local
```

### Complexity Violations

**Fix:**
1. Extract helper functions
2. Reduce nesting depth
3. Simplify conditional logic
4. Break long functions into smaller ones

**Verify locally:**
```bash
flake8 app/ --max-complexity=15 --select=C901,B001
```

### UI Issues

**Check:**
1. Browser console for JavaScript errors
2. Network tab for failed requests
3. Cloud Run logs for backend errors
4. Verify data files exist in GCS

---

## Related Documentation

- **E2E Testing:** Run `python e2e.py --help`
- **UI Testing:** `docs/ui-testing-checklist.md`
- **Operations:** `docs/dev-guides/OPERATIONS.md`
- **Docker Workflow:** `docs/DOCKER_DEV.md`
- **Architecture:** `docs/architecture/README.md`

---

## Future Enhancements

Potential additions for future consideration:
- Automated UI testing (Playwright/Selenium)
- Integration tests for critical modules
- Performance benchmarking
- Load testing for Cloud Run

**Current priority:** E2E testing provides adequate coverage for production needs.
