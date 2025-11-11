# Run-Density Architecture (v1.7.0)

**Last Updated:** 2025-11-01  
**Architecture Version:** v1.7.0  
**Status:** Active

---

## Overview

This document describes the v1.7 architecture of the run-density application, including directory structure, module organization, import patterns, and layer boundaries.

**Key Principles:**
- 🎯 Single absolute import pattern (no fallbacks)
- 📦 Clear layer boundaries (enforced by tests and linting)
- 🔒 Domain isolation (core logic independent of HTTP)
- ✅ Explicit dependencies (no shadow imports)

---

## Directory Structure

```
run-density/
├── app/                    # Application root
│   ├── api/               # FastAPI routes and models
│   │   ├── density.py     # Density API endpoints
│   │   ├── flow.py        # Flow API endpoints
│   │   ├── map.py         # Map API endpoints
│   │   ├── report.py      # Report generation API
│   │   └── models/        # Pydantic request/response models
│   │
│   ├── core/              # Business logic (domain layer)
│   │   ├── bin/           # Bin-level analysis
│   │   ├── density/       # Density computation
│   │   ├── flow/          # Temporal flow analysis
│   │   └── gpx/           # GPX processing
│   │
│   ├── routes/            # Additional HTTP handlers
│   │   ├── api_*.py       # API route handlers
│   │   ├── reports.py     # Report UI routes
│   │   └── ui.py          # Static UI routes
│   │
│   ├── utils/             # Shared utilities
│   │   ├── constants.py   # System-wide constants
│   │   ├── env.py         # Environment helpers
│   │   └── shared.py      # Common utility functions
│   │
│   ├── main.py            # FastAPI application entry point
│   └── *.py               # Supporting modules (reports, services, etc.)
│
├── /app/core/artifacts/  # UI artifacts & heatmap generation
├── data/                  # Input CSV files
├── config/                # YAML configuration
├── tests/                 # Test suite
└── docs/                  # Documentation
```

---

## Layer Architecture

### Layer Definitions

```
┌─────────────────────────────────────────────────┐
│  LAYER 1: API (HTTP Interface)                  │
│  - FastAPI routes                               │
│  - Request/response models                      │
│  - HTTP-specific logic only                     │
│  CAN import: Core, Utils                        │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  LAYER 2: Core (Business Logic)                 │
│  - Domain models                                │
│  - Analysis algorithms                          │
│  - Business rules                               │
│  CAN import: Utils only                         │
│  CANNOT import: API, Routes                     │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  LAYER 3: Utils (Shared Utilities)              │
│  - Constants                                    │
│  - Helper functions                             │
│  - Environment utilities                        │
│  CAN import: Standard library only              │
│  CANNOT import: API, Core, Routes               │
└─────────────────────────────────────────────────┘
```

### Layer Import Rules

| Layer | Can Import From | Cannot Import From | Why |
|-------|----------------|-------------------|-----|
| **API** | Core, Utils | Other API routes | Prevents coupling between routes |
| **Core** | Utils only | API, Routes | Domain isolation - business logic independent of HTTP |
| **Utils** | stdlib only | API, Core, Routes | Zero dependencies - pure utilities |

**Enforcement:**
- Architecture tests in `tests/test_architecture.py`
- Import-linter configuration in `.importlinter`
- CI pipeline validates on every PR

---

## Import Patterns

### v1.7.0 Standard Pattern

**All imports must use absolute paths with `app.` prefix:**

```python
# ✅ CORRECT - Absolute imports with app.* prefix
from app.api.density import router
from app.core.density.compute import analyze_density_segments
from app.core.flow.flow import analyze_temporal_flow_segments
from app.utils.constants import DEFAULT_STEP_KM
from app.utils.env import env_bool, env_str
```

```python
# ❌ FORBIDDEN - Relative imports
from .density import analyze_density_segments
from ..core.flow import analyze_temporal_flow_segments
```

```python
# ❌ FORBIDDEN - Try/except import fallbacks
try:
    from .module import function
except ImportError:
    from module import function
```

```python
# ❌ FORBIDDEN - Imports without app. prefix
from core.density.compute import analyze_density_segments
from constants import DEFAULT_STEP_KM
```

### Why This Pattern?

**Benefits:**
1. **Works in all environments** (local, Docker, Cloud Run) without fallbacks
2. **Explicit dependencies** - clear where code comes from
3. **Static analysis friendly** - tools can trace imports
4. **Refactoring safe** - moving files doesn't break imports
5. **No shadow dependencies** - everything is visible

