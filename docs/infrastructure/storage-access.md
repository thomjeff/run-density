# Storage Access Infrastructure

**Issue:** #451 Task 1  
**Date:** 2025-11-04  
**Purpose:** Document storage infrastructure access patterns across all runtime environments

## Overview

The Run Density application supports dual storage targets for Run ID artifacts:
1. **Local Storage:** `/Users/jthompson/Documents/runflow` (development/testing)
2. **Cloud Storage:** `gs://runflow` (staging/production)

All runtimes must have read/write access to both storage locations to support flexible deployment and testing scenarios.

## Storage Locations

### Local Storage
- **Host Path:** `/Users/jthompson/Documents/runflow`
- **Container Path:** `/runflow` (mounted via docker-compose.yml)
- **Purpose:** Local development, testing, and backup storage
- **Access:** Direct filesystem I/O

### Cloud Storage (GCS)
- **Bucket:** `gs://runflow`
- **Purpose:** Production storage, staging validation, cross-environment sharing
- **Access:** Google Cloud Storage API via `google-cloud-storage` Python client

## Runtime Environments

### 1. Local Docker (Development)

**Configuration:**
- Uses `docker-compose.yml` for container orchestration
- Environment variables loaded from `dev.env`
- Volume mount: `/Users/jthompson/Documents/runflow:/runflow`
- Service account key mounted: `./keys/gcs-sa.json:/tmp/keys/gcs-sa.json:ro`

**Storage Access Modes:**
- **Local-only mode** (default): `GCS_UPLOAD=false` in dev.env
  - Writes to `/runflow` only
  - GCS credentials not required
- **GCS-enabled mode**: `GCS_UPLOAD=true` in dev.env
  - Can read/write both local and GCS
  - Requires service account credentials

**Authentication:**
- GCS access via service account key file
- Environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json`

### 2. Staging Cloud Run

**Configuration:**
- Deployed to Cloud Run service: `run-density-staging`
- Region: `us-central1`
- Environment variables set via Cloud Run configuration

**Storage Access:**
- **Local storage:** Not available (Cloud Run is stateless)
- **GCS storage:** Full read/write access via service account
- Service account: `github-deployer@run-density.iam.gserviceaccount.com` or equivalent
- IAM roles: Storage Admin, Storage Object Viewer

**Authentication:**
- Uses Cloud Run's default service account
- No explicit credentials file required (Application Default Credentials)

### 3. Production Cloud Run

**Configuration:**
- Deployed to Cloud Run service: `run-density`
- Region: `us-central1`
- Last deployed: 2025-11-03 by `github-deployer@run-density.iam.gserviceaccount.com`

**Storage Access:**
- **Local storage:** Not available (Cloud Run is stateless)
- **GCS storage:** Full read/write access via service account
- Same service account and IAM configuration as staging

**Authentication:**
- Uses Cloud Run's default service account
- Application Default Credentials (ADC)

## Dependencies

### Python Packages
From `requirements.txt`:
```python
google-cloud-storage>=2.10.0
google-auth>=2.23.0
```

### Docker Configuration

**docker-compose.yml** (local development):
```yaml
volumes:
  # Mount local runflow directory for Run ID storage
  - /Users/jthompson/Documents/runflow:/runflow
  # Mount service account keys directory
  - ./keys:/tmp/keys:ro

env_file:
  - dev.env

environment:
  - PORT=8080
  - PYTHONPATH=/app
  - MPLBACKEND=Agg
```

**dev.env** (local development):
```bash
# Local-only mode (default)
GCS_UPLOAD=false

# GCS-enabled mode (testing)
GCS_UPLOAD=true
GOOGLE_CLOUD_PROJECT=run-density
GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

### Service Account

**Name:** `run-density-signer@run-density.iam.gserviceaccount.com`  
**IAM Roles:**
- Storage Admin
- Storage Object Viewer

**Key File:**
- Location: `./keys/gcs-sa.json` (gitignored)
- Container mount: `/tmp/keys/gcs-sa.json` (read-only)

