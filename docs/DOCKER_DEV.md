# Docker Development Guide

**Version:** 2.0  
**Last Updated:** 2025-11-10  
**Issues:** #464 (Phase 1 Declouding), #465 (Phase 0 - Disable Cloud CI)

This guide covers local development using Docker containers for the run-density application.

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

### 3. Run E2E Tests

```bash
make e2e-local-docker
```

This restarts the container and runs the complete E2E test suite with local filesystem storage.

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
| `make e2e-local-docker` | Run full E2E tests (restarts container automatically) |
| `make e2e-docker` | Run E2E tests in running container |

---

## E2E Testing

### `e2e-local-docker` - Full E2E Testing (Recommended)

**Purpose:** Comprehensive local testing with clean container restart

**Behavior:**
- Restarts container with `GCS_UPLOAD=false`
- Saves all files to local filesystem (`./reports/`, `./artifacts/`)
- Runs complete E2E test suite
- Uses `e2e.py --local` flag

**When to Use:**
- ✅ Before committing code changes
- ✅ Testing report generation logic
- ✅ Validating API endpoints
- ✅ Pre-merge verification

**Example:**
```bash
make e2e-local-docker
# Check results in ./reports/ and ./artifacts/
```

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

### `e2e-docker` - Quick E2E Testing

**Purpose:** Run E2E tests without container restart

**Behavior:**
- Uses already running container
- Faster than `e2e-local-docker` (no restart)
- Good for rapid iteration

**When to Use:**
- ✅ Quick validation during development
- ✅ After small code changes
- ✅ When container is already configured correctly

**Example:**
```bash
make dev-docker    # Start container first
make e2e-docker    # Run tests in existing container
```

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

# GCS Upload (disabled for local-only mode)
GCS_UPLOAD=false
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
docker-compose run --rm -e ENABLE_BIN_DATASET=false app python /app/e2e.py --local
```

---

## Volume Mounts

The container automatically mounts these directories:

| Local Path | Container Path | Purpose |
|------------|---------------|---------|
| `./app` | `/app/app` | Application code (hot-reload) |
| `./data` | `/app/data` | Input CSV and GPX files |
| `./config` | `/app/config` | YAML configuration files |
| `./reports` | `/app/reports` | Generated reports |
| `./artifacts` | `/app/artifacts` | UI artifacts (JSON, GeoJSON, heatmaps) |
| `./e2e.py` | `/app/e2e.py` | E2E test script |
| `/Users/jthompson/Documents/runflow` | `/app/runflow` | Run ID storage (Issue #455) |

### Hot Reload Behavior

Changes to Python files in mounted directories trigger automatic reload:
- Edit `app/main.py` → server restarts automatically
- Edit `app/density_report.py` → changes apply on next request
- Edit `data/runners.csv` → available immediately (no restart needed)

**Note:** Configuration changes in `dev.env` or `docker-compose.yml` require container restart.

---

## File Structure

### Local Filesystem Organization

After running E2E tests, the following structure is created:

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
        │   ├── Density.md
        │   ├── Flow.md
        │   └── Flow.csv
        ├── bins/
        │   ├── bins.parquet
        │   ├── bins.geojson.gz
        │   └── bin_summary.json
        ├── maps/
        │   └── map_data.json
        ├── heatmaps/
        │   └── *.png (17 files)
        └── ui/
            └── (7 JSON files)
```

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

**Verify Docker Compose configuration:**
```bash
docker-compose config
```

---

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

**Force container rebuild:**
```bash
make stop-docker
make build-docker
make dev-docker
```

---

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

**Check for missing dependencies:**
```bash
docker exec run-density-dev pip list | grep -E "pandas|numpy|fastapi"
```

---

### Reports Not Generating

**Verify input files exist:**
```bash
docker exec run-density-dev ls -la /app/data/
# Should show: runners.csv, segments.csv, *.gpx files
```

**Check output directory permissions:**
```bash
docker exec run-density-dev ls -ld /app/reports /app/artifacts
```

