# Docker Development Guide

**Version:** 1.0  
**Last Updated:** 2025-11-01  
**Issue:** #415 (Docker-first, GCS-always architecture)

This guide covers local development using Docker containers, replacing the legacy `.venv` workflow.

---

## Quick Start

### 1. Start Development Container

```bash
make dev-docker
```

This will:
- Build the Docker image (if not already built)
- Start the container on `http://localhost:8080`
- Enable hot-reload for code changes
- Mount all necessary directories

### 2. Verify Container is Running

```bash
make smoke-docker
```

This runs quick smoke tests to verify:
- Health endpoint responding
- Ready endpoint showing loaded data
- Core API endpoints functional

### 3. Run Full E2E Tests

```bash
make e2e-docker
```

This executes the complete E2E test suite inside the container.

### 4. Stop Container

```bash
make stop-docker
```

---

## Available Make Targets

### Development Commands

| Command | Description |
|---------|-------------|
| `make dev-docker` | Start development container with hot-reload |
| `make stop-docker` | Stop and remove the container |
| `make build-docker` | Build the Docker image (no start) |
| `make smoke-docker` | Run smoke tests against running container |
| `make e2e-docker` | Run full E2E tests inside container |

### Legacy Commands (Deprecated)

These commands still work but are deprecated in favor of Docker workflow:

| Command | Docker Equivalent | Notes |
|---------|------------------|-------|
| `make run-local` | `make dev-docker` | Uses venv, will be removed in future |
| `make stop-local` | `make stop-docker` | Kills port 8081, not Docker-aware |

---

## Configuration

### Environment Variables

Configuration is managed via `dev.env` file in the project root.

**Core Variables:**

```bash
# Bin Dataset Generation
ENABLE_BIN_DATASET=true

# Output Directory
OUTPUT_DIR=reports

# GCS Upload (false for local-only, true for GCS testing)
GCS_UPLOAD=false

# Google Cloud Project (required for GCS uploads)
# GOOGLE_CLOUD_PROJECT=run-density

# Service Account Key Path (required for GCS uploads)
# GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

### Overriding Environment Variables

**Method 1: Edit dev.env (Recommended)**

```bash
# Edit dev.env
nano dev.env

# Restart container to apply changes
make stop-docker
make dev-docker
```

**Method 2: One-time Override via CLI**

```bash
# Override specific variables for single run
docker-compose run --rm -e GCS_UPLOAD=true app python /app/e2e.py --local
```

**Method 3: Temporary dev.env.local**

```bash
# Create local override file
cp dev.env dev.env.local
# Edit dev.env.local with your changes
# Update docker-compose.yml to use dev.env.local
```

---

## GCS Upload Configuration

To enable GCS uploads from local Docker container:

### 1. Obtain Service Account Key

```bash
# Using gcloud CLI (recommended)
gcloud iam service-accounts keys create keys/gcs-sa.json \
  --iam-account=run-density-signer@run-density.iam.gserviceaccount.com

# Verify key created
ls -lh keys/gcs-sa.json
```

See `keys/README.md` for detailed service account setup instructions.

### 2. Update dev.env

```bash
# Enable GCS uploads
GCS_UPLOAD=true

# Set project ID
GOOGLE_CLOUD_PROJECT=run-density

# Set service account key path
GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

### 3. Restart Container

```bash
make stop-docker
make dev-docker
```

### 4. Verify GCS Uploads

```bash
# Run E2E test
make e2e-docker

# Check container logs for GCS uploads
docker logs run-density-dev | grep -i "uploaded to GCS"

# Verify files in GCS
gsutil ls gs://run-density-reports/$(date +%Y-%m-%d)/
```

---

## Volume Mounts

The container automatically mounts these directories:

| Local Path | Container Path | Purpose |
|------------|---------------|---------|
| `./app` | `/app/app` | Application code (hot-reload) |
| `./api` | `/app/api` | API routes (hot-reload) |
| `./core` | `/app/core` | Core utilities (hot-reload) |
| `./analytics` | `/app/analytics` | Analytics modules (hot-reload) |
| `./data` | `/app/data` | Input CSV files |
| `./config` | `/app/config` | YAML configuration |
| `./reports` | `/app/reports` | Generated reports |
| `./artifacts` | `/app/artifacts` | UI artifacts |
| `./keys` | `/tmp/keys` | Service account keys (read-only) |
| `./e2e.py` | `/app/e2e.py` | E2E test script |

### Hot Reload Behavior

Changes to Python files in mounted directories trigger automatic reload:
- Edit `app/main.py` → server restarts automatically
- Edit `app/density_report.py` → changes apply on next request
- Edit `data/runners.csv` → available immediately (no restart needed)

---

## Troubleshooting

### Container Won't Start

**Check if port 8080 is in use:**
```bash
lsof -i :8080
# Kill process if needed
kill -9 <PID>
```

