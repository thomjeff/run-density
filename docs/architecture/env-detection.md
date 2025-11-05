# Environment Detection Architecture

**Issue:** #451 Task 2  
**Date:** 2025-11-04  
**Purpose:** Document environment detection logic across runtime and storage configurations

## Overview

The Run Density application uses environment detection to automatically configure itself for different runtime environments and storage targets. This system was enhanced in Issue #447 to support E2E testing across local and staging environments.

**Key Principle:** Detection is based on environment variables, not hardcoded configuration files, enabling seamless deployment across local, staging, and production environments without code changes.

## Environment Variables

### Runtime Detection Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `K_SERVICE` | Cloud Run | Identifies Cloud Run runtime environment |
| `GAE_SERVICE` | App Engine | Identifies App Engine runtime (legacy support) |
| `GOOGLE_CLOUD_PROJECT` | Cloud Run / Manual | GCP project identifier |
| `GCS_UPLOAD` | Manual / CI | **Explicit override** for storage target selection |

### Storage Configuration Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GCS_UPLOAD` | Enable/disable GCS storage | `false` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `run-density` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account key | `/tmp/keys/gcs-sa.json` |
| `DATA_ROOT` | Local storage root (local mode) | Resolved from `artifacts/latest.json` or `./data` |
| `GCS_BUCKET` | GCS bucket name (cloud mode) | `run-density-reports` |
| `GCS_PREFIX` | GCS object prefix (cloud mode) | `artifacts` |

## Detection Functions

### Canonical Detection Functions (Issue #452)
**Location:** `app/utils/env.py`

These are the **canonical** environment detection functions that should be used across the application. They follow the Issue #447 priority order and provide consistent behavior.

#### `detect_runtime_environment()` - Canonical Runtime Detection
**Returns:** `Literal["local_docker", "cloud_run"]`

**Logic:**
```python
def detect_runtime_environment() -> Literal["local_docker", "cloud_run"]:
    # K_SERVICE is set automatically by Cloud Run
    if os.getenv('K_SERVICE'):
        return "cloud_run"
    else:
        return "local_docker"
```

**Used By:**
- `app/utils/metadata.py` - Run metadata generation
- Future: Other modules can be refactored to use this

---

#### `detect_storage_target()` - Canonical Storage Detection
**Returns:** `Literal["filesystem", "gcs"]`

**Logic (Priority Order):**
1. Check `GCS_UPLOAD=true` → Use GCS (explicit override for staging)
2. Check `K_SERVICE` or `GOOGLE_CLOUD_PROJECT` → Use GCS (Cloud Run auto-detect)
3. Default → Use filesystem (local development)

```python
def detect_storage_target() -> Literal["filesystem", "gcs"]:
    # Issue #447: Check GCS_UPLOAD flag first (staging mode)
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        return "gcs"
    # Check Cloud Run environment variables (automatic detection)
    elif os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        return "gcs"
    else:
        return "filesystem"
```

**Used By:**
- `app/utils/metadata.py` - Run metadata generation
- Future: StorageService, Storage, api_e2e can be refactored to use this

**Note:** These canonical functions were introduced in Issue #452 to ensure consistent environment detection across the application following Issue #447 standards.

---

### 1. `detect_environment()` - Runtime Detection (Informational)
**Location:** `app/main.py:400`

**Purpose:** Identify the cloud platform runtime environment (informational, broader scope)

**Logic:**
```python
def detect_environment() -> str:
    if os.getenv("K_SERVICE"):
        return "cloud-run"
    elif os.getenv("GAE_SERVICE"):
        return "app-engine"
    elif os.getenv("VERCEL"):
        return "vercel"
    else:
        return "local"
```

**Returns:** Platform identifier string (`cloud-run`, `app-engine`, `vercel`, `local`)

**Used By:** General runtime detection (informational)

---

### 2. `StorageService._detect_environment()` - Storage Target Detection
**Location:** `app/storage_service.py:62`

**Purpose:** Determine whether to use Cloud Storage or local filesystem for reports

**Logic (Priority Order):**
1. **Explicit GCS Flag (Highest Priority):**
   - If `GCS_UPLOAD=true` → Use Cloud Storage
   - Enables staging mode (local container, cloud storage)