**Run report generation manually:**
```bash
docker exec run-density-dev python -c "
from app.density_report import generate_density_report
generate_density_report('data/runners.csv', 'data/segments.csv', {'Full': 420, '10K': 440, 'Half': 460})
"
```

---

## Development Workflow

### Typical Development Session

```bash
# 1. Start container
make dev-docker

# 2. Edit code (auto-reloads)
# Open app/main.py in your editor and make changes

# 3. Test changes quickly
make smoke-docker

# 4. Run full E2E tests
make e2e-local-docker     # Restarts container, runs complete test suite

# 5. Stop container when done
make stop-docker
```

### Pre-Commit Workflow

```bash
# 1. Test locally with full E2E
make e2e-local-docker

# 2. Verify all artifacts generated
ls -la artifacts/
ls -la reports/
ls -la runflow/

# 3. Check for any errors in logs
docker logs run-density-dev | grep -i "error\|failed"

# 4. Commit changes
git add .
git commit -m "your commit message"

# 5. Stop container
make stop-docker
```

---

## Docker Workflow Benefits

**Advantages over legacy venv:**
- ✅ No Python version conflicts
- ✅ Consistent environment across developers
- ✅ No venv activation needed
- ✅ Hot-reload included
- ✅ Isolated dependencies
- ✅ Reproducible builds
- ✅ Simple cleanup (`make stop-docker` removes everything)

---

## Port Reference

| Environment | Port | URL |
|------------|------|-----|
| Docker Local | 8080 | `http://localhost:8080` |
| Legacy Local | 8081 | `http://localhost:8081` (deprecated) |

**Note:** Docker uses port 8080 as the standard development port.

---

## Advanced Usage

### Running Python Commands in Container

```bash
# Execute Python code
docker exec run-density-dev python -c "print('Hello from container')"

# Run specific module
docker exec run-density-dev python -m app.version current

# Interactive Python shell
docker exec -it run-density-dev python
```

### Accessing Container Shell

```bash
# Get a bash shell in the container
docker exec -it run-density-dev bash

# Inside container you can:
cd /app
ls -la
cat dev.env
python -c "import app; print(app.__file__)"
```

### Rebuilding After Dependency Changes

```bash
# If requirements.txt changed, rebuild image
make stop-docker
make build-docker
make dev-docker
```

---

## Implementation History

### Phase 1 Declouding (Issue #464) - 2025-11-10
- ✅ Removed all GCS upload configurations
- ✅ Simplified to local-only Docker development
- ✅ Archived cloud testing modes and documentation
- ✅ Updated guide for filesystem-only operation

### Phase 0 (Issue #465) - 2025-11-10
- ✅ Disabled Cloud CI/CD pipeline
- ✅ Commented out cloud Makefile targets
- ✅ Simplified `dev.env` and `docker-compose.yml`

### Previous Versions (Archived)
- **Issue #447:** E2E Test Modes (local, staging, production)
- **Issue #415:** Docker-first development workflow

**Note:** Previous multi-environment architecture is documented in archived version at `archive/declouding-2025/docs/DOCKER_DEV.md` (if needed).

---

## Next Steps

After mastering Docker development:

1. **Review architecture** → See `docs/architecture/env-detection.md`
2. **Understand testing** → See `docs/ui-testing-checklist.md`
3. **Read guardrails** → See `docs/GUARDRAILS.md`
4. **Learn about operations** → See `docs/dev-guides/OPERATIONS.md`

---

## Support

**Issues with Docker workflow?**
- Check `docker logs run-density-dev` for errors
- Review this guide's Troubleshooting section
- Verify Docker Desktop is running
- Ensure port 8080 is available

**Questions about configuration?**
- See `dev.env` comments for environment variable details
- See `docker-compose.yml` for volume mount configuration
- See `Makefile` for available commands

---

**Last Updated:** 2025-11-10  
**Updated By:** AI Assistant (Issue #464 - Phase 1 Declouding)  
**Architecture:** Local-only, filesystem-based development
