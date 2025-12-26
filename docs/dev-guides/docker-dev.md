# Docker Development Guide

**Version:** 3.1  
**Last Updated:** 2025-12-26  
**Issues:** #466 (Phase 2 Architecture Refinement), #464 (Phase 1 Declouding), #553 (v2.0.2+ API-driven configuration)

This guide covers local-only development using Docker containers for the run-density application.

**Note:** This guide is focused on Docker workflow. For complete v2 architecture and development patterns, see `docs/dev-guides/developer-guide-v2.md`.

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
# Check health endpoint
curl http://localhost:8080/health

# Check ready endpoint
curl http://localhost:8080/ready
```

Or manually test the API:
```bash
# Test v2 analyze endpoint
curl -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

### 3. Run E2E Tests

```bash
make e2e          # Run sat+sun E2E test (single run_id with both days)
make e2e-full     # Run full E2E test suite (all scenarios)
make e2e-sat      # Run Saturday-only E2E test
make e2e-sun      # Run Sunday-only E2E test
```

These commands restart the container and run E2E tests with local filesystem storage.

### 4. Stop Container

```bash
make stop
```

---

## Available Make Targets

### Core Commands (v2.0.2+)

| Command | Description |
|---------|-------------|
| `make dev` | Start development container with hot-reload |
| `make e2e` | Run sat+sun E2E test (single run_id with both days) |
| `make e2e-full` | Run full E2E test suite (all scenarios) |
| `make e2e-sat` | Run Saturday-only E2E test (~2 min) |
| `make e2e-sun` | Run Sunday-only E2E test (~2 min) |
| `make e2e-coverage-lite` | Run E2E with coverage (DAY=sat\|sun\|both) |
| `make validate-output` | Validate output integrity for latest run (Issue #467) |
| `make validate-all` | Validate all runs in index.json (Issue #467) |
| `make stop` | Stop and remove the container |
| `make build` | Build the Docker image (no start) |


---

## E2E Testing

### `e2e` - Sat+Sun E2E Test (Recommended)

**Purpose:** Run sat+sun E2E test with single run_id containing both days

**Behavior:**
- Restarts container automatically
- Saves all files to local filesystem (`./runflow/<run_id>/`)
- Runs `test_sat_sun_scenario` from `tests/v2/e2e.py`
- Generates unique run ID for the test
- Results organized by day: `runflow/<run_id>/sat/` and `runflow/<run_id>/sun/`

**When to Use:**
- ✅ Before committing code changes
- ✅ Testing multi-day analysis
- ✅ Validating day-partitioned outputs
- ✅ Pre-merge verification

**Example:**
```bash
make e2e
# Check results in ./runflow/<run_id>/sat/ and ./runflow/<run_id>/sun/
```

**Expected Output:**
```
✅ E2E test completed
💡 Container still running. Use 'make stop' to stop it.
```

### `e2e-full` - Full E2E Test Suite

**Purpose:** Run all E2E test scenarios

**Behavior:**
- Restarts container automatically
- Runs all tests in `tests/v2/e2e.py`
- Includes: sat-only, sun-only, sat+sun, mixed-day scenarios

**When to Use:**
- ✅ Comprehensive testing before major changes
- ✅ Regression testing
- ✅ Validating all API scenarios

**Example:**
```bash
make e2e-full
```

### `e2e-sat` / `e2e-sun` - Day-Specific Tests

**Purpose:** Run E2E test for a specific day only

**Behavior:**
- Restarts container automatically
- Runs Saturday-only or Sunday-only test scenario
- Faster execution (~2 minutes vs ~4 minutes for full)

**When to Use:**
- ✅ Testing day-specific logic
- ✅ Quick validation during development
- ✅ Debugging day-partitioned outputs

**Example:**
```bash
make e2e-sat   # Saturday only
make e2e-sun   # Sunday only
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
docker-compose run --rm -e ENABLE_BIN_DATASET=false app python -m pytest tests/v2/e2e.py -v
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
| `./tests` | `/app/tests` | Test suite (including v2 E2E tests) |

### Hot Reload Behavior

Changes to Python files in mounted directories trigger automatic reload:
- Edit `app/main.py` → server restarts automatically
- Edit `app/density_report.py` → changes apply on next request
- Edit `data/runners.csv` → available immediately (no restart needed)

**Note:** Configuration changes in `dev.env` or `docker-compose.yml` require container restart.

---

## File Structure

### Runflow Output Structure (v2.0.2+)

After running E2E tests, all outputs are organized under `runflow/<run_id>/` with day-partitioned structure:

```
run-density/
└── runflow/
    ├── latest.json              # Pointer to latest run_id
    ├── index.json               # Run history (all runs)
    └── {run_id}/                # UUID-based run directory
        ├── analysis.json        # Configuration (single source of truth)
        ├── metadata.json        # Run-level metadata
        ├── sat/                  # Saturday results
        │   ├── metadata.json    # Saturday-specific metadata
        │   ├── reports/         # Markdown + CSV reports
        │   │   ├── Density.md
        │   │   ├── Flow.md
        │   │   ├── Flow.csv
        │   │   └── Locations.csv
        │   ├── bins/            # Bin-level analysis data
        │   │   ├── bins.parquet
        │   │   ├── bins.geojson.gz
        │   │   └── bin_summary.json
        │   └── ui/              # Frontend artifacts
        │       └── heatmaps/
        └── sun/                  # Sunday results
            ├── metadata.json
            ├── reports/
            ├── bins/
            └── ui/
```

**Key Concepts:**
- **Day-Partitioned:** Each day has its own directory (`sat/`, `sun/`)
- **Single Source of Truth:** `analysis.json` contains all configuration
- **UUID-based:** Each run has a unique short ID (e.g., `hCjWfQNKMePnRkrN4GX9Rj`)
- **Pointer Files:** `latest.json` points to most recent run
- **Index File:** `index.json` contains history of all runs

**📖 Full Documentation:** See [`docs/user-guide/api-user-guide.md`](../user-guide/api-user-guide.md) (Understanding Results section) for complete output structure details.

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
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

**View full logs:**
```bash
docker logs run-density-dev --tail 100
```

**Run E2E with verbose output:**
```bash
docker exec run-density-dev python -m pytest tests/v2/e2e.py -v --base-url http://localhost:8080
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

**Test v2 API endpoint:**
```bash
# Create test payload
cat > /tmp/test_payload.json << 'EOF'
{
  "description": "Test analysis",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {"name": "elite", "day": "sat", "start_time": 480, "event_duration_minutes": 45, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"}
  ]
}
EOF

# Test API
curl -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @/tmp/test_payload.json
```

---

## Development Workflow

### Typical Development Session

```bash
# 1. Start container
make dev

# 2. Edit code (auto-reloads)
# Open app/main.py in your editor and make changes

# 3. Test changes (manual API test or E2E)
curl http://localhost:8080/health
# OR run E2E test

# 4. Run E2E tests
make e2e          # Restarts container, runs sat+sun test
# OR
make e2e-full     # Restarts container, runs all test scenarios

# 5. Stop container when done
make stop
```

### Pre-Commit Workflow

```bash
# 1. Test locally with E2E
make e2e          # Run sat+sun test (recommended)
# OR
make e2e-full     # Run all test scenarios

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
- ✅ Simplified Makefile commands
- ✅ Consolidated all outputs to `runflow/<run_id>/` structure
- ✅ Removed all lingering GCS/cloud references
- ✅ Streamlined storage abstraction (single unified layer)
- ✅ Centralized run ID logic in `app.utils.run_id`

### v2.0.2+ Updates (Issue #553) - 2025-12-26
- ✅ Updated to day-partitioned output structure (`runflow/<run_id>/sat/`, `runflow/<run_id>/sun/`)
- ✅ Updated E2E commands: `make e2e`, `make e2e-full`, `make e2e-sat`, `make e2e-sun`
- ✅ Removed references to deprecated `make test` and `make e2e-local` commands
- ✅ Updated output structure documentation to reflect v2.0.2+ architecture

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

1. **Understand output structure** → See `docs/user-guide/api-user-guide.md` (Understanding Results section)
2. **Review development environment** → See `docs/dev-guides/developer-guide-v2.md` (Development Environment section)
3. **Understand testing** → See `docs/ui-testing-checklist.md`
4. **Read AI developer guide** → See `docs/dev-guides/ai-developer-guide.md`

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

**Last Updated:** 2025-12-26  
**Updated By:** AI Assistant (Issue #553 - v2.0.2+ documentation refresh)  
**Architecture:** Local-only, UUID-based runflow structure, day-partitioned outputs
