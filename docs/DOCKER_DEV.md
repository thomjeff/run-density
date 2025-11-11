# Docker Development Guide

**Version:** 3.0  
**Last Updated:** 2025-11-11  
**Issues:** #466 (Phase 2 Architecture Refinement), #464 (Phase 1 Declouding)

This guide covers local-only development using Docker containers for the run-density application.

---

## Quick Start

### 1. Start Development Container

```bash
make dev
```

This will:
- Build the Docker image (if not already built)
- Start the container on `http://localhost:8080`
- Enable hot-reload for code changes
- Mount all necessary directories

### 2. Verify Container is Running

```bash
make test
```

This runs smoke tests to verify:
- Health endpoint responding (`/health`)
- Ready endpoint showing loaded data (`/ready`)
- Core API endpoints functional (Dashboard, Density, Reports)
- All checks pass in under 5 seconds

### 3. Run E2E Tests

```bash
make e2e-local
```

This restarts the container and runs the complete E2E test suite with local filesystem storage.

### 4. Stop Container

```bash
make stop
```

---

## Available Make Targets

### Core Commands (Issue #466)

| Command | Description |
|---------|-------------|
| `make dev` | Start development container with hot-reload |
| `make e2e-local` | Run end-to-end tests (restarts container automatically) |
| `make test` | Run smoke tests (health checks + API validation) |
| `make validate-output` | Validate output integrity for latest run (Issue #467) |
| `make validate-all` | Validate all runs in index.json (Issue #467) |
| `make stop` | Stop and remove the container |
| `make build` | Build the Docker image (no start) |

### Legacy Aliases (Backward Compatibility)

| Command | Alias For | Status |
|---------|-----------|---------|
| `make dev-docker` | `make dev` | ✅ Supported |
| `make e2e-local-docker` | `make e2e-local` | ✅ Supported |
| `make smoke-docker` | `make test` | ✅ Supported |
| `make e2e-docker` | `make e2e-local` | ✅ Supported |
| `make stop-docker` | `make stop` | ✅ Supported |
| `make build-docker` | `make build` | ✅ Supported |

---

## E2E Testing

### `e2e-local` - Full E2E Testing (Recommended)

**Purpose:** Comprehensive local testing with clean container restart

**Behavior:**
- Restarts container with `GCS_UPLOAD=false`
- Saves all files to local filesystem (`./runflow/<uuid>/`)
- Runs complete E2E test suite
- Uses `e2e.py --local` flag
- Generates unique run ID for each test

**When to Use:**
- ✅ Before committing code changes
- ✅ Testing report generation logic
- ✅ Validating API endpoints
- ✅ Pre-merge verification

**Example:**
```bash
make e2e-local
# Check results in ./runflow/<uuid>/
```

**Expected Output:**
```
✅ Health: OK
✅ Ready: OK
✅ Density Report: OK (run_id: abc123...)
✅ Temporal Flow Report: OK
✅ UI Artifacts: 7 files exported
✅ Heatmaps: 17 PNG files + 17 captions
✅ All tests passed!
```

---

### `test` - Smoke Tests

**Purpose:** Quick validation that all core APIs are responding

**Behavior:**
- Runs health checks
- Validates API endpoints
- Checks data integrity
- Completes in under 5 seconds

**When to Use:**
- ✅ Quick validation during development
- ✅ After small code changes
- ✅ Verifying container is healthy

**Example:**
```bash
make dev    # Start container first
make test   # Run smoke tests
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
| `./runflow` | `/app/runflow` | All run outputs (reports, bins, UI artifacts) |
| `./e2e.py` | `/app/e2e.py` | E2E test script |

### Hot Reload Behavior

Changes to Python files in mounted directories trigger automatic reload:
- Edit `app/main.py` → server restarts automatically
- Edit `app/density_report.py` → changes apply on next request
- Edit `data/runners.csv` → available immediately (no restart needed)

**Note:** Configuration changes in `dev.env` or `docker-compose.yml` require container restart.

---

## File Structure

### Runflow Output Structure (Issue #466)

After running E2E tests, all outputs are organized under `runflow/<uuid>/`:

```
run-density/
└── runflow/
    ├── latest.json              # Pointer to latest run_id
    ├── index.json               # Run history (all runs)
    └── {run_id}/                # UUID-based run directory
        ├── metadata.json        # Run metadata
        ├── reports/             # Markdown + CSV reports
        │   ├── Density.md
        │   ├── Flow.md
        │   └── Flow.csv
        ├── bins/                # Bin-level analysis data
        │   ├── bins.parquet     # Binary dataset
        │   ├── bins.geojson.gz  # Compressed geospatial
        │   └── bin_summary.json # Summary stats
        ├── maps/                # Map data (if enabled)
        │   └── map_data.json
        └── ui/                  # Frontend artifacts
            ├── meta.json
            ├── segment_metrics.json
            ├── flags.json
            ├── flow.json
            ├── segments.geojson
            ├── schema_density.json
            ├── health.json
            ├── captions.json
            └── heatmaps/
                └── *.png (17 files)
```

**Key Concepts:**
- **Single Source of Truth:** All outputs under `runflow/<uuid>/`
- **UUID-based:** Each run has a unique short ID (e.g., `kPJMRTxUE3rHPPcTbvWBYV`)
- **Pointer Files:** `latest.json` points to most recent run
- **Index File:** `index.json` contains history of all runs

**📖 Full Documentation:** See [`docs/architecture/output.md`](../architecture/output.md) for complete output structure details.

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
make dev

# 2. Edit code (auto-reloads)
# Open app/main.py in your editor and make changes

# 3. Test changes quickly
make test

# 4. Run full E2E tests
make e2e-local     # Restarts container, runs complete test suite

# 5. Stop container when done
make stop
```

### Pre-Commit Workflow

```bash
# 1. Test locally with full E2E
make e2e-local

# 2. Validate output integrity (Issue #467)
make validate-output

# 3. Verify all artifacts generated
ls -la runflow/

# 4. Check latest run outputs
cat runflow/latest.json
ls -la runflow/$(cat runflow/latest.json | jq -r '.run_id')/

# 5. Check for any errors in logs
docker logs run-density-dev | grep -i "error\|failed"

# 6. Commit changes
git add .
git commit -m "your commit message"

# 7. Stop container
make stop
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

### Phase 2 Architecture Refinement (Issue #466) - 2025-11-11
- ✅ Simplified Makefile to 3 core commands (`dev`, `e2e-local`, `test`)
- ✅ Consolidated all outputs to `runflow/<uuid>/` structure
- ✅ Removed all lingering GCS/cloud references
- ✅ Streamlined storage abstraction (single unified layer)
- ✅ Centralized run ID logic in `app.utils.run_id`

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

1. **Understand output structure** → See `docs/architecture/output.md`
2. **Review architecture** → See `docs/architecture/env-detection.md`
3. **Understand testing** → See `docs/ui-testing-checklist.md`
4. **Read guardrails** → See `docs/GUARDRAILS.md`

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

**Last Updated:** 2025-11-11  
**Updated By:** AI Assistant (Issue #466 - Phase 2 Architecture Refinement)  
**Architecture:** Local-only, UUID-based runflow structure
