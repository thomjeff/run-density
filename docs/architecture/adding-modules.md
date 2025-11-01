# How to Add a Module - v1.7.0

**Last Updated:** 2025-11-01  
**Architecture:** v1.7.0

---

## Overview

This guide provides step-by-step instructions for adding new modules to the run-density codebase following v1.7 architecture patterns.

**Before you start:**
- ✅ Read [Architecture README](README.md)
- ✅ Understand layer boundaries
- ✅ Know import patterns

---

## Adding a New API Endpoint

### Step 1: Create the Route Handler

**File:** `app/api/my_feature.py`

```python
"""
My Feature API

Provides endpoints for [feature description].
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.my_feature.logic import do_analysis
from app.utils.constants import SOME_CONSTANT

# Create router
router = APIRouter(prefix='/api/my-feature', tags=['my-feature'])

# Define request/response models
class MyRequest(BaseModel):
    data: str
    param: float = 1.0

class MyResponse(BaseModel):
    result: str
    computed: float

# Define endpoint
@router.post('/analyze', response_model=MyResponse)
async def analyze(request: MyRequest):
    """Analyze data using my feature."""
    result = do_analysis(request.data, request.param)
    return MyResponse(result=result['output'], computed=result['value'])
```

### Step 2: Register in main.py

**File:** `app/main.py`

```python
# Add to imports section (around line 15-35)
from app.api.my_feature import router as my_feature_router

# Add to router registration (around line 140-160)
app.include_router(my_feature_router)
```

### Step 3: Add Tests

**File:** `tests/test_my_feature.py`

```python
import pytest
from app.api.my_feature import analyze
from app.api.my_feature import MyRequest

def test_my_feature_basic():
    request = MyRequest(data="test", param=1.5)
    response = await analyze(request)
    assert response.result is not None
```

### Step 4: Verify

```bash
# Test locally
make smoke-docker    # Quick check
make e2e-docker      # Full validation

# Check architecture rules
pytest tests/test_architecture.py
lint-imports
```

---

## Adding Core Business Logic

### Step 1: Create the Module

**File:** `app/core/my_feature/logic.py`

```python
"""
My Feature Business Logic

Core analysis logic independent of HTTP layer.
"""

from app.utils.constants import SOME_CONSTANT
from app.utils.shared import some_helper
import pandas as pd

def do_analysis(data: str, param: float) -> dict:
    """
    Perform analysis on data.
    
    Args:
        data: Input data
        param: Analysis parameter
        
    Returns:
        Dictionary with analysis results
    """
    # Business logic here
    result = data.upper() * int(param)
    
    return {
        'output': result,
        'value': param * SOME_CONSTANT
    }
```

### Step 2: Add Domain Models (if needed)

**File:** `app/core/my_feature/models.py`

```python
"""
My Feature Domain Models

Data structures for my feature domain logic.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class MyDomainModel:
    field1: str
    field2: float
    field3: Optional[str] = None
```

### Step 3: Create __init__.py

**File:** `app/core/my_feature/__init__.py`

```python
"""
My Feature Core Module

[Description of what this module does]
"""

from app.core.my_feature.logic import do_analysis
from app.core.my_feature.models import MyDomainModel

__all__ = ['do_analysis', 'MyDomainModel']
```

### Step 4: Add Unit Tests

**File:** `tests/test_my_feature_core.py`

```python
import pytest
from app.core.my_feature.logic import do_analysis
from app.utils.constants import SOME_CONSTANT

def test_do_analysis_basic():
    result = do_analysis("test", 2.0)
    assert result['output'] == "TESTTEST"
    assert result['value'] == 2.0 * SOME_CONSTANT
```

---

## Adding a Utility Function

### Step 1: Choose Location

**New file in utils/:**
```
app/utils/my_utils.py
```

**Or add to existing:**
```
app/utils/shared.py  # For general utilities
app/utils/constants.py  # For constants only
```

### Step 2: Create Function

**File:** `app/utils/my_utils.py`

```python
"""
My Utilities

Shared helper functions for [purpose].

IMPORTANT: Utils should only import from standard library.
No imports from app.api, app.core, or app.routes.
"""

from typing import List
import re

def parse_something(input: str) -> List[str]:
    """
    Parse input into components.
    
    Args:
        input: String to parse
        
    Returns:
        List of parsed components
    """
    return re.split(r'\s+', input.strip())
```

