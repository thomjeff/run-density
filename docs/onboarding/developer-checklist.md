# Developer Onboarding Checklist

**Target Audience:** New developers joining the run-density project  
**Architecture Version:** v1.7.0  
**Estimated Time:** 2-4 hours

---

## Day 1: Environment Setup

### ✅ Prerequisites

- [ ] GitHub access to thomjeff/run-density repository
- [ ] Docker installed locally
- [ ] Git CLI configured
- [ ] Text editor/IDE set up

### ✅ Clone and Setup

```bash
# Clone repository
git clone https://github.com/thomjeff/run-density.git
cd run-density

# Verify Docker works
docker --version
docker-compose --version

# Start development environment
make dev-docker

# Verify application runs
# Open browser: http://localhost:8080
# Should see run-density UI
```

### ✅ Run Tests

```bash
# Quick smoke tests (< 1 minute)
make smoke-docker

# Full E2E tests (~ 2-3 minutes)
make e2e-docker

# Architecture tests
pytest tests/test_architecture.py -v
```

**Success Criteria:**
- ✅ Docker container starts successfully
- ✅ UI loads at http://localhost:8080
- ✅ All smoke tests pass
- ✅ E2E tests complete successfully

---

## Day 1: Architecture Understanding

### ✅ Read Core Documentation

**Required Reading** (30-45 minutes):

- [ ] [README.md](../../README.md) - Project overview
- [ ] [docs/GUARDRAILS.md](../GUARDRAILS.md) - Development rules
- [ ] [docs/architecture/README.md](../architecture/README.md) - Architecture overview
- [ ] [docs/architecture/v1.7-reset-rationale.md](../architecture/v1.7-reset-rationale.md) - Why v1.7

**Key Concepts to Understand:**
- Layer architecture (API → Core → Utils)
- Import patterns (app.* prefix required)
- Directory structure
- No relative imports, no try/except fallbacks

### ✅ Explore the Codebase

Navigate key directories:

```bash
# API layer (HTTP interface)
ls app/api/
# density.py, flow.py, map.py, report.py, models/

# Core layer (business logic)
ls app/core/
# bin/, density/, flow/, gpx/

# Utils layer (shared utilities)
ls app/utils/
# constants.py, env.py, shared.py

# Routes (additional HTTP handlers)
ls app/routes/
# api_*.py, reports.py, ui.py
```

**Understand:**
- Where each type of code belongs
- How layers interact
- Import patterns in real code

---

## Day 2: First Code Change

### ✅ Create a Feature Branch

```bash
# Always work on branches, never on main
git checkout main
git pull origin main
git checkout -b feature/my-first-change
```

### ✅ Make a Simple Change

**Task:** Add a new constant

**File:** `app/utils/constants.py`

```python
# Add at bottom of file
MY_TEST_CONSTANT = 42  # My first contribution
```

**File:** `tests/test_my_constant.py`

```python
from app.utils.constants import MY_TEST_CONSTANT

def test_my_constant():
    assert MY_TEST_CONSTANT == 42
```

### ✅ Test Your Change

```bash
# Run architecture tests
pytest tests/test_architecture.py

# Run your test
pytest tests/test_my_constant.py

# Run smoke tests
make smoke-docker

# Verify no regressions
make e2e-docker
```

### ✅ Commit and Push

```bash
git add app/utils/constants.py tests/test_my_constant.py
git commit -m "feat: add MY_TEST_CONSTANT for testing

Added test constant to verify development workflow"

git push -u origin feature/my-first-change
```

### ✅ Create Pull Request

```bash
gh pr create \
  --base refactor/v1.7-architecture \
  --title "feat: Add test constant" \
  --body "My first PR - adding a test constant to verify workflow"
```

**Note:** During v1.7 development, PRs target `refactor/v1.7-architecture`, not `main`.

---

## Architecture Validation Checklist

Before submitting any PR, verify:

### ✅ Import Patterns

- [ ] All imports use `from app.* import ...` pattern
- [ ] No relative imports (`from .module`)
- [ ] No try/except import fallbacks
- [ ] No imports without app. prefix

### ✅ Layer Boundaries