2. **Cloud Run Detection:**
   - If `K_SERVICE` or `GOOGLE_CLOUD_PROJECT` set → Use Cloud Storage
   - Automatic for production Cloud Run

3. **Default:**
   - Use local filesystem storage

**Implementation:**
```python
def _detect_environment(self):
    # Issue #447: Check for explicit GCS upload flag first (staging mode)
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        self.config.use_cloud_storage = True
        self.config.project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'run-density')
        logger.info("GCS uploads enabled via GCS_UPLOAD flag - using Cloud Storage")
    # Check for Cloud Run environment variables
    elif os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        self.config.use_cloud_storage = True
        self.config.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        logger.info("Detected Cloud Run environment - using Cloud Storage")
    else:
        self.config.use_cloud_storage = False
        logger.info("Detected local environment - using file system storage")
```

**Returns:** Configures `self.config.use_cloud_storage` boolean

**Used By:** `StorageService` (reports storage)

---

### 3. `create_storage_from_env()` - Artifacts Storage Detection
**Location:** `app/storage.py:295`

**Purpose:** Configure `Storage` instance for UI artifacts (heatmaps, metadata)

**Logic (Same Priority as StorageService):**
1. Check `GCS_UPLOAD=true` → Cloud mode
2. Check `K_SERVICE` or `GOOGLE_CLOUD_PROJECT` → Cloud mode
3. Default → Local mode

**Implementation:**
```python
def create_storage_from_env() -> Storage:
    # Auto-detect Cloud Run environment (same as storage_service.py)
    # Issue #447: Check GCS_UPLOAD flag first (staging mode)
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        is_cloud = True
    else:
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    env = "cloud" if is_cloud else "local"
    
    if env == "local":
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
        return Storage(mode="local", root=root)
    else:
        # Cloud Run mode - use GCS with defaults
        bucket = os.getenv("GCS_BUCKET", "run-density-reports")
        prefix = os.getenv("GCS_PREFIX", "artifacts")
        return Storage(mode="gcs", bucket=bucket, prefix=prefix)
```

**Returns:** `Storage` instance configured for local or GCS mode

**Used By:** Heatmap generation, UI artifacts storage

---

### 4. `_detect_environment()` - E2E API Detection
**Location:** `app/routes/api_e2e.py:34`

**Purpose:** Detect environment for E2E testing endpoints

**Logic (Same Priority):**
```python
def _detect_environment() -> Tuple[bool, str]:
    # Issue #447: Check GCS_UPLOAD flag first (staging mode)
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        is_cloud = True
    else:
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    environment = "Cloud Run" if is_cloud else "Local"
    return is_cloud, environment
```

**Returns:** Tuple of `(is_cloud: bool, environment_name: str)`

**Used By:** E2E API endpoints (`/api/e2e/run`, `/api/e2e/upload`)

## Environment Configurations

### Local Development (Default)
**Runtime:** Local Python process or Docker container  
**Storage:** Local filesystem

**Environment:**
```bash
# No special variables required
# Or explicitly set:
GCS_UPLOAD=false
```

**Detection Result:**
- Runtime: `local`
- Storage: Local filesystem
- Reports: `./reports/`
- Artifacts: `./artifacts/{run_id}/ui/`

**Use Cases:**
- Standard local development
- Testing without cloud dependencies
- Offline development

---

### Staging Mode (E2E Testing)
**Runtime:** Local Docker container  
**Storage:** Google Cloud Storage

**Environment:**
```bash
GCS_UPLOAD=true
GOOGLE_CLOUD_PROJECT=run-density
GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

**Detection Result:**
- Runtime: `local` (container)
- Storage: Cloud Storage (GCS)
- Reports: `gs://run-density-reports/YYYY-MM-DD/`
- Artifacts: `gs://run-density-reports/artifacts/{run_id}/ui/`

**Use Cases:**
- E2E testing against staging Cloud Run
- Validating GCS integration locally
- Pre-production testing

**Makefile Target:**
```bash
make e2e-staging-docker
```

---

### Production Cloud Run
**Runtime:** Google Cloud Run  
**Storage:** Google Cloud Storage (automatic)