**Historical Context:**
- v1.6.x used dual import pattern (try/except fallbacks)
- Caused shadow dependencies and environment-specific behavior
- Made safe refactoring impossible (Nov 2025 archival failure)
- v1.7 eliminates all fallbacks for clarity

---

## Module Organization

### app/api/ - API Layer

**Purpose:** HTTP interface (FastAPI routes)

**Contents:**
- Route handlers (`@router.get`, `@router.post`)
- Request/response models (Pydantic)
- HTTP-specific logic (status codes, responses)

**Import Rules:**
- ✅ Can import from `app.core.*` (business logic)
- ✅ Can import from `app.utils.*` (utilities)
- ❌ Cannot import from `app.routes.*` (prevents coupling)

**Example:**
```python
from app.api.density import router
from app.core.density.compute import analyze_density_segments
from app.utils.constants import DEFAULT_STEP_KM
```

### app/core/ - Core Domain Logic

**Purpose:** Business logic independent of HTTP

**Contents:**
- Domain models and algorithms
- Analysis functions
- Business rules
- Data transformations

**Import Rules:**
- ✅ Can import from `app.utils.*` (utilities)
- ❌ Cannot import from `app.api.*` (domain isolation)
- ❌ Cannot import from `app.routes.*` (domain isolation)

**Example:**
```python
from app.core.density.models import DensityConfig
from app.utils.constants import DISTANCE_BIN_SIZE_KM
```

**Why Domain Isolation?**
- Core logic can be tested without HTTP layer
- Algorithms can be reused in CLI, batch jobs, etc.
- Business rules don't depend on FastAPI

### app/routes/ - Additional HTTP Handlers

**Purpose:** Route handlers that don't fit in `/api`

**Contents:**
- UI serving routes
- Report download routes
- Dashboard routes
- Static file handlers

**Import Rules:**
- ✅ Can import from `app.core.*`
- ✅ Can import from `app.utils.*`
- ✅ Can import from `app.api.*` (to reuse models)

### app/utils/ - Shared Utilities

**Purpose:** Zero-dependency helper functions and constants

**Contents:**
- `constants.py` - System-wide constants
- `env.py` - Environment variable helpers
- `shared.py` - Common utility functions

**Import Rules:**
- ✅ Can import standard library only
- ❌ Cannot import ANY app modules

**Why Zero Dependencies?**
- Utils are leaf nodes in dependency graph
- Can be used anywhere without circular imports
- Easy to test in isolation

---

## Common Patterns

### Adding a New API Endpoint

See: [adding-modules.md](adding-modules.md) for step-by-step guide

**Quick Example:**
```python
# app/api/my_feature.py
from fastapi import APIRouter
from app.core.my_feature.logic import do_analysis
from app.utils.constants import SOME_CONSTANT

router = APIRouter(prefix='/api/my-feature', tags=['my-feature'])

@router.post('/analyze')
async def analyze(request: MyRequest):
    result = do_analysis(request.data)
    return {"result": result}

# In app/main.py, add:
from app.api.my_feature import router as my_feature_router
app.include_router(my_feature_router)
```

### Adding Core Business Logic

```python
# app/core/my_feature/logic.py
from app.utils.constants import SOME_CONSTANT

def do_analysis(data):
    # Business logic here
    return result
```

### Adding a Utility Function

```python
# app/utils/shared.py (or create new file in utils/)
def my_helper_function(input):
    # Utility logic using only stdlib
    return output
```

---

## Testing Strategy

### Architecture Tests

**File:** `tests/test_architecture.py`

**What's Tested:**
- ✅ No try/except import fallbacks exist
- ✅ All imports use app.* prefix
- ✅ No stub files remain
- ✅ Layer boundaries respected

**Run locally:**
```bash
pytest tests/test_architecture.py -v
```

### Import-Linter

**Config:** `.importlinter`

**What's Enforced:**
- Layer import rules (API → Core → Utils)
- Forbidden cross-layer imports
- Circular dependency prevention

**Run locally:**
```bash
lint-imports
```

### E2E Tests

Ensure all functionality still works after architectural changes.

**Run locally:**
```bash
make e2e-docker
```

---

## Migration from v1.6.x

### Breaking Changes in v1.7

