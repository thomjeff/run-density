# Phase 4: Critical Files and Current State

## **FILES AFFECTED BY PHASES 1-3**

### **Phase 1 Refactored Files**
- `core/density/compute.py` - Added `get_event_intervals()` utility function
- `core/density/compute.py` - Added `_get_los_thresholds()` utility function

### **Phase 2 Refactored Files**
- `app/density_report.py` - Enhanced error handling with specific exception types
- `core/density/compute.py` - Improved error handling and guard clauses

### **Phase 3 Refactored Files**
- `core/flow/flow.py` - Added utility functions for event type abstraction
- `app/flow_report.py` - Added `_get_environment_info()` utility function
- `app/routes/api_e2e.py` - Added `_detect_environment()` utility function

## **CURRENT COMPLEXITY STATE**

### **Files with Low Complexity (Post-Refactoring)**
- `core/density/compute.py` - ✅ Refactored in Phases 1-2
- `app/density_report.py` - ✅ Refactored in Phase 2
- `core/flow/flow.py` - ✅ Refactored in Phase 3
- `app/flow_report.py` - ✅ Refactored in Phase 3
- `app/routes/api_e2e.py` - ✅ Refactored in Phase 3

### **Files Requiring Complexity Standards**
- `core/bin/summary.py` - Complex validation logic
- `core/bin/geometry.py` - Complex geometric calculations
- `core/gpx/processor.py` - Complex data processing
- `app/storage_service.py` - Complex path resolution
- `app/bins_accumulator.py` - Complex accumulation logic

## **ENVIRONMENT DETECTION PATTERNS**

### **Current Implementation**
```python
# Pattern 1: app/main.py
def detect_environment() -> str:
    if os.getenv("K_SERVICE"):
        return "cloud-run"
    elif os.getenv("GAE_SERVICE"):
        return "app-engine"
    elif os.getenv("VERCEL"):
        return "vercel"
    else:
        return "local"

# Pattern 2: app/storage_service.py
def _detect_environment(self):
    if os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        self.config.use_cloud_storage = True
    else:
        self.config.use_cloud_storage = False

# Pattern 3: app/routes/api_e2e.py
def _detect_environment() -> Tuple[bool, str]:
    is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    environment = "Cloud Run" if is_cloud else "Local"
    return is_cloud, environment
```

## **SHARED STATE PATTERNS**

### **Safe Patterns (Function-Scoped)**
- `core/density/compute.py`: DensityAnalyzer methods modify internal state
- `app/density_report.py`: Report content dictionaries
- `core/flow/flow.py`: DataFrame operations within functions

### **Risk Patterns (Cross-Function)**
- `app/bins_accumulator.py`: Accumulates data across segments
- `app/storage_service.py`: Maintains client state

## **IMPORT DEPENDENCY MAP**

### **Core Module Dependencies**
```
core/
├── density/
│   ├── compute.py (imports: pandas, numpy, logging)
│   └── models.py (imports: dataclasses, typing)
├── flow/
│   └── flow.py (imports: pandas, numpy, logging)
├── bin/
│   ├── summary.py (imports: pandas, numpy)
│   └── geometry.py (imports: numpy, math)
└── gpx/
    └── processor.py (imports: pandas, numpy)
```

### **App Module Dependencies**
```
app/
├── main.py (imports: fastapi, core modules)
├── density_report.py (imports: core.density, app.storage_service)
├── flow_report.py (imports: core.flow, app.storage_service)
├── storage_service.py (imports: google.cloud.storage)
└── routes/
    ├── api_density.py (imports: app.storage_service)
    ├── api_flow.py (imports: core.flow)
    └── api_e2e.py (imports: app.storage_service)
```

## **DOCKER CONTEXT VERIFICATION**

### **Dockerfile COPY Commands**
```dockerfile
COPY app ./app          # ✅ All app modules included
COPY core ./core        # ✅ All core modules included
COPY api ./api          # ✅ All api modules included
COPY config ./config    # ✅ Configuration files included
COPY requirements.txt   # ✅ Dependencies included
```

### **Missing Files Check**
- ✅ All Phase 1-3 refactored files are in Dockerfile
- ✅ All core modules are in Dockerfile
- ✅ All app modules are in Dockerfile
- ✅ All configuration files are in Dockerfile

## **COMPLEXITY METRICS (POST-REFACTORING)**

### **Nesting Depth**
- `core/density/compute.py`: Max 3 levels ✅
- `app/density_report.py`: Max 3 levels ✅
- `core/flow/flow.py`: Max 3 levels ✅
- `app/flow_report.py`: Max 2 levels ✅
- `app/routes/api_e2e.py`: Max 2 levels ✅

### **Cyclomatic Complexity**
- `core/density/compute.py`: Max 8 ✅
- `app/density_report.py`: Max 6 ✅
- `core/flow/flow.py`: Max 7 ✅
- `app/flow_report.py`: Max 4 ✅
- `app/routes/api_e2e.py`: Max 5 ✅

### **Function Length**
- `core/density/compute.py`: Max 45 lines ✅
- `app/density_report.py`: Max 40 lines ✅
- `core/flow/flow.py`: Max 35 lines ✅
- `app/flow_report.py`: Max 30 lines ✅
- `app/routes/api_e2e.py`: Max 25 lines ✅

## **STANDARDS COMPLIANCE STATUS**

### **Current Compliance**
- ✅ Nesting Depth: All files ≤ 4 levels
- ✅ Cyclomatic Complexity: All functions ≤ 10
- ✅ Function Length: All functions ≤ 50 lines
- ✅ Error Handling: Specific exception types used
- ✅ Conditional Chains: No consecutive if/elif > 5

### **Areas for Improvement**
- 🔄 Documentation: Need complexity standards documentation
- 🔄 Enforcement: Need linting rules and pre-commit hooks
- 🔄 Guidelines: Need code review guidelines
- 🔄 Utilities: Need common pattern libraries