**Environment:**
```bash
# Auto-detected by Cloud Run:
K_SERVICE=run-density
GOOGLE_CLOUD_PROJECT=run-density
# Application Default Credentials (no key file)
```

**Detection Result:**
- Runtime: `cloud-run`
- Storage: Cloud Storage (GCS)
- Reports: `gs://run-density-reports/YYYY-MM-DD/`
- Artifacts: `gs://run-density-reports/artifacts/{run_id}/ui/`

**Use Cases:**
- Production workloads
- Public API serving
- Persistent storage requirements

---

### Staging Cloud Run
**Runtime:** Google Cloud Run (staging service)  
**Storage:** Google Cloud Storage (automatic)

**Environment:**
```bash
# Auto-detected by Cloud Run:
K_SERVICE=run-density-staging
GOOGLE_CLOUD_PROJECT=run-density
# Application Default Credentials (no key file)
```

**Detection Result:**
- Runtime: `cloud-run`
- Storage: Cloud Storage (GCS)
- Reports: `gs://run-density-reports/YYYY-MM-DD/`
- Artifacts: `gs://run-density-reports/artifacts/{run_id}/ui/`

**Use Cases:**
- Pre-production validation
- Integration testing
- Staging deployments

## E2E Testing Modes

### E2E Local Mode
**Command:** `python e2e.py --local` or `make e2e-local-docker`

**Configuration:**
- Target: `http://localhost:8080`
- Container environment: Local filesystem storage
- Tests: All endpoints against local server

**Environment Setup:**
```bash
GCS_UPLOAD=false  # Explicitly disable GCS
```

**Validation:**
- ✅ Local storage write access
- ✅ Report generation to `./reports/`
- ✅ Artifacts saved to `./artifacts/`

---

### E2E Staging Mode
**Command:** `make e2e-staging-docker`

**Configuration:**
- Target: `http://localhost:8080`
- Container environment: GCS storage enabled
- Tests: All endpoints with cloud storage

**Environment Setup:**
```bash
GCS_UPLOAD=true
GOOGLE_CLOUD_PROJECT=run-density
GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

**Validation:**
- ✅ GCS storage write access
- ✅ Report generation to `gs://run-density-reports/`
- ✅ Artifacts saved to GCS
- ✅ Service account authentication

---

### E2E Production Mode
**Command:** `python e2e.py --cloud` or `make e2e-prod-gcp`

**Configuration:**
- Target: `https://run-density-{hash}.us-central1.run.app`
- Container environment: Cloud Run production
- Tests: All endpoints against production service

**Environment:**
- Auto-detected by Cloud Run runtime
- No explicit configuration required

**Validation:**
- ✅ Production endpoint availability
- ✅ Cloud Run authentication
- ✅ GCS storage (automatic)

## Detection Flow Diagram

```
┌─────────────────────────────────────┐
│   Application Startup               │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Check Environment Variables       │
└──────────────┬──────────────────────┘
               │
               ▼
       ┌───────────────┐
       │  GCS_UPLOAD?  │
       └───┬───────┬───┘
           │       │
       Yes │       │ No
           │       │
           ▼       ▼
    ┌──────────┐  ┌────────────────┐
    │  Cloud   │  │  K_SERVICE or  │
    │ Storage  │  │  GCP_PROJECT?  │
    └──────────┘  └────┬───────┬───┘
                       │       │
                   Yes │       │ No
                       │       │
                       ▼       ▼
                ┌──────────┐  ┌──────────┐
                │  Cloud   │  │  Local   │
                │ Storage  │  │ Storage  │
                └──────────┘  └──────────┘
```

## Consistency Requirements

### Issue #447 Alignment
All detection functions must follow the same priority order:
1. **Check `GCS_UPLOAD` flag first** (explicit override for staging)
2. Check Cloud Run environment variables (`K_SERVICE`, `GOOGLE_CLOUD_PROJECT`)
3. Default to local mode

This ensures consistent behavior across:
- `StorageService` (reports)
- `Storage` (artifacts)
- `api_e2e` router (E2E endpoints)
- E2E test scripts

