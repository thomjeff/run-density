# Environment Detection Architecture

**Updated:** 2025-11-10 (Issue #464 - Phase 1 Declouding)  
**Previous Version:** Archived to `archive/declouding-2025/docs/architecture/env-detection.md`  
**Purpose:** Document environment detection logic for local-only architecture

## Overview

After Phase 1 declouding (Issue #464), the Run Density application operates exclusively in local-only mode. Environment detection has been dramatically simplified to support local Docker development without cloud dependencies.

**Key Principle:** The application uses local filesystem storage only. All cloud detection logic has been removed.

## Environment Variables

### Local Development Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `PORT` | Application server port | `8080` |
| `PYTHONPATH` | Python module path | `/app` |
| `OUTPUT_DIR` | Output directory for reports | `reports` |
| `ENABLE_BIN_DATASET` | Enable bin dataset generation | `true` |
| `DATA_ROOT` | Local storage root | Resolved from `artifacts/latest.json` or `./data` |

### Removed Variables (Phase 1 Declouding)

The following variables were removed in Issue #464:
- ~~`GCS_UPLOAD`~~ - GCS storage control (removed)
- ~~`GOOGLE_CLOUD_PROJECT`~~ - GCP project ID (removed)
- ~~`GOOGLE_APPLICATION_CREDENTIALS`~~ - Service account key (removed)
- ~~`K_SERVICE`~~ - Cloud Run detection (removed)
- ~~`GCS_BUCKET`~~ - GCS bucket name (removed)
- ~~`GCS_PREFIX`~~ - GCS path prefix (removed)

## Detection Functions

### Canonical Detection Functions (Simplified)
**Location:** `app/utils/env.py`

These are the **canonical** environment detection functions used across the application. After Phase 1 declouding, they always return local-only values.

#### `detect_runtime_environment()` - Runtime Detection
**Returns:** `Literal["local_docker"]`

**Logic:**
```python
def detect_runtime_environment() -> Literal["local_docker"]:
    """Always returns local_docker after Phase 1 declouding."""
    return "local_docker"
```

**Used By:**
- `app/utils/metadata.py` - Run metadata generation
- Any module needing runtime information

---

#### `detect_storage_target()` - Storage Detection
**Returns:** `Literal["filesystem"]`

**Logic:**
```python
def detect_storage_target() -> Literal["filesystem"]:
    """Always returns filesystem after Phase 1 declouding."""
    return "filesystem"
```

**Used By:**
- `app/utils/metadata.py` - Run metadata generation
- Storage layer initialization

---

### Storage Classes (Simplified)

#### `StorageService` - Reports Storage
**Location:** `app/storage_service.py`

**Purpose:** File operations for reports and artifacts using local filesystem

**Implementation:**
```python
def __init__(self, config: Optional[StorageConfig] = None):
    self.config = config or StorageConfig()
    logger.info("Detected local environment - using file system storage")
```

**Storage Location:**
- Reports: `./reports/`
- Artifacts: `./artifacts/{run_id}/ui/`

---

#### `Storage` - Artifacts Storage
**Location:** `app/storage.py`

**Purpose:** Unified interface for reading files from local filesystem

**Implementation:**
```python
def __init__(self, root: Optional[str] = None):
    self.mode = "local"
    self.root = Path(root) if root else None
```

**Storage Location:**
- UI Artifacts: `./artifacts/{run_id}/ui/`
- Data Files: `./data/`
- Config Files: `./config/`

---

### Helper Function: `create_storage_from_env()`
**Location:** `app/storage.py`

**Purpose:** Create Storage instance from environment variables

**Implementation:**
```python
def create_storage_from_env() -> Storage:
    """Create Storage instance for local filesystem."""
    root = os.getenv("DATA_ROOT")
    
    # Try to resolve from artifacts/latest.json pointer
    if not root:
        latest_pointer = Path("artifacts/latest.json")
        if latest_pointer.exists():
            pointer_data = json.loads(latest_pointer.read_text())
            run_id = pointer_data.get("run_id")
            if run_id:
                root = f"artifacts/{run_id}/ui"
    
    # Fallback to "./data" if pointer not found
    if not root:
        root = "./data"
    
    return Storage(root=root)
```

---

### Helper Function: `create_runflow_storage()`
**Location:** `app/storage.py`

**Purpose:** Create Storage instance for runflow operations

**Implementation:**
```python
def create_runflow_storage(run_id: str) -> Storage:
    """Create Storage instance for runflow with local filesystem."""
    from app.utils.constants import RUNFLOW_ROOT_LOCAL, RUNFLOW_ROOT_CONTAINER
    
    # Detect if we're in Docker container
    if Path(RUNFLOW_ROOT_CONTAINER).exists():
        root = RUNFLOW_ROOT_CONTAINER
    else:
        root = RUNFLOW_ROOT_LOCAL
    return Storage(root=f"{root}/{run_id}")
```

## Environment Configurations

### Local Development (Only Mode)
**Runtime:** Local Docker container  
**Storage:** Local filesystem

**Environment:**
```bash
# Standard local development
GCS_UPLOAD=false  # Default in dev.env
PORT=8080
ENABLE_BIN_DATASET=true
OUTPUT_DIR=reports
```

**Storage Locations:**
- Reports: `./reports/`
- Artifacts: `./artifacts/{run_id}/ui/`
- Runflow: `./runflow/{run_id}/` or `/app/runflow/{run_id}/` (Docker)
- Heatmaps: `./artifacts/{run_id}/ui/heatmaps/`

**Use Cases:**
- All development work
- All testing (E2E, smoke, unit)
- All report generation
- All API operations

---

## Testing

### E2E Local Mode (Only Mode)
**Command:** `make e2e-local-docker`

**Configuration:**
- Target: `http://localhost:8080`
- Storage: Local filesystem
- Tests: All endpoints against local server

**Environment Setup:**
```bash
GCS_UPLOAD=false
```

**Validation:**
- ✅ Local storage write access
- ✅ Report generation to `./reports/`
- ✅ Artifacts saved to `./artifacts/`
- ✅ All heatmaps generated locally

**Expected Output:**
```
✅ Health: OK
✅ Ready: OK
✅ Density Report: OK
✅ Map Manifest: OK
✅ Temporal Flow Report: OK
✅ UI Artifacts: 7 files exported
✅ Heatmaps: 17 PNG files + 17 captions
```

---

## File Structure

### Local Filesystem Organization

```
run-density/
├── artifacts/
│   ├── latest.json              # Pointer to latest run_id
│   ├── index.json               # Run history
│   └── {run_id}/
│       └── ui/
│           ├── meta.json
│           ├── segment_metrics.json
│           ├── flags.json
│           ├── flow.json
│           ├── segments.geojson
│           ├── schema_density.json
│           ├── health.json
│           ├── captions.json
│           └── heatmaps/
│               └── *.png (17 files)
├── reports/
│   └── {date}/
│       ├── Density.md
│       ├── Flow.md
│       └── Flow.csv
└── runflow/
    ├── latest.json
    ├── index.json
    └── {run_id}/
        ├── metadata.json
        ├── reports/
        ├── bins/
        ├── maps/
        ├── heatmaps/
        └── ui/
```

---

## Implementation History

### Phase 1 Declouding (Issue #464) - 2025-11-10
- ✅ Removed all GCS/Cloud Run detection logic
- ✅ Simplified `detect_runtime_environment()` - always returns "local_docker"
- ✅ Simplified `detect_storage_target()` - always returns "filesystem"
- ✅ Removed GCS imports from storage modules
- ✅ Archived `gcs_uploader.py`, cloud scripts, and GCS documentation

### Phase 0 (Issue #465) - 2025-11-10
- ✅ Disabled Cloud CI/CD pipeline
- ✅ Archived `ci-pipeline.yml`
- ✅ Commented out cloud targets in Makefile
- ✅ Removed Cloud Run references from README

### Previous Implementation (Archived)
- **Issue #447:** E2E Test Refactor (GCS_UPLOAD flag, staging mode)
- **Issue #451:** Infrastructure & Environment Readiness (multi-environment support)
- **Issue #452:** Phase 2 - Short UUID for Run ID (canonical detection functions)

**Note:** Previous multi-environment architecture is fully documented in archived version at `archive/declouding-2025/docs/architecture/env-detection.md`.

---

## References

### Active Files
- `app/utils/env.py` - Canonical detection functions (simplified)
- `app/storage_service.py` - Reports storage (local-only)
- `app/storage.py` - Artifacts storage (local-only)
- `app/utils/metadata.py` - Run metadata generation
- `Makefile` - E2E testing targets (local-only)
- `e2e.py` - E2E test script (local mode)
- `docker-compose.yml` - Local development configuration
- `dev.env` - Development environment variables

### Archived Files (Phase 1 Declouding)
- `archive/declouding-2025/app/gcs_uploader.py` - GCS upload utilities
- `archive/declouding-2025/scripts/test_storage_access.py` - GCS access testing
- `archive/declouding-2025/scripts/cleanup_cloud_run_revisions.sh` - Cloud Run operations
- `archive/declouding-2025/docs/infrastructure/storage-access.md` - GCS access patterns
- `archive/declouding-2025/docs/architecture/env-detection.md` (previous version) - Multi-environment detection

---

## Summary

After Phase 1 declouding:
- **Single Environment:** Local Docker only
- **Single Storage:** Filesystem only
- **Simplified Detection:** Always returns local values
- **No Cloud Dependencies:** All GCP logic removed
- **Clean Architecture:** Reduced complexity, easier maintenance

For historical multi-environment architecture, see archived version at `archive/declouding-2025/docs/architecture/env-detection.md`.
