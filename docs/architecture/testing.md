# Architecture Testing Strategy - v1.7.0

**Last Updated:** 2025-11-01  
**Architecture:** v1.7.0

---

## Overview

This document describes the testing strategy for enforcing v1.7 architectural rules and preventing regression to problematic patterns.

**Test Layers:**
1. **Architecture Tests** - Enforce structural rules
2. **Import Linting** - Validate layer boundaries
3. **Unit Tests** - Test individual modules
4. **E2E Tests** - Validate complete system

---

## Architecture Tests

**File:** `tests/test_architecture.py`

**Purpose:** Enforce v1.7 architectural rules through automated tests

### Test Classes

#### TestImportPatterns

**What it tests:**
- No try/except import fallbacks exist
- All imports use app.* prefix
- No stub redirect files remain

**Tests:**
```python
def test_no_import_fallbacks_in_main()
    # Ensures main.py has no try/except for imports
    
def test_all_imports_use_app_prefix()
    # Verifies all imports use from app.* pattern
    
def test_no_stub_files()
    # Confirms stub files (density_api.py, etc.) removed
```

**Why it matters:**
- Prevents shadow dependencies
- Catches regressions to v1.6.x patterns
- Ensures environment parity

#### TestLayerBoundaries

**What it tests:**
- Utils doesn't import from app modules
- Core doesn't import from API

**Tests:**
```python
def test_utils_no_app_imports()
    # Utils should only import stdlib
    
def test_core_no_api_imports()
    # Core should not depend on HTTP layer
```

**Why it matters:**
- Enforces domain isolation
- Prevents circular dependencies
- Maintains clear boundaries

#### TestDeprecatedFiles

**What it tests:**
- Deprecated files have warnings
- No deprecated code in production paths

**Why it matters:**
- Documents intent to remove
- Prevents accidental usage

#### TestStructure

**What it tests:**
- Required directories exist
- v1.7 structure in place

**Why it matters:**
- Validates migration complete
- Ensures structure consistency

---

## Import Linting

**Tool:** import-linter  
**Config:** `.importlinter`

### Contract Validation

**Layer Contract:**
```
layers =
    api
    routes
    core
    utils
```

**Rules Enforced:**
- API can import: Core, Utils
- Core can import: Utils only
- Utils can import: stdlib only

### Running Import Linter

**Local development:**
```bash
lint-imports
```

**Expected output:**
```
=============
Import Linter
=============

---------
Contracts
---------

Analyzed 4 contracts.
✓ Layer architecture must be respected
✓ API modules should not import from routes
✓ Core modules should not import from API
✓ Utils should not import from app modules

Completed successfully.
```

**On failure:**
```
✗ Core modules should not import from API

app.core.density.compute imports app.api.density:
    app/core/density/compute.py:15
```

Fix by following layer rules in [README.md](README.md).

---

## Unit Testing Strategy

### Core Module Tests

**Location:** `tests/test_*_core.py`

**What to test:**
- Business logic correctness
- Edge cases and error handling
- Algorithm behavior

**Example:**
```python
# tests/test_density_core.py
from app.core.density.compute import analyze_density_segments
from app.utils.constants import DEFAULT_STEP_KM

def test_density_analysis():
    result = analyze_density_segments(
        pace_csv="data/runners.csv",
        segments_csv="data/segments.csv"
    )
    assert result is not None
    assert 'segments' in result
```

**Pattern:**
- Test domain logic independently of HTTP
- Use real constants from app.utils.constants
- Mock external dependencies (GCS, etc.)

### API Route Tests

**Location:** `tests/test_*_api.py`

**What to test:**
- Request/response models
- HTTP status codes
- Error handling
- Integration with core logic

**Example:**
```python
# tests/test_density_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_density_endpoint():
    response = client.post('/api/density/analyze', json={
        'paceCsv': 'data/runners.csv',
        'segmentsCsv': 'data/segments.csv'
    })
    assert response.status_code == 200
    assert 'segments' in response.json()
```

---

## E2E Testing

**Tool:** `make e2e-docker` (runs `e2e.py` inside container)

**What it tests:**
- Complete request→response flow
- All APIs functional
- Report generation works
- Artifact creation successful

**Coverage:**
- `/health`, `/ready` - Health checks
- `/api/density-report` - Density analysis
- `/api/temporal-flow-report` - Flow analysis
- `/api/map/manifest` - Map data

**Success criteria:**
- All endpoints return 200 OK
- Reports generated correctly
- Artifacts created
- No runtime errors

---

## Test Execution Order

### Local Development Cycle