### Code Consistency Check
```bash
# All these should use identical detection logic:
grep -A 5 "_detect_environment" app/storage_service.py
grep -A 5 "create_storage_from_env" app/storage.py
grep -A 5 "_detect_environment" app/routes/api_e2e.py
```

## Troubleshooting

### Issue: Wrong storage target selected
**Symptoms:** Files saved to local when expecting GCS (or vice versa)

**Diagnosis:**
```python
# Add debug logging to check detection:
import os
print(f"GCS_UPLOAD: {os.getenv('GCS_UPLOAD')}")
print(f"K_SERVICE: {os.getenv('K_SERVICE')}")
print(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
```

**Resolution:**
1. Verify environment variables are set correctly
2. Check docker-compose.yml doesn't override with empty values
3. Restart container after env changes: `docker-compose restart`

---

### Issue: Staging mode not working in local Docker
**Symptoms:** `GCS_UPLOAD=true` but still using local storage

**Common Causes:**
1. Environment variable not passed to container
2. docker-compose.yml has conflicting override
3. Container not restarted after env change

**Resolution:**
```bash
# Verify env inside container:
docker-compose exec app env | grep GCS

# Should show:
# GCS_UPLOAD=true
# GOOGLE_CLOUD_PROJECT=run-density
# GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json

# If not, check docker-compose.yml env_file configuration
```

---

### Issue: Cloud Run not using GCS
**Symptoms:** Cloud Run deployment using local storage

**Diagnosis:**
- Cloud Run should automatically set `K_SERVICE`
- Check Cloud Run service configuration

**Resolution:**
1. Verify service account has Storage permissions
2. Check Cloud Run environment variables in GCP Console
3. Ensure `K_SERVICE` is present: `gcloud run services describe run-density`

## Testing Validation

### Validation Commands

**Test Local Mode:**
```bash
make e2e-local-docker
# Expected: Reports in ./reports/, artifacts in ./artifacts/
```

**Test Staging Mode:**
```bash
make e2e-staging-docker
# Expected: Reports in gs://run-density-reports/, GCS logs in container
```

**Test Production:**
```bash
make e2e-prod-gcp
# Expected: Tests pass against Cloud Run URL
```

### Expected Behaviors

| Mode | `GCS_UPLOAD` | `K_SERVICE` | Storage Target | Reports Location |
|------|--------------|-------------|----------------|------------------|
| Local Dev | `false` or unset | unset | Local | `./reports/` |
| Staging (local+GCS) | `true` | unset | GCS | `gs://run-density-reports/` |
| Cloud Run Staging | auto (ignored) | set | GCS | `gs://run-density-reports/` |
| Cloud Run Prod | auto (ignored) | set | GCS | `gs://run-density-reports/` |

## Implementation History

- **Issue #447:** E2E Test Refactor
  - Added `GCS_UPLOAD` flag for explicit storage control
  - Unified detection logic across all modules
  - Enabled staging mode (local runtime + cloud storage)
  - Added `make e2e-staging-docker` target

- **Issue #451:** Infrastructure & Environment Readiness
  - Documented detection flow
  - Validated detection across all runtimes
  - Created architecture documentation

## Implementation History (Continued)

- **Issue #452:** Phase 2 - Short UUID for Run ID
  - Created canonical detection functions in `app/utils/env.py`
  - Refactored `app/utils/metadata.py` to delegate to canonical functions
  - Established pattern for future module consolidation

## References

- Issue #447: E2E Test Refactor
- Issue #451: Run ID Phase 1 - Infrastructure & Environment Readiness
- Issue #452: Run ID Phase 2 - Short UUID for Run ID
- **Canonical Functions:** `app/utils/env.py` - detect_runtime_environment(), detect_storage_target()
- `app/utils/metadata.py` - Uses canonical functions (Issue #452)
- `app/storage_service.py` - Reports storage detection (can be refactored)
- `app/storage.py` - Artifacts storage detection (can be refactored)
- `app/routes/api_e2e.py` - E2E endpoint detection (can be refactored)
- `Makefile` - E2E testing targets
- `e2e.py` - E2E test script
- `docker-compose.yml` - Local development configuration
- `dev.env` - Development environment variables