### Step 3: Use in Code

```python
# From any module
from app.utils.my_utils import parse_something

result = parse_something("hello world")
```

### Step 4: Add Tests

**File:** `tests/test_my_utils.py`

```python
from app.utils.my_utils import parse_something

def test_parse_something():
    result = parse_something("hello world")
    assert result == ["hello", "world"]
```

---

## Adding a Constant

### Step 1: Add to constants.py

**File:** `app/utils/constants.py`

```python
# Add to appropriate section with comment
MY_NEW_CONSTANT = 100  # Description of what this constant means
```

### Step 2: Use in Code

```python
from app.utils.constants import MY_NEW_CONSTANT

value = data * MY_NEW_CONSTANT
```

### Step 3: Document

Add docstring or inline comment explaining:
- What the constant represents
- Why this value was chosen
- Any constraints or assumptions

---

## Architecture Checklist

Before committing new code, verify:

- [ ] **Imports use app.* prefix**
  ```python
  from app.core.X import Y  # ✅
  from core.X import Y      # ❌
  ```

- [ ] **No try/except import fallbacks**
  ```python
  try:
      from .module import X
  except ImportError:
      from module import X  # ❌ Remove this
  ```

- [ ] **Layer rules followed**
  - API can import Core, Utils ✅
  - Core can import Utils only ✅
  - Utils imports stdlib only ✅

- [ ] **Tests added**
  - Unit tests for core logic
  - Integration tests for API endpoints
  - Architecture tests pass

- [ ] **import-linter passes**
  ```bash
  lint-imports  # Should pass
  ```

---

## Examples from Codebase

### Example 1: Density API

**Location:** `app/api/density.py`

**Pattern:**
```python
from app.core.density.compute import analyze_density_segments
from app.utils.constants import DEFAULT_STEP_KM
from app.api.models.density import DensityAnalysisRequest
```

**Why it works:**
- API imports from Core (allowed)
- API imports from Utils (allowed)
- API imports from own models (allowed)

### Example 2: Flow Analysis

**Location:** `app/core/flow/flow.py`

**Pattern:**
```python
from app.utils.constants import DISTANCE_BIN_SIZE_KM
from app.utils.shared import load_pace_csv
from app.core.density.models import DensityConfig
```

**Why it works:**
- Core imports from Utils (allowed)
- Core imports from other Core modules (allowed)
- Core does NOT import from API (correct)

### Example 3: Utility Function

**Location:** `app/utils/shared.py`

**Pattern:**
```python
import pandas as pd
from app.utils.constants import SECONDS_PER_MINUTE
```

**Why it works:**
- Utils imports from Utils (allowed - same layer)
- Utils only imports stdlib and other utils
- Utils does NOT import from app modules (correct)

---

## Common Mistakes

### Mistake 1: Circular Import

**Problem:**
```python
# app/api/density.py
from app.core.density.compute import analyze_density_segments

# app/core/density/compute.py
from app.api.density import router  # ❌ CIRCULAR
```

**Solution:**
- Core should never import from API
- Move shared code to Utils if needed

### Mistake 2: Wrong Layer

**Problem:**
```python
# app/utils/my_utils.py
from app.core.density.compute import analyze_density_segments  # ❌
```

**Solution:**
- Utils cannot depend on Core
- Move function to Core if it needs Core imports

### Mistake 3: Relative Imports

**Problem:**
```python
from .constants import DEFAULT_STEP_KM  # ❌ Old pattern
```

**Solution:**
```python
from app.utils.constants import DEFAULT_STEP_KM  # ✅
```

---

## Getting Help

1. **Check existing patterns:**
   - Look at similar modules in codebase
   - Follow established patterns

2. **Run architecture tests:**
   ```bash
   pytest tests/test_architecture.py -v
   ```

3. **Use import-linter:**
   ```bash
   lint-imports
   ```

4. **Ask the team:**
   - Unclear where code belongs?
   - Unsure about import pattern?
   - Layer boundary question?

---

**Remember: Clear architecture now saves debugging time later.**