**Check Docker daemon:**
```bash
docker ps
# Restart Docker Desktop if needed
```

**View container logs:**
```bash
docker logs run-density-dev
```

### GCS Upload Failures

**Verify service account key exists:**
```bash
ls -lh keys/gcs-sa.json
```

**Check environment variables inside container:**
```bash
docker exec run-density-dev printenv | grep -E "GCS|GOOGLE"
```

**Verify key is mounted:**
```bash
docker exec run-density-dev ls -la /tmp/keys/gcs-sa.json
```

**Check container logs for GCS errors:**
```bash
docker logs run-density-dev | grep -i "gcs\|cloud storage"
```

### Hot Reload Not Working

**Ensure uvicorn --reload is enabled:**
```bash
docker exec run-density-dev ps aux | grep uvicorn
# Should show: uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**Check if volume is mounted correctly:**
```bash
docker exec run-density-dev ls -la /app/app/
```

### E2E Tests Failing

**Check container health:**
```bash
make smoke-docker
```

**View full logs:**
```bash
docker logs run-density-dev --tail 100
```

**Run E2E with verbose output:**
```bash
docker exec run-density-dev python /app/e2e.py --local
```

---

## Development Workflow

### Typical Development Session

```bash
# 1. Start container
make dev-docker

# 2. Edit code (auto-reloads)
# Open app/main.py in your editor and make changes

# 3. Test changes
make smoke-docker

# 4. Run full E2E
make e2e-docker

# 5. Stop container when done
make stop-docker
```

### Testing GCS Uploads

```bash
# 1. Configure GCS (one-time setup)
# - Place service account key in keys/gcs-sa.json
# - Edit dev.env to enable GCS_UPLOAD=true

# 2. Start container
make dev-docker

# 3. Run E2E (will upload to GCS)
make e2e-docker

# 4. Verify uploads
gsutil ls gs://run-density-reports/$(date +%Y-%m-%d)/

# 5. Disable GCS for normal dev
# - Edit dev.env, set GCS_UPLOAD=false
# - Restart: make stop-docker && make dev-docker
```

---

## CI/CD Integration

**Current Status (Phase 4):**
- CI still uses native venv workflow
- Docker workflow is local-only
- Future: CI will use Docker containers

**When CI moves to Docker (future):**
- `.github/workflows/` will use `docker-compose`
- Build image in CI
- Run tests in container
- Deploy from same image to Cloud Run

---

## Comparison: Legacy vs Docker Workflow

### Legacy Workflow (Deprecated)

```bash
# Create venv
make venv

# Activate venv
source test_env/bin/activate

# Start server
make run-local  # port 8081

# Run E2E
python e2e.py --local

# Deactivate
deactivate
```

### Docker Workflow (Current)

```bash
# Start container
make dev-docker  # port 8080

# Run E2E
make e2e-docker

# Stop container
make stop-docker
```

**Benefits of Docker:**
- ✅ No Python version conflicts
- ✅ Identical to Cloud Run environment
- ✅ No venv activation needed
- ✅ Consistent across developers
- ✅ Hot-reload included
- ✅ GCS testing capability

---

## Port Reference

| Environment | Port | URL |
|------------|------|-----|
| Docker Local | 8080 | `http://localhost:8080` |
| Legacy Local | 8081 | `http://localhost:8081` |
| Cloud Run | 443 | `https://run-density-ln4r3sfkha-uc.a.run.app` |

**Note:** Docker uses 8080 to match Cloud Run default, reducing config divergence.

---

## Security Notes

### Service Account Keys

⚠️ **NEVER commit service account keys to git**

- Keys are stored in `keys/` directory
- `keys/*.json` is git-ignored
- Keys are mounted read-only to container
- See `keys/README.md` for IAM role requirements

### Environment Variables

- Sensitive vars (project ID, credentials) are in `dev.env`
- `dev.env` can be committed (contains no secrets, only paths/flags)
- Actual service account key file is git-ignored

---

## Next Steps

After mastering Docker development:

1. **Learn about GCS uploads** → See `keys/README.md`
2. **Review architecture** → See `docs/dev-guides/ARCHITECTURE.md`
3. **Understand testing** → See `docs/ui-testing-checklist.md`
4. **Read guardrails** → See `docs/GUARDRAILS.md`

---

## Support

**Issues with Docker workflow?**
- Check `docker logs run-density-dev` for errors
- Review this guide's Troubleshooting section
- Verify Docker Desktop is running
- Ensure ports 8080 is available

**Questions about configuration?**
- See `dev.env` comments
- See `keys/README.md` for GCS setup
- See `docker-compose.yml` for volume mounts

---

**Last Updated:** 2025-11-01  
**Updated By:** AI Assistant (Issue #415 Phase 4)  
**Next Review:** When Docker workflow becomes primary development method

