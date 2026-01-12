# Run Density

[![Code Quality](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml)

## Overview
This service models runner density on shared course segments using a density engine and temporal flow analysis.  
It provides comprehensive reporting capabilities with both Markdown and CSV outputs, and is containerized for local development.

**v2.0.0 Features:**
- **Multi-day support**: Analyze Saturday and Sunday events independently or together
- **Day-scoped outputs**: All artifacts organized by `run_id/{day}/` (reports, bins, UI artifacts)
- **Dynamic event configuration**: Events defined in API payload, not hardcoded
- **Day selector UI**: Global day selector across all pages (Dashboard, Segments, Density, Flow, Locations, Reports)
- **E2E test suite**: Comprehensive regression testing with golden file comparisons

**Current Version: v2.0.6** - Data directory parameter, directory reorganization, baseline utility, performance optimization, and config integrity

## Key Features
- **Density Analysis**: Spatial concentration analysis with areal and crowd density calculations
- **Temporal Flow Analysis**: Convergence and overtaking analysis between different race events
- **Heatmap Visualizations**: Interactive PNG heatmaps for race segments
- **Comprehensive Reporting**: Auto-generated Markdown and CSV reports with detailed analytics
- **RESTful API**: Full FastAPI integration with configurable parameters
- **CLI Tools**: Command-line scripts for report generation and analysis
- **Web UI**: Interactive dashboard with segment details, heatmaps, and operational intelligence

## Quick Start (Local Development)

### Docker Development (Local-Only)

**Issue #466:** Simplified to 3 core commands for local-only Docker development.

Start the development container:
```bash
make dev
```

The container runs on `http://localhost:8080` with hot-reload enabled.

Run end-to-end tests:
```bash
# v1 E2E tests (legacy)
make e2e-local

# v2 E2E tests (recommended)
make e2e-v2
```

**v2 E2E Testing:**
- Base URL configurable via `BASE_URL` env var or `--base-url` pytest option
- Default: `http://localhost:8080`
- Tests three scenarios: Saturday-only, Sunday-only, Mixed-day
- Golden file regression testing with normalization for Markdown, CSV, JSON, GeoJSON, and Parquet
- Day isolation validation to ensure no cross-day contamination

Run smoke tests:
```bash
make test
```

Stop the container:
```bash
make stop
```

**📖 Full Documentation:** See [`docs/README.md`](docs/README.md) for complete documentation index.

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
- **Local Storage**: Heatmaps stored in `runflow/<uuid>/ui/heatmaps/`
- **Interactive Segments**: Click on segments to view detailed heatmap visualizations
- **Auto-Captions**: Text summaries for each heatmap generated automatically
- **UUID-Based Runs**: Each analysis run has a unique ID for tracking

### Access the Web UI
- **Local (Docker)**: http://localhost:8080/dashboard

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

## Makefile Commands

### Core Commands
- `make dev` – start Docker container on `http://localhost:8080` with hot-reload
- `make e2e` – run sat+sun E2E in a single run_id (fast sat/sun sanity)
- `make e2e-full` – run full v2 E2E suite (all scenarios, ~30 min)
- `make e2e-sat` – run Saturday-only E2E (~2 min)
- `make e2e-sun` – run Sunday-only E2E (~2 min)
- `make validate-output` – validate latest run outputs
- `make validate-all` – validate outputs for all runs in index.json
- `make prune-runs KEEP=n` – prune old run_ids, keeping last n
- `make stop` – stop and remove Docker container
- `make build` – build Docker image (no start)

### Legacy Aliases (Backward Compatibility)
- `make dev-docker` – alias for `make dev`
- `make e2e-local-docker` – alias for `make e2e-local`
- `make smoke-docker` – alias for `make test`
- `make stop-docker` – alias for `make stop`
- `make build-docker` – alias for `make build`  

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
make dev

# Run E2E tests
make e2e-local

# Run smoke tests
make test
```

### Test Coverage
- **E2E Tests**: Full workflow validation with `e2e.py`
- **Smoke Tests**: Health checks and API endpoint validation
- **Output Validation**: Automated integrity checks (Issue #467)
- **Code Quality**: Automated linting and formatting checks

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Testing requirements
- Branch naming and commit conventions
- Pull request process

**Quick Start for Contributors:**
```bash
git clone https://github.com/thomjeff/run-density.git
cd run-density
make dev           # Start container
make test          # Run smoke tests
make e2e-local     # Run E2E tests
make validate-output  # Validate output integrity
```

---

## License
MIT
