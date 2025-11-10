# Run Density

[![Code Quality](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml)

## Overview
This service models runner density on shared course segments using a density engine and temporal flow analysis.  
It provides comprehensive reporting capabilities with both Markdown and CSV outputs, and is containerized for local development.

**Current Version: v1.8.0** - Epic #444: UUID-Based Run ID System - Complete implementation with 5 phases, replacing date-based folders with UUID-based runflow structure

## Key Features
- **Density Analysis**: Spatial concentration analysis with areal and crowd density calculations
- **Temporal Flow Analysis**: Convergence and overtaking analysis between different race events
- **Heatmap Visualizations**: Interactive PNG heatmaps for race segments
- **Comprehensive Reporting**: Auto-generated Markdown and CSV reports with detailed analytics
- **RESTful API**: Full FastAPI integration with configurable parameters
- **CLI Tools**: Command-line scripts for report generation and analysis
- **Web UI**: Interactive dashboard with segment details, heatmaps, and operational intelligence

## Quick Start (Local Development)

### Docker Development (Recommended)

**New in v1.6.50:** Docker-first development workflow.

Start the development container:
```bash
make dev-docker
```

The container runs on `http://localhost:8080` with hot-reload enabled.

Run smoke tests:
```bash
make smoke-docker
```

Run full E2E tests:
```bash
make e2e-docker
```

Stop the container:
```bash
make stop-docker
```

**📖 Full Documentation:** See [`docs/DOCKER_DEV.md`](docs/DOCKER_DEV.md) for complete Docker development guide.

### Legacy venv Development (Deprecated)

> **⚠️ Deprecated:** This workflow will be removed in a future version. Use Docker development instead.

<details>
<summary>Click to expand legacy venv instructions</summary>

Create and activate a Python virtual environment:
```bash
python3 -m venv test_env
source test_env/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Run locally:
```bash
make run-local
```

Health checks:
```bash
curl -fsS http://localhost:8081/health | jq .
curl -fsS http://localhost:8081/ready | jq .
```

Smoke test locally:
```bash
make smoke-local
```

</details>

## Web UI Features

### Interactive Dashboard
- **Segment Overview**: All 22 race segments with density metrics and LOS ratings
- **Heatmap Visualizations**: PNG heatmaps for each segment showing density patterns
- **Operational Intelligence**: Bin-level details with filtering and sorting capabilities
- **Real-time Monitoring**: Health checks and API status monitoring

### Heatmap Display
- **Local Storage**: Heatmaps stored in local filesystem
- **Interactive Segments**: Click on segments to view detailed heatmap visualizations
- **Auto-Captions**: Text summaries for each heatmap generated automatically

### Access the Web UI
- **Local (Docker)**: http://localhost:8080/dashboard
- **Local (Legacy)**: http://localhost:8081/frontend/

## Report Generation

### CLI Tools
Generate comprehensive reports using command-line tools:

> **Note**: Legacy CLI scripts have been moved to `archive/` directory. The examples below use the modern module-based approach.

**Temporal Flow Report** (Markdown + CSV):
```bash
python3 -c "
from app.temporal_flow_report import generate_temporal_flow_report
result = generate_temporal_flow_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

**Density Report** (Markdown):
```bash
python3 -c "
from app.density_report import generate_density_report
result = generate_density_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

### API Endpoints
Generate reports via REST API:

**Temporal Flow Report**:
```bash
curl -X POST "http://localhost:8080/api/temporal-flow-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

**Density Report**:
```bash
curl -X POST "http://localhost:8080/api/density-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "densityCsv": "data/density.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

---

## Makefile Shortcuts

### Docker Commands (Recommended)
- `make dev-docker` – start Docker container on `http://localhost:8080` with hot-reload
- `make smoke-docker` – run smoke tests against Docker container
- `make e2e-docker` – run full E2E tests inside Docker container
- `make stop-docker` – stop and remove Docker container
- `make build-docker` – build Docker image (no start)

### Legacy Commands (Deprecated)
- `make bootstrap` – install runtime dependencies  
- `make run-local` – start service via venv on `http://localhost:8081`
- `make smoke-local` – hit `/health`, `/ready`, and test endpoints  

---

## Code Quality

Code quality is enforced with **GitHub Actions** (`.github/workflows/code-quality.yaml`).

### Quality Checks (On Pull Requests)
The CI pipeline runs automated checks on all Python code changes:

1. **flake8** - Complexity and lint checks
   - Max complexity: 15
   - Checks: B001 (bare exceptions), C901 (complexity), E/F/W (style)

2. **black** - Code formatting
   - Ensures consistent code style

3. **isort** - Import sorting
   - Maintains organized imports with black profile

All checks must pass before code can be merged to main.

---

## Testing

### Local Testing
Run end-to-end tests locally using Docker:

```bash
# Start container
make dev-docker

# Run E2E tests
make e2e-local-docker

# Run smoke tests
make smoke-docker
```

### Test Coverage
- **E2E Tests**: Full workflow validation with `e2e.py`
- **Smoke Tests**: Health checks and API endpoint validation
- **Code Quality**: Automated linting and formatting checks

---

## License
MIT