## Authentication Flow

### Local Docker
1. Container starts with `dev.env` loaded
2. If `GCS_UPLOAD=true`:
   - Reads `GOOGLE_APPLICATION_CREDENTIALS` environment variable
   - Loads service account key from `/tmp/keys/gcs-sa.json`
   - Initializes `google.cloud.storage.Client` with explicit credentials
3. If `GCS_UPLOAD=false`:
   - Uses local storage only
   - GCS client not initialized

### Cloud Run (Staging/Production)
1. Container starts with Cloud Run managed environment
2. Uses Application Default Credentials (ADC)
3. Authenticates as service account attached to Cloud Run service
4. No explicit credential file required

## Access Verification

### Test Script
Location: `scripts/test_storage_access.py`

**Purpose:** Verify read/write access to both storage locations

**Usage:**
```bash
# From within container
python3 /app/scripts/test_storage_access.py
```

**Tests Performed:**
1. **Local Storage:**
   - Directory exists check
   - Directory readable (list contents)
   - File write operation
   - File read operation
   - File delete operation

2. **GCS Storage:**
   - Credentials validation
   - GCS client initialization
   - Bucket exists check
   - Bucket readable (list objects)
   - Object write operation
   - Object read operation
   - Object delete operation

**Expected Results:**
- Local storage: ✅ PASSED (all environments with volume mount)
- GCS storage: ✅ PASSED (when credentials configured)
- GCS storage: ⚠️ SKIPPED (local-only mode, expected behavior)

### Manual Verification

**Local Storage (host):**
```bash
# Write test
echo "test" > /Users/jthompson/Documents/runflow/test.txt
rm /Users/jthompson/Documents/runflow/test.txt

# List contents
ls -la /Users/jthompson/Documents/runflow/
```

**Local Storage (container):**
```bash
# From container
touch /runflow/test.txt
rm /runflow/test.txt
ls -la /runflow/
```

**GCS Storage:**
```bash
# List bucket
gsutil ls gs://runflow/

# Write test
echo "test" | gsutil cp - gs://runflow/test.txt
gsutil rm gs://runflow/test.txt
```

## Security Considerations

### Credentials Management
- Service account keys are gitignored (`keys/*.json`)
- Keys mounted read-only in containers (`:ro` flag)
- Cloud Run uses managed service accounts (no key files)

### Access Control
- GCS bucket uses IAM for access control
- Service account has minimal required permissions
- Local storage isolated per developer workstation

### Environment Separation
- Development: Local-only by default (no production data access)
- Staging: Full GCS access for validation
- Production: Full GCS access, no local storage

## Troubleshooting

### Issue: Container cannot access local storage
**Symptoms:** `/runflow` directory not found or permission denied  
**Resolution:**
1. Check docker-compose.yml has correct volume mount
2. Verify host path exists: `/Users/jthompson/Documents/runflow`
3. Check Docker Desktop > Settings > Resources > File Sharing includes parent directory

### Issue: GCS access fails with authentication error
**Symptoms:** "No credentials found" or "Permission denied"  
**Resolution:**
1. Verify `GCS_UPLOAD=true` in dev.env
2. Check service account key exists: `./keys/gcs-sa.json`
3. Verify `GOOGLE_APPLICATION_CREDENTIALS` points to correct path
4. Restart container to pick up environment changes: `docker-compose restart`

### Issue: Environment variables not loaded in container
**Symptoms:** `env | grep GCS` shows empty or incorrect values  
**Resolution:**
1. Check `env_file: - dev.env` in docker-compose.yml
2. Verify no conflicting environment overrides in docker-compose.yml
3. Restart container: `docker-compose down && docker-compose up -d`

## References

- Issue #451: Infrastructure & Environment Readiness
- Issue #447: E2E Test Refactor (environment detection)
- Issue #444: Run ID Implementation (original requirement)
- Google Cloud Storage Python Client: https://cloud.google.com/python/docs/reference/storage/latest