```bash
# 1. Quick validation (< 5 seconds)
pytest tests/test_architecture.py

# 2. Import boundaries (< 10 seconds)
lint-imports

# 3. Smoke tests (< 1 minute)
make smoke-docker

# 4. Full E2E (2-3 minutes)
make e2e-docker
```

### Pre-Commit Validation

**Minimum before committing:**
```bash
pytest tests/test_architecture.py  # Must pass
lint-imports                        # Must pass
```

### Pre-PR Validation

**Minimum before creating PR:**
```bash
make smoke-docker  # Must pass
make e2e-docker    # Must pass
```

---

## CI Pipeline Integration

**File:** `.github/workflows/ci-pipeline.yml`

### Current Structure

```yaml
jobs:
  complexity-check:  # Step 0: Complexity standards
  build:             # Step 1: Build Docker image
  e2e-test:          # Step 2: Run E2E tests
  bin-datasets:      # Step 3: Bin dataset generation
  release:           # Step 4: Deploy to Cloud Run
```

### Proposed v1.7 Additions

**Add to complexity-check job:**
```yaml
- name: Architecture Tests
  run: pytest tests/test_architecture.py -v

- name: Import Linter
  run: lint-imports
```

**Why:**
- Catches architectural violations before deployment
- Prevents merge of code violating v1.7 rules
- Blocks regressions to dual import patterns

---

## Adding New Architecture Tests

### When to Add

Add architecture tests when:
- New architectural rule introduced
- Specific anti-pattern needs prevention
- Layer boundary expanded/changed
- New directory structure added

### How to Add

**File:** `tests/test_architecture.py`

**Pattern:**
```python
def test_my_architecture_rule():
    """Ensure [describe rule]."""
    # Scan relevant files
    files = Path('app/my_layer').glob('**/*.py')
    
    for file_path in files:
        content = file_path.read_text()
        
        # Assert rule compliance
        assert 'forbidden_pattern' not in content, \
            f"{file_path} violates architecture rule"
```

**Example:**

```python
def test_no_deprecated_imports():
    """Ensure no code imports from deprecated modules."""
    deprecated = ['new_density_report', 'new_flagging', 'storage']
    
    for py_file in Path('app').rglob('*.py'):
        content = py_file.read_text()
        for dep_module in deprecated:
            pattern = f'from app.{dep_module} import'
            assert pattern not in content, \
                f"{py_file} imports deprecated module: {dep_module}"
```

---

## Test Maintenance

### When Tests Fail

1. **Understand why**
   - Read test output carefully
   - Check what rule was violated
   - Understand the architectural principle

2. **Fix the code, not the test**
   - Architecture tests encode non-negotiable rules
   - If test fails, code is wrong
   - Don't weaken tests to pass

3. **Exception: Legitimate rule change**
   - Document WHY rule needs changing
   - Update architecture docs first
   - Then update test
   - Get team review

### Keeping Tests Updated

**When new layers added:**
- Update TestStructure
- Add layer boundary tests
- Update import-linter config

**When new patterns emerge:**
- Add tests for new patterns
- Document in architecture README
- Update GUARDRAILS.md

---

## Testing Anti-Patterns

### ❌ Don't Mock Architecture

```python
# BAD - defeats purpose of architecture tests
@mock.patch('builtins.open')
def test_no_fallbacks(mock_open):
    # This doesn't actually test the code
```

**Instead:** Test real code files

### ❌ Don't Skip Architecture Tests

```python
# BAD
@pytest.mark.skip("Imports are hard, fix later")
def test_layer_boundaries():
    ...
```

**Instead:** Fix the code to comply

### ❌ Don't Weaken Assertions

```python
# BAD - makes test pass when it shouldn't
assert 'except ImportError:' not in content[:100]  # Only checks first 100 chars

# GOOD - checks entire file
assert 'except ImportError:' not in content
```

---

## Quick Reference

### Run All Architecture Validation

```bash
# Complete validation suite
pytest tests/test_architecture.py -v
lint-imports
make smoke-docker
make e2e-docker
```

### Run Specific Test Class

```bash
pytest tests/test_architecture.py::TestImportPatterns -v
pytest tests/test_architecture.py::TestLayerBoundaries -v
```

### Run Single Test

```bash
pytest tests/test_architecture.py::TestImportPatterns::test_no_import_fallbacks_in_main -v
```

---

## Related Documentation

- [Architecture README](README.md) - Overall architecture
- [Adding Modules Guide](adding-modules.md) - How to add code
- [v1.7 Reset Rationale](v1.7-reset-rationale.md) - Why these rules exist

---

**Architecture tests are the safety net. Keep them strong, keep them passing.**