- [ ] API/Routes only import from Core and Utils
- [ ] Core only imports from Utils
- [ ] Utils only imports from stdlib

### ✅ Testing

- [ ] Architecture tests pass: `pytest tests/test_architecture.py`
- [ ] Import linter passes: `lint-imports`
- [ ] Smoke tests pass: `make smoke-docker`
- [ ] E2E tests pass: `make e2e-docker`

### ✅ Code Quality

- [ ] No hardcoded values (use constants.py)
- [ ] Docstrings added to new functions
- [ ] Type hints used where appropriate
- [ ] Complexity within limits (cyclomatic ≤ 15)

---

## Common Developer Tasks

### Adding a New API Endpoint

**See:** [docs/architecture/adding-modules.md](../architecture/adding-modules.md)

**Quick steps:**
1. Create `app/api/my_feature.py`
2. Import from app.core.* and app.utils.*
3. Register router in `app/main.py`
4. Add tests
5. Run smoke + E2E tests

### Adding Business Logic

**See:** [docs/architecture/adding-modules.md](../architecture/adding-modules.md)

**Quick steps:**
1. Create `app/core/my_feature/logic.py`
2. Import only from app.utils.*
3. Add unit tests
4. Use from API layer

### Fixing Import Errors

**Error:** `ModuleNotFoundError: No module named 'X'`

**Checklist:**
- [ ] Using app.* prefix? (`from app.X import Y`)
- [ ] Path correct after v1.7 reorganization?
  - `from api.X` → `from app.api.X`
  - `from core.X` → `from app.core.X`
  - `from constants` → `from app.utils.constants`
- [ ] File exists in expected location?

---

## Learning Resources

### Code Examples

**Best examples to study:**

| Feature | File | Learn About |
|---------|------|-------------|
| API endpoint | `app/api/density.py` | FastAPI routes, request models |
| Core logic | `app/core/density/compute.py` | Business logic, domain isolation |
| Utilities | `app/utils/shared.py` | Helper functions, zero dependencies |
| Testing | `tests/test_architecture.py` | Architecture validation |

### Key Documents

1. **[Architecture README](../architecture/README.md)** - Start here
2. **[Adding Modules Guide](../architecture/adding-modules.md)** - Step-by-step recipes
3. **[GUARDRAILS.md](../GUARDRAILS.md)** - Development rules
4. **[DOCKER_DEV.md](../DOCKER_DEV.md)** - Docker development guide

---

## Getting Help

### If You're Stuck

1. **Check documentation first**
   - Search docs/architecture/
   - Look at similar code in codebase

2. **Run diagnostic commands**
   ```bash
   pytest tests/test_architecture.py -v  # Architecture validation
   lint-imports                           # Layer boundary check
   docker logs run-density-dev            # Container logs
   ```

3. **Ask the team**
   - GitHub Discussions
   - Team chat
   - Code review comments

### Common Questions

**Q: Where should I put this code?**  
A: See [adding-modules.md](../architecture/adding-modules.md) decision tree

**Q: What import pattern should I use?**  
A: Always `from app.X.Y import Z` - see [Architecture README](../architecture/README.md#import-patterns)

**Q: Why can't I import from API in Core?**  
A: Domain isolation - Core should work without HTTP. See [Layer Rules](../architecture/README.md#layer-architecture)

**Q: Tests are failing after my change**  
A: Run `pytest tests/test_architecture.py -v` to see which architectural rule was violated

---

## Success Metrics

You're ready to contribute when you can:

- ✅ Start Docker environment without assistance
- ✅ Add a new API endpoint following patterns
- ✅ Add business logic to Core layer
- ✅ Write tests that pass
- ✅ Understand layer boundaries
- ✅ Use correct import patterns automatically
- ✅ Run architecture validation before committing

---

## Next Steps

After completing this checklist:

1. **Pick a starter issue**
   - Look for `good-first-issue` label
   - Or ask team for recommendations

2. **Read the full issue**
   - Title, description, ALL comments
   - Understand requirements completely

3. **Make a plan**
   - Break into small commits
   - Identify affected layers
   - Plan testing strategy

4. **Execute**
   - Follow adding-modules.md patterns
   - Test after each commit
   - Ask questions early

---

**Welcome to the team! 🎉**