**1. Import Paths Changed:**
```python
# v1.6.x (old)
from density import analyze_density_segments
from constants import DEFAULT_STEP_KM

# v1.7.0 (new)
from app.core.density.compute import analyze_density_segments
from app.utils.constants import DEFAULT_STEP_KM
```

**2. Stub Files Removed:**
- `app/density_api.py` → Use `app.api.density`
- `app/flow.py` → Use `app.core.flow.flow`
- `app/report.py` → Use `app.api.report`
- `app/map_api.py` → Use `app.api.map`

**3. Directory Structure:**
- `/api` → `/app/api`
- `/core` → `/app/core`
- `app/constants.py` → `app/utils/constants.py`

### Migration Guide

For existing code using old imports:

1. Replace relative imports with absolute:
   - `from .module` → `from app.module`

2. Update path to match new structure:
   - `from api.X` → `from app.api.X`
   - `from core.X` → `from app.core.X`
   - `from constants` → `from app.utils.constants`

3. Remove try/except import fallbacks:
   - Delete the entire try/except block
   - Keep only the absolute import

4. Run tests to verify:
   ```bash
   pytest tests/test_architecture.py
   lint-imports
   make e2e-docker
   ```

---

## Anti-Patterns to Avoid

### ❌ Don't Use Try/Except for Imports

**Why it's bad:**
- Creates shadow dependencies
- Different code paths in different environments
- Breaks static analysis tools
- Makes refactoring dangerous

**What to do instead:**
- Use single absolute import path
- Fix PYTHONPATH if imports fail
- Report error rather than silently falling back

### ❌ Don't Create Stub Files

**Why it's bad:**
- Adds indirection without benefit
- Makes dependency tree opaque
- Appears unused to analysis tools

**What to do instead:**
- Import directly from implementation
- Use explicit app.* paths

### ❌ Don't Import Across Layers Incorrectly

**Why it's bad:**
- Creates circular dependencies
- Violates domain isolation
- Makes testing harder

**What to do instead:**
- Follow layer import rules
- Core should never import from API
- Utils should never import from app modules

---

## Troubleshooting

### Import Errors After Upgrade

**Error:** `ModuleNotFoundError: No module named 'density'`

**Cause:** Old import path (v1.6.x style)

**Fix:** Update to v1.7 path:
```python
# Old
from density import analyze_density_segments

# New
from app.core.density.compute import analyze_density_segments
```

### PYTHONPATH Issues

**Error:** `No module named 'app'`

**Cause:** PYTHONPATH not set correctly

**Fix (Docker):** Already configured in `docker-compose.yml`

**Fix (Local venv):**
```bash
export PYTHONPATH=/path/to/run-density:$PYTHONPATH
```

Or run from project root:
```bash
cd /path/to/run-density
python -m app.main
```

### Import-Linter Failures

**Error:** `Layer contract violated: core imports from api`

**Cause:** Code violates layer boundaries

**Fix:** Review import rules above and refactor to follow layers

---

## Quick Reference

### Common Import Patterns

| What You Need | Import Statement |
|---------------|------------------|
| Density analysis | `from app.core.density.compute import analyze_density_segments` |
| Flow analysis | `from app.core.flow.flow import analyze_temporal_flow_segments` |
| Constants | `from app.utils.constants import DEFAULT_STEP_KM` |
| Environment vars | `from app.utils.env import env_bool, env_str` |
| Density API router | `from app.api.density import router` |
| Utility functions | `from app.utils.shared import load_pace_csv` |

### Common Commands

| Task | Command |
|------|---------|
| Run architecture tests | `pytest tests/test_architecture.py` |
| Check import rules | `lint-imports` |
| Start Docker dev | `make dev-docker` |
| Run smoke tests | `make smoke-docker` |
| Run E2E tests | `make e2e-docker` |

---

## Additional Documentation

- **[v1.7 Reset Rationale](v1.7-reset-rationale.md)** - Why we did the reset
- **[Current Import Dependencies](current-import-dependencies.md)** - Detailed import map
- **[Adding Modules Guide](adding-modules.md)** - Step-by-step module creation
- **[Architecture Testing](testing.md)** - Testing strategy and examples
- **[Developer Onboarding](../onboarding/developer-checklist.md)** - New developer guide

---

## Questions?

If you're unsure about:
- Where to put new code
- What import pattern to use
- Whether a change violates layer rules

See: [adding-modules.md](adding-modules.md) or ask the team.

---

**The v1.7 architecture prioritizes clarity and maintainability over backward compatibility.**

